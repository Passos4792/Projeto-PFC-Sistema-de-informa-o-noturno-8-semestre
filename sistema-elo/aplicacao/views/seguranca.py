from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, logout, password_validation, update_session_auth_hash
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from aplicacao.servicos.acesso import perfil_ativo
from aplicacao.servicos.limite_login import autenticar_com_limite
from aplicacao.servicos.auditoria import referencia_tentativa, registrar
from aplicacao.servicos.duplo_fator import (
    COOKIE_CONFIAVEL, criar_codigos_recuperacao, decifrar_segredo, eh_conta_administrativa,
    exige_segundo_fator, imagem_qr_em_base64, marcar_sessao_verificada,
    obter_configuracao, registrar_dispositivo, revogar_dispositivos,
    segundo_fator_verificado, uri_authenticator, validar_codigo,
    validar_recuperacao_administrador,
)
from aplicacao.forms import TrocaSenhaInicial
from aplicacao.models import CodigoRecuperacao2FA, DispositivoConfiavel2FA


def _permitido(request):
    perfil = perfil_ativo(request.user)
    if not exige_segundo_fator(request.user, perfil):
        raise PermissionDenied('A autenticação em duas etapas não se aplica a esta conta.')
    return perfil


def _registrar_falha_codigo(request, detalhes):
    registrar('FALHA_LOGIN', request=request, entidade='segundo fator', detalhes=detalhes)


def _destino_seguro(request):
    proximo = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if proximo.startswith('/') and not proximo.startswith('//') and url_has_allowed_host_and_scheme(
            proximo, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        if not proximo.startswith((reverse('2fa-configurar'), reverse('2fa-verificar'))):
            return proximo
    if request.user.is_staff and perfil_ativo(request.user) is None:
        return reverse('admin:index')
    return reverse('inicio')


def _com_confianca(request, response):
    if request.POST.get('confiar') == 'sim':
        return registrar_dispositivo(request, response)
    return response


@never_cache
@sensitive_post_parameters('codigo')
@require_http_methods(['GET', 'POST'])
def configurar(request):
    _permitido(request)
    config = obter_configuracao(request.user, criar=True)
    if config.confirmada_em:
        return redirect('2fa-seguranca' if segundo_fator_verificado(request, config) else '2fa-verificar')
    segredo = decifrar_segredo(config.segredo_criptografado)
    if not segredo:
        raise PermissionDenied('A chave de autenticação não pôde ser recuperada. Contate o administrador.')
    erro = None
    if request.method == 'POST':
        if validar_codigo(request.user, request.POST.get('codigo'), ativacao=True,
                          permite_recuperacao=False):
            with transaction.atomic():
                codigos = criar_codigos_recuperacao(request.user)
            config.refresh_from_db()
            marcar_sessao_verificada(request, config)
            registrar('PERMISSAO', request=request, entidade='segundo fator',
                      detalhes='Microsoft Authenticator (TOTP) configurado.')
            resposta = render(request, 'aplicacao/seguranca/2fa-codigos.html', {'codigos': codigos,
                'continuar_url': _destino_seguro(request)})
            return _com_confianca(request, resposta)
        _registrar_falha_codigo(request, 'Código recusado ao cadastrar o Authenticator.')
        erro = 'Código incorreto, já utilizado ou temporariamente bloqueado. Confira a hora do celular.'
    uri = uri_authenticator(segredo, request.user.get_username())
    return render(request, 'aplicacao/seguranca/2fa-configurar.html', {
        'qr_base64': imagem_qr_em_base64(uri), 'chave_manual': segredo,
        'erro': erro, 'next': request.POST.get('next') or request.GET.get('next') or '',
        'dias_confianca': 30,
    })


@never_cache
@sensitive_post_parameters('codigo')
@require_http_methods(['GET', 'POST'])
def verificar(request):
    _permitido(request)
    config = obter_configuracao(request.user)
    if not config or not config.confirmada_em:
        return redirect('2fa-configurar')
    if segundo_fator_verificado(request, config):
        return redirect(_destino_seguro(request))
    erro = None
    if request.method == 'POST':
        if validar_codigo(request.user, request.POST.get('codigo')):
            marcar_sessao_verificada(request, config)
            registrar('PERMISSAO', request=request, entidade='segundo fator',
                      detalhes='Autenticação em duas etapas confirmada.')
            resposta = redirect(_destino_seguro(request))
            return _com_confianca(request, resposta)
        _registrar_falha_codigo(request, 'Código do Authenticator recusado na verificação de entrada.')
        erro = ('Código inválido, já utilizado ou temporariamente bloqueado. '
                'Também é possível usar um código de recuperação não utilizado.')
    return render(request, 'aplicacao/seguranca/2fa-verificar.html', {
        'erro': erro, 'next': request.POST.get('next') or request.GET.get('next') or '',
        'dias_confianca': 30,
    })


@never_cache
@sensitive_post_parameters('codigo')
@require_http_methods(['GET', 'POST'])
def seguranca(request):
    _permitido(request)
    config = obter_configuracao(request.user)
    if not config or not config.confirmada_em or not segundo_fator_verificado(request, config):
        return redirect('2fa-verificar')
    if request.method == 'POST':
        if request.POST.get('acao') != 'novos-codigos':
            raise PermissionDenied
        if validar_codigo(request.user, request.POST.get('codigo'),
                          permite_recuperacao=False):
            with transaction.atomic():
                codigos = criar_codigos_recuperacao(request.user)
            registrar('PERMISSAO', request=request, entidade='segundo fator',
                      detalhes='Códigos de recuperação substituídos.')
            return render(request, 'aplicacao/seguranca/2fa-codigos.html', {'codigos': codigos, 'renovados': True,
                'continuar_url': _destino_seguro(request)})
        _registrar_falha_codigo(request, 'Código recusado ao gerar novos códigos de recuperação.')
        messages.error(request, 'Código do Authenticator inválido ou bloqueado. Aguarde o próximo código.')
    dispositivos = DispositivoConfiavel2FA.objects.filter(
        conta=request.user, expira_em__gt=timezone.now())
    return render(request, 'aplicacao/seguranca/2fa-seguranca.html', {
        'layout_2fa': 'aplicacao/comum/estrutura-base.html' if perfil_ativo(request.user)
                      else 'aplicacao/comum/estrutura-publica.html',
        'voltar_url': _destino_seguro(request),
        'dispositivos': dispositivos,
        'quantidade_codigos': CodigoRecuperacao2FA.objects.filter(conta=request.user).count(),
        'pagina_ativa': 'meus-dados',
    })


@never_cache
@require_POST
def revogar(request):
    _permitido(request)
    if not segundo_fator_verificado(request):
        return redirect('2fa-verificar')
    revogar_dispositivos(request.user)
    registrar('PERMISSAO', request=request, entidade='segundo fator',
              detalhes='Todos os navegadores confiáveis foram revogados.')
    messages.success(request, 'Todos os navegadores confiáveis foram revogados. Na próxima entrada, será exigido um código.')
    resposta = redirect('2fa-seguranca')
    resposta.delete_cookie(COOKIE_CONFIAVEL, path='/', samesite='Lax')
    return resposta


class TrocaSenhaAdministrador(TrocaSenhaInicial):
    codigo = forms.RegexField(
        regex=r'^[0-9]{6}$',
        label='Código atual do Microsoft Authenticator',
        min_length=6, max_length=6,
        error_messages={'invalid': 'Informe os seis dígitos exibidos no aplicativo.'},
        widget=forms.TextInput(attrs={
            'inputmode': 'numeric', 'autocomplete': 'one-time-code',
            'placeholder': '000000', 'maxlength': '6',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo'].widget.attrs['class'] = 'campo-formulario'


@never_cache
@sensitive_post_parameters('old_password', 'new_password1', 'new_password2', 'codigo')
@require_http_methods(['GET', 'POST'])
def trocar_senha_admin(request):
    if not request.user.is_authenticated or not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied('Apenas administradores podem acessar esta operação.')
    config = obter_configuracao(request.user)
    if not config or not config.confirmada_em:
        return redirect('2fa-configurar')
    if not segundo_fator_verificado(request, config):
        return redirect('2fa-verificar')

    formulario = TrocaSenhaAdministrador(
        request.user, request.POST if request.method == 'POST' else None
    )
    if request.method == 'POST' and formulario.is_valid():
        if validar_codigo(request.user, formulario.cleaned_data['codigo'],
                          permite_recuperacao=False):
            with transaction.atomic():
                conta = formulario.save()
                revogar_dispositivos(conta)
                registrar('SENHA', request=request, entidade='conta administrativa',
                          detalhes='Senha do próprio administrador alterada com TOTP confirmado; '
                          'navegadores confiáveis revogados.')
            update_session_auth_hash(request, conta)
            messages.success(request, 'Sua senha foi alterada com confirmação do Authenticator. '
                             'Os navegadores confiáveis foram revogados.')
            resposta = redirect('admin:index')
            resposta.delete_cookie(COOKIE_CONFIAVEL, path='/', samesite='Lax')
            return resposta
        _registrar_falha_codigo(request, 'Código recusado ao alterar a senha administrativa.')
        formulario.add_error('codigo', 'Código inválido, já utilizado ou bloqueado. '
                            'Aguarde o próximo código do aplicativo.')
    return render(request, 'aplicacao/seguranca/2fa-trocar-senha-admin.html', {
        'formulario': formulario,
    })


class RecuperacaoSenhaAdminForm(forms.Form):
    usuario = forms.CharField(label='Usuário do administrador', max_length=150,
        widget=forms.TextInput(attrs={'autocomplete': 'username'}))
    codigo = forms.RegexField(regex=r'^[0-9]{6}$',
        label='Código atual do Microsoft Authenticator', min_length=6, max_length=6,
        widget=forms.TextInput(attrs={'inputmode': 'numeric',
                                      'autocomplete': 'one-time-code', 'maxlength': '6'}))
    codigo_recuperacao = forms.CharField(label='Um código de recuperação de uso único',
        max_length=30, widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    new_password1 = forms.CharField(label='Nova senha',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    new_password2 = forms.CharField(label='Confirme a nova senha',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'

    def clean_usuario(self):
        return self.cleaned_data['usuario'].strip().lower()

    def clean(self):
        dados = super().clean()
        senha1, senha2 = dados.get('new_password1'), dados.get('new_password2')
        if senha1 and senha2 and senha1 != senha2:
            self.add_error('new_password2', 'As senhas informadas não coincidem.')
        if senha1:
            try:
                password_validation.validate_password(senha1)
            except ValidationError as erro:
                self.add_error('new_password1', erro)
        return dados


@never_cache
@sensitive_post_parameters('codigo', 'codigo_recuperacao', 'new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def recuperar_senha_admin(request):
    formulario = RecuperacaoSenhaAdminForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and formulario.is_valid():
        dados = formulario.cleaned_data
        nome = dados['usuario']

        def autorizar_e_redefinir(nome_validado):
            usuario = get_user_model().objects.filter(
                username__iexact=nome_validado, is_active=True).first()
            if not eh_conta_administrativa(usuario) or usuario.check_password(dados['new_password1']):
                return None
            try:
                password_validation.validate_password(dados['new_password1'], user=usuario)
            except ValidationError:
                return None
            with transaction.atomic():
                usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
                if not validar_recuperacao_administrador(
                        usuario, dados['codigo'], dados['codigo_recuperacao']):
                    return None
                usuario.set_password(dados['new_password1'])
                usuario.save(update_fields=['password'])
                revogar_dispositivos(usuario)
                config = obter_configuracao(usuario)
                from uuid import uuid4
                config.versao = uuid4()
                config.save(update_fields=['versao'])
                registrar('SENHA', request=request, entidade='conta administrativa',
                          objeto_id=usuario.pk,
                          detalhes='Senha esquecida redefinida sem e-mail, com TOTP e código reserva; '
                                   'navegadores e sessões anteriores invalidados.')
            return usuario

        usuario = autenticar_com_limite(request, nome, autorizar_e_redefinir)
        if usuario is not None:
            logout(request)
            messages.success(request, 'Senha administrativa redefinida com segurança. '
                             'Entre usando sua nova senha e confirme o Authenticator.')
            resposta = redirect('login')
            resposta.delete_cookie(COOKIE_CONFIAVEL, path='/', samesite='Lax')
            return resposta
        bloqueado = bool(getattr(request, 'login_espera', 0))
        registrar('BLOQUEIO_LOGIN' if bloqueado else 'FALHA_LOGIN', request=request,
                  entidade='recuperação de senha administrativa', objeto_id=referencia_tentativa(nome),
                  detalhes='Tentativa bloqueada temporariamente.' if bloqueado
                  else 'Recuperação recusada: conta, código do Authenticator ou código de recuperação inválido.')
        formulario.add_error(None, 'Não foi possível confirmar a recuperação. '
                             'Revise os códigos e a conta, ou aguarde o fim do bloqueio temporário.')
    return render(request, 'aplicacao/seguranca/2fa-recuperar-senha-admin.html', {'formulario': formulario})
