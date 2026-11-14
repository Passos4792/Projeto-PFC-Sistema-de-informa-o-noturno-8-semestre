import os
from pathlib import Path
import warnings
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


#leitura do .env
BASE_DIR = Path(__file__).resolve().parent.parent
ARQUIVO_ENV = Path(os.getenv("ELO_ARQUIVO_ENV") or (BASE_DIR.parent / ".env")).expanduser()
load_dotenv(ARQUIVO_ENV, override=False)


def env_bool(nome, padrao=False):
    valor = os.getenv(nome, "").strip().lower()
    if not valor:
        return padrao
    return valor in ("1", "true", "sim", "yes", "on")


def env_lista(nome, padrao=""):
    return [item.strip() for item in os.getenv(nome, padrao).split(",") if item.strip()]


#ambiente e chave secreta
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env_lista("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "").strip()
_CHAVES_DE_EXEMPLO = {"troque-esta-chave-em-producao", "SUBSTITUA_POR_CHAVE_ALEATORIA_FORTE"}
_COMO_GERAR = 'Gere uma com: python -c "import secrets; print(secrets.token_urlsafe(64))"'

if not SECRET_KEY:
    raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY no arquivo .env. " + _COMO_GERAR)

if SECRET_KEY in _CHAVES_DE_EXEMPLO or len(SECRET_KEY) < 50:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY é a chave de exemplo ou tem menos de 50 caracteres. " + _COMO_GERAR)
    warnings.warn("DJANGO_SECRET_KEY fraca: aceitável apenas em desenvolvimento. " + _COMO_GERAR)


#aplicativos e middlewares
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "aplicacao.apps.AplicacaoConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "aplicacao.servicos.politica_conteudo.PoliticaConteudo",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "aplicacao.servicos.acesso.ControleAcesso",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "configuracao.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "aplicacao.servicos.contexto.documentos_legais",
            ],
        },
    },
]

WSGI_APPLICATION = "configuracao.wsgi.application"
ASGI_APPLICATION = "configuracao.asgi.application"


#banco de dados
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "elo_db"),
        "USER": os.getenv("DB_USER", "root"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


#senhas e login
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = ['aplicacao.servicos.acesso.BackendElo']
LOGIN_URL = 'login'
LOGIN_MAX_FALHAS = 5
LOGIN_MAX_FALHAS_USUARIO = 30
LOGIN_MAX_FALHAS_IP = 100
LOGIN_JANELA_SEGUNDOS = 15 * 60
LOGIN_BLOQUEIO_SEGUNDOS = 5 * 60
ELO_2FA_ATIVO = True
ELO_2FA_DISPOSITIVO_DIAS = 30
LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = 'login'


#sessao e https
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
_HOSTS_LOCAIS = {"127.0.0.1", "localhost", "[::1]"}
_SOMENTE_LOCAL = set(ALLOWED_HOSTS) <= _HOSTS_LOCAIS
USAR_HTTPS = env_bool("DJANGO_HTTPS", padrao=not DEBUG and not _SOMENTE_LOCAL)
SESSION_COOKIE_SECURE = USAR_HTTPS
CSRF_COOKIE_SECURE = USAR_HTTPS
SECURE_SSL_REDIRECT = USAR_HTTPS
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS") or 0) if USAR_HTTPS else 0
CONFIAR_PROXY = env_bool("DJANGO_PROXY_HTTPS")

if CONFIAR_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = env_lista("DJANGO_CSRF_TRUSTED_ORIGINS")


#idioma e fuso horario
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True


#arquivos estaticos e privados
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_ROOT = BASE_DIR / 'arquivos_privados'


#api
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'user': os.getenv('DJANGO_API_LIMITE', '120/min')},
}


#registro de erros
_ARQUIVO_LOG = os.getenv("DJANGO_LOG_ARQUIVO", "").strip()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simples": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simples"},
        **({"arquivo": {"class": "logging.handlers.RotatingFileHandler", "filename": _ARQUIVO_LOG,
                        "maxBytes": 5 * 1024 * 1024, "backupCount": 3, "encoding": "utf-8",
                        "formatter": "simples"}} if _ARQUIVO_LOG else {}),
    },
    "loggers": {
        "django": {
            "handlers": ["console"] + (["arquivo"] if _ARQUIVO_LOG else []),
            "level": os.getenv("DJANGO_LOG_NIVEL", "ERROR"),
        },
    },
}


#google agenda
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:8000/google/retorno/')
GOOGLE_TOKEN_ENCRYPTION_KEY = os.getenv('GOOGLE_TOKEN_ENCRYPTION_KEY', '')


#verificacao das configuracoes de producao
def _erros_de_producao():
    erros = []
    if not DATABASES["default"]["PASSWORD"]:
        erros.append("DB_PASSWORD está vazio: o banco de produção precisa de senha.")
    if DATABASES["default"]["USER"] == "root":
        erros.append("DB_USER=root: use um usuário próprio do banco, sem privilégios de administrador.")
    if not USAR_HTTPS and not _SOMENTE_LOCAL:
        erros.append("DJANGO_HTTPS está desligado em um endereço público.")
    if GOOGLE_TOKEN_ENCRYPTION_KEY:
        try:
            from cryptography.fernet import Fernet
            Fernet(GOOGLE_TOKEN_ENCRYPTION_KEY.encode())
        except (ValueError, TypeError):
            erros.append("GOOGLE_TOKEN_ENCRYPTION_KEY inválida. Gere com: "
                         'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
        if GOOGLE_TOKEN_ENCRYPTION_KEY == SECRET_KEY:
            erros.append("GOOGLE_TOKEN_ENCRYPTION_KEY não pode ser igual à DJANGO_SECRET_KEY.")
    return erros


if not DEBUG and os.getenv("DJANGO_SETTINGS_MODULE") != "testes.configuracao":
    _erros = _erros_de_producao()
    if _erros:
        raise ImproperlyConfigured("Configuração insegura para produção:\n- " + "\n- ".join(_erros))
