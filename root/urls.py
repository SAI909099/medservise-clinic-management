from django.views.generic import TemplateView
from django.views.generic import TemplateView  # <-- add this

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.frontend_views import IndexView, ArchiveView, CashRegisterView, \
    DoctorView, DoctorAddView, DoctorPatientRoomsView, DoctorPaymentsView, PatientDetailView, PatientSelectionView, \
    PatientsView, PaymentsView, PriceManagementView, RegisterView, RegistrationView, RoomsView, ServicesView, \
    TreatmentView, TreatmentRegistrationView, TreatmentRoomManagementView, TurnDisplayView, TreatmentRoomPaymentsView, \
    AdminDashboardView , AccountantDashboardtView , PublicDoctorServicePageView, DoctorsListView, PatientBillingView
urlpatterns = [
    path('api/v1/' , include('apps.urls')),
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
                  # Optional UI:
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('', IndexView.as_view(), name='index'),
    path('accounting-dashboard/', AccountantDashboardtView.as_view(), name='accountant-dashboard'), 
    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('archive/', ArchiveView.as_view(), name='archive'),
    path('cash-register/', CashRegisterView.as_view(), name='cash-register'),
    path('doctor/', DoctorView.as_view(), name='doctor'),
    path('doctor-add/', DoctorAddView.as_view(), name='doctor-add'),
    path('doctor-patient-rooms/', DoctorPatientRoomsView.as_view(), name='doctor-patient-rooms'),
    path('doctor-payments/', DoctorPaymentsView.as_view(), name='doctor-payments'),
    path('doctor/patient-detail/', PatientDetailView.as_view(), name='doctor-patient-detail'),
    path('patient-selection/', PatientSelectionView.as_view(), name='patient-selection'),
    path('patients/', PatientsView.as_view(), name='patients'),
    path('payments/', PaymentsView.as_view(), name='payments'),
    path('price-management/', PriceManagementView.as_view(), name='price-management'),
    path('register/', RegisterView.as_view(), name='register'),
    path('registration/', RegistrationView.as_view(), name='registration'),
    path('rooms/', RoomsView.as_view(), name='rooms'),
    path('services/', ServicesView.as_view(), name='services'),
    path('doctors/', DoctorsListView.as_view(), name='doctors'),
    path('patient-billing/<int:patient_id>/', PatientBillingView.as_view(), name='patient-billing'),
    path('treatment/', TreatmentView.as_view(), name='treatment'),
    path('treatment-registration/', TreatmentRegistrationView.as_view(), name='treatment-registration'),
    path('treatment-room-management/', TreatmentRoomManagementView.as_view(),
       name='treatment-room-management'),
    path('treatment-room-payments/', TreatmentRoomPaymentsView.as_view(), name='treatment-room-payments'),
    path('turn-display/', TurnDisplayView.as_view(), name='turn-display'),
    path('print_receipt.html', TemplateView.as_view(template_name='print_receipt.html')),

    path("services/doctor/<int:doctor_id>/", PublicDoctorServicePageView.as_view(), name="public-doctor-service-page"),
    path('patient-balances/', TemplateView.as_view(template_name='patient-balances.html'), name='patient-balances'), 

    path( "doctor/service-worklist/", TemplateView.as_view(template_name="doctor-service-worklist.html"),name="doctor_service_worklist",),
    path('list_unpaid-patients/', TemplateView.as_view(template_name='list_unpaid-patients.html'), name='list_unpaid-patients'),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL,
                                                                                         document_root=settings.STATIC_ROOT)
from django.views.generic import TemplateView
urlpatterns += [
    path('patient-billing/', TemplateView.as_view(template_name='patient-billing.html')),
]
