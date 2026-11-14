from aplicacao.servicos.acesso import alunos_atividades_visiveis, alunos_com_funcao
from aplicacao.views.api import solicitacoes_permitidas
from aplicacao.views.senhas import pedidos_permitidos
from aplicacao.servicos.documentos_legais import DATA_VIGENCIA, VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.models import Professor, SolicitacaoSenha, ConexaoGoogle


def documentos_legais(request):
    perfil = getattr(request, 'perfil_elo', None)
    pendentes = 0
    pedidos_senha_pendentes = 0
    if perfil and perfil.tipo_perfil == 'PROFESSOR':
        pendentes = solicitacoes_permitidas(perfil).filter(situacao='PENDENTE').count()
        pedidos_senha_pendentes = pedidos_permitidos(perfil).filter(
            situacao=SolicitacaoSenha.Situacao.PENDENTE).count()
    tem_vinculo_aee = False
    if perfil and perfil.tipo_perfil == 'PROFESSOR':
        tem_vinculo_aee = alunos_com_funcao(perfil, Professor.Funcao.AEE).exists()
    tem_area_estudante = False
    if perfil and perfil.tipo_perfil == 'RESPONSAVEL':
        tem_area_estudante = alunos_atividades_visiveis(perfil).exists()
    pessoa = getattr(perfil, perfil.tipo_perfil.lower() + '_perfil', None) if perfil else None
    nome = (pessoa.nome_completo if pessoa else request.user.username) if getattr(request.user, 'is_authenticated', False) else ''
    palavras = nome.split()
    iniciais = ((palavras[0][:1] + palavras[-1][:1]) if len(palavras) > 1 else nome[:2]).upper()
    google_conexao_perfil = None
    if perfil and perfil.tipo_perfil in ('ALUNO', 'RESPONSAVEL'):
        google_conexao_perfil = ConexaoGoogle.objects.filter(usuario=perfil).first()
    return {
        'perfil_nome': nome,
        'perfil_iniciais': iniciais,
        'perfil_tem_foto': bool(perfil and perfil.foto_perfil),
        'google_conexao_perfil': google_conexao_perfil,
        'tem_vinculo_aee': tem_vinculo_aee,
        'tem_area_estudante': tem_area_estudante,
        'aprovacoes_pendentes': pendentes,
        'pedidos_senha_pendentes': pedidos_senha_pendentes,
        'versao_termos': VERSAO_TERMOS,
        'versao_privacidade': VERSAO_PRIVACIDADE,
        'data_vigencia': DATA_VIGENCIA,
    }
