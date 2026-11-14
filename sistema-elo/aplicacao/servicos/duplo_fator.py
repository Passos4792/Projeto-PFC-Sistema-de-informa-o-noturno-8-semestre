import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from datetime import timedelta
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from aplicacao.models import CodigoRecuperacao2FA, Configuracao2FA, DispositivoConfiavel2FA

COOKIE_CONFIAVEL = 'elo_dispositivo_confiavel_2fa'
SESSAO_VERIFICADA = 'elo_segundo_fator_verificado'
LIMITE_FALHAS = 5
BLOQUEIO_MINUTOS = 5


def exige_segundo_fator(usuario, perfil=None):
    if not getattr(settings, 'ELO_2FA_ATIVO', True) or not usuario.is_authenticated:
        return False
    return bool(usuario.is_staff or usuario.is_superuser or
                (perfil and perfil.tipo_perfil in ('PROFESSOR', 'RESPONSAVEL')))


def _chave_cifra():
    derivada = hashlib.sha256(b'ELO/segredo-totp/v1:' + settings.SECRET_KEY.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(derivada))


def cifrar_segredo(segredo):
    return _chave_cifra().encrypt(segredo.encode('ascii')).decode('ascii')


def decifrar_segredo(cifrado):
    try:
        return _chave_cifra().decrypt(cifrado.encode('ascii')).decode('ascii')
    except (InvalidToken, ValueError):
        return None


def novo_segredo():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def uri_authenticator(segredo, usuario):
    etiqueta = quote('ELO:' + usuario, safe='')
    parametros = urlencode({'secret': segredo, 'issuer': 'ELO', 'algorithm': 'SHA1',
                             'digits': 6, 'period': 30})
    return f'otpauth://totp/{etiqueta}?{parametros}'


def imagem_qr_em_base64(uri):
    import qrcode
    saida = io.BytesIO()
    qr = qrcode.make(uri, box_size=5, border=3)
    qr.save(saida, format='PNG')
    return base64.b64encode(saida.getvalue()).decode('ascii')


def codigo_totp(segredo, intervalo):
    chave = base64.b32decode(segredo + '=' * (-len(segredo) % 8), casefold=True)
    resumo = hmac.new(chave, struct.pack('>Q', intervalo), hashlib.sha1).digest()
    inicio = resumo[-1] & 0x0f
    numero = struct.unpack('>I', resumo[inicio:inicio + 4])[0] & 0x7fffffff
    return f'{numero % 1000000:06d}'


def obter_configuracao(usuario, criar=False):
    if criar:
        configuracao, _ = Configuracao2FA.objects.get_or_create(
            conta=usuario, defaults={'segredo_criptografado': cifrar_segredo(novo_segredo())})
        return configuracao
    return Configuracao2FA.objects.filter(conta=usuario).first()


def _digest(prefixo, valor):
    return hmac.new(settings.SECRET_KEY.encode(),
                    (prefixo + ':' + valor).encode('utf-8'), hashlib.sha256).hexdigest()


def _codigo_recuperacao_normalizado(codigo):
    return ''.join(c for c in codigo.upper() if c not in ' -')


def criar_codigos_recuperacao(usuario):
    CodigoRecuperacao2FA.objects.filter(conta=usuario).delete()
    codigos = []
    for _ in range(8):
        bruto = secrets.token_hex(10).upper()
        CodigoRecuperacao2FA.objects.create(conta=usuario,
            codigo_hash=_digest('recuperacao', bruto))
        codigos.append('-'.join(bruto[i:i+5] for i in range(0, 20, 5)))
    return codigos


def validar_codigo(usuario, codigo, *, ativacao=False, permite_recuperacao=True):
    codigo = str(codigo or '').strip()
    with transaction.atomic():
        configuracao = Configuracao2FA.objects.select_for_update().filter(conta=usuario).first()
        if not configuracao or bool(configuracao.confirmada_em) == bool(ativacao):
            return False
        agora = timezone.now()
        if configuracao.bloqueado_ate and configuracao.bloqueado_ate > agora:
            return False
        if configuracao.bloqueado_ate:
            configuracao.bloqueado_ate = None
            configuracao.falhas = 0

        segredo = decifrar_segredo(configuracao.segredo_criptografado)
        valido = False
        intervalo_aprovado = None
        if segredo and len(codigo) == 6 and codigo.isascii() and codigo.isdigit():
            intervalo_atual = int(agora.timestamp()) // 30
            for intervalo in (intervalo_atual, intervalo_atual - 1, intervalo_atual + 1):
                if intervalo > configuracao.ultimo_intervalo and hmac.compare_digest(
                        codigo, codigo_totp(segredo, intervalo)):
                    valido = True
                    intervalo_aprovado = intervalo
                    break
        if not valido and permite_recuperacao and not ativacao:
            bruto = _codigo_recuperacao_normalizado(codigo)
            if len(bruto) == 20 and all(c in '0123456789ABCDEF' for c in bruto):
                recuperacao = CodigoRecuperacao2FA.objects.filter(
                    conta=usuario, codigo_hash=_digest('recuperacao', bruto)).first()
                if recuperacao:
                    recuperacao.delete()
                    valido = True
        if valido:
            configuracao.falhas = 0
            configuracao.bloqueado_ate = None
            if intervalo_aprovado is not None:
                configuracao.ultimo_intervalo = intervalo_aprovado
            if ativacao:
                configuracao.confirmada_em = agora
            configuracao.save(update_fields=['falhas', 'bloqueado_ate', 'ultimo_intervalo', 'confirmada_em'])
            return True
        configuracao.falhas += 1
        if configuracao.falhas >= LIMITE_FALHAS:
            configuracao.bloqueado_ate = agora + timedelta(minutes=BLOQUEIO_MINUTOS)
            configuracao.falhas = 0
        configuracao.save(update_fields=['falhas', 'bloqueado_ate'])
        return False


def _assinatura_senha(usuario):
    return _digest('senha-do-dispositivo', usuario.password)


def registrar_dispositivo(request, response):
    dias = getattr(settings, 'ELO_2FA_DISPOSITIVO_DIAS', 30)
    usuario = request.user
    token = secrets.token_urlsafe(32)
    DispositivoConfiavel2FA.objects.filter(conta=usuario,
        expira_em__lte=timezone.now()).delete()
    antigos = list(DispositivoConfiavel2FA.objects.filter(conta=usuario).order_by('-criado_em')
                    .values_list('pk', flat=True)[9:])
    if antigos:
        DispositivoConfiavel2FA.objects.filter(pk__in=antigos).delete()
    DispositivoConfiavel2FA.objects.create(
        conta=usuario, token_hash=_digest('navegador', token),
        assinatura_senha=_assinatura_senha(usuario),
        descricao=request.META.get('HTTP_USER_AGENT', '')[:160] or 'Navegador não identificado',
        expira_em=timezone.now() + timedelta(days=dias),
    )
    response.set_cookie(COOKIE_CONFIAVEL, token, max_age=dias * 24 * 3600,
                        httponly=True, secure=settings.SESSION_COOKIE_SECURE,
                        samesite='Lax', path='/')
    return response


def marcar_sessao_verificada(request, configuracao):
    request.session[SESSAO_VERIFICADA] = f'{request.user.pk}:{configuracao.versao}'


def segundo_fator_verificado(request, configuracao=None):
    if not request.user.is_authenticated:
        return False
    configuracao = configuracao or obter_configuracao(request.user)
    if not configuracao or not configuracao.confirmada_em:
        return False
    chave = f'{request.user.pk}:{configuracao.versao}'
    if request.session.get(SESSAO_VERIFICADA) == chave:
        return True
    token = request.COOKIES.get(COOKIE_CONFIAVEL, '')
    if not token or len(token) > 150:
        return False
    registrado = DispositivoConfiavel2FA.objects.filter(
        conta=request.user, token_hash=_digest('navegador', token),
        expira_em__gt=timezone.now(), assinatura_senha=_assinatura_senha(request.user)).exists()
    if registrado:
        marcar_sessao_verificada(request, configuracao)
    return registrado


def revogar_dispositivos(usuario):
    return DispositivoConfiavel2FA.objects.filter(conta=usuario).delete()


def encerrar_sessoes(usuario):
    from django.contrib.sessions.models import Session
    alvo = str(usuario.pk)
    removidas = [s.pk for s in Session.objects.filter(expire_date__gt=timezone.now()).iterator()
                 if s.get_decoded().get('_auth_user_id') == alvo]
    Session.objects.filter(pk__in=removidas).delete()
    return len(removidas)


def redefinir_segundo_fator(usuario):
    with transaction.atomic():
        Configuracao2FA.objects.filter(conta=usuario).delete()
        CodigoRecuperacao2FA.objects.filter(conta=usuario).delete()
        revogar_dispositivos(usuario)
        encerrar_sessoes(usuario)


def eh_conta_administrativa(usuario):
    if not usuario or not usuario.is_active:
        return False
    if usuario.is_superuser:
        return True
    from aplicacao.models import Usuario
    return Usuario.objects.filter(conta=usuario, gestor=True, tipo_perfil=Usuario.TipoPerfil.PROFESSOR).exists()


def validar_recuperacao_administrador(usuario, codigo_totp_informado, codigo_reserva):
    if not getattr(settings, 'ELO_2FA_ATIVO', True) or not eh_conta_administrativa(usuario):
        return False
    bruto = _codigo_recuperacao_normalizado(str(codigo_reserva or ''))
    if len(bruto) != 20 or any(c not in '0123456789ABCDEF' for c in bruto):
        return False
    with transaction.atomic():
        config = Configuracao2FA.objects.select_for_update().filter(conta=usuario).first()
        if not config or not config.confirmada_em:
            return False
        reserva = CodigoRecuperacao2FA.objects.filter(
            conta=usuario, codigo_hash=_digest('recuperacao', bruto)).first()
        if reserva is None:
            return False
        if not validar_codigo(usuario, codigo_totp_informado, permite_recuperacao=False):
            return False
        reserva.delete()
        return True
