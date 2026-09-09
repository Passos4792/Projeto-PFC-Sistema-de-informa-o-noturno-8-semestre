from django import forms

from .models import Aluno, Atividade, Conteudo, Frequencia, Meta, Professor, Responsavel, Vinculo


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
