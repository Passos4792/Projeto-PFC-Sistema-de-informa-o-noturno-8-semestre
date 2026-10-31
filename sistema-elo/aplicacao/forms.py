#importacoes
from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from .models import RegistroAuditoria


#-------------------------------------------------------------------------------------

#filtros da auditoria
class FiltroAuditoria(forms.Form):
    acao = forms.ChoiceField(label='Ação', required=False,
                             choices=[('', 'Todas')] + list(RegistroAuditoria.Acao.choices))
    autor = forms.CharField(label='Usuário responsável', required=False, max_length=150)
    inicio = forms.DateField(label='De', required=False,
                             widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fim = forms.DateField(label='Até', required=False,
                          widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))

    #-------------------------------------------------------------------------------------

    #validacao dos dados
    def clean(self):
        dados = super().clean()
        if dados.get('inicio') and dados.get('fim') and dados['inicio'] > dados['fim']:
            raise forms.ValidationError('A data inicial deve ser anterior ou igual à data final.')
        return dados


from .models import Aluno, Atividade, Conteudo, Frequencia, Meta, Professor, Responsavel, Usuario, Vinculo
from .models import Disciplina


#-------------------------------------------------------------------------------------

#intervalo e ordem de chegada das solicitacoes
class FiltroAprovacoes(forms.Form):
    inicio = forms.DateField(required=False, label='Solicitações de',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'data-filtro-automatico': '', 'class': 'campo-formulario'}))
    fim = forms.DateField(required=False, label='Solicitações até',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'data-filtro-automatico': '', 'class': 'campo-formulario'}))
    ordem = forms.ChoiceField(label='Ordem de chegada', choices=[
        ('recentes', 'Mais recentes primeiro'), ('antigas', 'Mais antigas primeiro')],
        widget=forms.Select(attrs={'data-filtro-automatico': '', 'class': 'campo-formulario'}))

    #-------------------------------------------------------------------------------------

    #validacao do intervalo de datas
    def clean(self):
        dados = super().clean()
        if dados.get('inicio') and dados.get('fim') and dados['inicio'] > dados['fim']:
            raise forms.ValidationError('A data inicial deve ser anterior ou igual à data final.')
        return dados


#-------------------------------------------------------------------------------------

#formulario base
class FormularioBase(forms.ModelForm):

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "campo-formulario")
            if isinstance(campo, forms.ModelChoiceField):
                campo.empty_label = 'Selecione uma opção' if campo.required else 'Não definido'
        for nome, rotulo in {'titulo': 'Título', 'descricao': 'Descrição', 'situacao': 'Situação'}.items():
            if nome in self.fields:
                self.fields[nome].label = rotulo


#-------------------------------------------------------------------------------------

#formulario pessoa base
class FormularioPessoaBase(FormularioBase):
    nome_usuario = forms.CharField(
        label="Usuário",
        max_length=160,
        help_text="Este nome deve ser único em todo o sistema.",
    )
    tipo_perfil = None

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.usuario_id:
            self.fields["nome_usuario"].initial = self.instance.usuario.usuario

    #-------------------------------------------------------------------------------------

    #validacao do nome de usuario
    def clean_nome_usuario(self):
        nome_usuario = self.cleaned_data["nome_usuario"].strip().lower()
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

    #-------------------------------------------------------------------------------------

    #salvar registro
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


#-------------------------------------------------------------------------------------

#formulario professor
class FormularioProfessor(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.PROFESSOR

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Professor
        fields = ["nome", "sobrenome", "nome_usuario", "ativo"]


#-------------------------------------------------------------------------------------

#formulario responsavel
class FormularioResponsavel(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.RESPONSAVEL

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Responsavel
        fields = ["nome", "sobrenome", "nome_usuario", "ativo"]


#-------------------------------------------------------------------------------------

#formulario aluno
class FormularioAluno(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.ALUNO

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Aluno
        fields = ["nome", "sobrenome", "nome_usuario", "data_nascimento", "ativo"]
        widgets = {"data_nascimento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


#-------------------------------------------------------------------------------------

#formulario vinculo
class FormularioVinculo(FormularioBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Vinculo
        fields = ["aluno", "professor", "responsavel", "data_vinculo", "ativo"]
        widgets = {"data_vinculo": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


#-------------------------------------------------------------------------------------

#formulario meta
class FormularioMeta(FormularioBase):

    #-------------------------------------------------------------------------------------

    #campos e orientacoes dos periodos de metas
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_inicio'].label = 'Data de referência'
        self.fields['data_inicio'].help_text = 'A semana vai de segunda a domingo; os demais períodos seguem os meses do calendário.'
        self.fields['disciplina'].help_text = 'Deixe em branco para contar atividades de todos os conteúdos.'
        self.fields['disciplina'].empty_label = 'Todos os conteúdos'
        self.fields['quantidade_alvo'].help_text = 'Quantidade de atividades aprovadas que o aluno deve alcançar no período.'
        self.fields['disciplina'].queryset = Disciplina.objects.filter(ativo=True)
        if self.instance.disciplina_id:
            self.fields['disciplina'].queryset = Disciplina.objects.filter(
                Q(ativo=True) | Q(pk=self.instance.disciplina_id))
        if not self.instance.pk or self.instance.periodo != Meta.Periodo.PERSONALIZADO:
            self.fields['periodo'].choices = [c for c in Meta.Periodo.choices if c[0] != 'PERSONALIZADO']
            self.fields['periodo'].initial = Meta.Periodo.SEMANAL
            self.fields.pop('data_prazo')
            self.fields['situacao'].choices = [('EM_ANDAMENTO', 'Ativa'), ('CANCELADA', 'Cancelada')]
            self.fields['situacao'].help_text = 'O alcance da meta é calculado automaticamente pelas atividades aprovadas.'

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Meta
        fields = ["aluno", "professor", "titulo", "descricao", "periodo", "disciplina",
                  "quantidade_alvo", "data_inicio", "data_prazo", "situacao"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "data_prazo": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


#-------------------------------------------------------------------------------------

#formulario atividade
class FormularioAtividade(FormularioBase):

    #-------------------------------------------------------------------------------------

    #conteudo obrigatorio e metas limitadas ao aluno selecionado
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        self.fields['disciplina'].required = True
        self.fields['data_entrega'].required = True
        self.fields['disciplina'].queryset = Disciplina.objects.filter(Q(ativo=True) | Q(pk=self.instance.disciplina_id))
        self.fields['descricao'].label = 'Descrição / orientações'
        self.fields['meta'].help_text = 'Opcional. As metas por período também contam atividades automaticamente pela data de entrega.'
        self.fields['meta'].empty_label = 'Sem meta específica'
        self.fields['situacao'].help_text = 'Solicitações dos alunos e responsáveis são avaliadas na página Aprovações.'
        if self.instance.situacao != 'CONCLUIDA':
            self.fields['situacao'].choices = [('PENDENTE', 'Pendente'), ('CANCELADA', 'Cancelada')]
        aluno = self.data.get('aluno') if self.is_bound else self.instance.aluno_id
        self.fields['meta'].queryset = Meta.objects.filter(aluno_id=aluno) if str(aluno or '').isdigit() else Meta.objects.none()
        for nome in ('aluno', 'meta', 'disciplina'):
            self.fields[nome].widget.attrs['data-' + nome] = ''

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Atividade
        fields = ["aluno", "professor", "disciplina", "meta", "titulo", "descricao", "data_entrega", "situacao"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_entrega": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


#-------------------------------------------------------------------------------------

#formulario conteudo
class FormularioConteudo(FormularioBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Conteudo
        fields = ["aluno", "professor", "atividade", "titulo", "descricao", "tipo_conteudo"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4})}


#-------------------------------------------------------------------------------------

#formulario frequencia
class FormularioFrequencia(FormularioBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Frequencia
        fields = ["aluno", "professor", "data_acompanhamento", "compareceu", "observacao"]
        widgets = {"data_acompanhamento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


#-------------------------------------------------------------------------------------

#cadastro do catalogo de conteudos
class FormularioDisciplina(FormularioBase):
    class Meta:
        model = Disciplina
        fields = ['nome', 'descricao', 'ativo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}


#-------------------------------------------------------------------------------------

#percentual minimo de atividades realizadas por aluno
class FormularioFrequenciaMinima(forms.Form):
    aluno = forms.ModelChoiceField(queryset=Aluno.objects.all(), label='Aluno')
    frequencia_minima = forms.DecimalField(label='Frequência mínima (%)', max_digits=5,
        decimal_places=2, min_value=0, max_value=100, required=False,
        help_text='De 0 a 100. Deixe vazio para remover o mínimo. A realização depende da aprovação do professor.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'
#-------------------------------------------------------------------------------------
