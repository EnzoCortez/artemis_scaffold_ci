
import os
import sys
import traceback

# Add project root to path
sys.path.append(os.getcwd())

print(f"Python executable: {sys.executable}")
print(f"System path: {sys.path}")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')

print("Attempting to import wsgi application...")
try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    print("Success! loaded application.")
except Exception:
    print("Caught exception:")
    traceback.print_exc()
