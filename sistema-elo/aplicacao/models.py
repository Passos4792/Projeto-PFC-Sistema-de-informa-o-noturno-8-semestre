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
