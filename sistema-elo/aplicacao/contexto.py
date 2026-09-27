#importacoes
from .documentos_legais import DATA_VIGENCIA, VERSAO_PRIVACIDADE, VERSAO_TERMOS


#-------------------------------------------------------------------------------------

#documentos legais disponiveis nas telas
def documentos_legais(request):
    """Disponibiliza as versões vigentes para os templates públicos e autenticados."""
    return {
        'versao_termos': VERSAO_TERMOS,
        'versao_privacidade': VERSAO_PRIVACIDADE,
        'data_vigencia': DATA_VIGENCIA,
    }
