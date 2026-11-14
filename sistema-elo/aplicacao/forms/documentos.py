from django import forms
from django.core.validators import MaxLengthValidator
from django.utils import timezone
from aplicacao.forms.idioma import traduzir_opcoes
from aplicacao.models import Aluno, RelatorioPedagogico


CAMPOS_DOCUMENTOS = {
    'PEI': [
        ('conteudos', 'Conteúdos e habilidades curriculares para o bimestre'),
        ('estrategias', 'Estratégias, intervenções e recursos de acessibilidade'),
        ('avaliacao', 'Instrumentos de acompanhamento individualizado da aprendizagem'),
        ('materiais', 'Vídeos, livros, jogos e outras atividades de apoio'),
        ('observacoes', 'Observações de acompanhamento e ajustes planejados'),
    ],
    'ESTUDO': [
        ('escola_serie', 'Escola, ano e turma'),
        ('interesses', 'O estudante gosta da escola? Quais são seus interesses e amizades?'),
        ('participacao', 'Participação, interação e atividades mais desafiadoras'),
        ('comunicacao', 'Como expressa necessidades, desejos e interesses?'),
        ('apoios', 'Apoios disponíveis, necessários e recursos de acessibilidade'),
        ('habilidades', 'Habilidades, potencialidades e desafios de aprendizagem'),
        ('barreiras', 'Barreiras na escola que dificultam a participação'),
        ('familia', 'Informações e expectativas compartilhadas pela família'),
        ('leitura_escrita', 'Observações de leitura, escrita e alfabetização'),
        ('matematica', 'Observações de conhecimentos matemáticos'),
        ('sensorial', 'Observações sobre sensorialidade, interesses e autorregulação'),
        ('motricidade', 'Desenvolvimento motor, autonomia e comunicação alternativa'),
        ('sintese', 'Síntese do estudo e necessidades educacionais identificadas'),
    ],
    'PAEE': [
        ('sintese_estudo', 'Síntese das informações do Estudo de Caso'),
        ('apoios_servicos', 'Apoios, recursos e serviços necessários'),
        ('justificativa_apoio', 'Justificativa para os apoios indicados'),
        ('habilidades', 'Habilidades a desenvolver no AEE'),
        ('estrategias', 'Estratégias do AEE e recursos de acessibilidade'),
        ('planejamento_1', 'Planejamento do 1º bimestre'),
        ('planejamento_2', 'Planejamento do 2º bimestre'),
        ('planejamento_3', 'Planejamento do 3º bimestre'),
        ('planejamento_4', 'Planejamento do 4º bimestre'),
        ('tecnologias', 'Materiais pedagógicos e tecnologias assistivas'),
        ('observacoes', 'Observações e revisão do plano'),
    ],
}


class FormularioRelatorio(forms.ModelForm):
    class Meta:
        model = RelatorioPedagogico
        fields = ['aluno', 'titulo', 'data_referencia', 'periodo', 'relato']
        widgets = {
            'data_referencia': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'relato': forms.Textarea(attrs={'rows': 13, 'placeholder': 'Registre livremente o trabalho realizado, as observações, os avanços e os encaminhamentos...'}),
        }

    def __init__(self, *args, alunos, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['aluno'].queryset = alunos
        if not self.instance.pk:
            self.fields['data_referencia'].initial = timezone.localdate()
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', 'campo-formulario')
        self.fields['relato'].label = 'Relato pedagógico livre (após o atendimento)'
        self.fields['relato'].max_length = 12000
        self.fields['relato'].validators.append(MaxLengthValidator(12000))
        self.fields['relato'].widget.attrs['maxlength'] = '12000'
        self.fields['periodo'].required = False
        self.fields['periodo'].help_text = 'Ex.: 3º bimestre, semana de 10/11 ou acompanhamento mensal.'

    def clean_data_referencia(self):
        data = self.cleaned_data.get('data_referencia')
        if data and data > timezone.localdate():
            raise forms.ValidationError('O relatório não pode ter uma data de atendimento futura.')
        return data


class FormularioCabecalhoDocumento(forms.Form):
    aluno = forms.ModelChoiceField(queryset=Aluno.objects.none(), label='Aluno')
    ano_letivo = forms.IntegerField(min_value=2020, max_value=2100, label='Ano letivo')
    bimestre = forms.TypedChoiceField(required=False, coerce=int,
       empty_value=None, label='Bimestre (para PEI)', choices=[('', 'Sem bimestre'), (1, '1º bimestre'), (2, '2º bimestre'), (3, '3º bimestre'), (4, '4º bimestre')])

    def __init__(self, *args, alunos, tipo, valores=None, **kwargs):
        super().__init__(*args, **kwargs)
        traduzir_opcoes(self)
        self.fields['aluno'].queryset = alunos
        self.tipo = tipo
        self.fields['ano_letivo'].initial = timezone.localdate().year
        if tipo == 'PEI':
            self.fields['bimestre'].required = True
        else:
            self.fields.pop('bimestre')
        valores = valores or {}
        for chave, descricao in CAMPOS_DOCUMENTOS[tipo]:
            self.fields[chave] = forms.CharField(
                label=descricao, required=False, max_length=4000, initial=valores.get(chave, ''),
                widget=forms.Textarea(attrs={'rows': 4, 'class': 'campo-formulario'}))
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', 'campo-formulario')

    def respostas(self):
        return {chave: self.cleaned_data[chave] for chave, _ in CAMPOS_DOCUMENTOS[self.tipo]}
