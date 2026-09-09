from django.urls import path

from . import views


urlpatterns = [
    path("", views.professores, name="inicio"),
    path("professores/", views.professores, name="professor-listar"),
    path("professores/novo/", views.professor_criar, name="professor-criar"),
    path("professores/<int:pk>/editar/", views.professor_editar, name="professor-editar"),
    path("professores/<int:pk>/excluir/", views.professor_excluir, name="professor-excluir"),
    path("alunos/", views.alunos, name="aluno-listar"),
    path("alunos/novo/", views.aluno_criar, name="aluno-criar"),
    path("alunos/<int:pk>/editar/", views.aluno_editar, name="aluno-editar"),
    path("alunos/<int:pk>/excluir/", views.aluno_excluir, name="aluno-excluir"),
    path("responsaveis/", views.responsaveis, name="responsavel-listar"),
    path("responsaveis/novo/", views.responsavel_criar, name="responsavel-criar"),
    path("responsaveis/<int:pk>/editar/", views.responsavel_editar, name="responsavel-editar"),
    path("responsaveis/<int:pk>/excluir/", views.responsavel_excluir, name="responsavel-excluir"),
    path("vinculos/", views.vinculos, name="vinculo-listar"),
    path("vinculos/novo/", views.vinculo_criar, name="vinculo-criar"),
    path("vinculos/<int:pk>/editar/", views.vinculo_editar, name="vinculo-editar"),
    path("vinculos/<int:pk>/excluir/", views.vinculo_excluir, name="vinculo-excluir"),
]
