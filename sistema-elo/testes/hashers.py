from django.contrib.auth.hashers import PBKDF2PasswordHasher


class PBKDF2Rapido(PBKDF2PasswordHasher):
    iterations = 1000
