#importacoes
from django.apps import AppConfig


#-------------------------------------------------------------------------------------

#configuracao da aplicacao
class AplicacaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicacao"

    label = "elo"
    verbose_name = "Aplicação ELO"

    #-------------------------------------------------------------------------------------

    #carregamento dos sinais
    def ready(self):
        from . import auditoria  # Registra os sinais de autenticação do Django.
#-------------------------------------------------------------------------------------
