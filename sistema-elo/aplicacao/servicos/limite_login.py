from datetime import timedelta
from math import ceil
import unicodedata
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from aplicacao.models import LimiteLogin


def ip_cliente(request):
    if request is None:
        return 'local'
    if getattr(settings, 'CONFIAR_PROXY', False):
        encaminhados = [parte.strip() for parte in
                        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if parte.strip()]
        if encaminhados:
            return encaminhados[-1]
    return request.META.get('REMOTE_ADDR', '')


def autenticar_com_limite(request, username, autenticar):
    username = unicodedata.normalize('NFKC', username or '').strip().lower()
    ip = ip_cliente(request)
    chave_usuario_ip = salted_hmac('elo.login.usuario_ip', f'{username}|{ip}').hexdigest()
    chave_usuario = salted_hmac('elo.login.usuario', username).hexdigest()
    limites = {
        chave_usuario_ip: settings.LOGIN_MAX_FALHAS,
        chave_usuario: getattr(settings, 'LOGIN_MAX_FALHAS_USUARIO', settings.LOGIN_MAX_FALHAS),
        salted_hmac('elo.login.ip', ip).hexdigest(): settings.LOGIN_MAX_FALHAS_IP,
    }
    with transaction.atomic():
        registros = []
        for chave in sorted(limites):
            LimiteLogin.objects.get_or_create(chave=chave, defaults={'inicio': timezone.now()})
            registros.append(LimiteLogin.objects.select_for_update().get(chave=chave))
        agora = timezone.now()
        espera = max([ceil((r.bloqueado_ate - agora).total_seconds())
                      for r in registros if r.bloqueado_ate and r.bloqueado_ate > agora] or [0])
        if espera:
            if request is not None:
                request.login_espera = espera
            return None
        for registro in registros:
            if registro.bloqueado_ate or agora >= registro.inicio + timedelta(seconds=settings.LOGIN_JANELA_SEGUNDOS):
                registro.falhas = 0
                registro.inicio = agora
                registro.bloqueado_ate = None
        user = autenticar(username)
        for registro in registros:
            if user is not None:
                if registro.chave in (chave_usuario_ip, chave_usuario):
                    registro.falhas = 0
                    registro.inicio = agora
            else:
                registro.falhas += 1
                if registro.falhas >= limites[registro.chave]:
                    registro.bloqueado_ate = agora + \
                        timedelta(seconds=settings.LOGIN_BLOQUEIO_SEGUNDOS)
                    if request is not None:
                        request.login_espera = settings.LOGIN_BLOQUEIO_SEGUNDOS
            registro.save()
        return user
