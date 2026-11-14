from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from aplicacao.models import Atividade, SincronizacaoGoogle, Vinculo, VinculoFamiliar
from aplicacao.servicos.sincronizacao_automatica import agendar_atualizacao, remover_eventos_atividade_excluida


@receiver(post_save, sender=Atividade, dispatch_uid='elo.agenda.atividade.salva')
def atividade_salva(sender, instance, **kwargs):
    agendar_atualizacao(instance.pk)


@receiver(pre_delete, sender=Atividade, dispatch_uid='elo.agenda.atividade.antes_exclusao')
def atividade_antes_exclusao(sender, instance, **kwargs):
    instance._eventos_google_excluidos = list(SincronizacaoGoogle.objects.filter(
        atividade_id=instance.pk).values_list('usuario_id', 'identidade', 'evento_id'))


@receiver(post_delete, sender=Atividade, dispatch_uid='elo.agenda.atividade.excluida')
def atividade_excluida(sender, instance, **kwargs):
    eventos = getattr(instance, '_eventos_google_excluidos', [])
    if eventos:
        transaction.on_commit(lambda eventos=eventos: remover_eventos_atividade_excluida(eventos))


def _atualizar_atividades_de_aluno(aluno_ids):
    for pk in Atividade.objects.filter(aluno_id__in=aluno_ids).values_list('pk', flat=True):
        agendar_atualizacao(pk)


@receiver(pre_save, sender=Vinculo, dispatch_uid='elo.agenda.vinculo.antes_salvar')
@receiver(pre_save, sender=VinculoFamiliar, dispatch_uid='elo.agenda.familiar.antes_salvar')
def vinculo_antes_salvar(sender, instance, **kwargs):
    instance._aluno_id_anterior_google = (sender.objects.filter(pk=instance.pk)
        .values_list('aluno_id', flat=True).first()) if instance.pk else None


@receiver(post_save, sender=Vinculo, dispatch_uid='elo.agenda.vinculo.salvo')
@receiver(post_save, sender=VinculoFamiliar, dispatch_uid='elo.agenda.familiar.salvo')
@receiver(post_delete, sender=Vinculo, dispatch_uid='elo.agenda.vinculo.excluido')
@receiver(post_delete, sender=VinculoFamiliar, dispatch_uid='elo.agenda.familiar.excluido')
def vinculo_modificado(sender, instance, **kwargs):
    aluno_ids = {instance.aluno_id}
    anterior = getattr(instance, '_aluno_id_anterior_google', None)
    if anterior:
        aluno_ids.add(anterior)
    transaction.on_commit(lambda ids=tuple(aluno_ids): _atualizar_atividades_de_aluno(ids))
