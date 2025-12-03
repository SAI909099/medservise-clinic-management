from django.conf import settings

def brand(request):
    # Expose a brand name to templates. Safe default if not set in settings.
    return {"BRAND_NAME": getattr(settings, "BRAND_NAME", "Controllab")}
