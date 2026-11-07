
from .documentos_legais import DATA_VIGENCIA, VERSAO_PRIVACIDADE, VERSAO_TERMOS


def documentos_legais(request):
    """Disponibiliza as versões vigentes para os templates públicos e autenticados."""
    perfil = getattr(request, 'perfil_elo', None)
    pendentes = 0
    pedidos_senha_pendentes = 0
    if perfil and perfil.tipo_perfil == 'PROFESSOR':
        from .api import solicitacoes_permitidas
        pendentes = solicitacoes_permitidas(perfil).filter(situacao='PENDENTE').count()
        from .models import SolicitacaoSenha
        pedidos_senha_pendentes = SolicitacaoSenha.objects.filter(
            professor__usuario=perfil, situacao=SolicitacaoSenha.Situacao.PENDENTE).count()
    return {
        'aprovacoes_pendentes': pendentes,
        'pedidos_senha_pendentes': pedidos_senha_pendentes,
        'versao_termos': VERSAO_TERMOS,
        'versao_privacidade': VERSAO_PRIVACIDADE,
        'data_vigencia': DATA_VIGENCIA,
    }
