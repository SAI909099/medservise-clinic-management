# ✅ FIXED urls.py
from django.urls import path
from django.views.generic import TemplateView

from apps.views import UnpaidPatientsDataView  # add this import
from apps.views import AdminResetDoctorPasswordView  # ADD THIS IMPORT


# If you don't actually use this in urls, you can remove it.
# from apps.frontend_views import UserProfileView

# Alias so your frontend can call /api/v1/token/refresh/
from rest_framework_simplejwt.views import TokenRefreshView

# Use the CallTurnView defined in apps.views (not the one in models)
from apps.views import (
    # Auth
    RegisterAPIView, VerifyEmailAPIView, LoginAPIView, UserInfoListCreateAPIView,
    PasswordResetConfirmView, ActivateUserView,

    # Patients
    PatientRegistrationAPIView, PatientDetailAPIView, PatientListAPIView, RecentPatientsView, RecentPatientsByDaysView,

    # Doctors
    DoctorListCreateAPIView, DoctorRegistrationAPIView, DoctorDetailView,

    # Appointments
    AppointmentListCreateAPIView, DoctorAppointmentListAPIView, DoctorAppointmentDetailAPIView,

    # Services
    ServiceListCreateAPIView, ServiceDetailAPIView,

    # Payments
    PaymentListCreateAPIView, TreatmentRoomPaymentsView, DoctorPaymentsAPIView, DoctorPaymentListView,

    # Treatment Rooms
    TreatmentRoomListCreateAPIView, TreatmentRoomDetailAPIView, TreatmentRoomList,
    AssignRoomAPIView, RoomStatusAPIView,

    # Treatment Registrations
    TreatmentRegistrationListCreateAPIView,

    # Patient Results
    PatientResultListCreateAPIView, PatientResultDetailAPIView,

    # Cash Register
    CashRegistrationListView, CashRegistrationView, CashRegisterReceiptView,
    CashRegisterListAPIView, CashRegisterListCreateAPIView, RecentPatientsAPIView, TreatmentRegistrationListCreateView,
    TreatmentDischargeView, TreatmentMoveView, DoctorPatientRoomView, GenerateTurnView, CallPatientView,
    CurrentCallsView, PrintTurnView, ClearCallView, AdminStatisticsView, RecentTransactionsView, AdminChartDataView,
    TreatmentPaymentReceiptView, PrintTreatmentReceiptView, PrintTreatmentRoomReceiptView, TreatmentRoomStatsView,
    AccountantDashboardView, OutcomeListCreateView, UserProfileAPIView,
    LabRegistrationListCreateAPIView, LabRegistrationDetailAPIView, PublicDoctorServiceAPI,
    PatientArchiveView, RoomHistoryView, PatientBalancesAPIView, PatientBillingAPIView, PatientBillingReceiptHTMLView,
    DischargeReceiptHTMLView, DischargeReceiptAPIView, PatientBalancesDataView,
    CallTurnView,  # ← use the view from apps.views
)

urlpatterns = [
    # --- Auth ---
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('verify-email/', VerifyEmailAPIView.as_view(), name='verify-email'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('reset-password/', PasswordResetConfirmView.as_view(), name='reset-password'),
    path('activate/<uidb64>/<token>', ActivateUserView.as_view(), name='activate'),

    # JWT refresh under /api/v1/ to match your frontend
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh_v1'),

    # --- User Info ---
    path('user-detail/', UserInfoListCreateAPIView.as_view(), name='user-detail'),

    # --- Patients ---
    path('register-patient/', PatientRegistrationAPIView.as_view(), name='register-patient'),
    path('patients/', PatientListAPIView.as_view(), name='patient-list'),
    path('patients/<int:pk>/', PatientDetailAPIView.as_view(), name='patient-detail'),
    path('recent-patients/', RecentPatientsView.as_view(), name='recent-patients'),
    path('recent-patients-by-days/', RecentPatientsByDaysView.as_view(), name='recent-patients-by-days'),

    # --- Doctors ---
    path('doctor-list/', DoctorListCreateAPIView.as_view(), name='doctor-list'),
    path('doctor-list/<int:pk>/', DoctorDetailView.as_view(), name='doctor-detail'),
    path('doctor-register/', DoctorRegistrationAPIView.as_view(), name='doctor-register'),

    # --- Appointments ---
    path('appointment/', AppointmentListCreateAPIView.as_view(), name='appointment'),
    path('my-appointments/', DoctorAppointmentListAPIView.as_view(), name='doctor-appointments'),
    path('my-appointments/<int:pk>/', DoctorAppointmentDetailAPIView.as_view(), name='doctor-appointment-detail'),

    # --- Services ---
    path('services/', ServiceListCreateAPIView.as_view(), name='service-list-create'),
    path('services/<int:pk>/', ServiceDetailAPIView.as_view(), name='service-detail'),

    # --- Payments ---
    path('payment-list/', PaymentListCreateAPIView.as_view(), name='payment-list'),
    path('treatment-room-payments/', TreatmentRoomPaymentsView.as_view(), name='treatment-room-payments'),
    path('doctor-payments/', DoctorPaymentsAPIView.as_view(), name='doctor-payments-summary'),
    path('doctor-payments/list/', DoctorPaymentListView.as_view(), name='doctor-payments-list'),

    # --- Treatment Rooms ---
    path('treatment-rooms/', TreatmentRoomListCreateAPIView.as_view(), name='treatment-room-list-create'),
    path('treatment-rooms/list/', TreatmentRoomList.as_view(), name='treatment-room-list-only'),
    path('treatment-rooms/<int:pk>/', TreatmentRoomDetailAPIView.as_view(), name='treatment-room-detail'),
    path('room-status/', RoomStatusAPIView.as_view(), name='room-status'),
    path('assign-room/', AssignRoomAPIView.as_view(), name='assign-room'),
    path('assign-patient-to-room/', AssignRoomAPIView.as_view(), name='assign-room-alias'),

    # --- Treatment Registration ---
    path('treatment-register/', TreatmentRegistrationListCreateAPIView.as_view(), name='treatment-register'),

    # --- Patient Results ---
    path('patient-results/', PatientResultListCreateAPIView.as_view(), name='patient-result-list'),
    path('patient-results/<int:pk>/', PatientResultDetailAPIView.as_view(), name='patient-result-detail'),

    # --- Cash Register ---
    path('cash-registration/patients/', CashRegistrationListView.as_view(), name='cash-registration-patients'),
    path('cash-register/patient/<int:patient_id>/', CashRegistrationView.as_view(), name='cash-register-by-patient'),
    path('cash-register/receipt/<int:pk>/', CashRegisterReceiptView.as_view(), name='cash-register-receipt'),
    # 🔧 FIXED: allow POST at /api/v1/cash-register/
    path('cash-register/', CashRegisterListCreateAPIView.as_view(), name='cash-register'),

    # --- Treatment Registration: Discharge & Move ---
    path('treatment-registrations/', TreatmentRegistrationListCreateView.as_view(), name='treatment-registration-list-create'),
    path("discharge-patient/<int:pk>/", TreatmentDischargeView.as_view(), name="discharge-patient"),
    path("move-patient-room/<int:pk>/", TreatmentMoveView.as_view(), name="move-patient"),
    path("doctor/my-patient-rooms/", DoctorPatientRoomView.as_view(), name="doctor-my-patient-rooms"),

    path("generate-turn/", GenerateTurnView.as_view(), name="generate-turn"),
    path("call-turn/", CallTurnView.as_view(), name="call-turn"),
    path("call-patient/<int:appointment_id>/", CallPatientView.as_view(), name="call-patient"),
    path("current-calls/", CurrentCallsView.as_view(), name="current-calls"),
    path("print-turn/", PrintTurnView.as_view()),
    path("clear-call/<int:appointment_id>/", ClearCallView.as_view()),

    path('admin-statistics/', AdminStatisticsView.as_view(), name='admin-statistics'),
    path('recent-transactions/', RecentTransactionsView.as_view(), name='recent-transactions'),
    path('admin-chart-data/', AdminChartDataView.as_view(), name='admin-chart-data'),
    path("treatment-room-payments/receipt/<int:id>/", TreatmentPaymentReceiptView.as_view()),
    path("treatment-room-payments/print/", PrintTreatmentReceiptView.as_view(), name="treatment-room-print"),
    path("treatment-room-payments/room-print/", PrintTreatmentRoomReceiptView.as_view(), name="treatment-room-direct-print"),
    path("admin/treatment-room-stats/", TreatmentRoomStatsView.as_view()),

    path("accounting-dashboard/", AccountantDashboardView.as_view(), name="accounting-dashboard"),
    path("incomes/", AccountantDashboardView.as_view(), name="income-list"),
    path("doctor-income/", AccountantDashboardView.as_view(), name="doctor-income"),
    path("accountant/outcomes/", OutcomeListCreateView.as_view(), name="outcome-list-create"),

    path('user-profile/', UserProfileAPIView.as_view(), name='user-profile'),
    path("receipt-details/<int:id>/", TreatmentPaymentReceiptView.as_view()),
    path("profile/", UserProfileAPIView.as_view(), name="profile"),

    path('lab-registrations/', LabRegistrationListCreateAPIView.as_view(), name='lab-registration-list-create'),
    path('lab-registrations/<int:pk>/', LabRegistrationDetailAPIView.as_view(), name='lab-registration-detail'),
    path("services/doctor/<int:doctor_id>/", PublicDoctorServiceAPI.as_view(), name="public-doctor-service-api"),

    path('patients/archive/', PatientArchiveView.as_view(), name='patient-archive'),
    path('room-history/', RoomHistoryView.as_view(), name='room-history'),

    path('treatment-registrations/<int:pk>/receipt/', DischargeReceiptHTMLView.as_view(), name='discharge-receipt'),
    path("discharge-patient/<int:pk>/receipt/", DischargeReceiptAPIView.as_view(), name="discharge-receipt-api"),

    # page
    path('patient-balances/', TemplateView.as_view(template_name='patient-balances.html'),
         name='patient-balances-page'),

    # --- APIs ---
    path('patient-billing/<int:patient_id>/', PatientBillingAPIView.as_view(), name='patient-billing-data'),
    path('patient-billing/<int:patient_id>/print/', PatientBillingReceiptHTMLView.as_view(), name='patient-billing-print'),

    # New balances data API
    path('patient-balances/data/', PatientBalancesDataView.as_view(), name='patient-balances-data'),
       path('unpaid-patients/', TemplateView.as_view(template_name='unpaid-patients.html'),
         name='unpaid-patients-page'),

    # API
    path('unpaid-patients/data/', UnpaidPatientsDataView.as_view(),
         name='unpaid-patients-data'),

    path('doctors/<int:pk>/reset-password/', AdminResetDoctorPasswordView.as_view(), name='doctor-reset-password'),

]
