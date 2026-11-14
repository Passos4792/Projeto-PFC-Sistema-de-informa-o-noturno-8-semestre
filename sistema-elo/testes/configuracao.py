import os
from cryptography.fernet import Fernet
os.environ.setdefault('DJANGO_SECRET_KEY', 'chave-descartavel-exclusiva-da-suite-automatizada-elo')
from configuracao.settings import *


if os.environ.get('ELO_TEST_MYSQL') == '1':
    DATABASES['default']['TEST'] = {'NAME': 'test_elo_atualizado'}
    if DATABASES['default']['NAME'] == 'test_elo_atualizado':
        raise RuntimeError('O banco normal não pode ter o nome reservado aos testes.')
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}


SECRET_KEY = 'chave-descartavel-exclusiva-da-suite-automatizada-elo'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
GOOGLE_CLIENT_ID = 'cliente-ficticio.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = 'segredo-ficticio'
GOOGLE_REDIRECT_URI = 'http://testserver/google/retorno/'
GOOGLE_TOKEN_ENCRYPTION_KEY = Fernet.generate_key().decode()
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
TEST_RUNNER = 'testes.runner.ExecutorIsolado'


USAR_HTTPS = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
CONFIAR_PROXY = False
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {'user': '100000/min'}}
LOGGING['loggers']['django']['level'] = 'CRITICAL'

PASSWORD_HASHERS = ["testes.hashers.PBKDF2Rapido"]

ELO_2FA_ATIVO = False
