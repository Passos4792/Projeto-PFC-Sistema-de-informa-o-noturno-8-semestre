#importacoes
from datetime import timedelta
from math import ceil
import unicodedata

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import LimiteLogin


#-------------------------------------------------------------------------------------

#autenticar com limite
def autenticar_com_limite(request, username, autenticar):
    """Serialize attempts in the database, shared by all server processes.

    Only REMOTE_ADDR is trusted. Forwarded headers supplied by clients are ignored.
    Keys are HMACs so the throttle table stores neither usernames nor IPs in plain text.
    """
    username = unicodedata.normalize('NFKC', username or '').strip().lower()
    ip = request.META.get('REMOTE_ADDR', '') if request else 'local'
    chave_usuario = salted_hmac('elo.login.usuario', username).hexdigest()
    limites = {
        chave_usuario: settings.LOGIN_MAX_FALHAS,
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
                # A valid account must not reset an IP's failures against other accounts.
                if registro.chave == chave_usuario:
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
#-------------------------------------------------------------------------------------
