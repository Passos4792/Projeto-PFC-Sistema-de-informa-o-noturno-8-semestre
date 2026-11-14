from pathlib import Path
from uuid import uuid4
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver


EXTENSOES = {'.pdf', '.png', '.jpg', '.jpeg'}
TAMANHO_MAXIMO = 8 * 1024 * 1024


def validar_anexo_pedagogico(arquivo):
    extensao = Path(arquivo.name).suffix.lower()
    if extensao not in EXTENSOES:
        raise ValidationError('Envie um arquivo PDF, PNG ou JPEG.')
    if arquivo.size > TAMANHO_MAXIMO:
        raise ValidationError('O arquivo deve ter no máximo 8 MB.')
    if not arquivo.size:
        raise ValidationError('O arquivo não pode estar vazio.')
    posicao = arquivo.tell()
    try:
        arquivo.seek(0)
        cabecalho = arquivo.read(16)
    finally:
        arquivo.seek(posicao)
    assinaturas = {
        '.pdf': cabecalho.startswith(b'%PDF-'),
        '.png': cabecalho.startswith(b'\x89PNG\r\n\x1a\n'),
        '.jpg': cabecalho.startswith(b'\xff\xd8\xff'),
        '.jpeg': cabecalho.startswith(b'\xff\xd8\xff'),
    }
    if not assinaturas[extensao]:
        raise ValidationError('O conteúdo do arquivo não corresponde ao formato informado.')
    if extensao in {'.png', '.jpg', '.jpeg'}:
        posicao = arquivo.tell()
        try:
            arquivo.seek(0)
            with Image.open(arquivo) as imagem:
                if imagem.format != ('PNG' if extensao == '.png' else 'JPEG'):
                    raise ValidationError('O formato real da imagem não corresponde à extensão.')
                if imagem.width * imagem.height > 25_000_000:
                    raise ValidationError('A imagem possui dimensões excessivas.')
                imagem.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as erro:
            raise ValidationError('A imagem enviada está danificada ou é inválida.') from erro
        finally:
            arquivo.seek(posicao)


def caminho_material(instancia, nome):
    return f'atividades/materiais/{uuid4().hex}{Path(nome).suffix.lower()}'


def caminho_entrega(instancia, nome):
    return f'atividades/entregas/{uuid4().hex}{Path(nome).suffix.lower()}'


def _apagar_apos_gravar(storage, nome):
    if nome:
        transaction.on_commit(lambda: storage.delete(nome))


@receiver(post_delete, sender='elo.Atividade', dispatch_uid='elo.arquivos.material_excluido')
def apagar_material(sender, instance, **kwargs):
    _apagar_apos_gravar(instance.material_apoio.storage, instance.material_apoio.name)


@receiver(post_delete, sender='elo.SolicitacaoConclusao', dispatch_uid='elo.arquivos.entrega_excluida')
def apagar_entrega(sender, instance, **kwargs):
    _apagar_apos_gravar(instance.anexo.storage, instance.anexo.name)


@receiver(pre_save, sender='elo.Atividade', dispatch_uid='elo.arquivos.material_substituido')
def apagar_material_substituido(sender, instance, update_fields=None, **kwargs):
    if not instance.pk or (update_fields is not None and 'material_apoio' not in update_fields):
        return
    anterior = sender.objects.filter(pk=instance.pk).values_list('material_apoio', flat=True).first()
    if anterior and anterior != instance.material_apoio.name:
        _apagar_apos_gravar(instance.material_apoio.storage, anterior)
