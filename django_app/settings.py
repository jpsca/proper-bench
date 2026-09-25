"""The Django reference app: the same three routes over the same SQLite file."""
from pathlib import Path

HERE = Path(__file__).parent
SECRET_KEY = "bench" * 16
DEBUG = False
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = ["django_app"]
# The usual production stack: what a real Django site runs on every request.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
ROOT_URLCONF = "django_app.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [HERE / "templates"],
    "OPTIONS": {"autoescape": True},
}]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": HERE.parent / "app" / "fortunes.db",
        "CONN_MAX_AGE": None,  # keep the connection, like the others do
        "OPTIONS": {"init_command": "PRAGMA journal_mode=wal; PRAGMA cache_size=-64000;"},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
USE_TZ = False
LOGGING_CONFIG = None
