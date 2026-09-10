from django.db import models
from django.db.models import Q


class Usuario(models.Model):
    class TipoPerfil(models.TextChoices):
        PROFESSOR = "PROFESSOR", "Professor"
        ALUNO = "ALUNO", "Aluno"
        RESPONSAVEL = "RESPONSAVEL", "Responsável"

    usuario = models.CharField(max_length=160, unique=True)
    tipo_perfil = models.CharField(max_length=20, choices=TipoPerfil.choices)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "usuario"
        ordering = ["usuario"]
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.usuario


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

    class Meta:
        abstract = True

    @property
    def nome_completo(self):
        return f"{self.nome} {self.sobrenome}"

    def __str__(self):
        return self.nome_completo

    def delete(self, *args, **kwargs):
        conta = self.usuario
        resultado = super().delete(*args, **kwargs)
        conta.delete()
        return resultado


class Professor(PessoaBase):
    class Meta:
        db_table = "professor"
        ordering = ["nome", "sobrenome"]
        verbose_name = "professor"
        verbose_name_plural = "professores"


class Responsavel(PessoaBase):
    class Meta:
        db_table = "responsavel"
        ordering = ["nome", "sobrenome"]
        verbose_name = "responsável"
        verbose_name_plural = "responsáveis"


class Aluno(PessoaBase):
    data_nascimento = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "aluno"
        ordering = ["nome", "sobrenome"]
        verbose_name = "aluno"
        verbose_name_plural = "alunos"


class Vinculo(models.Model):
    aluno = models.OneToOneField(Aluno, on_delete=models.PROTECT, related_name="vinculo")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="vinculos")
    responsavel = models.ForeignKey(Responsavel, on_delete=models.PROTECT, related_name="vinculos")
    data_vinculo = models.DateField()
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "vinculo"
        ordering = ["aluno__nome"]
        verbose_name = "vínculo"
        verbose_name_plural = "vínculos"

    def __str__(self):
        return f"{self.aluno} - {self.professor}"


class Meta(models.Model):
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
        constraints = [
            models.CheckConstraint(
                condition=Q(data_prazo__isnull=True) | Q(data_prazo__gte=models.F("data_inicio")),
                name="chk_meta_datas",
            )
        ]

    def __str__(self):
        return self.titulo


class Atividade(models.Model):
    class Situacao(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"

    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="atividades")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="atividades")
    meta = models.ForeignKey(Meta, on_delete=models.SET_NULL, blank=True, null=True, related_name="atividades")
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

    class Meta:
        db_table = "atividade"
        ordering = ["data_entrega", "titulo"]

    def __str__(self):
        return self.titulo


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


class Frequencia(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="frequencias")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="frequencias")
    data_acompanhamento = models.DateField()
    compareceu = models.BooleanField(default=True)
    observacao = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "frequencia"
        ordering = ["-data_acompanhamento"]
        verbose_name = "frequência"
        verbose_name_plural = "frequências"

    def __str__(self):
        situacao = "Presente" if self.compareceu else "Ausente"
        return f"{self.aluno} - {self.data_acompanhamento} - {situacao}"
