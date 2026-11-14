from unicodedata import normalize
from django.contrib.auth.validators import UnicodeUsernameValidator
from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from aplicacao.forms.idioma import traduzir_opcoes
from aplicacao.models import Usuario


def validar_nome_pessoa(valor):
    valor = ' '.join(normalize('NFC', valor).split())
    permitidos = " '-.\u2019"
    if not any(caractere.isalpha() for caractere in valor) or any(
            not (caractere.isalpha() or caractere in permitidos) for caractere in valor):
        raise forms.ValidationError('Use apenas letras, espaços, hífen, ponto ou apóstrofo no nome.')
    return valor


def validar_nascimento(data):
    if data and data > timezone.localdate():
        raise forms.ValidationError('A data de nascimento não pode ser futura.')
    return data


class FormularioBase(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "campo-formulario")
            if isinstance(campo, forms.ModelChoiceField):
                campo.empty_label = 'Selecione uma opção' if campo.required else 'Não definido'
        for nome, rotulo in {'titulo': 'Título', 'descricao': 'Descrição', 'situacao': 'Situação'}.items():
            if nome in self.fields:
                self.fields[nome].label = rotulo


class FormularioPessoaBase(FormularioBase):
    nome_usuario = forms.CharField(
        label="Usuário",
        max_length=150,
        help_text="Este nome deve ser único em todo o sistema.",
    )
    tipo_perfil = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)

        if self.instance.pk and self.instance.usuario_id:
            self.fields["nome_usuario"].initial = self.instance.usuario.usuario

    def clean_nome(self):
        return validar_nome_pessoa(self.cleaned_data['nome'])

    def clean_sobrenome(self):
        return validar_nome_pessoa(self.cleaned_data['sobrenome'])

    def clean_data_nascimento(self):
        return validar_nascimento(self.cleaned_data.get('data_nascimento'))

    def clean_nome_usuario(self):
        nome_usuario = self.cleaned_data["nome_usuario"].strip().lower()
        try:
            UnicodeUsernameValidator()(nome_usuario)
        except forms.ValidationError:
            raise forms.ValidationError(
                'Use letras, números e apenas os caracteres @, ponto, +, hífen ou sublinhado.')
        contas = Usuario.objects.filter(usuario__iexact=nome_usuario)

        if self.instance.pk and self.instance.usuario_id:
            contas = contas.exclude(pk=self.instance.usuario_id)

        autenticacoes = get_user_model().objects.filter(username__iexact=nome_usuario)
        if self.instance.pk and self.instance.usuario.conta_id:
            autenticacoes = autenticacoes.exclude(pk=self.instance.usuario.conta_id)
        if len(nome_usuario) > 150:
            raise forms.ValidationError('Use no máximo 150 caracteres.')
        if contas.exists() or autenticacoes.exists():
            raise forms.ValidationError("Este usuário já está sendo utilizado por outro perfil.")

        return nome_usuario

    def save(self, commit=True):
        perfil = super().save(commit=False)

        if not commit:
            return perfil

        with transaction.atomic():
            if perfil.pk and perfil.usuario_id:
                conta = perfil.usuario
                conta.usuario = self.cleaned_data["nome_usuario"]
                conta.save()
                if conta.conta_id:
                    login = conta.conta
                    login.username = conta.usuario
                    login.is_active = perfil.ativo
                    login.first_name = perfil.nome
                    login.last_name = perfil.sobrenome
                    login.save()
            else:
                conta = Usuario.objects.create(
                    usuario=self.cleaned_data["nome_usuario"],
                    tipo_perfil=self.tipo_perfil,
                )

            perfil.usuario = conta
            perfil.save()
            self.save_m2m()

        return perfil
