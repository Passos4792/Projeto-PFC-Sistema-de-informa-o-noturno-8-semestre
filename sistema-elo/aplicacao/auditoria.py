"""Registro de eventos com metadados mínimos, sem conteúdo de formulários."""

#importacoes
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.utils.crypto import salted_hmac
from .models import RegistroAuditoria


#-------------------------------------------------------------------------------------

#registrar
def registrar(acao, request=None, objeto=None, autor=None, entidade='', objeto_id='', detalhes=''):
    usuario = autor if autor is not None else getattr(request, 'user', None)
    identificado = usuario is not None and usuario.is_authenticated
    return RegistroAuditoria.objects.create(
        autor_id_original=usuario.pk if identificado else None,
        autor=usuario.get_username()[:150] if identificado else (
            'Não autenticado' if request else 'Comando local'),
        acao=acao, entidade=objeto._meta.verbose_name if objeto is not None else entidade,
        objeto_id=str(objeto.pk) if objeto is not None else str(objeto_id),
        detalhes=detalhes[:500])


#-------------------------------------------------------------------------------------

#registrar login
@receiver(user_logged_in, dispatch_uid='elo.auditoria.login')
def registrar_login(sender, request, user, **kwargs):
    registrar('LOGIN', request=request, autor=user)


#-------------------------------------------------------------------------------------

#registrar saida
@receiver(user_logged_out, dispatch_uid='elo.auditoria.saida')
def registrar_saida(sender, request, user, **kwargs):
    if user is not None:
        registrar('SAIDA', request=request, autor=user)


#-------------------------------------------------------------------------------------

#registrar falha
@receiver(user_login_failed, dispatch_uid='elo.auditoria.falha')
def registrar_falha(sender, credentials, request, **kwargs):
    # Nunca armazenar credentials: pode conter senha e outros segredos.
    import unicodedata
    nome = unicodedata.normalize('NFKC', str(credentials.get('username', ''))).strip().lower()
    referencia = salted_hmac('elo.auditoria.tentativa', nome).hexdigest()
    bloqueado = bool(getattr(request, 'login_espera', 0))
    registrar('BLOQUEIO_LOGIN' if bloqueado else 'FALHA_LOGIN', request=request,
              entidade='tentativa de login', objeto_id=referencia)
#-------------------------------------------------------------------------------------
