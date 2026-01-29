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

if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False # Dejar en False si el IIS/Proxy hace la terminación SSL
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# settings.py
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM # Option 3: AES-GCM

# Database Decryption Logic (AES-GCM Mode)
try:
    _db_key_b64 = os.environ.get('DB_ENCRYPTION_KEY')
    _db_user_payload_b64 = os.environ.get('DB_USER_ENCRYPTED')
    _db_pwd_payload_b64 = os.environ.get('DB_PASSWORD_ENCRYPTED')
    
    _decrypted_user = None
    _decrypted_pwd = None

    if _db_key_b64:
        _key = base64.b64decode(_db_key_b64)
        aesgcm = AESGCM(_key)

        # Decrypt User
        if _db_user_payload_b64:
            _payload_u = base64.b64decode(_db_user_payload_b64)
            _decrypted_user = aesgcm.decrypt(_payload_u[:12], _payload_u[12:], associated_data=None).decode('utf-8')
        
        # Decrypt Password
        if _db_pwd_payload_b64:
            _payload_p = base64.b64decode(_db_pwd_payload_b64)
            _decrypted_pwd = aesgcm.decrypt(_payload_p[:12], _payload_p[12:], associated_data=None).decode('utf-8')

except Exception as e:
    print(f"CRITICAL SECURITY ERROR: Could not decrypt database credentials (AES-GCM): {e}")

DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': os.environ.get('DB_NAME', 'Artemis_db'),
        'USER': _decrypted_user or os.environ.get('DB_USER', 'Artemis'), 
        'PASSWORD': _decrypted_pwd or os.environ.get('DB_PASSWORD_RAW'),
        'HOST': os.environ.get('DB_HOST', 'DBSRV7'),
        'PORT': os.environ.get('DB_PORT', ''),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
        },
    }
}

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


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


