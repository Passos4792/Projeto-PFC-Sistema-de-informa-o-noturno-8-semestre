from aplicacao.forms.base import validar_nome_pessoa, validar_nascimento, FormularioBase, FormularioPessoaBase
from aplicacao.forms.contas import LoginElo, TrocaSenhaInicial, RedefinicaoSenha, PedidoRecuperacaoForm, CadastroUsuario, AceiteDocumentos
from aplicacao.forms.cadastros import FormularioProfessor, FormularioResponsavel, FormularioAluno, FormularioVinculo, FichaVinculos, FormularioVinculoProfissional, FormularioVinculoFamiliar
from aplicacao.forms.pedagogicos import FormularioMeta, FormularioAtividade, FormularioDisciplina, FormularioConteudo
from aplicacao.forms.filtros import FiltroPainel, FiltroAprovacoes, FiltroAuditoria
from aplicacao.forms.documentos import CAMPOS_DOCUMENTOS, FormularioCabecalhoDocumento, FormularioRelatorio
