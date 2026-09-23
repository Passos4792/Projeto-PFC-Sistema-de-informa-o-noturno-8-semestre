#importacoes
import os
from pathlib import Path

from dotenv import load_dotenv


#-------------------------------------------------------------------------------------

#caminho base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")

#-------------------------------------------------------------------------------------

#seguranca e ambiente
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "elo-chave-local-de-desenvolvimento")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

#-------------------------------------------------------------------------------------

#aplicacoes instaladas
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "aplicacao.apps.AplicacaoConfig",
]

#-------------------------------------------------------------------------------------

#processamento das requisicoes
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "aplicacao.acesso.ControleAcesso",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

#-------------------------------------------------------------------------------------

#rotas do projeto
ROOT_URLCONF = "configuracao.urls"

#-------------------------------------------------------------------------------------

#configuracao das telas
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
            ],
        },
    },
]

#-------------------------------------------------------------------------------------

#inicializacao do servidor
WSGI_APPLICATION = "configuracao.wsgi.application"
ASGI_APPLICATION = "configuracao.asgi.application"

#-------------------------------------------------------------------------------------

#conexao com o banco de dados
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

#-------------------------------------------------------------------------------------

#validacao das senhas
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

#-------------------------------------------------------------------------------------

#autenticacao
AUTHENTICATION_BACKENDS = ['aplicacao.acesso.BackendElo']

#-------------------------------------------------------------------------------------

#login e limites de tentativas
LOGIN_URL = 'login'
LOGIN_MAX_FALHAS = 5
LOGIN_MAX_FALHAS_IP = 20
LOGIN_JANELA_SEGUNDOS = 15 * 60
LOGIN_BLOQUEIO_SEGUNDOS = 5 * 60
LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = 'login'

#-------------------------------------------------------------------------------------

#configuracao da sessao
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

#-------------------------------------------------------------------------------------

#idioma e horario
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

#-------------------------------------------------------------------------------------

#arquivos de estilo, imagens e scripts
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

#-------------------------------------------------------------------------------------

#identificadores dos registros
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
#-------------------------------------------------------------------------------------
