# apps/serializers.py
from datetime import timedelta
from urllib.parse import urlparse
import logging
import os

from django.db import models
from django.db.models import OneToOneField, CASCADE, ForeignKey
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.apps import apps as django_apps

import redis
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.fields import HiddenField, CurrentUserDefault, IntegerField
from rest_framework.serializers import ModelSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from root import settings
from apps.models import (
    User, Doctor, Patient, PatientResult, Service, TreatmentPayment,
    CashRegister, TurnNumber, Outcome, TreatmentRegistration, Appointment,
    Payment, TreatmentRoom, LabRegistration
)

logger = logging.getLogger(__name__)

# ---------- Redis: robust init + tolerate read-only replicas ----------
def _build_redis():
    """
    Prefer a writable REDIS_URL; fall back to CACHE_URL or CELERY_BROKER_URL.
    Use decode_responses so .get() returns str.
    """
    url = getattr(settings, 'REDIS_URL', None) \
          or getattr(settings, 'CACHE_URL', None) \
          or getattr(settings, 'CELERY_BROKER_URL', None)

    if not url:
        logger.warning("No REDIS_URL/CACHE_URL/CELERY_BROKER_URL found; Redis features disabled.")
        return None
    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        return client
    except Exception as e:
        logger.error("Failed to init Redis from URL %r: %s", url, e)
        return None

r = _build_redis()

# -------------------- Register / Login / Password --------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'date_of_birth', 'phone_number', 'email', 'password', 'confirm_password']

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data, is_doctor=False)
        Patient.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    verification_code = serializers.CharField(write_only=True)


class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, email):
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                raise ValidationError("This email is not active.")
        except User.DoesNotExist:
            raise ValidationError("This email does not exist.")
        return email


from django.contrib.auth.password_validation import validate_password
class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data


class UserInfoSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        return token


class LoginUserModelSerializer(serializers.Serializer):
    """
    Fixed: uses Redis safely and tolerates read-only replicas so login never 500s.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        redis_key = f'failed_attempts_{email}'
        attempts = None

        # Read attempts (safe even if r is None)
        try:
            if r is not None:
                attempts = r.get(redis_key)
        except Exception as e:
            logger.warning("Redis GET failed for %s: %s", redis_key, e)
            attempts = None

        # rate-limit gate (5 attempts)
        try:
            if attempts and int(attempts) >= 5:
                raise DRFValidationError("Too many failed login attempts. Try again after 5 minutes.")
        except Exception:
            # if attempts is malformed, ignore it
            pass

        user = authenticate(email=email, password=password)

        if user is None:
            current_attempts = 0
            try:
                current_attempts = int(attempts) if attempts is not None else 0
            except Exception:
                current_attempts = 0

            # Write back to Redis but tolerate read-only error
            try:
                if r is not None:
                    r.setex(redis_key, timedelta(minutes=5), current_attempts + 1)
            except redis.exceptions.ReadOnlyError:
                logger.warning("Redis is read-only; cannot setex %s", redis_key)
            except Exception as e:
                logger.error("Redis SETEX failed for %s: %s", redis_key, e)

            raise DRFValidationError("Invalid email or password")

        # Successful login → clear counter, but don't crash if read-only
        try:
            if r is not None:
                r.delete(redis_key)
        except redis.exceptions.ReadOnlyError:
            logger.warning("Redis is read-only; skipping delete for %s", redis_key)
        except Exception as e:
            logger.error("Redis DELETE failed for %s: %s", redis_key, e)

        attrs['user'] = user
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address.")
        return email

    def save(self):
        request = self.context.get('request')
        user = User.objects.get(email=self.validated_data['email'])
        token = PasswordResetTokenGenerator().make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"{request._current_scheme_host}/reset-password/{uid}/{token}/"
        user.email_user(
            subject="Password Reset Request",
            message=f"Click the link below to reset your password:\n{reset_link}",
            from_email=None
        )


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            uid = urlsafe_base64_decode(data['uid']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise DRFValidationError("Invalid UID or user does not exist.")

        if not PasswordResetTokenGenerator().check_token(user, data['token']):
            raise DRFValidationError("Invalid or expired token.")

        self.user = user
        return data

    def save(self):
        self.user.set_password(self.validated_data['new_password'])
        self.user.save()


# -------------------- Domain Serializers --------------------
class UserForDoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'date_of_birth', 'phone_number']


# apps/serializers.py
from rest_framework import serializers
from apps.models import User, Doctor

class DoctorCreateSerializer(serializers.ModelSerializer):
    # Auth/user fields (always required)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name  = serializers.CharField(write_only=True)

    # Role selector (controls which fields are required)
    role = serializers.ChoiceField(
        choices=[
            ('doctor', 'Shifokor'),
            ('cashier', 'Kassir'),
            ('accountant', 'Buxgalter'),
            ('registration', 'Registrator'),
            ('admin', 'Admin'),
        ],
        write_only=True
    )

    # Doctor-only fields (must be tolerant for non-doctor roles)
    consultation_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    name = serializers.CharField(required=False, allow_blank=True)
    specialty = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'specialty', 'consultation_price',
            'email', 'password', 'first_name', 'last_name', 'role'
        ]

    def validate(self, attrs):
        role = attrs.get("role")

        # normalize blanks -> None
        for k in ("name", "specialty"):
            if attrs.get(k) == "":
                attrs[k] = None

        if role == "doctor":
            # doctors must have a specialty; price defaults to 0 if missing
            if not attrs.get("specialty"):
                raise serializers.ValidationError({"specialty": ["This field is required for doctors."]})
            if attrs.get("consultation_price") is None:
                attrs["consultation_price"] = 0
        else:
            # non-doctor roles: strip doctor-only fields to avoid model validation
            attrs.pop("specialty", None)
            attrs.pop("consultation_price", None)
            attrs.pop("name", None)

        return attrs

    def create(self, validated_data):
        role = validated_data.pop("role")
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        first_name = validated_data.pop("first_name")
        last_name  = validated_data.pop("last_name")

        is_doctor      = (role == "doctor")
        is_cashier     = (role == "cashier")
        is_accountant  = (role == "accountant")
        is_registrator = (role == "registration")
        is_superuser   = (role == "admin")
        is_staff       = is_superuser or is_cashier or is_accountant or is_registrator

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_doctor=is_doctor,
            is_cashier=is_cashier,
            is_accountant=is_accountant,
            is_registrator=is_registrator,
            is_superuser=is_superuser,
            is_staff=is_staff,
        )

        if is_doctor:
            name = validated_data.get("name") or f"{first_name} {last_name}"
            specialty = validated_data.get("specialty")
            consultation_price = validated_data.get("consultation_price") or 0
            return Doctor.objects.create(
                user=user,
                name=name,
                specialty=specialty,
                consultation_price=consultation_price
            )

        # non-doctor roles: return just the user
        return user


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['id', 'name', 'specialty', 'consultation_price']


class ServiceSerializer(serializers.ModelSerializer):
    doctor = DoctorSerializer(read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all(), source='doctor', write_only=True)

    class Meta:
        model = Service
        fields = ['id', 'name', 'price', 'doctor', 'doctor_id']


class DoctorDetailSerializer(serializers.ModelSerializer):
    user = UserForDoctorSerializer()
    consultation_price = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Doctor
        fields = ['id', 'user', 'specialty', 'consultation_price']


class PatientSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    last_visit = serializers.DateTimeField(read_only=True)
    total_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    patients_doctor = DoctorDetailSerializer(read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'address', 'created_at',
            'patients_doctor', 'balance', 'last_visit', 'total_due', 'total_paid'
        ]


class AppointmentSerializer(serializers.ModelSerializer):
    patient = PatientSerializer(read_only=True)
    doctor = DoctorSerializer(read_only=True)
    referred_by = DoctorSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    appointment = AppointmentSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'


class TreatmentPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TreatmentPayment
        fields = "__all__"


class TreatmentRoomSerializer(serializers.ModelSerializer):
    patients = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentRoom
        fields = '__all__'

    def get_patients(self, obj):
        active_regs = obj.treatmentregistration_set.filter(discharged_at__isnull=True).select_related('patient')
        out = []
        for reg in active_regs:
            p = reg.patient
            if not p:
                continue
            first = (p.first_name or '').strip()
            last  = (p.last_name  or '').strip()
            full  = f"{first} {last}".strip() or "—"
            out.append({
                "id": p.id,
                "registration_id": reg.id,
                "first_name": first,
                "last_name": last,
                "full_name": full,   # existing
                # new common aliases that many UIs use:
                "name": full,
                "fullName": full,
                "patient_name": full,
            })
        return out


# ---------------- TreatmentRegistration ----------------
class TreatmentRegistrationSerializer(serializers.ModelSerializer):
    # 🔹 Return nested patient (JS calls nameOf(x.patient))
    patient = PatientSerializer(read_only=True)

    # 🔹 Provide a simple room name alias (JS looks for x.room.name OR x.room_name OR x.treatment_room)
    room_name = serializers.CharField(source='room.name', read_only=True)

    # (keep appointment if you need it elsewhere)
    appointment = AppointmentSerializer(read_only=True)

    class Meta:
        model = TreatmentRegistration
        fields = [
            'id', 'patient', 'room', 'room_name', 'appointment',
            'assigned_at', 'discharged_at', 'total_paid'
        ]


class AppointmentStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['status']


class PatientResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientResult
        fields = '__all__'


class DoctorUserCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    date_of_birth = serializers.DateField()
    phone_number = serializers.CharField()
    specialty = serializers.CharField()
    role = serializers.ChoiceField(
        choices=[
            ("doctor", "Doctor"),
            ("cashier", "Cashier"),
            ("accountant", "Accountant"),
            ("registration", "Registration"),
            ("admin", "Admin"),
        ]
    )

    def create(self, validated_data):
        role = validated_data.pop("role")

        is_doctor = role == "doctor"
        is_cashier = role == "cashier"
        is_accountant = role == "accountant"
        is_registrator = role == "registration"
        is_superuser = role == "admin"
        is_staff = is_superuser or is_cashier or is_accountant or is_registrator

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            date_of_birth=validated_data["date_of_birth"],
            phone_number=validated_data["phone_number"],
            is_active=True,
            is_doctor=is_doctor,
            is_cashier=is_cashier,
            is_accountant=is_accountant,
            is_registrator=is_registrator,
            is_superuser=is_superuser,
            is_staff=is_staff,
        )

        if is_doctor:
            return Doctor.objects.create(
                user=user,
                name=f"{user.first_name} {user.last_name}",
                specialty=validated_data["specialty"]
            )

        return user


class RoomStatusSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    room_name = serializers.CharField()
    capacity = serializers.IntegerField()
    patients = serializers.ListField(child=serializers.CharField())


class DoctorPaymentSerializer(serializers.ModelSerializer):
    patient_first_name = serializers.CharField(source='patient.first_name', read_only=True)
    patient_last_name = serializers.CharField(source='patient.last_name', read_only=True)
    doctor_first_name = serializers.CharField(source='patient.patients_doctor.user.first_name', read_only=True)
    doctor_last_name = serializers.CharField(source='patient.patients_doctor.user.last_name', read_only=True)
    amount_paid = serializers.DecimalField(source='amount', max_digits=10, decimal_places=2, read_only=True)
    created_at = serializers.DateTimeField(source='date', read_only=True)
    notes = serializers.CharField(required=False)

    class Meta:
        model = TreatmentPayment
        fields = [
            'id',
            'patient_first_name',
            'patient_last_name',
            'doctor_first_name',
            'doctor_last_name',
            'amount_paid',
            'status',
            'created_at',
            'notes',
        ]


class CashRegisterSerializer(serializers.ModelSerializer):
    service_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    services = serializers.SerializerMethodField(read_only=True)
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = CashRegister
        fields = [
            'id',
            'patient_name',
            'transaction_type',
            'payment_method',
            'amount',
            'created_at',
            'services',
            'service_ids',
            'patient'
        ]

    def get_patient_name(self, obj):
        if obj.patient:
            return f"{obj.patient.first_name} {obj.patient.last_name}"
        return "—"

    def create(self, validated_data):
        service_ids = validated_data.pop("service_ids", [])
        if validated_data.get('transaction_type') == 'service' and service_ids:
            services = list(Service.objects.filter(id__in=service_ids))
            if len(services) != len(service_ids):
                raise serializers.ValidationError({"service_ids": "One or more service IDs are invalid"})
            names = ", ".join(s.name for s in services)
            validated_data["notes"] = f"Service Payment: {names}"

        patient = validated_data.get('patient')
        if not patient:
            raise serializers.ValidationError({"patient": "This field is required."})

        return super().create(validated_data)

    def get_services(self, obj):
        if obj.transaction_type == 'service' and obj.notes and obj.notes.startswith("Service Payment:"):
            names = obj.notes.replace("Service Payment:", "").strip()
            return [name.strip() for name in names.split(",")]
        return []


class CallTurnSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()

    class Meta:
        model = TreatmentRegistration
        fields = "__all__"


class TreatmentRegistrationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TreatmentRegistration
        fields = ['room']


class TurnNumberSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)

    class Meta:
        model = TurnNumber
        fields = ['doctor', 'doctor_name', 'letter', 'last_number', 'last_reset']


class TreatmentRoomPaymentReceiptSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    processed_by = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    receipt_number = serializers.SerializerMethodField()
    transaction_type = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentPayment
        fields = [
            "id",
            "receipt_number",
            "date",
            "patient_name",
            "amount",
            "payment_method",
            "status",
            "notes",
            "processed_by",
            "transaction_type",
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_processed_by(self, obj):
        return obj.processed_by.username if obj.processed_by else "—"

    def get_date(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M")

    def get_receipt_number(self, obj):
        return f"TR{obj.id:04}"

    def get_transaction_type(self, obj):
        return "Davolash xonasi"


class OutcomeSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = Outcome
        fields = '__all__'


class UserProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email',
            'is_superuser', 'is_doctor', 'is_cashier',
            'is_accountant', 'is_registrator',
            'role', 'is_admin', 'full_name'
        ]

    def get_role(self, obj):
        if obj.is_superuser:
            return 'admin'
        elif obj.is_doctor:
            return 'doctor'
        elif obj.is_cashier:
            return 'cashier'
        elif obj.is_accountant:
            return 'accountant'
        elif obj.is_registrator:
            return 'registration'
        return 'unknown'

    def get_is_admin(self, obj):
        return obj.is_superuser

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class RoomHistorySerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source='room.name', read_only=True)

    class Meta:
        model = TreatmentRegistration
        fields = ['id', 'room_name', 'assigned_at', 'discharged_at']


# ----------------------------- ✅ FIXED: LabRegistration serializer -----------------------------
# Detect presence of optional FK at import-time
_LabReg = django_apps.get_model('apps', 'LabRegistration')
_LAB_FIELDS = {f.name for f in _LabReg._meta.get_fields()}
_HAS_ASSIGNED = 'assigned_doctor' in _LAB_FIELDS

# ---------------- LabRegistration ----------------
from django.apps import apps as django_apps
from rest_framework import serializers
from apps.models import LabRegistration
# PatientSerializer is already defined above in your file

_LabReg = django_apps.get_model('apps', 'LabRegistration')
_HAS_ASSIGNED = any(f.name == 'assigned_doctor' for f in _LabReg._meta.get_fields())

class LabRegistrationSerializer(serializers.ModelSerializer):
    # 🔹 Return the whole patient object so nameOf(x.patient) works
    patient = PatientSerializer(read_only=True)

    # convenience fields used by the modal text
    service_name = serializers.CharField(source='service.name', read_only=True)
    assigned_doctor_name = serializers.SerializerMethodField(read_only=True)
    repeat_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LabRegistration
        base = ['id', 'patient', 'service', 'status', 'created_at',
                'service_name', 'assigned_doctor_name', 'repeat_count']
        fields = (['assigned_doctor'] + base) if _HAS_ASSIGNED else base

    def get_assigned_doctor_name(self, obj):
        # prefer assigned_doctor if your model has it
        if _HAS_ASSIGNED and getattr(obj, 'assigned_doctor', None):
            d = obj.assigned_doctor
            return getattr(d, 'name', None) or f"{getattr(d,'first_name','')} {getattr(d,'last_name','')}".strip() or None
        # otherwise try via visit -> appointment -> doctor
        v = getattr(obj, 'visit', None)
        if v and getattr(v, 'appointment', None) and v.appointment.doctor:
            d = v.appointment.doctor
            return getattr(d, 'name', None) or f"{getattr(d,'first_name','')} {getattr(d,'last_name','')}".strip() or None
        return None

    def get_repeat_count(self, obj):
        try:
            return LabRegistration.objects.filter(patient=obj.patient, service=obj.service).count()
        except Exception:
            return None


from apps.models import Patient, Appointment, TreatmentRegistration, LabRegistration, TreatmentPayment
from django.db import models

class PatientArchiveSerializer(serializers.ModelSerializer):
    appointments = serializers.SerializerMethodField()
    treatment_history = serializers.SerializerMethodField()
    total_payments = serializers.SerializerMethodField()
    lab_services = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id',
            'first_name',
            'last_name',
            'phone',
            'created_at',
            'doctor',
            'appointments',
            'treatment_history',
            'lab_services',
            'total_payments',
        ]

    def get_doctor(self, obj):
        if obj.patients_doctor:
            return {
                'id': obj.patients_doctor.id,
                'first_name': obj.patients_doctor.user.first_name,
                'last_name': obj.patients_doctor.user.last_name
            }
        return None

    def get_appointments(self, obj):
        appointments = Appointment.objects.filter(patient=obj)
        return [{
            'date': appt.created_at.strftime('%Y-%m-%d %H:%M'),
            'status': appt.status,
            'doctor': appt.doctor.name if appt.doctor else None,
        } for appt in appointments]

    def get_treatment_history(self, obj):
        registrations = TreatmentRegistration.objects.filter(patient=obj).select_related('room')
        if not registrations.exists():
            return [{"room": "Noma'lum", "assigned_at": obj.created_at.strftime('%Y-%m-%d %H:%M'), "discharged_at": None, "total_paid": "0"}]
        return [{
            'room': reg.room.name if reg.room else "Noma'lum",
            'assigned_at': reg.assigned_at.strftime('%Y-%m-%d %H:%M') if reg.assigned_at else "N/A",
            'discharged_at': reg.discharged_at.strftime('%Y-%m-%d %H:%M') if reg.discharged_at else None,
            'total_paid': str(reg.total_paid or 0),
        } for reg in registrations]

    def get_lab_services(self, obj):
        registrations = LabRegistration.objects.filter(patient=obj).select_related('service')
        return [{
            'service': lab.service.name,
            'price': str(lab.service.price),
            'registered_at': lab.created_at.strftime('%Y-%m-%d %H:%M'),
            'status': lab.status
        } for lab in registrations]

    def get_total_payments(self, obj):
        total = TreatmentPayment.objects.filter(patient=obj).aggregate(total=models.Sum('amount'))['total'] or 0
        return str(total)
