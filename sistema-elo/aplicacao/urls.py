from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from django.views.generic import TemplateView
from aplicacao.views import (anexos, api, area_estudante, atividades, cadastros, contas, inicio, paineis,
                             pedagogico, seguranca, senhas, vinculos)
from aplicacao.forms import LoginElo


#rotas
urlpatterns = [
    #entrada e senha
    path('', contas.inicio, name='inicio'),
    path('login/', LoginView.as_view(template_name='aplicacao/contas/login.html',
         authentication_form=LoginElo), name='login'),
    path('sair/', LogoutView.as_view(), name='logout'),
    path('seguranca/configurar/', seguranca.configurar, name='2fa-configurar'),
    path('seguranca/verificar/', seguranca.verificar, name='2fa-verificar'),
    path('seguranca/', seguranca.seguranca, name='2fa-seguranca'),
    path('seguranca/revogar-dispositivos/', seguranca.revogar, name='2fa-revogar'),
    path('seguranca/alterar-senha-admin/', seguranca.trocar_senha_admin, name='admin-trocar-senha'),
    path('recuperar-senha-admin/', seguranca.recuperar_senha_admin, name='admin-recuperar-senha'),
    path('recuperar-senha/', senhas.solicitar_senha, name='recuperar-senha'),
    path('trocar-senha/', contas.trocar_senha, name='trocar-senha'),
    path('meus-dados/', contas.meus_dados, name='meus-dados'),
    path('meus-dados/foto/', contas.foto_perfil, name='foto-perfil'),
    path('meus-dados/foto/alterar/', contas.alterar_foto_perfil, name='foto-perfil-alterar'),
    path('meus-dados/foto/remover/', contas.remover_foto_perfil, name='foto-perfil-remover'),
    path('aceitar-termos/', contas.aceitar_termos, name='aceitar-termos'),

    #paginas publicas
    path('sobre/', TemplateView.as_view(template_name='aplicacao/publico/sobre.html'), name='sobre'),
    path('politica-de-privacidade/', TemplateView.as_view(template_name='aplicacao/publico/politica-privacidade.html'),
         name='politica-privacidade'),
    path('termos-de-uso/', TemplateView.as_view(template_name='aplicacao/publico/termos-uso.html'), name='termos-uso'),
    path('privacidade-para-alunos/', TemplateView.as_view(template_name='aplicacao/publico/privacidade-aluno.html'),
         name='privacidade-aluno'),

    #painel do gestor
    path('pagina-inicial/', inicio.pagina_inicial, name='pagina-inicial'),
    path('auditoria/', inicio.auditoria, name='auditoria'),
    path('usuarios/novo/', contas.cadastrar, name='usuario-criar'),

    #professores
    path('professores/', cadastros.professores, name='professor-listar'),
    path('professores/novo/', contas.cadastrar, name='professor-criar'),
    path('professores/<int:pk>/editar/', cadastros.professor_editar, name='professor-editar'),
    path('professores/<int:pk>/excluir/', cadastros.professor_excluir, name='professor-excluir'),

    #alunos
    path('alunos/', cadastros.alunos, name='aluno-listar'),
    path('alunos/novo/', contas.cadastrar, name='aluno-criar'),
    path('alunos/novo-sem-login/', cadastros.aluno_criar, name='aluno-criar-sem-login'),
    path('alunos/<int:pk>/editar/', cadastros.aluno_editar, name='aluno-editar'),
    path('alunos/<int:pk>/relatorios-documentos/pdf/', cadastros.aluno_documentos_pdf, name='aluno-documentos-pdf'),
    path('alunos/<int:pk>/excluir/', cadastros.aluno_excluir, name='aluno-excluir'),
    path('alunos/<int:pk>/inicio/', paineis.aluno_inicio, name='aluno-inicio'),

    #responsaveis
    path('responsaveis/', cadastros.responsaveis, name='responsavel-listar'),
    path('responsaveis/novo/', contas.cadastrar, name='responsavel-criar'),
    path('responsaveis/<int:pk>/editar/', cadastros.responsavel_editar, name='responsavel-editar'),
    path('responsaveis/<int:pk>/excluir/', cadastros.responsavel_excluir, name='responsavel-excluir'),

    #acesso dos usuarios
    path('usuarios/<int:pk>/redefinir-senha/', contas.redefinir_senha, name='usuario-redefinir-senha'),
    path('usuarios/<int:pk>/redefinir-2fa/', contas.redefinir_segundo_fator_usuario, name='usuario-redefinir-2fa'),
    path('usuarios/<int:pk>/ativar-acesso/', senhas.ativar_acesso, name='usuario-ativar-acesso'),
    path('solicitacoes-de-senha/', senhas.lista_solicitacoes, name='solicitacao-senha-listar'),
    path('solicitacoes-de-senha/<int:pk>/atender/', senhas.atender_solicitacao,
         name='solicitacao-senha-atender'),

    #vinculos
    path('vinculos/', vinculos.vinculos_unificados, name='vinculo-listar'),
    path('vinculos/novo/', vinculos.vinculos_unificados, name='vinculo-criar'),
    path('vinculos/<int:pk>/editar/', cadastros.vinculo_editar, name='vinculo-editar'),
    path('vinculos/<int:pk>/excluir/', cadastros.vinculo_excluir, name='vinculo-excluir'),
    path('vinculos/profissionais/', pedagogico.vinculos_profissionais, name='vinculos-profissionais'),
    path('vinculos/familiares/', pedagogico.vinculos_familiares, name='vinculos-familiares'),
    path('familia/estudantes/', pedagogico.familia_estudantes, name='familia-estudantes'),
    path('profissional/estudantes/', pedagogico.profissional_estudantes, name='profissional-estudantes'),

    #metas
    path('metas/', paineis.metas, name='meta-listar'),
    path('metas/nova/', atividades.meta_criar, name='meta-criar'),
    path('metas/<int:pk>/editar/', atividades.meta_editar, name='meta-editar'),
    path('metas/<int:pk>/excluir/', atividades.meta_excluir, name='meta-excluir'),

    #atividades, historico e aprovacoes na mesma tela
    path('atividades/', atividades.atividades, name='atividade-listar'),
    path('atividades/historico/', atividades.atividades_historico, name='atividade-historico'),
    path('atividades/nova/', atividades.atividade_criar, name='atividade-criar'),
    path('atividades/<int:pk>/editar/', atividades.atividade_editar, name='atividade-editar'),
    path('atividades/<int:pk>/excluir/', atividades.atividade_excluir, name='atividade-excluir'),
    path('aprovacoes/', atividades.aprovacoes, name='aprovacoes'),

    #atividades do aluno
    path('minhas-atividades/', area_estudante.minhas_atividades, name='minhas-atividades'),
    path('minhas-atividades/<int:pk>/', area_estudante.atividade_detalhe, name='atividade-detalhe'),
    path('atividades/<int:pk>/enviar/', area_estudante.enviar_atividade, name='atividade-enviar'),
    path('atividades/<int:pk>/material/', anexos.baixar_material, name='atividade-material'),
    path('entregas/<int:pk>/anexo/', anexos.baixar_entrega, name='entrega-anexo'),

    #google agenda
    path('google/conectar/', area_estudante.conectar, name='google-conectar'),
    path('google/retorno/', area_estudante.retorno, name='google-retorno'),
    path('google/desconectar/', area_estudante.desconectar, name='google-desconectar'),
    path('atividades/<int:pk>/sincronizar-google/', area_estudante.sincronizar, name='google-sincronizar'),

    #documentos pedagogicos
    path('documentos-pedagogicos/', pedagogico.documentos_lista, name='documentos-lista'),
    path('documentos-pedagogicos/novo/<str:tipo>/', pedagogico.documento_criar, name='documento-criar'),
    path('documentos-pedagogicos/<int:pk>/', pedagogico.documento_detalhe, name='documento-detalhe'),
    path('documentos-pedagogicos/<int:pk>/pdf/', pedagogico.documento_pdf, name='documento-pdf'),
    path('documentos-pedagogicos/<int:pk>/editar/', pedagogico.documento_editar, name='documento-editar'),
    path('documentos-pedagogicos/<int:pk>/publicar/', pedagogico.documento_publicar, name='documento-publicar'),
    path('relatorios-pedagogicos/novo/', pedagogico.relatorio_criar, name='relatorio-criar'),
    path('relatorios-pedagogicos/<int:pk>/', pedagogico.relatorio_detalhe, name='relatorio-detalhe'),
    path('relatorios-pedagogicos/<int:pk>/pdf/', pedagogico.relatorio_pdf, name='relatorio-pdf'),
    path('relatorios-pedagogicos/<int:pk>/editar/', pedagogico.relatorio_editar, name='relatorio-editar'),
    path('relatorios-pedagogicos/<int:pk>/publicar/', pedagogico.relatorio_publicar, name='relatorio-publicar'),

    #api
    path('api/painel/', api.PainelApi.as_view(), name='api-painel'),
    path('api/alunos/<int:aluno_id>/metas/', api.MetasAlunoApi.as_view(), name='api-metas-aluno'),
    path('api/atividades/<int:pk>/solicitar-conclusao/', api.SolicitarConclusaoApi.as_view(),
         name='api-solicitar-conclusao'),
    path('api/solicitacoes/<int:pk>/decidir/', api.DecidirConclusaoApi.as_view(), name='api-decidir-conclusao'),
]
