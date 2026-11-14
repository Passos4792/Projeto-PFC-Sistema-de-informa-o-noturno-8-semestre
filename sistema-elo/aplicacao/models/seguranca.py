from django.conf import settings
from uuid import uuid4
from django.db import models


class Configuracao2FA(models.Model):
    conta = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='configuracao_2fa')
    segredo_criptografado = models.TextField()
    confirmada_em = models.DateTimeField(null=True, blank=True)
    ultimo_intervalo = models.BigIntegerField(default=-1)
    falhas = models.PositiveSmallIntegerField(default=0)
    bloqueado_ate = models.DateTimeField(null=True, blank=True)
    versao = models.UUIDField(default=uuid4, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'elo_configuracao_2fa'
        verbose_name = 'configuração de autenticação em duas etapas'


class DispositivoConfiavel2FA(models.Model):
    conta = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='dispositivos_confiaveis_2fa')
    token_hash = models.CharField(max_length=64, unique=True)
    assinatura_senha = models.CharField(max_length=64)
    descricao = models.CharField(max_length=160, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()

    class Meta:
        db_table = 'elo_dispositivo_confiavel_2fa'
        ordering = ['-criado_em']


class CodigoRecuperacao2FA(models.Model):
    conta = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='codigos_recuperacao_2fa')
    codigo_hash = models.CharField(max_length=64, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'elo_codigo_recuperacao_2fa'


class RegistroAuditoria(models.Model):
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

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    autor_id_original = models.PositiveBigIntegerField(null=True, blank=True)
    autor = models.CharField(max_length=150)
    acao = models.CharField(max_length=25, choices=Acao.choices, db_index=True)
    entidade = models.CharField(max_length=80, blank=True)
    objeto_id = models.CharField(max_length=64, blank=True)
    detalhes = models.CharField(max_length=500, blank=True)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)

    class Meta:
        db_table = 'registro_auditoria'
        ordering = ['-criado_em', '-pk']
        verbose_name = 'registro de auditoria'
        verbose_name_plural = 'registros de auditoria'


class LimiteLogin(models.Model):
    chave = models.CharField(max_length=64, unique=True)
    falhas = models.PositiveIntegerField(default=0)
    inicio = models.DateTimeField()
    bloqueado_ate = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'limite_login'


class SolicitacaoSenha(models.Model):
    class Situacao(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        ATENDIDA = 'ATENDIDA', 'Atendida'

    aluno = models.ForeignKey('Aluno', on_delete=models.PROTECT, related_name='solicitacoes_senha', null=True, blank=True)
    professor = models.ForeignKey('Professor', on_delete=models.PROTECT, related_name='solicitacoes_senha', null=True, blank=True)
    usuario_alvo = models.ForeignKey('Usuario', on_delete=models.PROTECT,
                                    related_name='solicitacoes_recuperacao', null=True, blank=True)
    situacao = models.CharField(max_length=12, choices=Situacao.choices, default=Situacao.PENDENTE, db_index=True)
    criada_em = models.DateTimeField(auto_now_add=True, db_index=True)
    atendida_em = models.DateTimeField(null=True, blank=True)
    origem_hash = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        db_table = 'solicitacao_senha'
        ordering = ['-criada_em', '-pk']
        verbose_name = 'solicitação de senha'
        verbose_name_plural = 'solicitações de senha'

    def __str__(self):
        return f'Solicitação de acesso - {self.usuario_alvo or self.aluno} ({self.get_situacao_display()})'
