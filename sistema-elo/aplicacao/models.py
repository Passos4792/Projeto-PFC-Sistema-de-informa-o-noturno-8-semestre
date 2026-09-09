from django.db import models


class PessoaBase(models.Model):
    nome = models.CharField(max_length=80)
    sobrenome = models.CharField(max_length=120)
    usuario = models.CharField(max_length=160, unique=True)
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
