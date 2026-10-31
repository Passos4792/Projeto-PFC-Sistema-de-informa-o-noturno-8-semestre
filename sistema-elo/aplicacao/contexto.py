#importacoes
from .documentos_legais import DATA_VIGENCIA, VERSAO_PRIVACIDADE, VERSAO_TERMOS


#-------------------------------------------------------------------------------------

#documentos legais disponiveis nas telas
def documentos_legais(request):
    """Disponibiliza as versões vigentes para os templates públicos e autenticados."""
    perfil = getattr(request, 'perfil_elo', None)
    pendentes = 0
    if perfil and perfil.tipo_perfil == 'PROFESSOR':
        from .api import solicitacoes_permitidas
        pendentes = solicitacoes_permitidas(perfil).filter(situacao='PENDENTE').count()
    return {
        'aprovacoes_pendentes': pendentes,
        'versao_termos': VERSAO_TERMOS,
        'versao_privacidade': VERSAO_PRIVACIDADE,
        'data_vigencia': DATA_VIGENCIA,
    }
