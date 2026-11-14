from django.db import models
from aplicacao.models.pedagogico import Atividade
from aplicacao.models.usuarios import Usuario


class ConexaoGoogle(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='conexao_google')
    identidade = models.CharField(max_length=64)
    credenciais = models.TextField()
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conexao_google'


class SincronizacaoGoogle(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    atividade = models.ForeignKey(Atividade, on_delete=models.CASCADE)
    identidade = models.CharField(max_length=64)
    evento_id = models.CharField(max_length=128)
    sincronizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sincronizacao_google'
        constraints = [models.UniqueConstraint(
            fields=['usuario', 'atividade', 'identidade'], name='google_evento_usuario_atividade')]
