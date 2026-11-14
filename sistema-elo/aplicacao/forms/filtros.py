from django import forms
from aplicacao.servicos.acesso import alunos_com_funcao, alunos_permitidos
from aplicacao.forms.idioma import traduzir_opcoes
from aplicacao.models import MetaAluno, Professor, RegistroAuditoria


class FiltroPainel(forms.Form):
    aluno = forms.ModelChoiceField(queryset=None, required=False, label='Aluno')
    periodo = forms.ChoiceField(required=False, label='Período da meta',
        choices=[('', 'Todos os períodos')] + list(MetaAluno.Periodo.choices))
    inicio = forms.DateField(required=False, label='Entregas a partir de',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fim = forms.DateField(required=False, label='Entregas até',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    busca = forms.CharField(required=False, max_length=100, label='Pesquisar',
        widget=forms.TextInput(attrs={'type': 'search', 'placeholder': 'Buscar meta, aluno ou conteúdo'}))


    def __init__(self, *args, perfil, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['aluno'].queryset = (alunos_com_funcao(perfil, Professor.Funcao.AEE)
            if perfil.tipo_perfil == 'PROFESSOR' else alunos_permitidos(perfil))
        self.fields['aluno'].empty_label = 'Todos os alunos permitidos'
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'

    def clean(self):
        dados = super().clean()
        if dados.get('inicio') and dados.get('fim') and dados['inicio'] > dados['fim']:
            raise forms.ValidationError('A data inicial não pode ser posterior à data final.')
        return dados


class FiltroAprovacoes(forms.Form):
    inicio = forms.DateField(required=False, label='Solicitações de',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'data-filtro-automatico': '', 'class': 'campo-formulario'}))
    fim = forms.DateField(required=False, label='Solicitações até',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'data-filtro-automatico': '', 'class': 'campo-formulario'}))
    ordem = forms.ChoiceField(label='Ordem de chegada', choices=[
        ('recentes', 'Mais recentes primeiro'), ('antigas', 'Mais antigas primeiro')],
        widget=forms.Select(attrs={'data-filtro-automatico': '', 'class': 'campo-formulario'}))

    def clean(self):
        dados = super().clean()
        if dados.get('inicio') and dados.get('fim') and dados['inicio'] > dados['fim']:
            raise forms.ValidationError('A data inicial deve ser anterior ou igual à data final.')
        return dados


class FiltroAuditoria(forms.Form):
    acao = forms.ChoiceField(label='Ação', required=False,
                             choices=[('', 'Todas')] + list(RegistroAuditoria.Acao.choices))
    autor = forms.CharField(label='Usuário responsável', required=False, max_length=150)
    inicio = forms.DateField(label='De', required=False,
                             widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fim = forms.DateField(label='Até', required=False,
                          widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))

    def clean(self):
        dados = super().clean()
        if dados.get('inicio') and dados.get('fim') and dados['inicio'] > dados['fim']:
            raise forms.ValidationError('A data inicial deve ser anterior ou igual à data final.')
        return dados
