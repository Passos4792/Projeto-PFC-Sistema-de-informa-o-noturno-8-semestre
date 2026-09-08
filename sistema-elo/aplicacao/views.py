from django.contrib import messages
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import FormularioProfessor, FormularioResponsavel
from .models import Professor, Responsavel


def _texto_ativo(valor):
    return "Ativo" if valor else "Inativo"


def _mostrar_lista(request, titulo, subtitulo, pagina_ativa, cabecalhos, linhas, rota_novo):
    return render(request, "aplicacao/lista-padrao.html", {
        "titulo": titulo, "subtitulo": subtitulo, "pagina_ativa": pagina_ativa,
        "cabecalhos": cabecalhos, "linhas": linhas, "url_novo": reverse(rota_novo),
    })


def _salvar(request, formulario_classe, titulo, pagina_ativa, rota_sucesso, instancia=None):
    formulario = formulario_classe(request.POST or None, instance=instancia)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Registro salvo com sucesso.")
        return redirect(rota_sucesso)
    return render(request, "aplicacao/formulario-padrao.html", {
        "formulario": formulario, "titulo": titulo, "pagina_ativa": pagina_ativa,
        "url_voltar": reverse(rota_sucesso),
    })


def _excluir(request, modelo, pk, titulo, pagina_ativa, rota_sucesso):
    objeto = get_object_or_404(modelo, pk=pk)
    if request.method == "POST":
        try:
            objeto.delete()
            messages.success(request, "Registro excluído com sucesso.")
        except ProtectedError:
            messages.error(request, "Este registro possui outros dados vinculados e não pode ser excluído.")
        return redirect(rota_sucesso)
    return render(request, "aplicacao/confirmar-exclusao.html", {
        "objeto": objeto, "titulo": titulo, "pagina_ativa": pagina_ativa,
        "url_voltar": reverse(rota_sucesso),
    })


def professores(request):
    termo = request.GET.get("busca", "").strip()
    lista = Professor.objects.all()
    if termo:
        lista = lista.filter(Q(nome__icontains=termo) | Q(sobrenome__icontains=termo) | Q(usuario__icontains=termo))
    return render(request, "aplicacao/tela-professores.html", {
        "pagina_ativa": "professores", "professores": lista, "busca": termo,
        "total_professores": Professor.objects.count(),
        "professores_ativos": Professor.objects.filter(ativo=True).count(),
    })


def professor_criar(request):
    return _salvar(request, FormularioProfessor, "Novo professor", "professores", "professor-listar")


def professor_editar(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    return _salvar(request, FormularioProfessor, "Editar professor", "professores", "professor-listar", professor)


def professor_excluir(request, pk):
    return _excluir(request, Professor, pk, "Excluir professor", "professores", "professor-listar")


def responsaveis(request):
    linhas = [{
        "valores": [r.nome_completo, r.usuario, _texto_ativo(r.ativo)],
        "url_editar": reverse("responsavel-editar", args=[r.pk]),
        "url_excluir": reverse("responsavel-excluir", args=[r.pk]),
    } for r in Responsavel.objects.all()]
    return _mostrar_lista(request, "Responsáveis", "Cadastre as pessoas responsáveis pelos alunos.",
                          "responsaveis", ["Responsável", "Usuário", "Situação"], linhas, "responsavel-criar")


def responsavel_criar(request):
    return _salvar(request, FormularioResponsavel, "Novo responsável", "responsaveis", "responsavel-listar")


def responsavel_editar(request, pk):
    responsavel = get_object_or_404(Responsavel, pk=pk)
    return _salvar(request, FormularioResponsavel, "Editar responsável", "responsaveis", "responsavel-listar", responsavel)


def responsavel_excluir(request, pk):
    return _excluir(request, Responsavel, pk, "Excluir responsável", "responsaveis", "responsavel-listar")
