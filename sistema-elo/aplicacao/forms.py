from django import forms

from .models import Aluno, Professor, Responsavel, Vinculo


class FormularioBase(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "campo-formulario")


class FormularioProfessor(FormularioBase):
    class Meta:
        model = Professor
        fields = ["nome", "sobrenome", "usuario", "ativo"]


class FormularioResponsavel(FormularioBase):
    class Meta:
        model = Responsavel
        fields = ["nome", "sobrenome", "usuario", "ativo"]


class FormularioAluno(FormularioBase):
    class Meta:
        model = Aluno
        fields = ["nome", "sobrenome", "usuario", "data_nascimento", "ativo"]
        widgets = {"data_nascimento": forms.DateInput(attrs={"type": "date"})}


class FormularioVinculo(FormularioBase):
    class Meta:
        model = Vinculo
        fields = ["aluno", "professor", "responsavel", "data_vinculo", "ativo"]
        widgets = {"data_vinculo": forms.DateInput(attrs={"type": "date"})}
