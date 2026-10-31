#importacoes
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


#-------------------------------------------------------------------------------------

#registros de auditoria
class RegistroAuditoria(models.Model):

    #-------------------------------------------------------------------------------------

    #tipos de acao
    class Acao(models.TextChoices):
        LOGIN = 'LOGIN', 'Entrada no sistema'
        SAIDA = 'SAIDA', 'Saída do sistema'
        FALHA_LOGIN = 'FALHA_LOGIN', 'Falha no login'
        BLOQUEIO_LOGIN = 'BLOQUEIO_LOGIN', 'Login bloqueado'
        ACESSO_NEGADO = 'ACESSO_NEGADO', 'Acesso negado'
        CRIACAO = 'CRIACAO', 'Cadastro criado'
        EDICAO = 'EDICAO', 'Cadastro alterado'
        EXCLUSAO = 'EXCLUSAO', 'Cadastro excluído'
        PERMISSAO = 'PERMISSAO', 'Permissão definida ou alterada'
        SENHA = 'SENHA', 'Senha definida ou redefinida'
        DOCUMENTOS = 'DOCUMENTOS', 'Aceite de termos e privacidade'
        CONSULTA = 'CONSULTA', 'Consulta de dados'
        SOLICITACAO = 'SOLICITACAO', 'Conclusão solicitada'
        APROVACAO = 'APROVACAO', 'Conclusão aprovada'
        RECUSA = 'RECUSA', 'Conclusão recusada'
        FREQUENCIA = 'FREQUENCIA', 'Frequência mínima alterada'

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    autor_id_original = models.PositiveBigIntegerField(null=True, blank=True)
    autor = models.CharField(max_length=150)
    acao = models.CharField(max_length=25, choices=Acao.choices, db_index=True)
    entidade = models.CharField(max_length=80, blank=True)
    objeto_id = models.CharField(max_length=64, blank=True)
    detalhes = models.CharField(max_length=500, blank=True)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = 'registro_auditoria'
        ordering = ['-criado_em', '-pk']
        verbose_name = 'registro de auditoria'
        verbose_name_plural = 'registros de auditoria'


#-------------------------------------------------------------------------------------

#controle de tentativas de login
class LimiteLogin(models.Model):
    chave = models.CharField(max_length=64, unique=True)
    falhas = models.PositiveIntegerField(default=0)
    inicio = models.DateTimeField()
    bloqueado_ate = models.DateTimeField(null=True, blank=True)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = 'limite_login'


#-------------------------------------------------------------------------------------

#usuarios
class Usuario(models.Model):

    #-------------------------------------------------------------------------------------

    #tipos de perfil
    class TipoPerfil(models.TextChoices):
        PROFESSOR = "PROFESSOR", "Professor"
        ALUNO = "ALUNO", "Aluno"
        RESPONSAVEL = "RESPONSAVEL", "Responsável"

    conta = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="perfil_elo")
    professor_principal = models.BooleanField(default=False)
    troca_senha_obrigatoria = models.BooleanField(default=True)

    # Registro do aceite das versões vigentes dos documentos legais.
    documentos_aceitos_em = models.DateTimeField(null=True, blank=True)
    versao_termos_aceita = models.CharField(max_length=20, blank=True)
    versao_privacidade_ciente = models.CharField(max_length=20, blank=True)

    usuario = models.CharField(max_length=160, unique=True)
    tipo_perfil = models.CharField(max_length=20, choices=TipoPerfil.choices)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "usuario"
        ordering = ["usuario"]
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    #-------------------------------------------------------------------------------------

    #representacao do registro
    def __str__(self):
        return self.usuario


#-------------------------------------------------------------------------------------

#dados comuns das pessoas
class PessoaBase(models.Model):
    nome = models.CharField(max_length=80)
    sobrenome = models.CharField(max_length=120)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name="%(class)s_perfil",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        abstract = True

    #-------------------------------------------------------------------------------------

    #nome completo
    @property
    def nome_completo(self):
        return f"{self.nome} {self.sobrenome}"

    #-------------------------------------------------------------------------------------

    #representacao do registro
    def __str__(self):
        return self.nome_completo

    #-------------------------------------------------------------------------------------

    #excluir registro
    def delete(self, *args, **kwargs):
        conta = self.usuario
        resultado = super().delete(*args, **kwargs)
        conta.delete()
        return resultado


#-------------------------------------------------------------------------------------

#professores
class Professor(PessoaBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "professor"
        ordering = ["nome", "sobrenome"]
        verbose_name = "professor"
        verbose_name_plural = "professores"


#-------------------------------------------------------------------------------------

#responsaveis
class Responsavel(PessoaBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "responsavel"
        ordering = ["nome", "sobrenome"]
        verbose_name = "responsável"
        verbose_name_plural = "responsáveis"


#-------------------------------------------------------------------------------------

#alunos
class Aluno(PessoaBase):
    data_nascimento = models.DateField(blank=True, null=True)
    frequencia_minima = models.DecimalField(
        'Frequência mínima (%)', max_digits=5, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)])

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "aluno"
        ordering = ["nome", "sobrenome"]
        verbose_name = "aluno"
        verbose_name_plural = "alunos"
        constraints = [models.CheckConstraint(
            condition=Q(frequencia_minima__isnull=True) | Q(frequencia_minima__gte=0, frequencia_minima__lte=100),
            name='aluno_frequencia_entre_0_100')]


#-------------------------------------------------------------------------------------

#catalogo de conteudos curriculares compartilhado pelas atividades
class Disciplina(models.Model):
    nome = models.CharField('Conteúdo', max_length=100, unique=True)
    descricao = models.TextField('Descrição', blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = 'disciplina'
        ordering = ['nome']
        verbose_name = 'conteúdo curricular'
        verbose_name_plural = 'conteúdos curriculares'

    #-------------------------------------------------------------------------------------

    #validacao do nome sem repeticoes de maiusculas e espacos
    def clean(self):
        super().clean()
        self.nome = ' '.join(self.nome.split())
        if not self.nome:
            raise ValidationError({'nome': 'Informe o nome do conteúdo.'})
        if Disciplina.objects.filter(nome__iexact=self.nome).exclude(pk=self.pk).exists():
            raise ValidationError({'nome': 'Este conteúdo já está cadastrado.'})

    #-------------------------------------------------------------------------------------

    #representacao do registro
    def __str__(self):
        return self.nome


#-------------------------------------------------------------------------------------

#vinculos
class Vinculo(models.Model):
    aluno = models.OneToOneField(Aluno, on_delete=models.PROTECT, related_name="vinculo")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="vinculos")
    responsavel = models.ForeignKey(Responsavel, on_delete=models.PROTECT, related_name="vinculos")
    data_vinculo = models.DateField()
    ativo = models.BooleanField(default=True)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "vinculo"
        ordering = ["aluno__nome"]
        verbose_name = "vínculo"
        verbose_name_plural = "vínculos"

    #-------------------------------------------------------------------------------------

    #representacao do registro
    def __str__(self):
        return f"{self.aluno} - {self.professor}"


#-------------------------------------------------------------------------------------

#metas
class Meta(models.Model):

    #-------------------------------------------------------------------------------------

    #periodos do acompanhamento
    class Periodo(models.TextChoices):
        SEMANAL = 'SEMANAL', 'Semanal'
        MENSAL = 'MENSAL', 'Mensal'
        TRIMESTRAL = 'TRIMESTRAL', 'Trimestral'
        SEMESTRAL = 'SEMESTRAL', 'Semestral'
        PERSONALIZADO = 'PERSONALIZADO', 'Registro anterior'

    #-------------------------------------------------------------------------------------

    #situacoes disponiveis
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
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, blank=True, null=True,
                                   related_name='metas', verbose_name='Conteúdo')
    situacao = models.CharField(
        max_length=20,
        choices=Situacao.choices,
        default=Situacao.EM_ANDAMENTO,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "meta"
        ordering = ["data_prazo", "titulo"]
        constraints = [
            models.CheckConstraint(
                condition=Q(data_prazo__isnull=True) | Q(data_prazo__gte=models.F("data_inicio")),
                name="chk_meta_datas",
            ),
            models.CheckConstraint(condition=Q(quantidade_alvo__gte=1), name='meta_alvo_positivo'),
        ]

    #-------------------------------------------------------------------------------------

    #validacao do periodo e da quantidade planejada
    def clean(self):
        super().clean()
        if self.data_inicio and self.periodo in ('SEMANAL', 'MENSAL', 'TRIMESTRAL', 'SEMESTRAL'):
            from .periodos import limites_periodo
            self.data_inicio, self.data_prazo = limites_periodo(self.periodo, self.data_inicio)
        if self.data_inicio and self.data_prazo and self.data_prazo < self.data_inicio:
            raise ValidationError({'data_prazo': 'O prazo não pode ser anterior ao início.'})

    #-------------------------------------------------------------------------------------

    #representacao do registro
    def __str__(self):
        return self.titulo


#-------------------------------------------------------------------------------------

#atividades
class Atividade(models.Model):

    #-------------------------------------------------------------------------------------

    #situacoes disponiveis
    class Situacao(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"

    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="atividades")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="atividades")
    meta = models.ForeignKey(Meta, on_delete=models.SET_NULL, blank=True,
                             null=True, related_name="atividades")
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, blank=True, null=True,
                                   related_name='atividades', verbose_name='Conteúdo')
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    data_entrega = models.DateField(blank=True, null=True)
    situacao = models.CharField(
        max_length=20,
        choices=Situacao.choices,
        default=Situacao.PENDENTE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    concluida_em = models.DateTimeField(blank=True, null=True, editable=False)

    #-------------------------------------------------------------------------------------

    #consistencia entre aluno, conteudo e meta opcional
    def clean(self):
        super().clean()
        if self.meta_id:
            if self.meta.aluno_id != self.aluno_id:
                raise ValidationError({'meta': 'A meta deve pertencer ao mesmo aluno da atividade.'})
            if self.meta.disciplina_id and self.meta.disciplina_id != self.disciplina_id:
                raise ValidationError({'disciplina': 'Selecione o conteúdo definido na meta.'})
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

    #-------------------------------------------------------------------------------------

    #registro da conclusao validada pelo professor
    def save(self, *args, **kwargs):
        if self.situacao == self.Situacao.CONCLUIDA and not self.concluida_em:
            self.concluida_em = timezone.now()
        elif self.situacao != self.Situacao.CONCLUIDA:
            self.concluida_em = None
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'concluida_em'}
        return super().save(*args, **kwargs)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "atividade"
        ordering = ["data_entrega", "titulo"]

    #-------------------------------------------------------------------------------------

    #representacao do registro
    def __str__(self):
        return self.titulo


#-------------------------------------------------------------------------------------

#solicitacoes de conclusao e decisoes do professor
class SolicitacaoConclusao(models.Model):
    atividade = models.ForeignKey(Atividade, on_delete=models.CASCADE, related_name='solicitacoes')
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='solicitacoes')
    solicitante = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='solicitacoes')
    mensagem = models.CharField('Mensagem', max_length=500, blank=True)
    situacao = models.CharField(max_length=10, choices=[
        ('PENDENTE', 'Aguardando aprovação'), ('APROVADA', 'Aprovada'), ('RECUSADA', 'Recusada')],
        default='PENDENTE', db_index=True)
    resposta = models.CharField(max_length=500, blank=True)
    professor = models.ForeignKey(Professor, on_delete=models.SET_NULL, null=True, blank=True)
    solicitado_em = models.DateTimeField(auto_now_add=True)
    respondido_em = models.DateTimeField(null=True, blank=True)

    #-------------------------------------------------------------------------------------

    #historico das solicitacoes de conclusao
    class Meta:
        db_table = 'solicitacao_conclusao'
        ordering = ['-solicitado_em', '-pk']


#-------------------------------------------------------------------------------------

#registros de conteudos da versao anterior, preservados para consulta
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

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "conteudo"
        ordering = ["titulo"]

    #-------------------------------------------------------------------------------------

    #representacao do registro
    def __str__(self):
        return self.titulo


#-------------------------------------------------------------------------------------

#conexao e credenciais da conta Google
class ConexaoGoogle(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='conexao_google')
    identidade = models.CharField(max_length=64)
    credenciais = models.TextField()
    atualizado_em = models.DateTimeField(auto_now=True)


    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = 'conexao_google'


#-------------------------------------------------------------------------------------

#registro dos eventos sincronizados com o Google
class SincronizacaoGoogle(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    atividade = models.ForeignKey(Atividade, on_delete=models.CASCADE)
    identidade = models.CharField(max_length=64)
    evento_id = models.CharField(max_length=128)
    sincronizado_em = models.DateTimeField(null=True, blank=True)


    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = 'sincronizacao_google'
        constraints = [models.UniqueConstraint(
            fields=['usuario', 'atividade', 'identidade'], name='google_evento_usuario_atividade')]


#-------------------------------------------------------------------------------------

#frequencias
class Frequencia(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="frequencias")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="frequencias")
    data_acompanhamento = models.DateField()
    compareceu = models.BooleanField(default=True)
    observacao = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "frequencia"
        ordering = ["-data_acompanhamento"]
        verbose_name = "frequência"
        verbose_name_plural = "frequências"

    #-------------------------------------------------------------------------------------

    #representacao do registro
    def __str__(self):
        situacao = "Presente" if self.compareceu else "Ausente"
        return f"{self.aluno} - {self.data_acompanhamento} - {situacao}"
#-------------------------------------------------------------------------------------
