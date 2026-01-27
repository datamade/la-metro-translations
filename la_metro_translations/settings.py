"""
Django settings for la_metro_translations project.

For more information on this file, see
https://docs.djangoproject.com/en/stable/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/stable/ref/settings/
"""

import os

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from la_metro_translations.logging import before_send

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Retrieve the secret key from the DJANGO_SECRET_KEY environment variable
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Set the DJANGO_DEBUG environment variable to False to disable debug mode
DEBUG = False if os.getenv("DJANGO_DEBUG", True) == "False" else True

# Define DJANGO_ALLOWED_HOSTS as a comma-separated list of valid hosts,
# e.g. localhost,127.0.0.1,.herokuapp.com
allowed_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", [])
ALLOWED_HOSTS = allowed_hosts.split(",") if allowed_hosts else []

# Adding localhost by default allows for wagtail previews to work when editing pages
ALLOWED_HOSTS.append("localhost")


# Configure Sentry for error logging
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        before_send=before_send,
        integrations=[DjangoIntegration()],
    )

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.simple_translation",
    "wagtail.contrib.table_block",
    "wagtail.locales",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "webpack_loader",
    "la_metro_translations",
    "storages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.cache.UpdateCacheMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.cache.FetchFromCacheMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

SERIALIZATION_MODULES = {
    "geojson": "django.contrib.gis.serializers.geojson",
}

ROOT_URLCONF = "la_metro_translations.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": ["templates/"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "la_metro_translations.wsgi.application"

# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases

DATABASES = {}

DATABASES["default"] = dj_database_url.parse(
    os.getenv(
        "DATABASE_URL",
        "postgres://postgres:postgres@postgres:5432/la_metro_translations",
    ),
    conn_max_age=600,
    ssl_require=True if os.getenv("POSTGRES_REQUIRE_SSL") else False,
    engine="django.db.backends.postgresql",
)

# Caching
# https://docs.djangoproject.com/en/stable/topics/cache/

cache_backend = "dummy.DummyCache" if DEBUG is True else "db.DatabaseCache"
CACHES = {
    "default": {
        "BACKEND": f"django.core.cache.backends.{cache_backend}",
        "LOCATION": "site_cache",
        "TIMEOUT": 30,
    }
}

# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = "/static"
STATICFILES_DIRS = (os.path.join(BASE_DIR, "assets"),)
STATICFILES_STORAGE = os.getenv(
    "DJANGO_STATICFILES_STORAGE",
    "whitenoise.storage.CompressedManifestStaticFilesStorage",
)
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": not DEBUG,
        "STATS_FILE": os.path.join(BASE_DIR, "webpack-stats.json"),
        "POLL_INTERVAL": not DEBUG,
        "IGNORE": [r".+\.hot-update.js", r".+\.map"],
    }
}

MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

try:
    AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]

except KeyError:
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    print("AWS config not found, defaulting to local storage")

else:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

STORAGES = {
    "default": {
        "BACKEND": DEFAULT_FILE_STORAGE,
    },
    "staticfiles": {
        "BACKEND": STATICFILES_STORAGE,
    },
}


WAGTAIL_SITE_NAME = "La Metro Translation Suite"

# Disable moderation
WAGTAIL_MODERATION_ENABLED = False
# Disable commenting
WAGTAILADMIN_COMMENTS_ENABLED = False
WAGTAIL_ENABLE_UPDATE_CHECK = False

WAGTAILEMBEDS_RESPONSIVE_HTML = True


# Enforce SSL in production
if DEBUG is False:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True

# Derive allowed origins from configured hosts
CSRF_TRUSTED_ORIGINS = []

for host in ALLOWED_HOSTS:
    if host.startswith("."):
        origin = f"https://*{host}"
    else:
        origin = f"https://{host}"

    CSRF_TRUSTED_ORIGINS.append(origin)

try:
    MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]
except KeyError:
    print("Please enter a Mistral api key in order to enable OCR and translation.")
