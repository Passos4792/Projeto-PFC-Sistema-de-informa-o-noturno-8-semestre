from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from aplicacao.models.usuarios import Aluno, Professor, Responsavel


class Vinculo(models.Model):
    aluno = models.OneToOneField(Aluno, on_delete=models.PROTECT, related_name="vinculo")
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name="vinculos")
    responsavel = models.ForeignKey(Responsavel, on_delete=models.PROTECT, related_name="vinculos")
    data_vinculo = models.DateField()
    mesclar_perfis = models.BooleanField(default=False, verbose_name="Mesclar acesso com o responsável")
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "vinculo"
        ordering = ["aluno__nome"]
        verbose_name = "vínculo"
        verbose_name_plural = "vínculos"

    def __str__(self):
        return f"{self.aluno} - {self.professor}"


class VinculoProfissional(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='vinculos_profissionais')
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, related_name='atribuicoes')
    funcao = models.CharField(max_length=15, choices=Professor.Funcao.choices)
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'vinculo_profissional'
        ordering = ['aluno__nome', 'professor__nome']
        constraints = [models.UniqueConstraint(fields=['aluno', 'professor', 'funcao'], name='elo_vinculo_profissional_unico')]

    def clean(self):
        if self.data_fim and self.data_inicio and self.data_fim < self.data_inicio:
            raise ValidationError({'data_fim': 'A data final não pode anteceder a inicial.'})

    def __str__(self):
        return f'{self.aluno} — {self.professor} ({self.get_funcao_display()})'


class VinculoFamiliar(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='vinculos_familiares')
    responsavel = models.ForeignKey(Responsavel, on_delete=models.PROTECT, related_name='vinculos_familiares')
    mesclar_perfis = models.BooleanField(default=False, verbose_name='Mesclar acesso com o responsável')
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vinculo_familiar'
        constraints = [models.UniqueConstraint(fields=['aluno', 'responsavel'], name='elo_vinculo_familiar_unico')]

    def __str__(self):
        return f'{self.aluno} — {self.responsavel}'
