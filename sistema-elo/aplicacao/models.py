#importacoes
from django.conf import settings
from django.db import models
from django.db.models import Q


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

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        db_table = "aluno"
        ordering = ["nome", "sobrenome"]
        verbose_name = "aluno"
        verbose_name_plural = "alunos"


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
            )
        ]

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

#conteudos
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
