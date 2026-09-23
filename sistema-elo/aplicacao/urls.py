#importacoes
from django.urls import path

from . import views, contas
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView


#-------------------------------------------------------------------------------------

#rotas
urlpatterns = [
    path('auditoria/', views.auditoria, name='auditoria'),
    path('login/', LoginView.as_view(template_name='aplicacao/login.html',
         authentication_form=contas.LoginElo), name='login'),
    path('sair/', LogoutView.as_view(), name='logout'),
    path('usuarios/novo/', contas.cadastrar, name='usuario-criar'),
    path('recuperar-senha/', TemplateView.as_view(template_name='aplicacao/recuperar-senha.html'),
         name='recuperar-senha'),
    path('sobre/', TemplateView.as_view(template_name='aplicacao/sobre.html'), name='sobre'),
    path("", contas.inicio, name="inicio"),
    path("professores/", views.professores, name="professor-listar"),
    path("professores/novo/", contas.cadastrar, name="professor-criar"),
    path("professores/<int:pk>/editar/", views.professor_editar, name="professor-editar"),
    path("professores/<int:pk>/excluir/", views.professor_excluir, name="professor-excluir"),
    path("alunos/", views.alunos, name="aluno-listar"),
    path("alunos/novo/", contas.cadastrar, name="aluno-criar"),
    path("alunos/<int:pk>/editar/", views.aluno_editar, name="aluno-editar"),
    path("alunos/<int:pk>/excluir/", views.aluno_excluir, name="aluno-excluir"),
    path("alunos/<int:pk>/inicio/", views.aluno_inicio, name="aluno-inicio"),
    path("responsaveis/", views.responsaveis, name="responsavel-listar"),
    path("responsaveis/novo/", contas.cadastrar, name="responsavel-criar"),
    path("responsaveis/<int:pk>/editar/", views.responsavel_editar, name="responsavel-editar"),
    path("responsaveis/<int:pk>/excluir/", views.responsavel_excluir, name="responsavel-excluir"),
    path("vinculos/", views.vinculos, name="vinculo-listar"),
    path("vinculos/novo/", views.vinculo_criar, name="vinculo-criar"),
    path("vinculos/<int:pk>/editar/", views.vinculo_editar, name="vinculo-editar"),
    path("vinculos/<int:pk>/excluir/", views.vinculo_excluir, name="vinculo-excluir"),
    path("metas/", views.metas, name="meta-listar"),
    path("metas/nova/", views.meta_criar, name="meta-criar"),
    path("metas/<int:pk>/editar/", views.meta_editar, name="meta-editar"),
    path("metas/<int:pk>/excluir/", views.meta_excluir, name="meta-excluir"),
    path("atividades/", views.atividades, name="atividade-listar"),
    path("atividades/nova/", views.atividade_criar, name="atividade-criar"),
    path("atividades/<int:pk>/editar/", views.atividade_editar, name="atividade-editar"),
    path("atividades/<int:pk>/excluir/", views.atividade_excluir, name="atividade-excluir"),
    path("conteudos/", views.conteudos, name="conteudo-listar"),
    path("conteudos/novo/", views.conteudo_criar, name="conteudo-criar"),
    path("conteudos/<int:pk>/editar/", views.conteudo_editar, name="conteudo-editar"),
    path("conteudos/<int:pk>/excluir/", views.conteudo_excluir, name="conteudo-excluir"),
    path("frequencias/", views.frequencias, name="frequencia-listar"),
    path("frequencias/nova/", views.frequencia_criar, name="frequencia-criar"),
    path("frequencias/<int:pk>/editar/", views.frequencia_editar, name="frequencia-editar"),
    path("frequencias/<int:pk>/excluir/", views.frequencia_excluir, name="frequencia-excluir"),
]
#-------------------------------------------------------------------------------------
