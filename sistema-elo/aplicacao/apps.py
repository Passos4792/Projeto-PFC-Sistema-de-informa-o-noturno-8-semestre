from django.apps import AppConfig


class AplicacaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicacao"

    label = "elo"
    verbose_name = "Aplicação ELO"

    def ready(self):
        from aplicacao.servicos import auditoria
        from aplicacao.servicos import sinais_calendario
