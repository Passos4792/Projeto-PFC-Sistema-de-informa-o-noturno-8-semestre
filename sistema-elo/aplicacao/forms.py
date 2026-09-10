from django import forms
from django.db import transaction

from .models import Aluno, Atividade, Conteudo, Frequencia, Meta, Professor, Responsavel, Usuario, Vinculo


class FormularioBase(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "campo-formulario")


class FormularioPessoaBase(FormularioBase):
    nome_usuario = forms.CharField(
        label="Usuário",
        max_length=160,
        help_text="Este nome deve ser único em todo o sistema.",
    )
    tipo_perfil = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.usuario_id:
            self.fields["nome_usuario"].initial = self.instance.usuario.usuario

    def clean_nome_usuario(self):
        nome_usuario = self.cleaned_data["nome_usuario"].strip().lower()
        contas = Usuario.objects.filter(usuario__iexact=nome_usuario)

        if self.instance.pk and self.instance.usuario_id:
            contas = contas.exclude(pk=self.instance.usuario_id)

        if contas.exists():
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
                conta.tipo_perfil = self.tipo_perfil
                conta.save()
            else:
                conta = Usuario.objects.create(
                    usuario=self.cleaned_data["nome_usuario"],
                    tipo_perfil=self.tipo_perfil,
                )

            perfil.usuario = conta
            perfil.save()
            self.save_m2m()

        return perfil


class FormularioProfessor(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.PROFESSOR

    class Meta:
        model = Professor
        fields = ["nome", "sobrenome", "nome_usuario", "ativo"]


class FormularioResponsavel(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.RESPONSAVEL

    class Meta:
        model = Responsavel
        fields = ["nome", "sobrenome", "nome_usuario", "ativo"]


class FormularioAluno(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.ALUNO

    class Meta:
        model = Aluno
        fields = ["nome", "sobrenome", "nome_usuario", "data_nascimento", "ativo"]
        widgets = {"data_nascimento": forms.DateInput(attrs={"type": "date"})}


class FormularioVinculo(FormularioBase):
    class Meta:
        model = Vinculo
        fields = ["aluno", "professor", "responsavel", "data_vinculo", "ativo"]
        widgets = {"data_vinculo": forms.DateInput(attrs={"type": "date"})}


class FormularioMeta(FormularioBase):
    class Meta:
        model = Meta
        fields = ["aluno", "professor", "titulo", "descricao", "data_inicio", "data_prazo", "situacao"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_prazo": forms.DateInput(attrs={"type": "date"}),
        }


class FormularioAtividade(FormularioBase):
    class Meta:
        model = Atividade
        fields = ["aluno", "professor", "meta", "titulo", "descricao", "data_entrega", "situacao"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_entrega": forms.DateInput(attrs={"type": "date"}),
        }


class FormularioConteudo(FormularioBase):
    class Meta:
        model = Conteudo
        fields = ["aluno", "professor", "atividade", "titulo", "descricao", "tipo_conteudo"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4})}


class FormularioFrequencia(FormularioBase):
    class Meta:
        model = Frequencia
        fields = ["aluno", "professor", "data_acompanhamento", "compareceu", "observacao"]
        widgets = {"data_acompanhamento": forms.DateInput(attrs={"type": "date"})}
