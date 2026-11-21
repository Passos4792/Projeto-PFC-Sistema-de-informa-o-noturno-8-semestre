"""Acesso de menores de 12 anos mediante autorização do responsável vinculado.

A autorização de acesso é específica por aluno e por responsável, distinta do
aceite das condições de uso da conta do adulto. Não substitui a avaliação da
base legal para os demais tratamentos de dados pessoais no ELO.
"""
from django.db.models import F, Q
from django.utils import timezone
from aplicacao.models import Aluno, AutorizacaoAcessoMenor, Responsavel
from aplicacao.servicos.documentos_legais import MARCADOR_REVOGACAO, VERSAO_PRIVACIDADE, VERSAO_TERMOS


def menor_de_12(data_nascimento, hoje=None):
    if not data_nascimento:
        return False
    hoje = hoje or timezone.localdate()
    anos = hoje.year - data_nascimento.year - (
        (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day)
    )
    return anos < 12


def alunos_menores_vinculados(perfil):
    """Somente crianças de vínculos familiares ativos do responsável logado."""
    if perfil is None or perfil.tipo_perfil != 'RESPONSAVEL':
        return []
    alunos = Aluno.objects.filter(ativo=True).filter(
        Q(vinculo__responsavel__usuario=perfil, vinculo__ativo=True)
        | Q(vinculos_familiares__responsavel__usuario=perfil, vinculos_familiares__ativo=True)
    ).distinct().order_by('nome', 'sobrenome', 'pk')
    return [aluno for aluno in alunos if menor_de_12(aluno.data_nascimento)]


def acesso_menor_autorizado(aluno):
    """Exige aceite vigente do adulto, vínculo familiar ativo e autorização específica.

    O requisito é avaliado no banco a cada requisição, inclusive com sessão
    aberta, para refletir revogações de vínculos e atualização dos termos.
    """
    if not menor_de_12(aluno.data_nascimento):
        return True
    # O bloqueio explícito de qualquer responsável atualmente vinculado
    # prevalece até ele voltar a aceitar os documentos. Não depende de haver
    # outra autorização de um responsável diferente e não apaga cadastros.
    if Responsavel.objects.filter(
        ativo=True, usuario__versao_termos_aceita=MARCADOR_REVOGACAO,
    ).filter(
        Q(vinculos__aluno=aluno, vinculos__ativo=True)
        | Q(vinculos_familiares__aluno=aluno, vinculos_familiares__ativo=True)
    ).exists():
        return False
    return AutorizacaoAcessoMenor.objects.filter(
        aluno=aluno,
        aluno__ativo=True,
        responsavel__ativo=True,
        responsavel__usuario__conta__is_active=True,
        responsavel__usuario__documentos_aceitos_em__isnull=False,
        responsavel__usuario__versao_termos_aceita=VERSAO_TERMOS,
        responsavel__usuario__versao_privacidade_ciente=VERSAO_PRIVACIDADE,
        versao_termos=VERSAO_TERMOS,
        versao_privacidade=VERSAO_PRIVACIDADE,
        autorizado_em__gte=F('responsavel__usuario__documentos_aceitos_em'),
    ).filter(
        Q(responsavel__vinculos__aluno=aluno, responsavel__vinculos__ativo=True)
        | Q(responsavel__vinculos_familiares__aluno=aluno,
            responsavel__vinculos_familiares__ativo=True)
    ).exists()


def menores_pendentes(perfil):
    """Lista as crianças vinculadas ainda sem autorização vigente."""
    if perfil is None or perfil.tipo_perfil != 'RESPONSAVEL':
        return []
    autorizados = set(AutorizacaoAcessoMenor.objects.filter(
        responsavel__usuario=perfil,
        versao_termos=VERSAO_TERMOS,
        versao_privacidade=VERSAO_PRIVACIDADE,
        autorizado_em__gte=F('responsavel__usuario__documentos_aceitos_em'),
    ).values_list('aluno_id', flat=True))
    return [aluno for aluno in alunos_menores_vinculados(perfil) if aluno.pk not in autorizados]
