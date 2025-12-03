from django.contrib import admin
from django import forms
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html
import random
import string

from .models import (
    Patient, Doctor, Service, Appointment, Payment, TreatmentRoom,
    TreatmentRegistration, CashRegister, Outcome, LabRegistration, Visit
)

from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html


# ---------------- Patient admin ---------------- #

class PatientAdminForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        required=False,
        label="Assign Doctor (auto-create appointment)"
    )
    class Meta:
        model = Patient
        fields = '__all__'

class PatientAdmin(admin.ModelAdmin):
    form = PatientAdminForm
    actions = [
        "safe_delete_patients_keep_income",
        "safe_delete_patients_wipe_income",
        "hard_delete_patients",
    ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        doctor = form.cleaned_data.get('doctor')
        if doctor:
            Appointment.objects.create(
                patient=obj,
                doctor=doctor,
                reason="Admin registration",
                status="queued"
            )

    # internal: safe delete impl (handles CashRegister PROTECT)
    def _safe_delete_impl(self, request, queryset, wipe_income=False):
        pks = list(queryset.values_list("pk", flat=True))
        if not pks:
            self.message_user(request, "No patients selected.")
            return

        dummy, _ = Patient.objects.get_or_create(
            first_name="Deleted", last_name="Patient",
            defaults={'phone':'0000000','address':'(removed)'}
        )
        if dummy.pk in pks:
            pks = [pk for pk in pks if pk != dummy.pk]
        if not pks:
            self.message_user(request, "Selection only contained the placeholder; nothing to delete.")
            return

        with transaction.atomic():
            # delete treatment/lab registrations for those patients (UI cleanliness; CASCADE would also handle)
            TreatmentRegistration.objects.filter(patient_id__in=pks).delete()
            LabRegistration.objects.filter(patient_id__in=pks).delete()

            # optionally wipe incomes (service + consultation only)
            wiped = 0
            if wipe_income:
                wiped = CashRegister.objects.filter(
                    patient_id__in=pks,
                    transaction_type__in=['service','consultation']
                ).delete()[0]

            # reassign any remaining CashRegister rows (room/treatment/other) to placeholder
            reassigned = CashRegister.objects.filter(patient_id__in=pks).update(patient=dummy)

            # finally delete the patients themselves
            deleted = Patient.objects.filter(pk__in=pks).delete()

        msg = (f"Wiped incomes (service+consultation): {wiped}; "
               f"CashRegister reassigned: {reassigned}; "
               f"Patients deleted (tuple): {deleted}")
        self.message_user(request, msg)

    def safe_delete_patients_keep_income(self, request, queryset):
        self._safe_delete_impl(request, queryset, wipe_income=False)
    safe_delete_patients_keep_income.short_description = "Delete patients (safe) — keep income records"

    def safe_delete_patients_wipe_income(self, request, queryset):
        self._safe_delete_impl(request, queryset, wipe_income=True)
    safe_delete_patients_wipe_income.short_description = "Delete patients (safe) + wipe shifokor/service daromadi"

    def hard_delete_patients(self, request, queryset):
        deleted = Patient.objects.filter(pk__in=list(queryset.values_list("pk", flat=True))).delete()
        self.message_user(request, f"Hard-deleted patients (tuple): {deleted}")
    hard_delete_patients.short_description = "Delete patients (HARD, cascade)"

# ---------------- Doctor admin with inline + reset password ---------------- #

class AppointmentInline(admin.TabularInline):
    model = Appointment
    fk_name = 'doctor'
    extra = 0
    fields = ('patient', 'reason', 'status', 'created_at')
    readonly_fields = ('patient', 'reason', 'status', 'created_at')
    can_delete = False
    show_change_link = True


class DoctorPasswordForm(forms.ModelForm):
    # Extra, non-model fields shown in the admin
    new_password1 = forms.CharField(
        label="Set password",
        widget=forms.PasswordInput,
        required=False,
        help_text="Fill both fields to change the linked user's password."
    )
    new_password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
        required=False
    )

    class Meta:
        model = Doctor
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1") or ""
        p2 = cleaned.get("new_password2") or ""
        if p1 or p2:
            if not p1 or not p2:
                raise forms.ValidationError("Please enter the password twice.")
            if p1 != p2:
                raise forms.ValidationError("Passwords do not match.")
            if len(p1) < 1:
                raise forms.ValidationError("Password must be at least 6 characters.")
        return cleaned


# 2) Then define the ModelAdmin that uses it
class DoctorAdmin(admin.ModelAdmin):
    form = DoctorPasswordForm
    list_display = ('name', 'specialty', 'queued_patients_count')
    inlines = [AppointmentInline]

    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'specialty', 'consultation_price'),
        }),
        ('Set password (optional)', {
            'fields': ('new_password1', 'new_password2'),
            'description': "If you fill both fields, the linked user's password will be changed."
        }),
    )

    def queued_patients_count(self, obj):
        return obj.appointments.filter(status="queued").count()
    queued_patients_count.short_description = "Patients Waiting"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        p1 = form.cleaned_data.get("new_password1")
        if p1:
            user = getattr(obj, "user", None)
            if not user:
                messages.error(request, "This doctor has no linked user; cannot set password.")
                return
            user.set_password(p1)
            user.save()
            messages.success(
                request,
                f"Password updated for {user.get_full_name() or user.email}."
            )

class DoctorAdmin(admin.ModelAdmin):
    form = DoctorPasswordForm
    list_display = ('name', 'specialty', 'queued_patients_count')
    inlines = [AppointmentInline]

    # Show the two inputs on the edit page
    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'specialty', 'consultation_price'),
        }),
        ('Set password (optional)', {
            'fields': ('new_password1', 'new_password2'),
            'description': 'If you fill both fields, the linked user\'s password will be changed.'
        }),
    )

    def queued_patients_count(self, obj):
        return obj.appointments.filter(status="queued").count()
    queued_patients_count.short_description = "Patients Waiting"

    # When you click Save, if passwords were provided, update the linked User
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        p1 = form.cleaned_data.get("new_password1")
        if p1:
            user = getattr(obj, "user", None)
            if not user:
                messages.error(request, "This doctor has no linked user; cannot set password.")
                return
            user.set_password(p1)
            user.save()
            messages.success(
                request,
                f"Password updated for {user.get_full_name() or user.email}."
            )







# ---------------- TreatmentRegistration admin ---------------- #

@admin.register(TreatmentRegistration)
class TreatmentRegistrationAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'room', 'assigned_at', 'discharged_at', 'total_paid')
    actions = ["delete_all_treatment_regs"]

    def delete_all_treatment_regs(self, request, queryset):
        with transaction.atomic():
            count = TreatmentRegistration.objects.all().delete()[0]
        self.message_user(request, f"Deleted ALL TreatmentRegistration rows: {count}")
    delete_all_treatment_regs.short_description = "Delete ALL treatment registrations"

# ---------------- CashRegister admin (daromad buttons) ---------------- #

@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'transaction_type', 'amount', 'payment_method', 'doctor', 'room', 'created_at')
    list_filter  = ('transaction_type', 'payment_method', 'created_at')
    actions = ['delete_xizmat_daromadi', 'delete_shifokor_daromadi']

    def delete_xizmat_daromadi(self, request, queryset):
        n = CashRegister.objects.filter(transaction_type='service').delete()[0]
        self.message_user(request, f"Deleted XIZMAT daromadi rows: {n}")
    delete_xizmat_daromadi.short_description = "Delete XIZMAT daromadi (transaction_type=service)"

    def delete_shifokor_daromadi(self, request, queryset):
        n = CashRegister.objects.filter(transaction_type='consultation').delete()[0]
        self.message_user(request, f"Deleted SHIFOKOR/CONSULTATION daromadi rows: {n}")
    delete_shifokor_daromadi.short_description = "Delete SHIFOKOR daromadi (transaction_type=consultation)"

# ---------------- Outcome admin (Umumiy xarajat button) ---------------- #

@admin.register(Outcome)
class OutcomeAdmin(admin.ModelAdmin):
    list_display = ('id','title','category','amount','payment_method','created_at','created_by')
    list_filter  = ('category','payment_method','created_at')
    search_fields = ('title','notes','created_by__email')

    actions = ['delete_umumiy_xarajat']

    def delete_umumiy_xarajat(self, request, queryset):
        q = (Q(title__iexact='Umumiy xarajat') | Q(notes__iexact='Umumiy xarajat') |
             Q(title__iregex=r'(?i)\bumumiy\b.*\bxarajat\b') |
             Q(notes__iregex=r'(?i)\bumumiy\b.*\bxarajat\b'))
        n = Outcome.objects.filter(q).delete()[0]
        self.message_user(request, f"Deleted UMUMIY XARAJAT rows: {n}")
    delete_umumiy_xarajat.short_description = "Delete UMUMIY XARAJAT rows"

# ---------------- Register remaining basics ---------------- #

admin.site.register(Patient, PatientAdmin)
admin.site.register(Doctor, DoctorAdmin)
admin.site.register(Appointment)
admin.site.register(Payment)
admin.site.register(TreatmentRoom)
admin.site.register(Service)
admin.site.register(LabRegistration)
admin.site.register(Visit)
