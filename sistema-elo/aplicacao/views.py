from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import FormularioAluno, FormularioProfessor, FormularioResponsavel, FormularioVinculo
from .models import Aluno, Professor, Responsavel, Vinculo


def _texto_ativo(valor):
    return "Ativo" if valor else "Inativo"


def _data(valor):
    return valor.strftime("%d/%m/%Y") if valor else "—"


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
    lista = Professor.objects.annotate(
        quantidade_alunos=Count("vinculos", filter=Q(vinculos__ativo=True))
    )
    if termo:
        lista = lista.filter(
            Q(nome__icontains=termo)
            | Q(sobrenome__icontains=termo)
            | Q(usuario__icontains=termo)
        )
    return render(request, "aplicacao/tela-professores.html", {
        "pagina_ativa": "professores",
        "professores": lista,
        "busca": termo,
        "total_professores": Professor.objects.count(),
        "total_alunos": Aluno.objects.count(),
        "professores_ativos": Professor.objects.filter(ativo=True).count(),
    })


def professor_criar(request):
    return _salvar(request, FormularioProfessor, "Novo professor", "professores", "professor-listar")


def professor_editar(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    return _salvar(request, FormularioProfessor, "Editar professor", "professores", "professor-listar", professor)


def professor_excluir(request, pk):
    return _excluir(request, Professor, pk, "Excluir professor", "professores", "professor-listar")


def alunos(request):
    linhas = [{
        "valores": [aluno.nome_completo, aluno.usuario, _data(aluno.data_nascimento), _texto_ativo(aluno.ativo)],
        "url_editar": reverse("aluno-editar", args=[aluno.pk]),
        "url_excluir": reverse("aluno-excluir", args=[aluno.pk]),
    } for aluno in Aluno.objects.all()]
    return _mostrar_lista(request, "Alunos", "Cadastre e consulte os alunos acompanhados.",
                          "alunos", ["Aluno", "Usuário", "Nascimento", "Situação"], linhas, "aluno-criar")


def aluno_criar(request):
    return _salvar(request, FormularioAluno, "Novo aluno", "alunos", "aluno-listar")


def aluno_editar(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    return _salvar(request, FormularioAluno, "Editar aluno", "alunos", "aluno-listar", aluno)


def aluno_excluir(request, pk):
    return _excluir(request, Aluno, pk, "Excluir aluno", "alunos", "aluno-listar")


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


def vinculos(request):
    objetos = Vinculo.objects.select_related("aluno", "professor", "responsavel")
    linhas = [{
        "valores": [
            vinculo.aluno.nome_completo,
            vinculo.professor.nome_completo,
            vinculo.responsavel.nome_completo,
            _data(vinculo.data_vinculo),
            _texto_ativo(vinculo.ativo),
        ],
        "url_editar": reverse("vinculo-editar", args=[vinculo.pk]),
        "url_excluir": reverse("vinculo-excluir", args=[vinculo.pk]),
    } for vinculo in objetos]
    return _mostrar_lista(request, "Vínculos", "Relacione cada aluno ao professor e ao responsável.",
                          "vinculos", ["Aluno", "Professor", "Responsável", "Data", "Situação"], linhas, "vinculo-criar")


def vinculo_criar(request):
    return _salvar(request, FormularioVinculo, "Novo vínculo", "vinculos", "vinculo-listar")


def vinculo_editar(request, pk):
    vinculo = get_object_or_404(Vinculo, pk=pk)
    return _salvar(request, FormularioVinculo, "Editar vínculo", "vinculos", "vinculo-listar", vinculo)


def vinculo_excluir(request, pk):
    return _excluir(request, Vinculo, pk, "Excluir vínculo", "vinculos", "vinculo-listar")
