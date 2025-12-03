from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from apps.models import Patient, TreatmentRegistration

class Command(BaseCommand):
    help = "Delete patients older than 1 year with no active registrations."

    def handle(self, *args, **opts):
        cutoff = now() - timedelta(days=365)
        qs = Patient.objects.filter(created_at__lt=cutoff)
        # keep anyone who still has an active registration
        ids_with_active = TreatmentRegistration.objects.filter(
            patient_id__in=qs.values_list('id', flat=True),
            discharged_at__isnull=True
        ).values_list('patient_id', flat=True).distinct()

        victims = qs.exclude(id__in=list(ids_with_active))
        count = victims.count()
        victims.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} old patient(s)."))
