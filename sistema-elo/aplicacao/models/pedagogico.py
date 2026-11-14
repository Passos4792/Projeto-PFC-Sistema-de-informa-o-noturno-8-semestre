from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from aplicacao.servicos.arquivos import caminho_entrega, caminho_material, validar_anexo_pedagogico
from aplicacao.servicos.periodos import limites_periodo
from aplicacao.models.usuarios import Aluno, Professor, Usuario


class Disciplina(models.Model):
    nome = models.CharField('Conteúdo', max_length=100, unique=True)
    descricao = models.TextField('Descrição', blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'disciplina'
        ordering = ['nome']
        verbose_name = 'conteúdo curricular'
        verbose_name_plural = 'conteúdos curriculares'

    def clean(self):
        super().clean()
        self.nome = ' '.join(self.nome.split())
        if not self.nome:
            raise ValidationError({'nome': 'Informe o nome do conteúdo.'})
        if Disciplina.objects.filter(nome__iexact=self.nome).exclude(pk=self.pk).exists():
            raise ValidationError({'nome': 'Este conteúdo já está cadastrado.'})

    def __str__(self):
        return self.nome


class MetaAluno(models.Model):
    class Periodo(models.TextChoices):
        SEMANAL = 'SEMANAL', 'Semanal'
        MENSAL = 'MENSAL', 'Mensal'
        TRIMESTRAL = 'TRIMESTRAL', 'Trimestral'
        SEMESTRAL = 'SEMESTRAL', 'Semestral'
        PERSONALIZADO = 'PERSONALIZADO', 'Registro anterior'

    class Situacao(models.TextChoices):
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"

    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="metas")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="metas")
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    data_inicio = models.DateField()
    data_prazo = models.DateField(blank=True, null=True)
    periodo = models.CharField('Período', max_length=20, choices=Periodo.choices, default=Periodo.PERSONALIZADO)
    quantidade_alvo = models.PositiveIntegerField('Atividades a realizar', default=1, validators=[MinValueValidator(1)])
    situacao = models.CharField(
        max_length=20,
        choices=Situacao.choices,
        default=Situacao.EM_ANDAMENTO,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meta"
        ordering = ["data_prazo", "titulo"]
        verbose_name = "meta"
        verbose_name_plural = "metas"
        constraints = [
            models.CheckConstraint(
                condition=Q(data_prazo__isnull=True) | Q(data_prazo__gte=models.F("data_inicio")),
                name="chk_meta_datas",
            ),
            models.CheckConstraint(condition=Q(quantidade_alvo__gte=1), name='meta_alvo_positivo'),
        ]

    def clean(self):
        super().clean()
        if self.data_inicio and self.periodo in ('SEMANAL', 'MENSAL', 'TRIMESTRAL', 'SEMESTRAL'):
            self.data_inicio, self.data_prazo = limites_periodo(self.periodo, self.data_inicio)
        if self.data_inicio and self.data_prazo and self.data_prazo < self.data_inicio:
            raise ValidationError({'data_prazo': 'O prazo não pode ser anterior ao início.'})

    def __str__(self):
        return self.titulo


class Atividade(models.Model):
    class TipoEntrega(models.TextChoices):
        ENVIO = 'ENVIO', 'Resposta ou anexo do aluno'
        REGISTRO = 'REGISTRO', 'Registro presencial (sem envio)'

    class Situacao(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"

    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="atividades")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="atividades")
    meta = models.ForeignKey(MetaAluno, on_delete=models.SET_NULL, blank=True,
                             null=True, related_name="atividades")
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, blank=True, null=True,
                                   related_name='atividades', verbose_name='Conteúdo')
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    tipo_entrega = models.CharField(max_length=12, choices=TipoEntrega.choices, default=TipoEntrega.ENVIO)
    material_apoio = models.FileField(upload_to=caminho_material, blank=True,
                                     validators=[validar_anexo_pedagogico])
    material_nome = models.CharField(max_length=255, blank=True)
    data_entrega = models.DateField(blank=True, null=True)
    situacao = models.CharField(
        max_length=20,
        choices=Situacao.choices,
        default=Situacao.PENDENTE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    concluida_em = models.DateTimeField(blank=True, null=True, editable=False)

    def clean(self):
        super().clean()
        if self.meta_id:
            if self.meta.aluno_id != self.aluno_id:
                raise ValidationError({'meta': 'A meta deve pertencer ao mesmo aluno da atividade.'})
        if self.disciplina_id and not self.disciplina.ativo:
            anterior = Atividade.objects.filter(pk=self.pk).values_list('disciplina_id', flat=True).first()
            if anterior != self.disciplina_id:
                raise ValidationError({'disciplina': 'Escolha um conteúdo ativo.'})
        if self.pk and SolicitacaoConclusao.objects.filter(atividade_id=self.pk, situacao='PENDENTE').exists():
            anterior = Atividade.objects.filter(pk=self.pk).values('aluno_id', 'situacao').first()
            if anterior and (anterior['aluno_id'] != self.aluno_id or anterior['situacao'] != self.situacao):
                raise ValidationError('Analise a solicitação de conclusão antes de mudar o aluno ou a situação.')
        if self.pk and self.situacao == 'CONCLUIDA':
            anterior = Atividade.objects.filter(pk=self.pk).values('aluno_id').first()
            if anterior and anterior['aluno_id'] != self.aluno_id:
                raise ValidationError({'aluno': 'Uma realização confirmada não pode ser transferida para outro aluno.'})

    def save(self, *args, **kwargs):
        if self.situacao == self.Situacao.CONCLUIDA and not self.concluida_em:
            self.concluida_em = timezone.now()
        elif self.situacao != self.Situacao.CONCLUIDA:
            self.concluida_em = None
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'concluida_em'}
        return super().save(*args, **kwargs)

    class Meta:
        db_table = "atividade"
        ordering = ["data_entrega", "titulo"]

    def __str__(self):
        return self.titulo


class SolicitacaoConclusao(models.Model):
    atividade = models.ForeignKey(Atividade, on_delete=models.CASCADE, related_name='solicitacoes')
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='solicitacoes')
    solicitante = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='solicitacoes')
    mensagem = models.CharField('Mensagem', max_length=500, blank=True)
    resposta_aluno = models.TextField('Resposta do aluno', blank=True)
    anexo = models.FileField(upload_to=caminho_entrega, blank=True,
                             validators=[validar_anexo_pedagogico])
    anexo_nome = models.CharField(max_length=255, blank=True)
    situacao = models.CharField(max_length=10, choices=[
        ('PENDENTE', 'Aguardando aprovação'), ('APROVADA', 'Aprovada'), ('RECUSADA', 'Recusada')],
        default='PENDENTE', db_index=True)
    resposta = models.CharField(max_length=500, blank=True)
    professor = models.ForeignKey(Professor, on_delete=models.SET_NULL, null=True, blank=True)
    solicitado_em = models.DateTimeField(auto_now_add=True)
    respondido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'solicitacao_conclusao'
        ordering = ['-solicitado_em', '-pk']


class Conteudo(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="conteudos")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="conteudos")
    atividade = models.ForeignKey(
        Atividade,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="conteudos",
    )
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    tipo_conteudo = models.CharField(max_length=40, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conteudo"
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo


class RelatorioPedagogico(models.Model):
    class Situacao(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        FINALIZADO = 'FINALIZADO', 'Finalizado (interno)'
        PUBLICADO = 'PUBLICADO', 'Disponível à família'

    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='relatorios_pedagogicos')
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name='relatorios_pedagogicos')
    titulo = models.CharField(max_length=180)
    data_referencia = models.DateField(default=timezone.localdate)
    periodo = models.CharField(max_length=80, blank=True)
    relato = models.TextField(help_text='Registro descritivo feito após o atendimento ou período acompanhado.')
    situacao = models.CharField(max_length=12, choices=Situacao.choices, default=Situacao.RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'relatorio_pedagogico'
        ordering = ['-data_referencia', '-pk']

    def __str__(self):
        return self.titulo


class DocumentoPedagogico(models.Model):
    class Tipo(models.TextChoices):
        PEI = 'PEI', 'Plano Educacional Individualizado (PEI)'
        ESTUDO = 'ESTUDO', 'Estudo de Caso'
        PAEE = 'PAEE', 'Plano de Atendimento Educacional Especializado (PAEE)'

    class Situacao(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        FINALIZADO = 'FINALIZADO', 'Finalizado (interno)'
        PUBLICADO = 'PUBLICADO', 'Disponível à família'

    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='documentos_pedagogicos')
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name='documentos_pedagogicos')
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    ano_letivo = models.PositiveSmallIntegerField()
    bimestre = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(4)])
    campos = models.JSONField(default=dict)
    situacao = models.CharField(max_length=12, choices=Situacao.choices, default=Situacao.RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'documento_pedagogico'
        ordering = ['-ano_letivo', 'tipo', '-pk']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.aluno} ({self.ano_letivo})'
