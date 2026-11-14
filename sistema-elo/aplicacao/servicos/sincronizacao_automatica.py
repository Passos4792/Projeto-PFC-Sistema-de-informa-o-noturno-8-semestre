import logging
from django.db import transaction
from django.utils import timezone
from aplicacao.servicos import google_calendar as google
from aplicacao.servicos.acesso import alunos_permitidos
from aplicacao.models import Atividade, ConexaoGoogle, SincronizacaoGoogle

logger = logging.getLogger(__name__)


def _pode_receber(conexao, atividade):
    perfil = conexao.usuario
    if perfil.tipo_perfil not in ('ALUNO', 'RESPONSAVEL') or not atividade:
        return False
    return alunos_permitidos(perfil).filter(pk=atividade.aluno_id).exists()


def _atualizar_para_conexao(conexao, atividade_id, atividade=None):
    anterior = SincronizacaoGoogle.objects.filter(
        usuario_id=conexao.usuario_id, atividade_id=atividade_id,
        identidade=conexao.identidade,
    ).first()
    elegivel = (
        atividade is not None and atividade.data_entrega is not None
        and atividade.data_entrega >= timezone.localdate()
        and atividade.situacao != Atividade.Situacao.CANCELADA
        and _pode_receber(conexao, atividade)
    )
    if elegivel:
        identificador = anterior.evento_id if anterior else google.evento_id(
            conexao.usuario, conexao.identidade, atividade)
        evento = google.enviar_atividade(conexao, atividade, identificador)
        SincronizacaoGoogle.objects.update_or_create(
            usuario_id=conexao.usuario_id, atividade_id=atividade_id,
            identidade=conexao.identidade,
            defaults={'evento_id': evento, 'sincronizado_em': timezone.now()},
        )
        return True
    if anterior:
        google.excluir_evento(conexao, anterior.evento_id)
        anterior.delete()
    return False


def sincronizar_atividade(atividade_id):
    if not google.configurado():
        return (0, 0)
    atividade = Atividade.objects.select_related('aluno').filter(pk=atividade_id).first()
    conectados = ConexaoGoogle.objects.select_related('usuario').filter(
        usuario__tipo_perfil__in=('ALUNO', 'RESPONSAVEL'))
    realizados = falhas = 0
    for conexao in conectados.iterator():
        anterior_existe = SincronizacaoGoogle.objects.filter(
            usuario_id=conexao.usuario_id, atividade_id=atividade_id,
            identidade=conexao.identidade,
        ).exists()
        if not anterior_existe and not (atividade and atividade.data_entrega
                and atividade.data_entrega >= timezone.localdate()
                and atividade.situacao != Atividade.Situacao.CANCELADA
                and _pode_receber(conexao, atividade)):
            continue
        try:
            if _atualizar_para_conexao(conexao, atividade_id, atividade):
                realizados += 1
        except google.GoogleErro as erro:
            falhas += 1
            logger.warning('Falha ao atualizar atividade %s na agenda do perfil %s: %s',
                           atividade_id, conexao.usuario_id, type(erro).__name__)
    return realizados, falhas


def sincronizar_usuario(perfil):
    if not google.configurado() or perfil.tipo_perfil not in ('ALUNO', 'RESPONSAVEL'):
        return (0, 0)
    conexao = ConexaoGoogle.objects.select_related('usuario').filter(usuario=perfil).first()
    if not conexao:
        return (0, 0)
    SincronizacaoGoogle.objects.filter(usuario=perfil).exclude(identidade=conexao.identidade).delete()
    atividades = Atividade.objects.filter(
        aluno__in=alunos_permitidos(perfil),
        data_entrega__gte=timezone.localdate(),
    ).exclude(situacao=Atividade.Situacao.CANCELADA).values_list('pk', flat=True)
    antigos = SincronizacaoGoogle.objects.filter(
        usuario=perfil, identidade=conexao.identidade).values_list('atividade_id', flat=True)
    ids = set(atividades) | set(antigos)
    realizados = falhas = 0
    for atividade_id in sorted(ids):
        atividade = Atividade.objects.select_related('aluno').filter(pk=atividade_id).first()
        try:
            if _atualizar_para_conexao(conexao, atividade_id, atividade):
                realizados += 1
        except google.GoogleErro as erro:
            falhas += 1
            logger.warning('Falha ao conciliar agenda do perfil %s, atividade %s: %s',
                           perfil.pk, atividade_id, type(erro).__name__)
    return realizados, falhas


def remover_eventos_atividade_excluida(eventos):
    if not google.configurado():
        return
    for usuario_id, identidade, evento_id in eventos:
        conexao = ConexaoGoogle.objects.filter(usuario_id=usuario_id, identidade=identidade).first()
        if conexao:
            try:
                google.excluir_evento(conexao, evento_id)
            except google.GoogleErro as erro:
                logger.warning('Falha ao excluir evento de atividade removida para perfil %s: %s',
                               usuario_id, type(erro).__name__)


def agendar_atualizacao(atividade_id):
    transaction.on_commit(lambda: sincronizar_atividade(atividade_id))
