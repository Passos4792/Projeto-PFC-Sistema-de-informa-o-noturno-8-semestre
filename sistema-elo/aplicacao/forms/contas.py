from math import ceil
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (AuthenticationForm, PasswordChangeForm, SetPasswordForm, UserCreationForm)
from django.db import transaction
from aplicacao.models import Aluno, Professor, Responsavel, Usuario
from aplicacao.forms.base import validar_nascimento, validar_nome_pessoa


class LoginElo(AuthenticationForm):
    def get_invalid_login_error(self):
        espera = getattr(self.request, 'login_espera', 0)
        if espera:
            return forms.ValidationError(
                'Muitas tentativas de acesso. Tente novamente em %(minutos)s minuto(s).',
                code='login_bloqueado', params={'minutos': ceil(espera / 60)})
        return super().get_invalid_login_error()

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()


class TrocaSenhaInicial(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Senha atual'
        self.fields['old_password'].help_text = ''
        self.fields['new_password2'].label = 'Confirme a nova senha'
        self.fields['new_password2'].help_text = ''
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'

    def clean_new_password1(self):
        senha = self.cleaned_data['new_password1']
        if self.user.check_password(senha):
            raise forms.ValidationError('Escolha uma senha diferente da senha atual.')
        return senha


class RedefinicaoSenha(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Senha temporária'
        self.fields['new_password2'].label = 'Confirme a senha temporária'
        self.fields['new_password2'].help_text = ''
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'

    def clean_new_password1(self):
        senha = self.cleaned_data['new_password1']
        if self.user.check_password(senha):
            raise forms.ValidationError('Defina uma senha diferente da senha atual do usuário.')
        return senha


class PedidoRecuperacaoForm(forms.Form):
    usuario = forms.CharField(
        label='Nome de usuário', max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'campo-formulario', 'autocomplete': 'username',
            'placeholder': 'Digite seu usuário',
        }),
    )

    def clean_usuario(self):
        return self.cleaned_data['usuario'].strip().lower()


class CadastroUsuario(UserCreationForm):
    tipo_perfil = forms.ChoiceField(
        label='Nível de acesso',
        help_text='Escolha primeiro o nível de acesso. Os campos abaixo se ajustam ao perfil selecionado.',
        error_messages={'required': 'Selecione o nível de acesso.'})
    nome = forms.CharField(max_length=80)
    sobrenome = forms.CharField(max_length=120)
    funcao_profissional = forms.ChoiceField(
        label='Função de referência do professor', required=False,
        choices=Professor.Funcao.choices,
        help_text='A função exercida e os acessos são definidos por aluno na ficha de vínculos.')
    data_nascimento = forms.DateField(required=False, label='Data de nascimento',
                                      widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = get_user_model()
        fields = ['tipo_perfil', 'nome', 'sobrenome', 'username',
                  'funcao_profissional', 'data_nascimento', 'password1', 'password2']

    def __init__(self, *args, operador, **kwargs):
        super().__init__(*args, **kwargs)
        escolhas = [('', 'Selecione o nível de acesso'), ('ALUNO', 'Aluno'), ('RESPONSAVEL', 'Responsável')]
        if operador.gestor:
            escolhas.append(('PROFESSOR', 'Professor'))
        self.fields['tipo_perfil'].choices = escolhas
        if not operador.gestor:
            self.fields.pop('funcao_profissional')
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'
        self.fields['tipo_perfil'].widget.attrs['data-nivel-acesso'] = ''
        if 'funcao_profissional' in self.fields:
            self.fields['funcao_profissional'].widget.attrs['data-somente-nivel'] = 'PROFESSOR'
        self.fields['data_nascimento'].widget.attrs['data-obrigatorio-nivel'] = 'ALUNO'
        if self.is_bound and self.data.get('tipo_perfil') == 'ALUNO':
            self.fields['data_nascimento'].required = True
            self.fields['data_nascimento'].error_messages['required'] = 'Informe a data de nascimento do aluno.'

    def clean_nome(self):
        return validar_nome_pessoa(self.cleaned_data['nome'])

    def clean_sobrenome(self):
        return validar_nome_pessoa(self.cleaned_data['sobrenome'])

    def clean_data_nascimento(self):
        return validar_nascimento(self.cleaned_data.get('data_nascimento'))

    def clean_username(self):
        nome = self.cleaned_data['username'].strip().lower()
        if Usuario.objects.filter(usuario__iexact=nome).exists() or get_user_model().objects.filter(username__iexact=nome).exists():
            raise forms.ValidationError('Este usuário já está sendo utilizado.')
        return nome

    @transaction.atomic
    def save(self, commit=True):
        conta = super().save(commit=False)
        conta.first_name = self.cleaned_data['nome']
        conta.last_name = self.cleaned_data['sobrenome']
        conta.save()
        tipo = self.cleaned_data['tipo_perfil']
        perfil = Usuario.objects.create(usuario=conta.username, tipo_perfil=tipo, conta=conta)
        campos = dict(nome=conta.first_name, sobrenome=conta.last_name, usuario=perfil)
        if tipo == 'PROFESSOR':
            campos['funcao'] = self.cleaned_data.get('funcao_profissional') or Professor.Funcao.AEE
        campos['data_nascimento'] = self.cleaned_data.get('data_nascimento')
        {'PROFESSOR': Professor, 'ALUNO': Aluno, 'RESPONSAVEL': Responsavel}[
            tipo].objects.create(**campos)
        return conta


class AceiteDocumentos(forms.Form):
    aceite = forms.BooleanField(
        required=True,
        label='Li e concordo com os Termos de Uso e declaro que tive acesso à Política de Privacidade.',
        error_messages={'required': 'Marque a caixa de aceite para continuar.'},
    )
