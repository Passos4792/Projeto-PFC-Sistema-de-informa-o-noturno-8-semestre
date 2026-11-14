from django.conf import settings
from datetime import date
from django.db import models
from django.utils import timezone


class Usuario(models.Model):
    class TipoPerfil(models.TextChoices):
        PROFESSOR = "PROFESSOR", "Professor"
        ALUNO = "ALUNO", "Aluno"
        RESPONSAVEL = "RESPONSAVEL", "Responsável"

    conta = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="perfil_elo")
    gestor = models.BooleanField(default=False)
    troca_senha_obrigatoria = models.BooleanField(default=True)
    foto_perfil = models.FileField(upload_to="fotos_perfil/", blank=True)

    documentos_aceitos_em = models.DateTimeField(null=True, blank=True)
    versao_termos_aceita = models.CharField(max_length=20, blank=True)
    versao_privacidade_ciente = models.CharField(max_length=20, blank=True)

    usuario = models.CharField(max_length=160, unique=True)
    tipo_perfil = models.CharField(max_length=20, choices=TipoPerfil.choices)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "usuario"
        ordering = ["usuario"]
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def save(self, *args, **kwargs):
        self.usuario = (self.usuario or '').strip().lower()
        super().save(*args, **kwargs)

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
    data_nascimento = models.DateField(blank=True, null=True)
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
        perfil = self.usuario
        login = perfil.conta
        resultado = super().delete(*args, **kwargs)
        perfil.delete()
        if login is not None:
            login.delete()
        return resultado


class Professor(PessoaBase):
    class Funcao(models.TextChoices):
        AEE = 'AEE', 'Professor do AEE'
        REGENTE = 'REGENTE', 'Professor regente'
        ACOMPANHANTE = 'ACOMPANHANTE', 'Professor acompanhante'

    funcao = models.CharField(max_length=15, choices=Funcao.choices, default=Funcao.AEE)

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
    inativado_em = models.DateTimeField(null=True, blank=True, editable=False, db_index=True)

    @property
    def documentos_disponiveis_ate(self):
        if self.ativo or not self.inativado_em:
            return None
        inicio = timezone.localtime(self.inativado_em).date()
        try:
            return inicio.replace(year=inicio.year + 5)
        except ValueError:
            return date(inicio.year + 5, 2, 28)

    @property
    def documentos_em_prazo(self):
        limite = self.documentos_disponiveis_ate
        return bool(not self.ativo and limite and timezone.localdate() <= limite)

    def save(self, *args, **kwargs):
        anterior = (type(self).objects.filter(pk=self.pk).values_list('ativo', 'inativado_em').first()
                    if self.pk else None)
        if self.ativo:
            if anterior is None or not anterior[0]:
                self.inativado_em = None
        elif anterior is None or anterior[0] or anterior[1] is None:
            self.inativado_em = timezone.now()
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'inativado_em'}
        super().save(*args, **kwargs)

    class Meta:
        db_table = "aluno"
        ordering = ["nome", "sobrenome"]
        verbose_name = "aluno"
        verbose_name_plural = "alunos"
