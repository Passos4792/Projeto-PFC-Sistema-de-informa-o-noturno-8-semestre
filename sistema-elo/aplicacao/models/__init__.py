from aplicacao.models.usuarios import Usuario, PessoaBase, Professor, Responsavel, Aluno
from aplicacao.models.seguranca import Configuracao2FA, DispositivoConfiavel2FA, CodigoRecuperacao2FA, RegistroAuditoria, LimiteLogin, SolicitacaoSenha
from aplicacao.models.vinculos import Vinculo, VinculoProfissional, VinculoFamiliar
from aplicacao.models.pedagogico import Disciplina, MetaAluno, Atividade, SolicitacaoConclusao, Conteudo, RelatorioPedagogico, DocumentoPedagogico
from aplicacao.models.google import ConexaoGoogle, SincronizacaoGoogle
