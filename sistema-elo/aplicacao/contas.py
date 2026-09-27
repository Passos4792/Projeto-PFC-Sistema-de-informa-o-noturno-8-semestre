#importacoes
from django import forms
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from .models import Usuario, Professor, Aluno, Responsavel
from .acesso import alunos_permitidos
from .documentos_legais import (
    DATA_VIGENCIA, VERSAO_PRIVACIDADE, VERSAO_TERMOS, documentos_aceitos,
)


#-------------------------------------------------------------------------------------

#formulario de troca obrigatoria de senha
class TrocaSenhaInicial(PasswordChangeForm):

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Senha atual'
        self.fields['old_password'].help_text = ''
        self.fields['new_password2'].label = 'Confirme a nova senha'
        self.fields['new_password2'].help_text = ''
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'


    #-------------------------------------------------------------------------------------

    #validacao da nova senha
    def clean_new_password1(self):
        senha = self.cleaned_data['new_password1']
        if self.user.check_password(senha):
            raise forms.ValidationError('Escolha uma senha diferente da senha atual.')
        return senha


#-------------------------------------------------------------------------------------

#troca obrigatoria de senha no primeiro acesso
def trocar_senha(request):
    perfil = request.perfil_elo
    if not perfil.troca_senha_obrigatoria:
        return redirect('inicio')
    formulario = TrocaSenhaInicial(request.user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and formulario.is_valid():
        from .auditoria import registrar
        with transaction.atomic():
            conta = formulario.save()
            perfil.troca_senha_obrigatoria = False
            perfil.save(update_fields=['troca_senha_obrigatoria', 'atualizado_em'])
            registrar('SENHA', request=request, objeto=perfil,
                      detalhes='Senha inicial alterada pelo usuário.')
        update_session_auth_hash(request, conta)
        return redirect('inicio')
    return render(request, 'aplicacao/trocar-senha.html', {'formulario': formulario})


#-------------------------------------------------------------------------------------

#formulario de redefinicao de senha
class RedefinicaoSenha(SetPasswordForm):

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Senha temporária'
        self.fields['new_password2'].label = 'Confirme a senha temporária'
        self.fields['new_password2'].help_text = ''
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'


    #-------------------------------------------------------------------------------------

    #validacao da nova senha
    def clean_new_password1(self):
        senha = self.cleaned_data['new_password1']
        if self.user.check_password(senha):
            raise forms.ValidationError('Defina uma senha diferente da senha atual do usuário.')
        return senha


#-------------------------------------------------------------------------------------

#redefinicao de senha pelo professor
@sensitive_post_parameters('new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def redefinir_senha(request, pk):
    if request.perfil_elo.tipo_perfil != Usuario.TipoPerfil.PROFESSOR:
        raise PermissionDenied
    perfil = get_object_or_404(
        Usuario.objects.select_related('conta'), pk=pk,
        tipo_perfil__in=[Usuario.TipoPerfil.ALUNO, Usuario.TipoPerfil.RESPONSAVEL],
        conta__isnull=False, conta__is_superuser=False,
    )
    pessoa = perfil.aluno_perfil if perfil.tipo_perfil == 'ALUNO' else perfil.responsavel_perfil
    rota = 'aluno-listar' if perfil.tipo_perfil == 'ALUNO' else 'responsavel-listar'
    formulario = RedefinicaoSenha(perfil.conta, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and formulario.is_valid():
        from .auditoria import registrar
        with transaction.atomic():
            formulario.save()
            perfil.troca_senha_obrigatoria = True
            perfil.save(update_fields=['troca_senha_obrigatoria', 'atualizado_em'])
            registrar('SENHA', request=request, objeto=perfil,
                      detalhes='Senha temporária redefinida pelo professor; troca obrigatória no próximo acesso.')
        messages.success(request, f'Senha temporária de {pessoa.nome_completo} redefinida. O usuário deverá trocá-la no próximo acesso.')
        return redirect(rota)
    return render(request, 'aplicacao/redefinir-senha.html', {
        'formulario': formulario, 'pessoa': pessoa, 'perfil_alvo': perfil,
        'rota_voltar': rota, 'pagina_ativa': 'alunos' if perfil.tipo_perfil == 'ALUNO' else 'responsaveis',
    })


#-------------------------------------------------------------------------------------

#formulario de login
class LoginElo(AuthenticationForm):

    #-------------------------------------------------------------------------------------

    #mensagem de erro no login
    def get_invalid_login_error(self):
        espera = getattr(self.request, 'login_espera', 0)
        if espera:
            from math import ceil
            return forms.ValidationError(
                'Muitas tentativas de acesso. Tente novamente em %(minutos)s minuto(s).',
                code='login_bloqueado', params={'minutos': ceil(espera / 60)})
        return super().get_invalid_login_error()

    #-------------------------------------------------------------------------------------

    #validacao do nome de usuario
    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()


#-------------------------------------------------------------------------------------

#formulario de cadastro de usuario
class CadastroUsuario(UserCreationForm):
    nome = forms.CharField(max_length=80)
    sobrenome = forms.CharField(max_length=120)
    tipo_perfil = forms.ChoiceField(label='Nível de acesso')
    data_nascimento = forms.DateField(required=False, label='Data de nascimento (aluno)',
                                      widget=forms.DateInput(attrs={'type': 'date'}))

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = get_user_model()
        fields = ['nome', 'sobrenome', 'username', 'tipo_perfil',
                  'data_nascimento', 'password1', 'password2']

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, *args, operador, **kwargs):
        super().__init__(*args, **kwargs)
        escolhas = [('ALUNO', 'Aluno'), ('RESPONSAVEL', 'Responsável')]
        if operador.professor_principal:
            escolhas.append(('PROFESSOR', 'Professor'))
        self.fields['tipo_perfil'].choices = escolhas
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'

    #-------------------------------------------------------------------------------------

    #validacao do nome de usuario
    def clean_username(self):
        nome = self.cleaned_data['username'].strip().lower()
        if Usuario.objects.filter(usuario__iexact=nome).exists() or get_user_model().objects.filter(username__iexact=nome).exists():
            raise forms.ValidationError('Este usuário já está sendo utilizado.')
        return nome

    #-------------------------------------------------------------------------------------

    #salvar registro
    @transaction.atomic
    def save(self, commit=True):
        conta = super().save(commit=False)
        conta.first_name = self.cleaned_data['nome']
        conta.last_name = self.cleaned_data['sobrenome']
        conta.save()
        tipo = self.cleaned_data['tipo_perfil']
        perfil = Usuario.objects.create(usuario=conta.username, tipo_perfil=tipo, conta=conta)
        campos = dict(nome=conta.first_name, sobrenome=conta.last_name, usuario=perfil)
        if tipo == 'ALUNO':
            campos['data_nascimento'] = self.cleaned_data['data_nascimento']
        {'PROFESSOR': Professor, 'ALUNO': Aluno, 'RESPONSAVEL': Responsavel}[
            tipo].objects.create(**campos)
        return conta


#-------------------------------------------------------------------------------------

#formulario de aceite dos documentos legais
class AceiteDocumentos(forms.Form):
    aceite = forms.BooleanField(
        required=True,
        label='Li e concordo com os Termos de Uso e declaro que tive acesso à Política de Privacidade.',
        error_messages={'required': 'Marque a caixa de aceite para continuar.'},
    )


#-------------------------------------------------------------------------------------

#aceite dos termos e ciencia da politica de privacidade
def aceitar_termos(request):
    perfil = request.perfil_elo
    proximo = request.POST.get('next') or request.GET.get('next') or ''

    if documentos_aceitos(perfil):
        return redirect('inicio')

    formulario = AceiteDocumentos(request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        perfil.documentos_aceitos_em = timezone.now()
        perfil.versao_termos_aceita = VERSAO_TERMOS
        perfil.versao_privacidade_ciente = VERSAO_PRIVACIDADE
        perfil.save(update_fields=[
            'documentos_aceitos_em',
            'versao_termos_aceita',
            'versao_privacidade_ciente',
            'atualizado_em',
        ])

        from .auditoria import registrar
        registrar(
            'DOCUMENTOS',
            request=request,
            objeto=perfil,
            detalhes=f'Termos v{VERSAO_TERMOS}; Política v{VERSAO_PRIVACIDADE}',
        )

        if proximo and url_has_allowed_host_and_scheme(
            proximo, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(proximo)
        return redirect('inicio')

    return render(request, 'aplicacao/aceitar-termos.html', {
        'documento': 'privacidade' if request.GET.get('documento') == 'privacidade' else 'termos',
        'formulario': formulario,
        'versao_termos': VERSAO_TERMOS,
        'versao_privacidade': VERSAO_PRIVACIDADE,
        'data_vigencia': DATA_VIGENCIA,
        'next': proximo,
    })


#-------------------------------------------------------------------------------------

#cadastrar
def cadastrar(request):
    form = CadastroUsuario(request.POST or None, operador=request.perfil_elo)
    if request.method == 'POST' and form.is_valid():
        from .auditoria import registrar
        with transaction.atomic():
            conta = form.save()
            registrar('CRIACAO', request=request, objeto=conta.perfil_elo)
            registrar('PERMISSAO', request=request, objeto=conta.perfil_elo,
                      detalhes='Perfil definido: ' + conta.perfil_elo.get_tipo_perfil_display())
        from django.contrib import messages
        messages.success(request, 'Usuário criado com o nível de acesso selecionado.')
        return redirect('usuario-criar')
    return render(request, 'aplicacao/formulario-padrao.html', {
        'formulario': form, 'titulo': 'Cadastrar usuário', 'pagina_ativa': 'usuarios', 'url_voltar': '/'})


#-------------------------------------------------------------------------------------

#inicio
def inicio(request):
    perfil = request.perfil_elo
    if perfil.tipo_perfil == 'PROFESSOR':
        return redirect('pagina-inicial')
    if perfil.tipo_perfil == 'ALUNO':
        return redirect('aluno-inicio', pk=perfil.aluno_perfil.pk)
    return render(request, 'aplicacao/portal.html', {'alunos': alunos_permitidos(perfil)})
#-------------------------------------------------------------------------------------
