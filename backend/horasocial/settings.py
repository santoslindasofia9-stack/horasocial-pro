"""
Configuracion Django para HORASOCIAL PRO - Modulo de Docentes.

Proyecto: horasocial
App principal: docentes

Base de datos: MySQL 8.4 (Laragon / XAMPP) en 127.0.0.1:3306
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-pu*4bbt%sx=tw^n9rj@x--(vk4=n+ssm_5z)r$$6oyecjd4hfc',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'docentes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'horasocial.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'horasocial.wsgi.application'
ASGI_APPLICATION = 'horasocial.asgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases
#
# Conexion al MySQL de Laragon. Requiere estar corriendo el MySQL en el
# puerto 3306 antes de ejecutar migrate (Laragon > Start All).

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'horas_sociales_docentes'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'TEST': {
            'CHARSET': 'utf8mb4',
            'COLLATION': 'utf8mb4_unicode_ci',
        },
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


# Autenticacion
# Usamos un modelo de usuario propio (docentes.Usuario) porque el login es
# por CORREO electronico y necesitamos los campos del modulo (rol, grado,
# intentos_fallidos, estado_cuenta).

AUTH_USER_MODEL = 'docentes.Usuario'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = 'docentes:login'
LOGIN_REDIRECT_URL = 'docentes:dashboard'
LOGOUT_REDIRECT_URL = 'docentes:login'

# A donde vuelve el formulario decorado de login (server.js en :3000) despues
# de autenticar contra MySQL. Si el frontend se publica en otro host o puerto,
# cambiar SOLO esta URL. Con cadena vacia, el login vuelve al panel de Django.
DASHBOARD_DOCENTE_URL = os.environ.get(
    'DASHBOARD_DOCENTE_URL',
    'http://127.0.0.1:3000/profesor/dashboard',
)

# A donde vuelve el formulario decorado cuando el login FALLA. Sin esto, un
# intento fallido rebotaba a las pantallas planas de Django y el docente
# terminaba en una pagina que ofrece "olvide mi contrasena" en vez de volver
# al formulario que estaba usando. Con cadena vacia, vuelve al login de Django.
LOGIN_DOCENTE_URL = os.environ.get(
    'LOGIN_DOCENTE_URL',
    'http://127.0.0.1:3000/profesor/login',
)


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Control de intentos fallidos (usa Usuario.intentos_fallidos / estado_cuenta)
MAX_INTENTOS_FALLIDOS = 5


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'es-co'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]


# Email
# En desarrollo los correos se imprimen en la consola del servidor.
# Nota: Django 6.1 no permite EMAIL_BACKEND junto a MAILERS.

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

DEFAULT_FROM_EMAIL = 'no-reply@horasocial.local'
