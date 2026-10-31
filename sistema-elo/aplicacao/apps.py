
from django.apps import AppConfig


class AplicacaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicacao"

    label = "elo"
    verbose_name = "Aplicação ELO"


    def ready(self):
        from . import auditoria

