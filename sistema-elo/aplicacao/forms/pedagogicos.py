from django.core.validators import MaxLengthValidator
from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.db.models import Q
from aplicacao.forms.idioma import traduzir_opcoes
from aplicacao.models import Atividade, Conteudo, Disciplina, MetaAluno
from aplicacao.forms.base import FormularioBase


class FormularioMeta(FormularioBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['data_inicio'].label = 'Data de referência'
        self.fields['data_inicio'].help_text = 'A semana vai de segunda a domingo; os demais períodos seguem os meses do calendário.'
        self.fields['quantidade_alvo'].help_text = 'Quantidade de atividades aprovadas que o aluno deve alcançar no período.'
        self.fields['descricao'].max_length = 4000
        self.fields['descricao'].validators.append(MaxLengthValidator(4000))
        self.fields['descricao'].widget.attrs['maxlength'] = '4000'
        if not self.instance.pk or self.instance.periodo != MetaAluno.Periodo.PERSONALIZADO:
            self.fields['periodo'].choices = [c for c in MetaAluno.Periodo.choices if c[0] != 'PERSONALIZADO']
            self.fields['periodo'].initial = MetaAluno.Periodo.SEMANAL
            self.fields.pop('data_prazo')
            self.fields['situacao'].choices = [('EM_ANDAMENTO', 'Ativa'), ('CANCELADA', 'Cancelada')]
            self.fields['situacao'].help_text = 'O alcance da meta é calculado automaticamente pelas atividades aprovadas.'

    class Meta:
        model = MetaAluno
        fields = ["aluno", "professor", "titulo", "descricao", "periodo",
                  "quantidade_alvo", "data_inicio", "data_prazo", "situacao"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "data_prazo": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


class FormularioAtividade(FormularioBase):
    novo_conteudo = forms.CharField(
        label='Novo conteúdo curricular', required=False, max_length=100,
        help_text='Se não encontrar o conteúdo na lista, escreva um novo aqui. Ele será cadastrado ao salvar a atividade.',
        widget=forms.TextInput(attrs={'placeholder': 'Ex.: Comunicação e linguagem'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['disciplina'].required = False
        self.fields['disciplina'].label = 'Conteúdo curricular existente'
        self.fields['disciplina'].help_text = 'Selecione um conteúdo existente OU preencha o novo conteúdo abaixo.'
        self.fields['disciplina'].queryset = Disciplina.objects.filter(
            Q(ativo=True) | Q(pk=self.instance.disciplina_id))
        self.fields['data_entrega'].required = True
        self.fields['descricao'].label = 'Descrição detalhada / instruções ao aluno'
        self.fields['descricao'].required = True
        self.fields['descricao'].max_length = 5000
        self.fields['descricao'].validators.append(MaxLengthValidator(5000))
        self.fields['descricao'].widget.attrs['maxlength'] = '5000'
        self.fields['descricao'].help_text = 'Explique o que será realizado e como a atividade deve ser entregue.'
        self.fields['tipo_entrega'].help_text = 'A resposta ou o anexo enviado será avaliado pelo professor.'
        if not self.instance.pk:
            self.fields['tipo_entrega'].initial = Atividade.TipoEntrega.ENVIO
        self.fields['material_apoio'].help_text = 'Opcional: PDF ou imagem (PNG/JPEG) de até 8 MB; acesso restrito aos vinculados.'
        self.fields['material_apoio'].widget = forms.FileInput(attrs={
            'class': 'campo-formulario', 'accept': '.pdf,.png,.jpg,.jpeg'})
        self.fields['meta'].help_text = 'Opcional. Escolha qualquer meta deste aluno, independentemente do conteúdo. As metas por período contam atividades pela data de entrega.'
        self.fields['meta'].empty_label = 'Sem meta específica'
        self.fields['situacao'].help_text = 'Entregas pendentes de aprovação podem ser avaliadas na página Atividades.'
        if self.instance.situacao != 'CONCLUIDA':
            self.fields['situacao'].choices = [('PENDENTE', 'Pendente'), ('CANCELADA', 'Cancelada')]
        aluno = self.data.get('aluno') if self.is_bound else self.instance.aluno_id
        self.fields['meta'].queryset = MetaAluno.objects.filter(aluno_id=aluno) if str(aluno or '').isdigit() else MetaAluno.objects.none()
        for nome in ('aluno', 'meta', 'disciplina'):
            self.fields[nome].widget.attrs['data-' + nome] = ''
        self.fields['novo_conteudo'].widget.attrs['class'] = 'campo-formulario'

    def clean(self):
        dados = super().clean()
        conteudo_atual = dados.get('disciplina')
        nome_novo = ' '.join((dados.get('novo_conteudo') or '').split())
        dados['novo_conteudo'] = nome_novo
        if conteudo_atual and nome_novo:
            self.add_error('novo_conteudo', 'Escolha o conteúdo existente OU informe um novo, não os dois.')
        elif not conteudo_atual and not nome_novo:
            self.add_error('disciplina', 'Selecione um conteúdo ou informe um novo abaixo.')
        elif nome_novo:
            existente = Disciplina.objects.filter(nome__iexact=nome_novo).first()
            if not existente:
                existente = next((item for item in Disciplina.objects.all()
                                 if item.nome.casefold() == nome_novo.casefold()), None)
            if existente:
                if not existente.ativo:
                    self.add_error('novo_conteudo', 'Este conteúdo está inativo. Solicite sua reativação ao gestor.')
                else:
                    dados['disciplina'] = existente
                    dados['novo_conteudo'] = ''
        return dados

    def save(self, commit=True):
        atividade = super().save(commit=False)
        arquivo = self.cleaned_data.get('material_apoio')
        if arquivo is False:
            atividade.material_nome = ''
        elif isinstance(arquivo, UploadedFile):
            atividade.material_nome = arquivo.name[:255]
        nome_novo = self.cleaned_data.get('novo_conteudo')
        if nome_novo and commit:
            try:
                with transaction.atomic():
                    atividade.disciplina, criada = Disciplina.objects.get_or_create(nome=nome_novo)
                    self.conteudo_criado = atividade.disciplina if criada else None
            except IntegrityError:
                atividade.disciplina = Disciplina.objects.get(nome__iexact=nome_novo)
        if commit:
            atividade.save()
            self.save_m2m()
        return atividade

    class Meta:
        model = Atividade
        fields = ['aluno', 'professor', 'disciplina', 'novo_conteudo', 'meta', 'titulo', 'descricao',
                  'tipo_entrega', 'material_apoio', 'data_entrega', 'situacao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Descreva a atividade, as instruções e as adaptações necessárias.'}),
            'data_entrega': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }


class FormularioDisciplina(FormularioBase):
    class Meta:
        model = Disciplina
        fields = ['nome', 'descricao', 'ativo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}


class FormularioConteudo(FormularioBase):
    class Meta:
        model = Conteudo
        fields = ["aluno", "professor", "atividade", "titulo", "descricao", "tipo_conteudo"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4})}
