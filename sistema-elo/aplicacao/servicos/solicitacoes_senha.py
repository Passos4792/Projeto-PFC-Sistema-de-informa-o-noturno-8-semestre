"""Finalização segura de pedidos de senha quando o titular recupera o acesso.

A data de resolução usa a coluna atendida_em já existente no banco, também
para cancelamentos/negações, evitando qualquer alteração estrutural de dados.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from aplicacao.models import SolicitacaoSenha, Usuario
from aplicacao.servicos.auditoria import registrar


def cancelar_pedidos_apos_login(conta, request):
    """Cancelar pendências deste titular SOMENTE após login/2FA bem-sucedido.

    Considera também pedidos legados que identificam o aluno só pelo vínculo
    `aluno`, para não deixar pendência antiga disponível para atendimento.
    Nunca cancela pedidos de terceiros ou já atendidos.
    """
    perfil = Usuario.objects.filter(conta=conta, conta_encerrada_em__isnull=True).first()
    if perfil is None:
        return 0
    alvo = Q(usuario_alvo_id=perfil.pk)
    if perfil.tipo_perfil == Usuario.TipoPerfil.ALUNO:
        alvo |= Q(usuario_alvo__isnull=True, aluno__usuario_id=perfil.pk)

    with transaction.atomic():
        ids = list(SolicitacaoSenha.objects.select_for_update().filter(
            situacao=SolicitacaoSenha.Situacao.PENDENTE
        ).filter(alvo).values_list('pk', flat=True))
        if not ids:
            return 0
        SolicitacaoSenha.objects.filter(
            pk__in=ids, situacao=SolicitacaoSenha.Situacao.PENDENTE
        ).update(situacao=SolicitacaoSenha.Situacao.CANCELADA, atendida_em=timezone.now())
        for pedido_id in ids:
            registrar('SENHA', request=request, autor=conta,
                      entidade='solicitacao_senha', objeto_id=pedido_id,
                      detalhes='Pedido cancelado automaticamente após autenticação bem-sucedida do titular.')
    return len(ids)
