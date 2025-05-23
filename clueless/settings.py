"""
Django settings for the Clue-Less project, a multiplayer game with WebSocket support.

Generated by 'django-admin startproject' using Django 5.1.7. This file configures the
project's core settings, including database, middleware, session management, static
files, and ASGI/WebSocket integration. For detailed documentation, see:
- https://docs.djangoproject.com/en/5.1/topics/settings/
- https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/
- https://docs.djangoproject.com/en/5.1/howto/static-files/
- https://docs.djangoproject.com/en/5.1/topics/i18n/
"""

# Production Settings
PRODUCTION = True
PRODUCTION_NGROK_APP = 'cba9-118-221-199-11.ngrok-free.app'  # Add proper ngrok app in '*.ngrok-free.app'
PRODUCTION_NGROK_URL = 'https://' + PRODUCTION_NGROK_APP


from pathlib import Path
import os

# Define the base directory of the project for file path resolution
# BASE_DIR points to the parent directory of this settings.py file, used for paths
# like database location and static file directories
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: The secret key is critical for cryptographic signing
# In production, replace this with a secure, unique value stored in an environment
# variable (e.g., via dotenv or secrets management) to prevent security risks
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#secret-key
SECRET_KEY = 'django-insecure-n2p=z$%=_2l4&_w&tm9%^a$d(f+^sdxebwdrkj0d5y5!^o9e=_'

# Enable debug mode for development to show detailed error pages and logs
# SECURITY WARNING: Set DEBUG = False in production to prevent exposing sensitive
# information. Ensure proper error handling and logging are configured
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#debug
DEBUG = True

# Specify allowed hosts for the application to prevent Host header attacks
# Empty list is safe for local development (127.0.0.1, localhost)
# In production, add your domain (e.g., ['example.com', 'www.example.com'])
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#allowed-hosts
if PRODUCTION:
    # ALLOWED_HOSTS = ['127.0.0.1', '*.ngrok-free.app']  # Add proper ngrok app in '*.ngrok-free.app'
    ALLOWED_HOSTS = ['127.0.0.1', PRODUCTION_NGROK_APP]
else:
    # Localhost testing:
    ALLOWED_HOSTS = []

# List of Django applications installed in the project
# Includes core Django apps for admin, authentication, sessions, and messages,
# plus Channels for WebSocket support and the custom 'game' app for Clue-Less logic
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#installed-apps
INSTALLED_APPS = [
    'django.contrib.admin',           # Admin interface for managing models
    'django.contrib.auth',            # Authentication system for user management
    'django.contrib.contenttypes',    # Framework for content type relationships
    'django.contrib.sessions',        # Session management for user state
    'django.contrib.messages',        # Messaging framework for user notifications
    'daphne',                         # ASGI server for handling WebSocket requests
    'django.contrib.staticfiles',     # Static file handling for CSS, JS, images
    'channels',                       # Channels framework for WebSocket support
    'game',                           # Custom app containing game logic and views
    'chatting',                       # Custom app containing chatting logic in lobby
]

# Middleware stack defining request/response processing order
# Each middleware handles specific functionality, such as security, sessions, and
# authentication. The order is critical: AuthenticationMiddleware must precede
# SessionValidationMiddleware to set request.user, avoiding AttributeError
# See: https://docs.djangoproject.com/en/5.1/topics/http/middleware/
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',         # Security enhancements (e.g., HTTPS, HSTS)
    'django.contrib.sessions.middleware.SessionMiddleware',  # Manages session creation and cookies
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # Sets request.user for authenticated users
    'game.middleware.SessionValidationMiddleware',           # Custom middleware for session cookie validation
    'django.middleware.common.CommonMiddleware',             # Common request/response handling (e.g., URL normalization)
    'django.middleware.csrf.CsrfViewMiddleware',             # CSRF protection for POST requests
    'django.contrib.messages.middleware.MessageMiddleware',  # Handles user messages
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # Prevents clickjacking via X-Frame-Options
]

# URL configuration entry point
# Points to the project's URL patterns defined in clueless/urls.py
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#root-urlconf
ROOT_URLCONF = 'clueless.urls'

# Template configuration for rendering HTML views
# Uses Django's template engine with app directories enabled and context processors
# for injecting common variables (e.g., request.user, CSRF token) into templates
# See: https://docs.djangoproject.com/en/5.1/topics/templates/
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],  # No custom template directories; uses app templates
        'APP_DIRS': True,  # Automatically loads templates from app directories (e.g., game/templates)
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',       # Adds debug info to templates (if DEBUG=True)
                'django.template.context_processors.request',     # Adds request object to template context
                'django.contrib.auth.context_processors.auth',   # Adds request.user and authentication status
                'django.contrib.messages.context_processors.messages',  # Adds user messages to templates
            ],
        },
    },
]

# WSGI and ASGI application settings for HTTP and WebSocket handling
# WSGI_APPLICATION is used for standard HTTP requests (served by Django)
# ASGI_APPLICATION is used for WebSocket requests (served by Daphne via Channels)
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#wsgi-application
# See: https://channels.readthedocs.io/en/stable/topics/configuration.html
WSGI_APPLICATION = 'clueless.wsgi.application'
ASGI_APPLICATION = 'clueless.asgi.application'

# Configure Redis as the channel layer backend for WebSocket communication
# Channels uses Redis to manage WebSocket message passing between clients
# Ensure Redis is running locally on port 6379 (default configuration)
# In production, configure a secure Redis instance with authentication
# See: https://channels.readthedocs.io/en/stable/topics/channel-layers.html
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],  # Local Redis instance
        },
    },
}

# Session management configuration for maintaining user state
# Uses database-backed sessions with a 30-minute timeout and strict cookie settings
# Clear the django_session table if session issues occur (e.g., overwrites):
#   python manage.py dbshell
#   sqlite> DELETE FROM django_session;
# In production, consider cached_db for performance and enable SESSION_COOKIE_SECURE
# See: https://docs.djangoproject.com/en/5.1/topics/http/sessions/
SESSION_COOKIE_NAME = 'sessionid'  # Name of the session cookie
SESSION_COOKIE_HTTPONLY = True     # Prevent JavaScript access to session cookies
SESSION_COOKIE_AGE = 1800         # 30-minute session duration
SESSION_COOKIE_PATH = '/'         # Cookie applies to all paths
if PRODUCTION:
    SESSION_COOKIE_SAMESITE = 'Strict'  # Prevent cross-site cookie sharing
    SESSION_COOKIE_SECURE = True  # Require HTTPS for cookies
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'  # Use Redis caching
    CSRF_TRUSTED_ORIGINS = [PRODUCTION_NGROK_URL]  # Ensure CSRF_TRUSTED_ORIGINS includes the exact URL
else:
    # Localhost testing:
    SESSION_COOKIE_SAMESITE = 'Strict'  # Prevent cross-site cookie sharing
    SESSION_COOKIE_SECURE = False      # Disable secure flag for local HTTP development
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Store sessions in database

# Database configuration using SQLite for local development
# SQLite is suitable for development but consider PostgreSQL/MySQL for production
# due to better concurrency and performance
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # SQLite database file in project root
    }
}

# Password validation rules for user authentication
# Enforces strong passwords to enhance security
# Customize validators based on your security requirements
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        # Prevents passwords too similar to user attributes (e.g., username)
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        # Enforces minimum password length (default: 8 characters)
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
        # Blocks commonly used passwords
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
        # Prevents entirely numeric passwords
    },
]

# Internationalization and localization settings
# Configures language, time zone, and translation support
# Suitable for English-speaking users; adjust for multi-language support
# See: https://docs.djangoproject.com/en/5.1/topics/i18n/
LANGUAGE_CODE = 'en-us'  # Default language for the application
TIME_ZONE = 'UTC'        # Time zone for date/time handling
USE_I18N = True          # Enable internationalization for translations
USE_TZ = True            # Enable timezone-aware datetimes

# Static file configuration for serving CSS, JavaScript, and images
# STATIC_URL defines the URL prefix for static assets
# STATICFILES_DIRS specifies additional directories for static files
# In production, run `python manage.py collectstatic` to gather static files
# See: https://docs.djangoproject.com/en/5.1/howto/static-files/
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",  # Directory for custom static files (e.g., images)
]


# Default primary key field type for models
# AutoField is suitable for most use cases; BigAutoField supports larger ID ranges
# See: https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'