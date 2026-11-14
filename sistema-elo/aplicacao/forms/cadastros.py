from django import forms
from django.utils import timezone
from aplicacao.forms.idioma import traduzir_opcoes
from aplicacao.models import Aluno, Professor, Responsavel, Usuario, Vinculo, VinculoFamiliar, VinculoProfissional
from aplicacao.forms.base import FormularioBase, FormularioPessoaBase


class FormularioProfessor(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.PROFESSOR

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['funcao'].label = 'Função de referência do cadastro'
        self.fields['funcao'].help_text = (
            'A função efetiva e as permissões são definidas separadamente para cada aluno '
            'na ficha Vínculos dos alunos.')

    class Meta:
        model = Professor
        fields = ["nome", "sobrenome", "nome_usuario", "funcao", "data_nascimento", "ativo"]
        widgets = {"data_nascimento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class FormularioResponsavel(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.RESPONSAVEL

    class Meta:
        model = Responsavel
        fields = ["nome", "sobrenome", "nome_usuario", "data_nascimento", "ativo"]
        widgets = {"data_nascimento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class FormularioAluno(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.ALUNO

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['nome_usuario'].label = 'Identificador interno do aluno (sem e-mail)'
        self.fields['nome_usuario'].help_text = 'Use um identificador único. Não será criada senha nem login próprio.'

    class Meta:
        model = Aluno
        fields = ["nome", "sobrenome", "nome_usuario", "data_nascimento", "ativo"]
        widgets = {"data_nascimento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class FormularioVinculo(FormularioBase):
    class Meta:
        model = Vinculo
        fields = ["aluno", "professor", "responsavel", "data_vinculo", "ativo"]
        widgets = {"data_vinculo": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class FichaVinculos(forms.Form):
    aluno = forms.ModelChoiceField(label='Aluno', queryset=Aluno.objects.none())
    responsavel = forms.ModelChoiceField(label='Responsável principal', queryset=Responsavel.objects.none())
    professor_aee = forms.ModelChoiceField(label='Professor AEE', queryset=Professor.objects.none())
    professor_regente = forms.ModelChoiceField(label='Professor regente', queryset=Professor.objects.none(), required=False)
    professor_acompanhante = forms.ModelChoiceField(label='Professor acompanhante', queryset=Professor.objects.none(), required=False)
    data_vinculo = forms.DateField(label='Data de início', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    ativo = forms.BooleanField(label='Vínculo ativo', required=False, initial=True)
    mesclar_perfis = forms.BooleanField(
        label='Mesclar perfis — permitir que este responsável use a área do aluno',
        required=False, initial=False,
        help_text='Ative apenas quando a criança precisar do adulto para acessar e enviar atividades. Os documentos continuam exclusivos do responsável.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['aluno'].queryset = Aluno.objects.filter(ativo=True).order_by('nome', 'sobrenome')
        self.fields['responsavel'].queryset = Responsavel.objects.filter(ativo=True).order_by('nome', 'sobrenome')
        for nome in ('professor_aee', 'professor_regente', 'professor_acompanhante'):
            self.fields[nome].queryset = Professor.objects.filter(ativo=True).order_by('nome', 'sobrenome')
            self.fields[nome].help_text = 'A função vale apenas para este estudante; o mesmo profissional pode ter outra função com outro aluno.'
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', 'campo-formulario')
        self.fields['data_vinculo'].initial = timezone.localdate()


class FormularioVinculoProfissional(forms.ModelForm):
    class Meta:
        model = VinculoProfissional
        fields = ['aluno', 'professor', 'funcao', 'data_inicio', 'data_fim', 'ativo']
        widgets = {'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
                   'data_fim': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['professor'].queryset = Professor.objects.filter(ativo=True)
        self.fields['funcao'].required = False
        self.fields['aluno'].queryset = Aluno.objects.filter(ativo=True)
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'campo-formulario')

    def clean(self):
        dados = super().clean()
        if not dados.get('funcao') and dados.get('professor'):
            dados['funcao'] = dados['professor'].funcao
        return dados

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.full_clean()
        if commit:
            obj.save()
        return obj


class FormularioVinculoFamiliar(forms.ModelForm):
    class Meta:
        model = VinculoFamiliar
        fields = ['aluno', 'responsavel', 'mesclar_perfis', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['responsavel'].queryset = Responsavel.objects.filter(ativo=True)
        self.fields['aluno'].queryset = Aluno.objects.filter(ativo=True)
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'campo-formulario')
