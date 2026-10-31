"""OAuth e Calendar REST. Tokens ficam cifrados; o ELO não coleta o e-mail Google."""
#importacoes
import base64
import hashlib
import json
import secrets
import time
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_variables

#-------------------------------------------------------------------------------------

#escopos e enderecos da API do Google
SCOPES = ['openid', 'https://www.googleapis.com/auth/calendar.events.owned']
#permissoes equivalentes que podem ter sido concedidas em uma conexao anterior
SCOPES_CALENDARIO = {
    'https://www.googleapis.com/auth/calendar.events.owned',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar',
}
TOKEN_URL = 'https://oauth2.googleapis.com/token'
EVENTS_URL = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'


#-------------------------------------------------------------------------------------

#erro na integracao com o Google
class GoogleErro(Exception):
    pass


#-------------------------------------------------------------------------------------

#necessidade de nova autorizacao do Google
class ReconectarGoogle(GoogleErro):
    pass


#-------------------------------------------------------------------------------------

#autorizacao parcial que ainda precisa da permissao do calendario
class PermissaoCalendarioPendente(GoogleErro):

    #-------------------------------------------------------------------------------------

    #identificacao da conta para continuar o mesmo fluxo de autorizacao
    def __init__(self, identidade):
        self.identidade = identidade
        super().__init__('O Google não concedeu acesso ao calendário. Clique em Conectar conta Google '
                         'e marque a permissão para ver e editar os eventos antes de continuar.')


#-------------------------------------------------------------------------------------

#tratamento da resposta de erro do Google
class RespostaGoogle(GoogleErro):

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, status, codigo=''):
        self.status, self.codigo = status, codigo
        super().__init__('O Google não concluiu a solicitação.')


#-------------------------------------------------------------------------------------

#verificacao das configuracoes do Google
def configurado():
    if not all([settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET,
                settings.GOOGLE_REDIRECT_URI, settings.GOOGLE_TOKEN_ENCRYPTION_KEY]):
        return False
    try:
        Fernet(settings.GOOGLE_TOKEN_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        return False
    return True


#-------------------------------------------------------------------------------------

#requisicoes para a API do Google
@sensitive_variables()
def requisicao(url, *, metodo='GET', token=None, formulario=None, dados=None):
    headers = {'Accept': 'application/json'}
    body = None
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if formulario is not None:
        body = urlencode(formulario).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif dados is not None:
        body = json.dumps(dados).encode()
        headers['Content-Type'] = 'application/json'
    try:
        with urlopen(Request(url, data=body, headers=headers, method=metodo), timeout=15) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        codigo = ''
        try:
            payload = json.loads(exc.read())
            if isinstance(payload.get('error'), str):
                codigo = payload['error']
        except (ValueError, AttributeError):
            pass
        raise RespostaGoogle(exc.code, codigo) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise GoogleErro('Não foi possível comunicar com o Google. Tente novamente.') from None


#-------------------------------------------------------------------------------------

#criptografia das credenciais
@sensitive_variables()
def cifrar(dados):
    return Fernet(settings.GOOGLE_TOKEN_ENCRYPTION_KEY.encode()).encrypt(json.dumps(dados).encode()).decode()


#-------------------------------------------------------------------------------------

#leitura das credenciais criptografadas
@sensitive_variables()
def decifrar(conexao):
    try:
        return json.loads(Fernet(settings.GOOGLE_TOKEN_ENCRYPTION_KEY.encode()).decrypt(conexao.credenciais.encode()))
    except (InvalidToken, ValueError, TypeError):
        raise ReconectarGoogle('Conecte sua conta Google novamente.') from None


#-------------------------------------------------------------------------------------

#inicio da autorizacao com estado e PKCE
def iniciar_oauth(request, conta_google=None):
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    request.session['google_oauth'] = {
        'state': state, 'verifier': verifier, 'criado': time.time(),
        'usuario': request.user.pk,
        'conta_google': conta_google,
    }
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    parametros = {
        'client_id': settings.GOOGLE_CLIENT_ID, 'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'response_type': 'code', 'scope': ' '.join(SCOPES), 'state': state,
        'access_type': 'offline', 'prompt': 'consent' if conta_google else 'consent select_account',
        'include_granted_scopes': 'true',
        'code_challenge': challenge, 'code_challenge_method': 'S256',
    }
    if conta_google:
        #o identificador confirmado pelo Google evita pedir a escolha da conta outra vez
        parametros['login_hint'] = conta_google
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(parametros)


#-------------------------------------------------------------------------------------

#troca do codigo de autorizacao por credenciais
@sensitive_variables()
def trocar_codigo(code, verifier, conexao_anterior=None, conta_esperada=None):
    dados = requisicao(TOKEN_URL, metodo='POST', formulario={
        'code': code, 'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET, 'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code', 'code_verifier': verifier,
    })
    if not dados.get('access_token'):
        raise GoogleErro('O Google não retornou a credencial de acesso. Tente conectar novamente.')
    identidade = requisicao('https://openidconnect.googleapis.com/v1/userinfo', token=dados['access_token'])
    if not identidade.get('sub'):
        raise GoogleErro('Não foi possível identificar a conta Google.')
    if conta_esperada and identidade['sub'] != conta_esperada:
        raise GoogleErro('A conta Google foi alterada durante a autorização. Inicie a conexão novamente.')
    if not SCOPES_CALENDARIO.intersection(dados.get('scope', '').split()):
        raise PermissaoCalendarioPendente(identidade['sub'])
    # Identificador opaco; não solicitamos nem guardamos o endereço de e-mail.
    identificador = salted_hmac('elo.google.identidade', identidade['sub'], algorithm='sha256').hexdigest()
    #a identificacao confirmada pelo Google impede reaproveitar tokens de outra conta
    refresh_token = dados.get('refresh_token')
    if not refresh_token and conexao_anterior and conexao_anterior.identidade == identificador:
        try:
            refresh_token = decifrar(conexao_anterior).get('refresh_token')
        except ReconectarGoogle:
            pass
    if not refresh_token:
        raise GoogleErro('O Google não concedeu acesso para manter a conexão. '
                         'Remova o acesso do ELO nas conexões da sua Conta Google e conecte novamente.')
    credenciais = {
        'access_token': dados['access_token'], 'refresh_token': refresh_token,
        'expira': time.time() + int(dados.get('expires_in', 3600)),
    }
    return identificador, cifrar(credenciais)


#-------------------------------------------------------------------------------------

#consulta e renovacao do token de acesso
@sensitive_variables()
def token_acesso(conexao, renovar=False):
    dados = decifrar(conexao)
    if not renovar and dados.get('expira', 0) > time.time() + 60:
        return dados['access_token']
    try:
        resposta = requisicao(TOKEN_URL, metodo='POST', formulario={
            'client_id': settings.GOOGLE_CLIENT_ID, 'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'refresh_token': dados['refresh_token'], 'grant_type': 'refresh_token',
        })
    except RespostaGoogle as exc:
        if exc.codigo == 'invalid_grant':
            raise ReconectarGoogle('A autorização expirou ou foi revogada. Conecte novamente.') from None
        raise
    if not resposta.get('access_token'):
        raise ReconectarGoogle('Conecte sua conta Google novamente.')
    dados.update(access_token=resposta['access_token'], expira=time.time() + int(resposta.get('expires_in', 3600)))
    if resposta.get('refresh_token'):
        dados['refresh_token'] = resposta['refresh_token']
    conexao.credenciais = cifrar(dados)
    conexao.save(update_fields=['credenciais', 'atualizado_em'])
    return dados['access_token']


#-------------------------------------------------------------------------------------

#chamada ao calendario com renovacao de acesso
@sensitive_variables()
def chamar_calendar(conexao, url, metodo, dados=None):
    token = token_acesso(conexao)
    try:
        return requisicao(url, metodo=metodo, token=token, dados=dados)
    except RespostaGoogle as exc:
        if exc.status != 401:
            raise
    token = token_acesso(conexao, renovar=True)
    try:
        return requisicao(url, metodo=metodo, token=token, dados=dados)
    except RespostaGoogle as exc:
        if exc.status in (401, 403):
            raise ReconectarGoogle('Conecte sua conta Google novamente.') from None
        raise


#-------------------------------------------------------------------------------------

#identificacao do evento para evitar duplicatas
def evento_id(perfil, identidade, atividade):
    return 'elo' + salted_hmac('elo.google.evento', f'{perfil.pk}:{identidade}:{atividade.pk}', algorithm='sha256').hexdigest()


#-------------------------------------------------------------------------------------

#confirmacao do conteudo realmente salvo no calendario
def conferir_evento(conexao, url, identificador, dados):
    evento = chamar_calendar(conexao, url, 'GET')
    if evento.get('status') == 'cancelled':
        raise RespostaGoogle(410)
    corresponde = (
        evento.get('id') == identificador
        and evento.get('status') == 'confirmed'
        and evento.get('summary') == dados['summary']
        and evento.get('description') == dados['description']
        and evento.get('start', {}).get('date') == dados['start']['date']
        and evento.get('end', {}).get('date') == dados['end']['date']
    )
    if not corresponde:
        raise GoogleErro('O Google ainda não confirmou os dados atualizados da atividade. '
                         'Tente sincronizar novamente.')


#-------------------------------------------------------------------------------------

#criacao e atualizacao do evento da atividade
def enviar_atividade(conexao, atividade, identificador, tentativas=0):
    if not atividade.data_entrega:
        raise GoogleErro('Esta atividade precisa de uma data de entrega para ser sincronizada.')
    dados = {
        'summary': 'ELO · ' + atividade.titulo,
        'description': f'Aluno: {atividade.aluno.nome_completo}\n{atividade.descricao}\nSituação: {atividade.get_situacao_display()}',
        'start': {'date': atividade.data_entrega.isoformat()},
        'end': {'date': (atividade.data_entrega + timedelta(days=1)).isoformat()},
        'visibility': 'private',
        #restaura eventos que foram enviados para a lixeira do Google Agenda
        'status': 'confirmed',
        'extendedProperties': {'private': {'elo_atividade': str(atividade.pk)}},
    }
    url = EVENTS_URL + '/' + quote(identificador, safe='')
    # ID estável evita duplicatas, inclusive depois de timeout ou reconexão.
    try:
        chamar_calendar(conexao, url, 'PATCH', dados)
    except RespostaGoogle as exc:
        if exc.status not in (404, 410):
            raise
        try:
            chamar_calendar(conexao, EVENTS_URL, 'POST', dict(dados, id=identificador))
        except RespostaGoogle as insert_exc:
            if insert_exc.status != 409:
                raise
            try:
                chamar_calendar(conexao, url, 'PATCH', dados)
            except RespostaGoogle as update_exc:
                if update_exc.status not in (404, 410) or tentativas >= 3:
                    raise
                # O Google pode reservar o ID de um evento apagado. O sucessor
                # determinístico mantém as novas tentativas idempotentes.
                proximo = 'elo' + hashlib.sha256((identificador + ':recriado').encode()).hexdigest()
                return enviar_atividade(conexao, atividade, proximo, tentativas + 1)
    try:
        conferir_evento(conexao, url, identificador, dados)
    except RespostaGoogle as exc:
        #um 404 logo apos salvar pode ser temporario: nao criar outro evento nesse caso
        if exc.status != 410 or tentativas >= 3:
            raise
        #alguns eventos excluidos respondem sem erro, mas continuam na lixeira
        proximo = 'elo' + hashlib.sha256((identificador + ':recriado').encode()).hexdigest()
        return enviar_atividade(conexao, atividade, proximo, tentativas + 1)
    return identificador


#-------------------------------------------------------------------------------------

#revogacao da autorizacao do Google
@sensitive_variables()
def revogar(conexao):
    dados = decifrar(conexao)
    try:
        requisicao('https://oauth2.googleapis.com/revoke', metodo='POST',
                   formulario={'token': dados['refresh_token']})
    except RespostaGoogle as exc:
        if exc.status != 400:
            raise
