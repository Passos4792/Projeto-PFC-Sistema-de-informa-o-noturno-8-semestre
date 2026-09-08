from django import forms

from .models import Professor, Responsavel


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
