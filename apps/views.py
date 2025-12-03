# apps/views.py
import random
import string
import json
from decimal import Decimal

from escpos.printer import Win32Raw, Usb
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
    Count,
    Q,
)
from django.db.models.functions import (
    Coalesce,
    ExtractDay,
    Now,
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.utils.timezone import localtime
from django.utils.dateparse import parse_date
from django.utils.timezone import now
from datetime import timedelta
from django.apps import apps as django_apps

from drf_spectacular.utils import extend_schema

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
    RetrieveAPIView,
    ListAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

# ➕ For HTML receipt rendering / URL reversing
from django.views import View
from django.shortcuts import render
from django.urls import reverse

from apps.models import (
    User,
    Doctor,
    Patient,
    Appointment,
    Payment,
    TreatmentRoom,
    TreatmentRegistration,
    PatientResult,
    Service,
    TreatmentPayment,
    CashRegister,
    TurnNumber,
    CurrentCall,
    Outcome,
    LabRegistration,
)
from apps.serializers import (
    ForgotPasswordSerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    LoginSerializer,
    LoginUserModelSerializer,
    UserInfoSerializer,
    DoctorSerializer,
    PatientSerializer,
    AppointmentSerializer,
    PaymentSerializer,
    TreatmentRoomSerializer,
    TreatmentRegistrationSerializer,
    PatientResultSerializer,
    ServiceSerializer,
    DoctorCreateSerializer,
    DoctorUserCreateSerializer,
    DoctorDetailSerializer,
    TreatmentPaymentSerializer,
    DoctorPaymentSerializer,
    CashRegisterSerializer,
    CallTurnSerializer,
    UserProfileSerializer,
    LabRegistrationSerializer,
    RoomHistorySerializer,
    PatientArchiveSerializer, 
    OutcomeSerializer,   
)

from apps.tasks import send_verification_email
from utils.receipt_printer import ReceiptPrinter

import logging
logger = logging.getLogger(__name__)


# ------------------------------------Register ------------------------------------------
@extend_schema(tags=['Login-Register'])
class RegisterAPIView(APIView):
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            verification_code = ''.join(random.choices(string.digits, k=6))
            user.reset_token = verification_code
            user.save()

            send_verification_email.delay(user.email, verification_code)

            return Response({"message": "User registered successfully. Check your email for the verification code."},
                            status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Login-Register'])
class VerifyEmailAPIView(APIView):
    serializer_class = LoginSerializer

    def post(self, request):
        email = request.data.get('email')
        verification_code = request.data.get('verification_code') or request.data.get('password')

        if not email or not verification_code:
            return Response({"error": "Email and verification code are required."}, status=400)

        try:
            user = User.objects.get(email=email, reset_token=verification_code)
            user.is_active = True
            user.reset_token = ''
            user.save()
            return Response({"message": "Email verified successfully."}, status=200)
        except User.DoesNotExist:
            return Response({"error": "Invalid email or verification code."}, status=400)


@extend_schema(tags=['Login-Register'])
class LoginAPIView(GenericAPIView):
    serializer_class = LoginUserModelSerializer
    permission_classes = [AllowAny]
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': user.role if hasattr(user, 'role') else None,
            'is_admin': user.is_superuser
        }, status=status.HTTP_200_OK)


@extend_schema(tags=['Access-Token'])
class ActivateUserView(APIView):
    def get(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            uid, is_active = uid.split('/')
            user = User.objects.get(pk=uid, is_active=is_active)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user and PasswordResetTokenGenerator().check_token(user, token):
            user.is_active = True
            user.save()
            return Response({"message": "User successfully verified!"})
        raise AuthenticationFailed('The link is invalid or expired.')


# -------------------------------Forgot password---------------------------------
class ForgotPasswordView(GenericAPIView):
    serializer_class = ForgotPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password reset link has been sent to your email."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)


# ----------------------------------User info -------------------------------
@extend_schema(tags=['user'])
class UserInfoListCreateAPIView(ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserInfoSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return super().get_queryset().filter(id=self.request.user.id)


# ------------------------------- Patients / Doctors / Appointments / Payments --------------
@extend_schema(tags=['Patient'])
class PatientRegistrationAPIView(APIView):
    @extend_schema(
        tags=["Registration"],
        request=PatientSerializer,
        responses={201: AppointmentSerializer}
    )
    def post(self, request):
        print("✅ Received patient data:", request.data)

        doctor_id = request.data.get("doctor_id")
        if not doctor_id:
            return Response({"error": "Doctor ID is required."}, status=400)

        try:
            doctor = Doctor.objects.get(id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor not found"}, status=404)

        patient_data = {
            "first_name": request.data.get("first_name"),
            "last_name": request.data.get("last_name"),
            "phone": request.data.get("phone"),
            "address": request.data.get("address"),
            "age": request.data.get("age"),
        }

        services = request.data.get("services", [])
        reason = request.data.get("reason")
        amount_paid = float(request.data.get("amount_paid", 0))
        amount_owed = float(request.data.get("amount_owed", 0))

        patient_serializer = PatientSerializer(data=patient_data)

        if patient_serializer.is_valid():
            patient = patient_serializer.save(patients_doctor=doctor)
            print("✅ Patient saved:", patient)

            turn_instance, created = TurnNumber.objects.get_or_create(doctor=doctor)
            if created or not turn_instance.letter:
                used_letters = set(TurnNumber.objects.exclude(letter=None).values_list("letter", flat=True))
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    if letter not in used_letters:
                        turn_instance.letter = letter
                        break
                else:
                    return Response({"error": "No available letters for doctor turn codes."}, status=400)
                turn_instance.save()

            try:
                turn_code = turn_instance.get_next_turn()
            except Exception as e:
                print("❌ Turn number generation failed:", e)
                return Response({"error": "Failed to generate turn number."}, status=400)

            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                reason=reason,
                status='queued',
                turn_number=turn_code
            )
            print("✅ Appointment created:", appointment)

            for service_id in services:
                try:
                    service = Service.objects.get(id=service_id)
                    appointment.services.add(service)
                except Service.DoesNotExist:
                    print(f"⚠️ Service ID {service_id} not found")

            Payment.objects.create(
                appointment=appointment,
                amount_paid=amount_paid,
                amount_due=amount_owed,
                status='partial' if amount_owed > 0 else 'paid'
            )

            response_data = AppointmentSerializer(appointment).data
            response_data["turn_number"] = appointment.turn_number
            response_data["doctor_name"] = doctor.user.get_full_name()

            return Response(response_data, status=HTTP_201_CREATED)

        else:
            print("❌ Patient serializer errors:", patient_serializer.errors)
            return Response(patient_serializer.errors, status=400)


@extend_schema(tags=['Doctor'])
class DoctorListCreateAPIView(ListCreateAPIView):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return super().get_queryset()


@extend_schema(tags=['Appointment'])
class AppointmentListCreateAPIView(ListCreateAPIView):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer


@extend_schema(tags=['Payment'])
class PaymentListCreateAPIView(ListCreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


@extend_schema(tags=['Treatment'])
class TreatmentRoomListCreateAPIView(ListCreateAPIView):
    queryset = TreatmentRoom.objects.all()
    serializer_class = TreatmentRoomSerializer


@extend_schema(tags=['Treatment-register'])
class TreatmentRegistrationListCreateAPIView(ListCreateAPIView):
    queryset = TreatmentRegistration.objects.all()
    serializer_class = TreatmentRegistrationSerializer


@extend_schema(tags=["Doctor Appointments"])
class DoctorAppointmentListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if not getattr(user, 'is_doctor', False):
            return Response({"error": "Only doctors can access this endpoint"}, status=403)

        try:
            doctor = Doctor.objects.get(user=user)
        except Doctor.DoesNotExist:
            return Response({"error": "This user is not linked to a Doctor profile"}, status=404)

        appointments = Appointment.objects.filter(doctor=doctor).order_by("created_at")
        serializer = AppointmentSerializer(appointments, many=True)
        queued_count = appointments.filter(status="queued").count()

        return Response({
            "total_appointments": appointments.count(),
            "queued_patients": queued_count,
            "appointments": serializer.data
        })


@extend_schema(tags=["Doctor Appointments"])
class DoctorAppointmentDetailAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Appointment.objects.filter(doctor__user=self.request.user)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"message": "Appointment deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=['Treatment'])
class AssignRoomAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        print("📥 Incoming data:", request.data)

        patient_id = request.data.get("patient_id")
        room_id = request.data.get("room_id")

        if not patient_id or not room_id:
            print("❌ Missing data")
            return Response({"error": "Missing patient_id or room_id"}, status=400)

        try:
            patient = Patient.objects.get(id=patient_id)
            print("✅ Found patient:", patient)

            room = TreatmentRoom.objects.get(id=room_id)
            print("✅ Found room:", room)

            active_regs = TreatmentRegistration.objects.filter(room=room, discharged_at__isnull=True).count()
            if active_regs >= room.capacity:
                return Response({"error": "Room is full"}, status=400)

            appointment = Appointment.objects.filter(patient=patient).latest("created_at")
            print("✅ Latest appointment:", appointment)

            TreatmentRegistration.objects.create(
                patient=patient,
                room=room,
                appointment=appointment,
                total_paid=room.price_per_day,
                assigned_at=now()
            )

            return Response({"message": "Patient assigned successfully"}, status=200)

        except Patient.DoesNotExist:
            print("❌ Patient not found")
            return Response({"error": "Patient not found"}, status=404)

        except Appointment.DoesNotExist:
            print("❌ No appointment found for patient")
            return Response({"error": "No appointment found for patient"}, status=404)

        except TreatmentRoom.DoesNotExist:
            print("❌ Room not found")
            return Response({"error": "Room not found"}, status=404)

        except Exception as e:
            print("❌ Unexpected error:", str(e))
            return Response({"error": str(e)}, status=500)


@extend_schema(tags=['Treatment'])
class TreatmentRoomDetailAPIView(RetrieveUpdateDestroyAPIView):
    queryset = TreatmentRoom.objects.all()
    serializer_class = TreatmentRoomSerializer
    permission_classes = [IsAuthenticated]


class PatientResultListCreateAPIView(ListCreateAPIView):
    queryset = PatientResult.objects.all()
    serializer_class = PatientResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        patient_id = self.request.query_params.get("patient")
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        return queryset


class PatientResultDetailAPIView(RetrieveUpdateDestroyAPIView):
    queryset = PatientResult.objects.all()
    serializer_class = PatientResultSerializer
    permission_classes = [IsAuthenticated]


class PatientDetailAPIView(RetrieveAPIView):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer


class PatientListAPIView(ListAPIView):
    queryset = Patient.objects.all().order_by('-created_at')
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]


class ServiceListCreateAPIView(ListCreateAPIView):
    queryset = Service.objects.select_related('doctor').all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]


class ServiceDetailAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]


@extend_schema(tags=['Doctor'])
class DoctorRegistrationAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data.copy()
        role = data.get("role")

        data["is_doctor"] = role == "doctor"
        data["is_cashier"] = role == "cashier"
        data["is_accountant"] = role == "accountant"
        data["is_registrator"] = role == "registration"
        data["is_superuser"] = role == "admin"

        serializer = DoctorCreateSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Foydalanuvchi muvaffaqiyatli ro'yxatdan o'tkazildi."}, status=201)
        return Response(serializer.errors, status=400)


class DoctorDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Doctor.objects.all()
    serializer_class = DoctorDetailSerializer
    permission_classes = [IsAuthenticated]


class RoomStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = []
        rooms = TreatmentRoom.objects.all()
        for room in rooms:
            active_regs = TreatmentRegistration.objects.filter(room=room, discharged_at__isnull=True)
            patient_names = [f"{reg.patient.first_name} {reg.patient.last_name}" for reg in active_regs]
            data.append({
                "room_id": room.id,
                "room_name": room.name,
                "capacity": room.capacity,
                "patients": patient_names
            })
        return Response(data)


@property
def is_active(self):
    return self.discharged_at is None


class TreatmentRoomList(ListAPIView):
    queryset = TreatmentRoom.objects.all()
    serializer_class = TreatmentRoomSerializer
    permission_classes = [IsAuthenticated]


# --------------------- Treatment Payments & Receipts ---------------------
@extend_schema(tags=["Treatment Payments"])
class TreatmentRoomPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rooms = TreatmentRoom.objects.all()
        data = []

        for room in rooms:
            registrations = TreatmentRegistration.objects.filter(room=room, discharged_at__isnull=True)
            patients_data = []
            for reg in registrations:
                total_paid = reg.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
                daily_price = room.price_per_day or 0
                days = (timezone.now().date() - reg.created_at.date()).days or 1
                amount_due = days * daily_price

                if total_paid >= amount_due:
                    status_str = "paid"
                elif total_paid > 0:
                    status_str = "partial"
                else:
                    status_str = "unpaid"

                patients_data.append({
                    "patient_id": reg.patient.id,
                    "patient_name": f"{reg.patient.first_name} {reg.patient.last_name}",
                    "amount_due": amount_due,
                    "amount_paid": total_paid,
                    "status": status_str,
                })

            data.append({
                "room_id": room.id,
                "room_name": room.name,
                "floor": room.floor,
                "patients": patients_data
            })

        return Response(data)


@extend_schema(tags=["Treatment Payments"])
class TreatmentRoomPaymentsView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TreatmentPaymentSerializer

    def get(self, request):
        rooms_data = []

        rooms = TreatmentRoom.objects.all()
        for room in rooms:
            active_regs = TreatmentRegistration.objects.filter(
                room=room, discharged_at__isnull=True
            ).select_related("patient")

            patients_data = []
            for reg in active_regs:
                patient = reg.patient

                payments = TreatmentPayment.objects.filter(patient=patient).order_by("date")
                total_paid = sum(p.amount for p in payments)
                expected = reg.total_paid

                if total_paid == 0:
                    status_str = "unpaid"
                elif total_paid < expected:
                    status_str = "partial"
                elif total_paid == expected:
                    status_str = "paid"
                else:
                    status_str = "prepaid"

                overpaid_amount = max(0, total_paid - expected)

                patients_data.append({
                    "id": patient.id,
                    "first_name": patient.first_name,
                    "last_name": patient.last_name,
                    "payments": TreatmentPaymentSerializer(payments, many=True).data,
                    "total_paid": float(total_paid),
                    "expected": float(expected),
                    "status": status_str,
                    "overpaid_amount": float(overpaid_amount),
                })

            rooms_data.append({
                "id": room.id,
                "name": room.name,
                "floor": room.floor,
                "price": float(room.price_per_day),
                "patients": patients_data,
            })

        return Response(rooms_data)

    def post(self, request, *args, **kwargs):
        print("🔥 Incoming POST:", request.data)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            print("❌ Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=400)


@extend_schema(tags=["Doctor Payments"])
class DoctorPaymentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            payments = TreatmentPayment.objects.select_related(
                'patient__patients_doctor__user'
            ).all().order_by("-date")
            serializer = DoctorPaymentSerializer(payments, many=True)
            return Response(serializer.data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Doctor Payments"])
class DoctorPaymentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = TreatmentPayment.objects.select_related(
            'patient__patients_doctor__user'
        ).all().order_by("-date")
        serializer = DoctorPaymentSerializer(payments, many=True)
        return Response(serializer.data)


class CashRegistrationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patients = Patient.objects.annotate(
            total_paid=Coalesce(Sum('treatmentpayment__amount'), 0),
            services_value=Coalesce(Sum('appointment__services__price'), 0),
            room_charges=Coalesce(Sum(
                ExpressionWrapper(
                    F('treatmentregistration__room__price_per_day') *
                    (ExtractDay(Now() - F('treatmentregistration__assigned_at')) + 1),
                    output_field=DecimalField()
                )
            ), 0),
            total_due=F('services_value') + F('room_charges'),
            balance=F('total_due') - F('total_paid')
        ).select_related(
            'patients_doctor'
        ).prefetch_related(
            'appointment_set__services',
            'treatmentregistration_set__room'
        )

    def post(self, request):
        serializer = CashRegisterSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class CashRegistrationView(ListCreateAPIView):
    serializer_class = CashRegisterSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        patient_id = self.kwargs.get('patient_id')
        return CashRegister.objects.filter(
            patient_id=patient_id
        ).select_related('patient', 'created_by')

    def list(self, request, *args, **kwargs):
        patient_id = self.kwargs.get('patient_id')

        try:
            patient = Patient.objects.select_related('patients_doctor__user').prefetch_related('services').get(
                id=patient_id)
        except Patient.DoesNotExist:
            return Response({"error": "Patient not found"}, status=404)

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        total_paid = queryset.aggregate(
            total=Sum(ExpressionWrapper(F('amount'), output_field=DecimalField()))
        )['total'] or Decimal('0.00')

        doctor_data = DoctorDetailSerializer(patient.patients_doctor).data if patient.patients_doctor else None
        latest_service = patient.services.last()
        service_data = ServiceSerializer(latest_service).data if latest_service else None

        balance = self.calculate_patient_balance(patient)

        return Response({
            'transactions': serializer.data,
            'summary': {
                'total_paid': total_paid,
                'balance': balance,
                'patient': {
                    'id': patient.id,
                    'name': f"{patient.first_name} {patient.last_name}",
                    'phone': patient.phone,
                    'patients_doctor': doctor_data,
                    'patients_service': service_data,
                }
            }
        })

    def calculate_patient_balance(self, patient):
        if patient.patients_doctor:
            consultation_price = patient.patients_doctor.consultation_price or Decimal('0.00')
            return consultation_price

        latest_service = patient.services.last()
        if latest_service:
            return latest_service.price

        return self._get_room_charges(patient)

    def _get_room_charges(self, patient):
        active_regs = TreatmentRegistration.objects.filter(
            patient=patient,
            discharged_at__isnull=True
        )
        days_expr = ExpressionWrapper(
            ExtractDay(Now() - F('assigned_at')) + 1,
            output_field=DecimalField(max_digits=5, decimal_places=2)
        )
        cost_expr = ExpressionWrapper(
            F('room__price_per_day') * days_expr,
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
        return active_regs.aggregate(total=Sum(cost_expr))['total'] or Decimal('0.00')


class CashRegisterReceiptView(RetrieveAPIView):
    queryset = CashRegister.objects.all()
    serializer_class = CashRegisterSerializer
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        doctor = instance.patient.patients_doctor
        doctor_name = f"{doctor.user.first_name} {doctor.user.last_name}" if doctor else None

        receipt_data = {
            'receipt_number': instance.reference or f"CR-{instance.id}",
            'date': instance.created_at.strftime("%Y-%m-%d %H:%M"),
            'patient_name': f"{instance.patient.first_name} {instance.patient.last_name}",
            'doctor_name': doctor_name,
            'transaction_type': instance.get_transaction_type_display(),
            'amount': float(instance.amount),
            'payment_method': instance.get_payment_method_display(),
            'processed_by': instance.created_by.get_full_name(),
            'notes': instance.notes
        }

        return Response(receipt_data)


class RecentPatientsByDaysView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 1))
        since_date = timezone.now() - timedelta(days=days)
        patients = Patient.objects.filter(created_at__gte=since_date)
        return Response(PatientSerializer(patients, many=True).data)


class CashRegisterListAPIView(ListAPIView):
    queryset = CashRegister.objects.select_related("patient", "created_by").all()
    serializer_class = CashRegisterSerializer
    permission_classes = [IsAuthenticated]


class CashRegisterListCreateAPIView(ListCreateAPIView):
    queryset = CashRegister.objects.all().order_by('-created_at')
    serializer_class = CashRegisterSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        transaction_type = self.request.data.get("transaction_type")
        prefix = "A" if transaction_type == "consultation" else "B"
        last = CashRegister.objects.filter(reference__startswith=prefix).order_by("-id").first()

        if last and last.turn_number:
            last_number = int(last.turn_number[1:])
        else:
            last_number = 0

        new_turn_number = f"{prefix}{last_number + 1:03d}"
        serializer.save(created_by=self.request.user, turn_number=new_turn_number)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        instance = serializer.save(created_by=self.request.user)

        receipt_data = {
            'receipt_number': instance.reference or f"CR-{instance.id}",
            'date': localtime(instance.created_at).strftime("%Y-%m-%d %H:%M"),
            'patient_name': f"{instance.patient.first_name} {instance.patient.last_name}",
            'transaction_type': instance.get_transaction_type_display(),
            'amount': float(instance.amount),
            'payment_method': instance.get_payment_method_display(),
            'processed_by': instance.created_by.get_full_name(),
            'notes': instance.notes or ""
        }

        try:
            printer = ReceiptPrinter()
            printer.print_receipt(receipt_data)
        except Exception as e:
            print("🖨️ Error printing receipt:", e)

        return Response(self.get_serializer(instance).data, status=201)


class RecentPatientsAPIView(APIView):
    def get(self, request):
        days = int(request.GET.get("days", 1))
        since = timezone.now() - timedelta(days=days)
        patients = Patient.objects.filter(created_at__gte=since)
        serializer = PatientSerializer(patients, many=True)
        return Response(serializer.data)


class RecentPatientsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 1))
        since = timezone.now() - timedelta(days=days)
        patients = Patient.objects.filter(created_at__gte=since).order_by("-created_at")
        patients = patients.exclude(first_name__isnull=True).exclude(last_name__isnull=True)
        serializer = PatientSerializer(patients, many=True)
        return Response(serializer.data)


# ✅ Active treatment registrations
class TreatmentRegistrationListCreateView(ListCreateAPIView):
    queryset = TreatmentRegistration.objects.filter(discharged_at__isnull=True)
    serializer_class = TreatmentRegistrationSerializer

    def perform_create(self, serializer):
        serializer.save()


# ➕ A4 DISCHARGE RECEIPT SUMMARY + HTML VIEW
def _discharge_summary(reg):
    patient = reg.patient
    appointment = reg.appointment
    doctor = getattr(appointment, "doctor", None)

    # costs
    consultation_cost = getattr(doctor, "consultation_price", 0) or 0
    services_cost = 0
    if appointment:
        try:
            services_cost = sum((s.price or 0) for s in appointment.services.all())
        except Exception:
            services_cost = 0

    end_dt = reg.discharged_at or timezone.now()
    days = (end_dt.date() - reg.assigned_at.date()).days + 1
    room_rate = (reg.room.price_per_day or 0) if reg.room else 0
    room_cost = days * room_rate

    # payments history
    cash_qs = CashRegister.objects.filter(patient=patient).order_by('created_at')
    room_qs = TreatmentPayment.objects.filter(patient=patient).order_by('date')

    cash_total = sum((p.amount or 0) for p in cash_qs) if cash_qs else 0
    room_total = sum((p.amount or 0) for p in room_qs) if room_qs else 0
    paid_total = cash_total + room_total

    due_total = (consultation_cost or 0) + (services_cost or 0) + (room_cost or 0)
    balance = due_total - paid_total

    return {
        "clinic_name": "Controllab",
        "patient": patient,
        "doctor": doctor,
        "registration": reg,
        "room": reg.room,
        "assigned_at": reg.assigned_at,
        "discharged_at": reg.discharged_at,
        "days": days,
        "room_rate": float(room_rate),
        "room_cost": float(room_cost),
        "consultation_cost": float(consultation_cost),
        "services_cost": float(services_cost),
        "due_total": float(due_total),
        "paid_total": float(paid_total),
        "balance": float(balance),
        "cash_payments": cash_qs,    # queryset of CashRegister
        "room_payments": room_qs,    # queryset of TreatmentPayment
    }


class DischargeReceiptHTMLView(View):
    template_name = "receipts/discharge.html"

    def get(self, request, pk):
        reg = get_object_or_404(TreatmentRegistration, pk=pk)
        ctx = _discharge_summary(reg)
        return render(request, self.template_name, ctx)


# SAFE CHANGE: keep only one final TreatmentDischargeView definition (with permissions)
class TreatmentDischargeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        registration = get_object_or_404(TreatmentRegistration, pk=pk, discharged_at__isnull=True)
        registration.discharged_at = now()
        registration.save()
        try:
            url = reverse('discharge-receipt', args=[pk])
        except Exception:
            url = f"/api/v1/treatment-registrations/{pk}/receipt/"
        return Response({"detail": "✅ Patient discharged.", "receipt_url": url}, status=status.HTTP_200_OK)


# -------------------- Move patient between rooms --------------------
from django.db import transaction  # safe local import
from django.utils.timezone import now as tz_now  # SAFE CHANGE: alias to avoid confusion with function name

class TreatmentMoveView(APIView):
    """
    Move a patient to another room by closing the current registration at the move
    moment and starting a new registration in the target room at the *same* moment.
    """

    def post(self, request, pk):
        old_reg = get_object_or_404(
            TreatmentRegistration.objects.select_related("room", "appointment", "patient"),
            pk=pk, discharged_at__isnull=True
        )

        new_room_id = request.data.get("room_id")
        if not new_room_id:
            return Response({"error": "room_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        if str(old_reg.room_id) == str(new_room_id):
            return Response({"detail": "Patient is already in this room."}, status=status.HTTP_200_OK)

        new_room = get_object_or_404(TreatmentRoom, pk=new_room_id)

        active_in_target = TreatmentRegistration.objects.filter(
            room=new_room, discharged_at__isnull=True
        ).count()
        if active_in_target >= (new_room.capacity or 0):
            return Response({"error": "Room is full"}, status=status.HTTP_400_BAD_REQUEST)

        move_time = tz_now()

        with transaction.atomic():
            old_reg = (
                TreatmentRegistration.objects
                .select_for_update()
                .get(pk=old_reg.pk)
            )
            if old_reg.discharged_at is not None:
                return Response({"error": "Registration is already closed."}, status=status.HTTP_409_CONFLICT)

            old_reg.discharged_at = move_time
            old_reg.save(update_fields=["discharged_at"])

            new_reg = TreatmentRegistration.objects.create(
                patient=old_reg.patient,
                room=new_room,
                appointment=old_reg.appointment,
                assigned_at=move_time,
            )

        return Response({
            "detail": "✅ Patient moved to new room.",
            "moved_at": move_time.isoformat(),
            "from_room": {"id": old_reg.room_id, "name": old_reg.room.name if old_reg.room else None},
            "to_room": {"id": new_room.id, "name": new_room.name},
            "old_registration_id": old_reg.id,
            "new_registration_id": new_reg.id,
        }, status=status.HTTP_200_OK)


class DoctorPatientRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor = request.user.doctor
        patients = Patient.objects.filter(patients_doctor=doctor)
        data = []

        for patient in patients:
            reg = TreatmentRegistration.objects.filter(patient=patient, discharged_at__isnull=True).first()
            if reg and reg.room:
                data.append({
                    "id": patient.id,
                    "first_name": patient.first_name,
                    "last_name": patient.last_name,
                    "room": reg.room.name,
                    "floor": reg.room.floor
                })

        return Response(data)


class GenerateTurnView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            doctor = Doctor.objects.get(user=user)
        except Doctor.DoesNotExist:
            return Response({"detail": "Siz shifokor emassiz"}, status=status.HTTP_403_FORBIDDEN)

        turn_number_obj, _ = TurnNumber.objects.get_or_create(doctor=doctor, defaults={
            "letter": self.assign_letter(),
        })

        next_turn = turn_number_obj.get_next_turn()
        return Response({
            "doctor": doctor.user.get_full_name(),
            "turn_number": next_turn
        })

    def assign_letter(self):
        used_letters = set(TurnNumber.objects.values_list('letter', flat=True))
        for char in map(chr, range(65, 91)):  # A-Z
            if char not in used_letters:
                return char
        raise ValueError("No letters available")


class CallPatientView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id):
        try:
            appointment = Appointment.objects.get(id=appointment_id, doctor=request.user.doctor)
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found"}, status=404)

        CurrentCall.objects.update_or_create(
            appointment=appointment,
            defaults={"called_at": timezone.now()}
        )

        return Response({"message": "Patient called (or recalled)"})


class CurrentCallsView(APIView):
    def get(self, request):
        doctor_calls = []
        service_calls = []
        queued = []

        for call in CurrentCall.objects.select_related('appointment__patient', 'appointment__doctor'):
            appointment = call.appointment
            patient = appointment.patient
            turn = getattr(appointment, "turn_number", None)
            if not turn:
                continue
            entry = {
                "id": appointment.id,
                "turn_number": turn,
                "patient_name": f"{patient.first_name} {patient.last_name}"
            }
            if turn.startswith("A"):
                doctor_calls.append(entry)
            elif turn.startswith("B"):
                service_calls.append(entry)

        called_ids = CurrentCall.objects.values_list("appointment_id", flat=True)
        queued_apps = Appointment.objects.filter(status="queued").exclude(id__in=called_ids).select_related("patient", "doctor")

        for app in queued_apps:
            if not app.turn_number:
                continue
            queued.append({
                "turn_number": app.turn_number,
                "patient_name": f"{app.patient.first_name} {app.patient.last_name}"
            })

        return Response({
            "doctor_calls": doctor_calls,
            "service_calls": service_calls,
            "queued": queued
        })


@extend_schema(request=CallTurnSerializer, tags=["Turn"])
class CallTurnView(APIView):
    def post(self, request):
        appointment_id = request.data.get("appointment_id")
        if not appointment_id:
            return Response({"error": "appointment_id required"}, status=400)

        try:
            appointment = Appointment.objects.get(id=appointment_id)
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found"}, status=404)

        CurrentCall.objects.update_or_create(
            appointment=appointment,
            defaults={"called_at": timezone.now()}
        )

        return Response({"success": True, "message": "Patient called"})


class PrintTurnView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patient_name = request.data.get("patient_name")
        doctor_name = request.data.get("doctor_name")
        turn_number = request.data.get("turn_number")
        patient_id = request.data.get("patient_id")

        if not all([patient_name, doctor_name, turn_number, patient_id]):
            return Response({"error": "Missing fields"}, status=400)

        try:
            p = Win32Raw("ReceiptPrinter")

            p.set(align='center', bold=True, width=2, height=2)
            p.text("Controllab Clinic\n")

            p.set(align='left', bold=False, width=1, height=1)
            p.text("--------------------------------\n")
            p.text(f"Bemor: {patient_name}\n")
            p.text(f"Shifokor: {doctor_name}\n")
            p.text(f"Sana: {timezone.now().strftime('%Y-%m-%d %H:%M')}\n")
            p.text("--------------------------------\n")

            p.set(align='center', bold=True)
            p.text("Iltimos navbatni kuting\n\n")

            p.set(width=8, height=8, bold=True)
            p.text(f"{turn_number}\n\n")

            location_url = f"http://yourdomain.com/patient/detail/{patient_id}/"
            p.qr(location_url, size=10)
            p.text(" Bemor haqida ma'lumot \n")
            p.cut()

            return Response({"message": "Printed ✅"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ClearCallView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id):
        try:
            call = CurrentCall.objects.get(appointment_id=appointment_id)
            call.delete()
            return Response({"message": "Call cleared"})
        except CurrentCall.DoesNotExist:
            return Response({"error": "Call not found"}, status=404)


class AdminStatisticsView(APIView):
    def get(self, request):
        start_date_raw = request.GET.get('start_date')
        end_date_raw = request.GET.get('end_date')

        start_date = parse_date(start_date_raw) if start_date_raw else None
        end_date = parse_date(end_date_raw) if end_date_raw else None

        cash_qs = CashRegister.objects.all()
        if start_date and end_date:
            cash_qs = cash_qs.filter(created_at__date__range=(start_date, end_date))

        room_qs = TreatmentPayment.objects.all()
        if start_date and end_date:
            room_qs = room_qs.filter(date__date__range=(start_date, end_date))

        total_profit = cash_qs.aggregate(total=Sum('amount'))['total'] or 0
        treatment_room_profit = room_qs.aggregate(total=Sum('amount'))['total'] or 0
        doctor_profit = cash_qs.filter(transaction_type='consultation').aggregate(total=Sum('amount'))['total'] or 0
        service_profit = cash_qs.filter(transaction_type='service').aggregate(total=Sum('amount'))['total'] or 0

        return Response({
            "total_profit": total_profit + treatment_room_profit,
            "treatment_room_profit": treatment_room_profit,
            "doctor_profit": doctor_profit,
            "service_profit": service_profit
        })


class RecentTransactionsView(APIView):
    def get(self, request):
        start_date_raw = request.GET.get('start_date')
        end_date_raw = request.GET.get('end_date')

        start_date = parse_date(start_date_raw) if start_date_raw else now().date() - timedelta(days=30)
        end_date = parse_date(end_date_raw) if end_date_raw else now().date()

        qs = CashRegister.objects.all()
        if start_date and end_date:
            qs = qs.filter(created_at__date__range=(start_date, end_date))

        qs = qs.order_by('-created_at')[:100]

        serializer = CashRegisterSerializer(qs, many=True)
        return Response(serializer.data)


class AdminChartDataView(APIView):
    def get(self, request):
        start_raw = request.GET.get('start_date')
        end_raw = request.GET.get('end_date')
        start = parse_date(start_raw) if start_raw else None
        end = parse_date(end_raw) if end_raw else None

        data = {
            "doctors": [],
            "services": [],
            "rooms": []
        }

        qs = CashRegister.objects.all()
        if start and end:
            qs = qs.filter(created_at__date__range=(start, end))

        doctor_qs = qs.filter(transaction_type='consultation')
        doctors = doctor_qs.values('doctor__name').annotate(profit=Sum('amount'))
        data['doctors'] = [{"name": d['doctor__name'] or "—", "profit": d['profit']} for d in doctors]

        service_qs = qs.filter(transaction_type='service')
        for s in service_qs:
            if s.notes and "Service Payment:" in s.notes:
                names = s.notes.replace("Service Payment:", "").split(",")
                for name in names:
                    clean = name.strip()
                    match = next((i for i in data["services"] if i["name"] == clean), None)
                    if match:
                        match["profit"] += s.amount
                    else:
                        data["services"].append({"name": clean, "profit": s.amount})

        room_qs = qs.filter(transaction_type='treatment')
        for r in room_qs:
            if r.notes and "Room Payment:" in r.notes:
                room_name = r.notes.replace("Room Payment:", "").strip()
                match = next((i for i in data["rooms"] if i["name"] == room_name), None)
                if match:
                    match["profit"] += r.amount
                else:
                    data["rooms"].append({"name": room_name, "profit": r.amount})

        today = now().date()
        first_day_this_month = today.replace(day=1)
        first_day_last_month = (first_day_this_month - timedelta(days=1)).replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)

        def get_month_data(s, e):
            base_qs = CashRegister.objects.filter(created_at__date__range=(s, e))
            return {
                "doctor_profit": base_qs.filter(transaction_type='consultation').aggregate(total=Sum('amount'))['total'] or 0,
                "service_profit": base_qs.filter(transaction_type='service').aggregate(total=Sum('amount'))['total'] or 0,
            }

        data["monthly_comparison"] = {
            "this_month": get_month_data(first_day_this_month, today),
            "last_month": get_month_data(first_day_last_month, last_day_last_month)
        }

        return Response(data)


class TreatmentPaymentReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        logger.info(f"Fetching payment with id={id} for user={request.user.id}")
        try:
            payment = get_object_or_404(TreatmentPayment._default_manager, id=id)
            patient = payment.patient
            user = payment.created_by
            logger.info(f"Payment found: id={payment.id}, patient={patient.id}, created_by={user.id if user else None}")

            try:
                registration = TreatmentRegistration.objects.filter(
                    patient=patient, discharged_at__isnull=True
                ).latest("assigned_at")
                doctor = registration.appointment.doctor if registration.appointment else None
                logger.info(f"Registration found: doctor={doctor.id if doctor else None}")
            except TreatmentRegistration.DoesNotExist:
                logger.info(f"No active registration for patient={patient.id}")
                doctor = None
            except Exception as e:
                logger.error(f"Error fetching registration for payment_id={id}: {str(e)}")
                doctor = None

            type_map = {
                'consultation': 'Konsultatsiya',
                'treatment': 'Davolash',
                'service': 'Xizmat',
                'room': 'Xona',
                'other': 'Boshqa'
            }

            method_map = {
                'cash': 'Naqd',
                'card': 'Karta',
                'insurance': 'Sug‘urta',
                'transfer': 'Bank'
            }

            return Response({
                "id": payment.id,
                "receipt_number": f"TP-{payment.id}",
                "date": payment.date.strftime("%Y-%m-%d %H:%M:%S") if payment.date else now().strftime("%Y-%m-%d %H:%M:%S"),
                "amount": float(payment.amount) if payment.amount else 0.0,
                "payment_method": method_map.get(payment.payment_method, payment.payment_method or "unknown"),
                "status": payment.status or "unknown",
                "notes": payment.notes or "",
                "patient_name": f"{patient.first_name} {patient.last_name}".strip() if patient else "Unknown",
                "doctor_name": f"{doctor.first_name} {doctor.last_name}".strip() if doctor else "—",
                "processed_by": user.get_full_name() if user else "Unknown",
                "transaction_type": type_map.get(payment.transaction_type, payment.transaction_type or "treatment")
            }, status=status.HTTP_200_OK)
        except TreatmentPayment.DoesNotExist:
            logger.error(f"TreatmentPayment with id={id} not found")
            return Response({"error": "To‘lov topilmadi"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Unexpected error in TreatmentPaymentReceiptView for payment_id={id}: {str(e)}")
            return Response({"error": f"Server xatosi: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PrintTreatmentRoomReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get("payment_id")
        if not payment_id:
            return Response({"error": "payment_id kiritilmadi"}, status=400)

        try:
            payment = get_object_or_404(TreatmentPayment, id=payment_id)
        except TreatmentPayment.DoesNotExist:
            logger.error(f"TreatmentPayment with id={payment_id} not found")
            return Response({"error": "To‘lov topilmadi"}, status=404)

        try:
            registration = TreatmentRegistration.objects.filter(
                patient=payment.patient, discharged_at__isnull=True
            ).latest("assigned_at")
            doctor = registration.appointment.doctor if registration.appointment else None
        except TreatmentRegistration.DoesNotExist:
            doctor = None
        except Exception as e:
            logger.error(f"Error fetching registration for payment_id={payment_id}: {str(e)}")
            doctor = None

        try:
            p = Usb(0x0483, 0x070b)
            p.set(align='center', text_type='B', width=2, height=2)
            p.text("🏥 NEURO PULS KLINIKASI\n\n")

            p.set(align='left', text_type='B', width=1, height=1)
            p.text(f"Chek raqami: TP-{payment.id}\n")
            p.text(f"Sana      : {payment.date.strftime('%Y-%m-%d %H:%M:%S')}\n")
            p.text(f"Bemor     : {payment.patient.first_name} {payment.patient.last_name}\n")
            p.text(f"Turi      : {payment.transaction_type or 'Davolash'}\n")
            p.text(f"Miqdor    : {float(payment.amount):.0f}.00 so'm\n")
            p.text(f"Usul      : {payment.payment_method or 'N/A'}\n")
            p.text(f"Qabulchi  : {payment.created_by.get_full_name() if payment.created_by else 'N/A'}\n")
            if payment.notes:
                p.text(f"Izoh      : {payment.notes}\n")
            p.text("-----------------------------\n")  # SAFE CHANGE: ensure newline
            p.text("Rahmat! Kuningiz yaxshi o‘tsin!\n")

            qr_data = json.dumps({
                "name": f"{payment.patient.first_name} {payment.patient.last_name}",
                "amount": str(payment.amount),
                "payment_method": payment.payment_method,
                "status": payment.status,
                "doctor": doctor.get_full_name() if doctor else "-",
                "note": payment.notes or "",
                "date": payment.date.strftime('%Y-%m-%d %H:%M:%S')
            }, ensure_ascii=False)

            p.text("\n\n")
            p.qr(qr_data, size=6)
            p.text("\n\n\n")
            p.cut()

            return Response({"success": True}, status=200)
        except Exception as e:
            logger.exception(f"❌ USB printerda xatolik for payment_id={payment_id}: {str(e)}")
            return Response({"error": str(e)}, status=500)


class TreatmentRoomStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = now().date()
        current_month = today.month
        current_year = today.year

        daily_total = TreatmentPayment.objects.filter(date__date=today).aggregate(
            total=Sum("amount")
        )["total"] or 0

        monthly_total = TreatmentPayment.objects.filter(
            date__year=current_year, date__month=current_month
        ).aggregate(total=Sum("amount"))["total"] or 0

        total_all = TreatmentPayment.objects.aggregate(
            total=Sum("amount")
        )["total"] or 0

        return Response({
            "daily_total": daily_total,
            "monthly_total": monthly_total,
            "total_all": total_all,
        })


class AccountantDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        cash_qs = CashRegister.objects.all()
        outcome_qs = Outcome.objects.all()
        treatment_qs = TreatmentPayment.objects.filter(status='paid')

        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            cash_qs = cash_qs.filter(created_at__date__range=(start, end))
            outcome_qs = outcome_qs.filter(created_at__date__range=(start, end))
            treatment_qs = treatment_qs.filter(date__date__range=(start, end))

        room_income = treatment_qs.aggregate(total=Sum('amount'))['total'] or 0

        income_summary = {}
        for item in cash_qs.values('payment_method').annotate(total=Sum('amount')):
            method = item['payment_method']
            income_summary[method] = income_summary.get(method, 0) + item['total']

        for item in treatment_qs.values('payment_method').annotate(total=Sum('amount')):
            method = item['payment_method']
            income_summary[method] = income_summary.get(method, 0) + item['total']

        income_summary_list = [{"payment_method": k, "total": v} for k, v in income_summary.items()]

        cash_total = cash_qs.aggregate(total=Sum('amount'))['total'] or 0
        total_income = cash_total + room_income
        total_outcome = outcome_qs.aggregate(total=Sum('amount'))['total'] or 0

        doctor_income = (
            cash_qs.filter(transaction_type='consultation')
            .select_related('doctor__user')
            .values('doctor__id', 'doctor__user__first_name', 'doctor__user__last_name')
            .annotate(total=Sum('amount'))
        )

        doctor_income_formatted = [
            {
                "doctor": {
                    "id": item['doctor__id'],
                    "first_name": item['doctor__user__first_name'],
                    "last_name": item['doctor__user__last_name'],
                },
                "total": float(item['total'])
            }
            for item in doctor_income
        ]

        service_income = []
        service_qs = cash_qs.filter(transaction_type='service')
        for s in service_qs:
            if s.notes and "Service Payment:" in s.notes:
                names = s.notes.replace("Service Payment:", "").split(",")
                for name in names:
                    clean = name.strip()
                    match = next((i for i in service_income if i["name"] == clean), None)
                    if match:
                        match["amount"] += s.amount
                    else:
                        service_income.append({"name": clean, "amount": s.amount})

        return Response({
            "total_income": float(total_income),
            "total_outcome": float(total_outcome),
            "balance": float(total_income - total_outcome),
            "incomes_by_method": income_summary_list,
            "doctor_income": doctor_income_formatted,
            "service_income": service_income,
            "room_income": float(room_income),
        })


class OutcomeListCreateView(generics.ListCreateAPIView):
    queryset = Outcome.objects.all().order_by('-created_at')
    serializer_class = OutcomeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        start = self.request.query_params.get('start_date')
        end = self.request.query_params.get('end_date')
        if start and end:
            qs = qs.filter(created_at__date__range=[start, end])
        return qs


class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class PrintTreatmentReceiptView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({"message": "Receipt printed"})


# ----------------------------- ✅ FIXED: SINGLE, ROBUST LabRegistration API -----------------------------
def _doctor_name(d):
    if not d:
        return None
    return getattr(d, "full_name", None) or f"{getattr(d, 'first_name', '')} {getattr(d, 'last_name', '')}".strip() or None


def _guess_doctor_from_service(service):
    """Works with either FK service.doctor or M2M service.doctors."""
    try:
        d = getattr(service, "doctor", None)
        if d:
            return d
        docs = getattr(service, "doctors", None)
        if docs:
            return docs.first()
    except Exception:
        pass
    return None


class LabRegistrationListCreateAPIView(generics.ListCreateAPIView):
    """
    List + create lab registrations safely.
    - Never evaluates a class-level queryset.
    - Treats 'undefined'/'null'/'' as missing IDs.
    - Returns 400 JSON for bad IDs instead of 500.
    """
    _LabReg = django_apps.get_model('apps', 'LabRegistration')
    _lab_fields = {f.name for f in _LabReg._meta.get_fields()}

    _rel = ['patient', 'service']
    if 'visit' in _lab_fields:
        _rel.append('visit')
    if 'assigned_doctor' in _lab_fields:
        _rel.append('assigned_doctor')

    queryset = None
    serializer_class = LabRegistrationSerializer
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _to_int_or_none(v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("", "null", "none", "undefined"):
                return None
            if s.isdigit():
                try:
                    return int(s)
                except Exception:
                    return None
        return None

    def _patient_is_required(self) -> bool:
        try:
            fld = self._LabReg._meta.get_field('patient')
            return not getattr(fld, 'null', False) and not getattr(fld, 'blank', False)
        except Exception:
            return True

    def _resolve_patient(self, patient_id):
        if patient_id is None:
            if self._patient_is_required():
                return None, {"detail": "patient_id is required"}
            return None, None
        try:
            return Patient.objects.get(pk=patient_id), None
        except Patient.DoesNotExist:
            return None, {"detail": f"Patient {patient_id} not found"}

    def _resolve_service(self, service_id):
        if service_id is None:
            return None, {"detail": "service_id is required"}
        try:
            return Service.objects.get(pk=service_id), None
        except Service.DoesNotExist:
            return None, {"detail": f"Service {service_id} not found"}

    def _resolve_doctor(self, explicit_doctor_id, service):
        if explicit_doctor_id is not None:
            try:
                return Doctor.objects.get(pk=explicit_doctor_id)
            except Doctor.DoesNotExist:
                pass
        d = getattr(service, 'doctor', None)
        if d:
            return d
        docs = getattr(service, 'doctors', None)
        if docs:
            first = docs.first()
            if first:
                return first
        return None

    def get_queryset(self):
        qs = self._LabReg.objects.select_related(*self._rel).order_by('-created_at')
        raw_patient = self.request.query_params.get('patient')
        pid = self._to_int_or_none(raw_patient)
        if pid is not None:
            qs = qs.filter(patient_id=pid)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = self.get_serializer(queryset, many=True)
        return Response(ser.data)

    def create(self, request, *args, **kwargs):
        patient_id = self._to_int_or_none(request.data.get('patient_id') or request.data.get('patient'))
        service_id = self._to_int_or_none(request.data.get('service_id') or request.data.get('service'))
        explicit_doctor_id = self._to_int_or_none(request.data.get('doctor_id'))

        patient, perr = self._resolve_patient(patient_id)
        if perr:
            return Response(perr, status=status.HTTP_400_BAD_REQUEST)

        service, serr = self._resolve_service(service_id)
        if serr:
            return Response(serr, status=status.HTTP_400_BAD_REQUEST)

        doctor = self._resolve_doctor(explicit_doctor_id, service)

        create_kwargs = dict(service=service, status='new')
        if patient is not None:
            create_kwargs['patient'] = patient
        if 'assigned_doctor' in self._lab_fields and doctor:
            create_kwargs['assigned_doctor'] = doctor

        try:
            reg = self._LabReg.objects.create(**create_kwargs)
        except Exception as e:
            return Response({"detail": f"Could not create registration: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        ser = self.get_serializer(reg)
        data = dict(ser.data)
        data.update({
            "service_name": getattr(service, "name", None),
            "assigned_doctor_name": _doctor_name(doctor),
            "repeat_count": (
                self._LabReg.objects.filter(patient=patient, service=service).count()
                if patient is not None else None
            ),
        })
        headers = self.get_success_headers(ser.data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)


class LabRegistrationDetailAPIView(RetrieveUpdateDestroyAPIView):
    queryset = LabRegistration.objects.all()
    serializer_class = LabRegistrationSerializer
    permission_classes = [IsAuthenticated]


class PublicDoctorServiceAPI(APIView):
    permission_classes = []  # public

    def get(self, request, doctor_id):
        qs = LabRegistration.objects.filter(service__doctor_id=doctor_id).select_related('patient', 'service')
        serializer = LabRegistrationSerializer(qs, many=True)
        return Response(serializer.data)


class PatientArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patients = Patient.objects.select_related('patients_doctor__user').prefetch_related(
            'appointment_set', 'treatmentregistration_set__room', 'labregistration_set__service'
        ).all().order_by('-created_at')
        serializer = PatientArchiveSerializer(patients, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RoomHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        registrations = TreatmentRegistration.objects.select_related('room').all()
        serializer = RoomHistorySerializer(registrations, many=True)
        return Response(serializer.data)


from django.template.loader import render_to_string

def _build_discharge_context(reg, request=None):
    """
    Compute all numbers needed for the A4 discharge receipt.
    """
    from decimal import Decimal
    from django.utils import timezone
    from django.db.models.functions import Coalesce
    from django.db.models import Sum
    from apps.models import Appointment, CashRegister, TreatmentPayment

    patient = reg.patient
    room = reg.room
    assigned_at = reg.assigned_at
    discharged_at = reg.discharged_at or timezone.now()

    days = max((discharged_at.date() - assigned_at.date()).days + 1, 1)

    room_rate = (room.price_per_day or Decimal("0.00")) if room else Decimal("0.00")
    room_cost = room_rate * days

    consultation_cost = Decimal("0.00")
    try:
        if patient.patients_doctor and patient.patients_doctor.consultation_price:
            consultation_cost = patient.patients_doctor.consultation_price
    except Exception:
        pass

    services_cost = Decimal("0.00")
    try:
        appts = Appointment.objects.filter(
            patient=patient,
            created_at__range=(assigned_at, discharged_at)
        ).prefetch_related("services")
        for a in appts:
            for s in a.services.all():
                services_cost += (s.price or Decimal("0.00"))
    except Exception:
        pass

    cash_payments = CashRegister.objects.filter(
        patient=patient,
        created_at__range=(assigned_at, discharged_at)
    )
    room_payments = TreatmentPayment.objects.filter(
        patient=patient,
        date__range=(assigned_at, discharged_at)
    )

    paid_total = (
        cash_payments.aggregate(t=Coalesce(Sum("amount"), Decimal("0.00")))["t"]
        + room_payments.aggregate(t=Coalesce(Sum("amount"), Decimal("0.00")))["t"]
    )

    due_total = room_cost + consultation_cost + services_cost
    balance = due_total - paid_total

    return {
        "clinic_name": "Controllab Clinic",
        "registration": reg,
        "patient": patient,
        "doctor": (reg.appointment.doctor if reg.appointment else None),
        "room": room,
        "assigned_at": assigned_at,
        "discharged_at": discharged_at,
        "days": days,
        "room_rate": room_rate,
        "room_cost": room_cost,
        "consultation_cost": consultation_cost,
        "services_cost": services_cost,
        "due_total": due_total,
        "paid_total": paid_total,
        "balance": balance,
        "cash_payments": list(cash_payments),
        "room_payments": list(room_payments),
        "request": request,
    }


class DischargeReceiptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        reg = get_object_or_404(TreatmentRegistration, pk=pk)
        ctx = _build_discharge_context(reg, request=request)
        html = render_to_string("receipts/discharge.html", ctx)
        return Response({"html": html}, status=200)


class TreatmentDischargeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        registration = get_object_or_404(TreatmentRegistration, pk=pk, discharged_at__isnull=True)
        registration.discharged_at = now()
        registration.save()

        receipt_api = reverse("discharge-receipt-api", args=[registration.pk])
        return Response(
            {"detail": "✅ Patient discharged.", "receipt_api": receipt_api},
            status=status.HTTP_200_OK
        )


# === Patient balances & printable statement ===
from django.template.response import TemplateResponse
from django.utils.timezone import localtime
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal as _Dec
from zoneinfo import ZoneInfo
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.urls import reverse

UZT = ZoneInfo("Asia/Tashkent")

def _to_int(x):
    try:
        return int(_Dec(x or 0))
    except Exception:
        return 0

def _count_9am_days(start_dt, end_dt):
    """
    Count “days” as 09:00→09:00 slots in Asia/Tashkent.

    Rules:
      - If start is at/after 09:00 local, you are already in Day 1.
      - If start is before 09:00, Day 1 starts at that day’s 09:00 (only if end reaches it).
      - Crossing a 09:00 boundary increments the day count, but EXACTLY at 09:00
        still belongs to the previous day (boundary itself does NOT increment).
    """
    if not start_dt or not end_dt or end_dt <= start_dt:
        return 0

    s = timezone.localtime(start_dt, UZT)
    e = timezone.localtime(end_dt, UZT)

    # Determine the 09:00 slot that 's' belongs to: [slot_start, slot_end)
    day_9 = s.replace(hour=9, minute=0, second=0, microsecond=0)
    if s >= day_9:
        slot_start = day_9                    # same day 09:00
    else:
        slot_start = day_9 - timedelta(days=1)  # previous day 09:00
    slot_end = slot_start + timedelta(days=1)   # next 09:00

    # If we never reach the first slot_end:
    if e <= slot_end:
        # Day 1 applies if we were already after today's 09:00, or
        # we started before 09:00 and reached it.
        return 1 if (s >= day_9 or e >= day_9) and e > s else 0

    # We passed the first 09:00 boundary strictly → at least 2 days.
    delta_after_first = e - slot_end
    extra = delta_after_first.days
    if delta_after_first.seconds or delta_after_first.microseconds:
        extra += 1
    return 1 + extra


class _BillingMath:
    """Compute per-patient expected & paid totals (receipt view).
       Room (yotoqxona) uses 09:00→09:00 charging. If a new stay starts on the
       same *calendar* day the previous stay ended, that first day is NOT double-charged.
    """

    @staticmethod
    def compute_for_patient(p):
        # --- find doctor for header/consultation price
        doctor = getattr(p, "patients_doctor", None)
        if not doctor:
            try:
                last_app = p.appointment_set.order_by("-created_at").first()
            except Exception:
                last_app = None
            if last_app and getattr(last_app, "doctor", None):
                doctor = last_app.doctor
        if not doctor:
            try:
                for reg in p.treatmentregistration_set.all():
                    if getattr(reg, "appointment", None) and getattr(reg.appointment, "doctor", None):
                        doctor = reg.appointment.doctor
                        break
            except Exception:
                pass

        doctor_name = None
        if doctor:
            if getattr(doctor, "user", None):
                full = (doctor.user.get_full_name() or "").strip()
                doctor_name = full or getattr(doctor, "name", None) or None
            else:
                doctor_name = getattr(doctor, "name", None) or None

        # consultation
        consult_expected = float(doctor.consultation_price) if (doctor and doctor.consultation_price) else 0.0

        # services
        services_expected = 0.0
        try:
            lrs = getattr(p, "labregistration_set", None)
            if lrs is not None and lrs.exists():
                for lr in lrs.select_related("service"):
                    status = (getattr(lr, "status", "") or "").lower()
                    if status in ("cancelled", "canceled", "bekor", "bekor qilingan"):
                        continue
                    svc = getattr(lr, "service", None)
                    services_expected += float(getattr(svc, "price", 0) or 0)
            else:
                seen = set()
                for app in p.appointment_set.all():
                    for s in app.services.all():
                        if s.id in seen:
                            continue
                        seen.add(s.id)
                        services_expected += float(s.price or 0)
        except Exception:
            services_expected = 0.0

        # room (09:00 logic)
        room_expected = 0.0
        try:
            regs = (
                p.treatmentregistration_set
                 .select_related("room")
                 .order_by("assigned_at", "id")
            )
            prev_end_local_date = None

            for reg in regs:
                room = getattr(reg, "room", None)
                if not room:
                    continue

                start = (
                    getattr(reg, "assigned_at", None)
                    or getattr(reg, "admitted_at", None)
                    or getattr(reg, "start_date", None)
                    or getattr(reg, "created_at", None)
                )
                end = getattr(reg, "discharged_at", None) or timezone.now()

                ticks = _count_9am_days(start, end)

                # If a new reg starts the same *calendar* day the previous ended, avoid double baseline.
                if prev_end_local_date and timezone.localtime(start, UZT).date() == prev_end_local_date:
                    ticks = max(ticks - 1, 0)

                room_expected += ticks * float(getattr(room, "price_per_day", 0) or 0)
                prev_end_local_date = timezone.localtime(end, UZT).date()
        except Exception:
            pass

        expected_due = consult_expected + services_expected + room_expected

        # paid (cash register)
        paid_consult = 0.0
        paid_service = 0.0
        paid_other_cash = 0.0
        try:
            for cr in p.cashregister_set.all():
                t = (cr.transaction_type or "").lower()
                amt = float(cr.amount or 0)
                if t == "consultation":
                    paid_consult += amt
                elif t == "service":
                    paid_service += amt
                else:
                    paid_other_cash += amt
        except Exception:
            pass

        # paid (room)
        paid_room = 0.0
        try:
            qs = p.treatmentpayment_set.exclude(status__in=["unpaid", "canceled", "cancelled"])
            for tp in qs:
                paid_room += float(tp.amount or 0)
        except Exception:
            pass

        paid_total = paid_consult + paid_service + paid_other_cash + paid_room

        return {
            "doctor_name": doctor_name,
            "consult_expected": round(consult_expected),
            "services_expected": round(services_expected),
            "room_expected": round(room_expected),
            "expected_due": round(expected_due),
            "paid_consult": round(paid_consult),
            "paid_service": round(paid_service),
            "paid_other_cash": round(paid_other_cash),
            "paid_room": round(paid_room),
            "paid_total": round(paid_total),
            "balance": round(expected_due - paid_total),
        }


class PatientBalancesAPIView(APIView):
    """List last N patients (default 200) with expected/paid/balance."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get("limit", 200))
        patients = (
            Patient.objects
                .order_by('-created_at')[:limit]
                .select_related('patients_doctor__user')
                .prefetch_related(
                    'appointment_set__services',
                    'treatmentregistration_set__room',
                    'cashregister_set',
                    'treatmentpayment_set',
                )
        )

        rows = []
        for p in patients:
            math = _BillingMath.compute_for_patient(p)
            rows.append({
                "id": p.id,
                "name": f"{p.first_name} {p.last_name}".strip(),
                "phone": p.phone,
                "doctor": math["doctor_name"],
                "consultation_expected": math["consult_expected"],
                "services_expected": math["services_expected"],
                "room_expected": math["room_expected"],
                "expected_due": math["expected_due"],
                "paid_consultation": math["paid_consult"],
                "paid_service": math["paid_service"],
                "paid_room": math["paid_room"],
                "paid_other_cash": math["paid_other_cash"],
                "paid_total": math["paid_total"],
                "balance": math["balance"],
                "created_at": p.created_at,
            })
        return Response(rows)


class PatientBillingAPIView(APIView):
    """Per-patient breakdown + a URL to printable A4 receipt."""
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        p = get_object_or_404(
            Patient.objects
                .select_related('patients_doctor__user')
                .prefetch_related(
                    'appointment_set__services',
                    'treatmentregistration_set__room',
                    'cashregister_set',
                    'treatmentpayment_set',
                ),
            pk=patient_id
        )
        math = _BillingMath.compute_for_patient(p)

        cash_payments = []
        for cr in p.cashregister_set.all().order_by('-created_at'):
            cash_payments.append({
                "date": localtime(cr.created_at).strftime("%Y-%m-%d %H:%M"),
                "type": cr.get_transaction_type_display() if hasattr(cr, "get_transaction_type_display") else (cr.transaction_type or "-"),
                "method": cr.get_payment_method_display() if hasattr(cr, "get_payment_method_display") else (cr.payment_method or "-"),
                "amount": float(cr.amount or 0),
                "notes": cr.notes or "",
            })

        room_payments = []
        for tp in p.treatmentpayment_set.all().order_by('-date'):
            room_payments.append({
                "date": localtime(tp.date).strftime("%Y-%m-%d %H:%M") if tp.date else "",
                "status": tp.status or "-",
                "method": tp.get_payment_method_display() if hasattr(tp, "get_payment_method_display") else (tp.payment_method or "-"),
                "amount": float(tp.amount or 0),
                "notes": tp.notes or "",
            })

        return Response({
            "patient": {
                "id": p.id,
                "name": f"{p.first_name} {p.last_name}".strip(),
                "phone": p.phone,
                "doctor": math["doctor_name"],
            },
            "expected": {
                "consultation": math["consult_expected"],
                "services": math["services_expected"],
                "room": math["room_expected"],
                "total": math["expected_due"],
            },
            "paid": {
                "consultation": math["paid_consult"],
                "services": math["paid_service"],
                "room": math["paid_room"],
                "other_cash": math["paid_other_cash"],
                "total": math["paid_total"],
            },
            "balance": math["balance"],
            "cash_payments": cash_payments,
            "room_payments": room_payments,
            "receipt_url": request.build_absolute_uri(
                reverse('patient-billing-print', args=[p.id])
            ),
        })


class PatientBillingReceiptHTMLView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        p = get_object_or_404(
            Patient.objects
                .select_related('patients_doctor__user')
                .prefetch_related(
                    'appointment_set__services',
                    'treatmentregistration_set__room',
                    'cashregister_set',
                    'treatmentpayment_set',
                ),
            pk=patient_id
        )
        math = _BillingMath.compute_for_patient(p)

        ctx = {
            "clinic_name": "Controllab Clinic",
            "patient": p,
            "doctor_name": math["doctor_name"] or "—",
            "consultation_cost": math["consult_expected"],
            "services_cost": math["services_expected"],
            "room_cost": math["room_expected"],
            "due_total": math["expected_due"],
            "paid_total": math["paid_total"],
            "balance": math["balance"],
            "cash_payments": p.cashregister_set.all().order_by('-created_at'),
            "room_payments": p.treatmentpayment_set.all().order_by('-date'),
        }
        return TemplateResponse(request, "receipts/patient_billing.html", ctx)


# ------------------------ Compact balances API (new shape + legacy rows) ------------------------
class PatientBalancesDataView(APIView):
    """
    GET /api/v1/patient-balances/data/?q=&limit=200

    Returns two shapes to keep old JS (v6/v8) working:
      - items[]  (new, rich)
      - rows[]   (legacy alias)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        try:
            limit = int(request.GET.get("limit", 200))
        except Exception:
            limit = 200

        qs = (
            Patient.objects
            .select_related("patients_doctor", "patients_doctor__user")
            .order_by("-id")
        )
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(phone__icontains=q)
            )
        qs = qs[:limit]

        items = []
        total_billed = _Dec(0)
        total_paid = _Dec(0)

        for p in qs:
            m = _BillingMath.compute_for_patient(p)

            billed  = _Dec(m.get("expected_due", 0) or 0)
            paid    = _Dec(m.get("paid_total", 0) or 0)
            balance = billed - paid

            total_billed += billed
            total_paid   += paid

            doctor_name = (m.get("doctor_name") or "—")

            item = {
                "id": p.id,
                "first_name": getattr(p, "first_name", ""),
                "last_name": getattr(p, "last_name", ""),
                "name": f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip(),
                "phone": getattr(p, "phone", "") or "",
                "doctor_name": doctor_name,
                "doctor": doctor_name,
                "consultation_cost": _to_int(m.get("consult_expected", 0)),
                "services_cost":     _to_int(m.get("services_expected", 0)),
                "room_cost":         _to_int(m.get("room_expected", 0)),
                "expected_due":      _to_int(billed),
                "paid_total":        _to_int(paid),
                "balance":           _to_int(balance),
                "breakdown": {
                    "konsultatsiya": _to_int(m.get("consult_expected", 0)),
                    "xizmat":        _to_int(m.get("services_expected", 0)),
                    "yotoq":         _to_int(m.get("room_expected", 0)),
                },
                "billed_total": _to_int(billed),
            }
            items.append(item)

        rows = [{
            "id": x["id"],
            "first_name": x["first_name"],
            "last_name": x["last_name"],
            "phone": x["phone"],
            "doctor_name": x["doctor_name"],
            "billed": x["billed_total"],
            "paid": x["paid_total"],
            "balance": x["balance"],
            "breakdown": x["breakdown"],
        } for x in items]

        return Response({
            "count": len(items),
            "totals": {
                "billed": _to_int(total_billed),
                "paid": _to_int(total_paid),
                "balance": _to_int(total_billed - total_paid),
            },
            "items": items,
            "rows": rows,
        })


# ------------------------ Unpaid patients (balance > 0) ------------------------
class UnpaidPatientsDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q_raw = (request.query_params.get("q") or "").strip()
        q = q_raw.lower()

        try:
            limit = max(1, int(request.query_params.get("limit", 200)))
        except Exception:
            limit = 200
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
        except Exception:
            offset = 0

        patients = (
            Patient.objects.order_by("-id")
            .select_related("patients_doctor", "patients_doctor__user")
            .prefetch_related(
                "appointment_set__services",
                "treatmentregistration_set__room",
                "cashregister_set",
                "treatmentpayment_set",
                "labregistration_set__service",
            )
        )

        if q:
            patients = patients.filter(
                Q(first_name__icontains=q_raw)
                | Q(last_name__icontains=q_raw)
                | Q(phone__icontains=q_raw)
            )

        results = []
        for p in patients:
            math = _BillingMath.compute_for_patient(p)

            balance = int(math.get("balance") or 0)
            if balance <= 0:
                continue

            name = (f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()
                    or getattr(p, "full_name", "") or "—")

            results.append({
                "id": p.id,
                "name": name,
                "phone": getattr(p, "phone", "") or "",
                "doctor": (math.get("doctor_name") or "—"),
                "expected_due": int(math.get("expected_due") or 0),
                "paid_total":   int(math.get("paid_total")   or 0),
                "balance":      balance,
            })

        total_count = len(results)
        page = results[offset:offset + limit]

        role = getattr(request.user, "role", None)
        can_take_payment = (
            getattr(request.user, "is_superuser", False)
            or role in ("admin", "cashier")
            or getattr(request.user, "is_cashier", False)
        )

        return Response({
            "count": total_count,
            "can_take_payment": bool(can_take_payment),
            "results": page,
        }, status=200)


# ------------------------ Admin: reset doctor password ------------------------
from django.utils.crypto import get_random_string
from django.contrib.auth import get_user_model

class AdminResetDoctorPasswordView(APIView):
    """
    Reset a user's password and return a one-time temporary password.
    Only for admins/superusers/staff.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        me = request.user
        if not (getattr(me, "is_superuser", False) or getattr(me, "is_staff", False) or getattr(me, "role", "") == "admin"):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        UserModel = get_user_model()
        user = get_object_or_404(UserModel, pk=pk)

        temp_pw = get_random_string(length=12)
        user.set_password(temp_pw)
        user.save(update_fields=["password"])

        return Response({
            "id": user.id,
            "email": getattr(user, "email", None),
            "temporary_password": temp_pw
        }, status=status.HTTP_200_OK)
