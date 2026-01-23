import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'changeme')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'ioc_manager.apps.IocManagerConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware", # Added whitenoise
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'artemis_project.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'ioc_manager' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': ['django.template.context_processors.debug',
                                           'django.template.context_processors.request',
                                           'django.contrib.auth.context_processors.auth',
                                           'django.contrib.messages.context_processors.messages']},
    }
]
WSGI_APPLICATION = 'artemis_project.wsgi.application'


# settings.py
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM # Option 3: AES-GCM

# Database Decryption Logic (AES-GCM Mode)
try:
    _db_key_b64 = os.environ.get('DB_ENCRYPTION_KEY')
    _db_payload_b64 = os.environ.get('DB_PASSWORD')
    
    if _db_key_b64 and _db_payload_b64:
        # 1. Decode Base64
        _key = base64.b64decode(_db_key_b64)
        _payload = base64.b64decode(_db_payload_b64)
        
        # 2. Extract Nonce (First 12 bytes for GCM)
        _nonce = _payload[:12]
        _ciphertext = _payload[12:]
        
        # 3. Decrypt
        aesgcm = AESGCM(_key)
        # AESGCM.decrypt validates the tag automatically (included in ciphertext end)
        _decrypted_pwd = aesgcm.decrypt(_nonce, _ciphertext, associated_data=None).decode('utf-8')
    else:
        # _decrypted_pwd = os.environ.get('DB_PASSWORD_RAW') # Fallback commented out for production safety
        _decrypted_pwd = None
except Exception as e:
    print(f"CRITICAL SECURITY ERROR: Could not decrypt database password (AES-GCM): {e}")
    _decrypted_pwd = None

DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': os.environ.get('DB_NAME', 'Artemis_db'),
        'USER': os.environ.get('DB_USER', 'Artemis'),
        'PASSWORD': _decrypted_pwd,
        'HOST': os.environ.get('DB_HOST', 'DBSRV7'),
        'PORT': os.environ.get('DB_PORT', ''),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
        },
    }
}


STATIC_URL = '/static/'
STATIC_ROOT= BASE_DIR /"staticfiles"

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'},},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
REST_FRAMEWORK = {'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],}


