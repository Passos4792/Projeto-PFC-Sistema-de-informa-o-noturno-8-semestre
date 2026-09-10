"""Regras simples das telas das funcionalidades 2 e 3."""

from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    FormularioAluno,
    FormularioAtividade,
    FormularioConteudo,
    FormularioFrequencia,
    FormularioMeta,
    FormularioProfessor,
    FormularioResponsavel,
    FormularioVinculo,
)
from .models import Aluno, Atividade, Conteudo, Frequencia, Meta, Professor, Responsavel, Vinculo


def _texto_ativo(valor):
    """Transforma True e False em um texto mais fácil de entender."""

    return "Ativo" if valor else "Inativo"


def _data(valor):
    """Formata uma data ou apresenta um traço quando ela não existir."""

    return valor.strftime("%d/%m/%Y") if valor else "—"


def _mostrar_lista(request, titulo, subtitulo, pagina_ativa, cabecalhos, linhas, rota_novo):
    """Reutiliza a mesma estrutura visual nas listas simples do projeto."""

    return render(
        request,
        "aplicacao/lista-padrao.html",
        {
            "titulo": titulo,
            "subtitulo": subtitulo,
            "pagina_ativa": pagina_ativa,
            "cabecalhos": cabecalhos,
            "linhas": linhas,
            "url_novo": reverse(rota_novo),
        },
    )


def _salvar(request, formulario_classe, titulo, pagina_ativa, rota_sucesso, instancia=None):
    """Cria ou atualiza um registro usando um ModelForm."""

    formulario = formulario_classe(request.POST or None, instance=instancia)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Registro salvo com sucesso.")
        return redirect(rota_sucesso)

    return render(
        request,
        "aplicacao/formulario-padrao.html",
        {
            "formulario": formulario,
            "titulo": titulo,
            "pagina_ativa": pagina_ativa,
            "url_voltar": reverse(rota_sucesso),
        },
    )


def _excluir(request, modelo, pk, titulo, pagina_ativa, rota_sucesso):
    """Mostra uma confirmação antes de excluir um registro."""

    objeto = get_object_or_404(modelo, pk=pk)

    if request.method == "POST":
        try:
            objeto.delete()
            messages.success(request, "Registro excluído com sucesso.")
        except ProtectedError:
            messages.error(request, "Este registro possui outros dados vinculados e não pode ser excluído.")
        return redirect(rota_sucesso)

    return render(
        request,
        "aplicacao/confirmar-exclusao.html",
        {
            "objeto": objeto,
            "titulo": titulo,
            "pagina_ativa": pagina_ativa,
            "url_voltar": reverse(rota_sucesso),
        },
    )


# Tela principal de professores, com busca e indicadores reais do banco.
def professores(request):
    termo = request.GET.get("busca", "").strip()
    lista = Professor.objects.annotate(
        quantidade_alunos=Count("vinculos", filter=Q(vinculos__ativo=True))
    )

    if termo:
        lista = lista.filter(
            Q(nome__icontains=termo)
            | Q(sobrenome__icontains=termo)
            | Q(usuario__usuario__icontains=termo)
        )

    contexto = {
        "pagina_ativa": "professores",
        "professores": lista,
        "busca": termo,
        "total_professores": Professor.objects.count(),
        "total_alunos": Aluno.objects.count(),
        "professores_ativos": Professor.objects.filter(ativo=True).count(),
        "metas_andamento": Meta.objects.filter(situacao=Meta.Situacao.EM_ANDAMENTO).count(),
        "atividades_pendentes": Atividade.objects.filter(situacao=Atividade.Situacao.PENDENTE).count(),
    }
    return render(request, "aplicacao/tela-professores.html", contexto)


def professor_criar(request):
    return _salvar(request, FormularioProfessor, "Novo professor", "professores", "professor-listar")


def professor_editar(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    return _salvar(request, FormularioProfessor, "Editar professor", "professores", "professor-listar", professor)


def professor_excluir(request, pk):
    return _excluir(request, Professor, pk, "Excluir professor", "professores", "professor-listar")


# Funcionalidade 2: alunos, responsáveis e vínculos.
def alunos(request):
    linhas = [
        {
            "valores": [aluno.nome_completo, aluno.usuario, _data(aluno.data_nascimento), _texto_ativo(aluno.ativo)],
            "url_editar": reverse("aluno-editar", args=[aluno.pk]),
            "url_excluir": reverse("aluno-excluir", args=[aluno.pk]),
            "url_extra": reverse("aluno-inicio", args=[aluno.pk]),
            "texto_extra": "Ver painel",
        }
        for aluno in Aluno.objects.all()
    ]
    return _mostrar_lista(
        request,
        "Alunos",
        "Cadastre e consulte os alunos acompanhados.",
        "alunos",
        ["Aluno", "Usuário", "Nascimento", "Situação"],
        linhas,
        "aluno-criar",
    )


def aluno_criar(request):
    return _salvar(request, FormularioAluno, "Novo aluno", "alunos", "aluno-listar")


def aluno_editar(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    return _salvar(request, FormularioAluno, "Editar aluno", "alunos", "aluno-listar", aluno)


def aluno_excluir(request, pk):
    return _excluir(request, Aluno, pk, "Excluir aluno", "alunos", "aluno-listar")


def responsaveis(request):
    linhas = [
        {
            "valores": [responsavel.nome_completo, responsavel.usuario, _texto_ativo(responsavel.ativo)],
            "url_editar": reverse("responsavel-editar", args=[responsavel.pk]),
            "url_excluir": reverse("responsavel-excluir", args=[responsavel.pk]),
        }
        for responsavel in Responsavel.objects.all()
    ]
    return _mostrar_lista(
        request,
        "Responsáveis",
        "Cadastre as pessoas responsáveis pelos alunos.",
        "responsaveis",
        ["Responsável", "Usuário", "Situação"],
        linhas,
        "responsavel-criar",
    )


def responsavel_criar(request):
    return _salvar(request, FormularioResponsavel, "Novo responsável", "responsaveis", "responsavel-listar")


def responsavel_editar(request, pk):
    responsavel = get_object_or_404(Responsavel, pk=pk)
    return _salvar(
        request,
        FormularioResponsavel,
        "Editar responsável",
        "responsaveis",
        "responsavel-listar",
        responsavel,
    )


def responsavel_excluir(request, pk):
    return _excluir(
        request, Responsavel, pk, "Excluir responsável", "responsaveis", "responsavel-listar"
    )


def vinculos(request):
    objetos = Vinculo.objects.select_related("aluno", "professor", "responsavel")
    linhas = [
        {
            "valores": [
                vinculo.aluno.nome_completo,
                vinculo.professor.nome_completo,
                vinculo.responsavel.nome_completo,
                _data(vinculo.data_vinculo),
                _texto_ativo(vinculo.ativo),
            ],
            "url_editar": reverse("vinculo-editar", args=[vinculo.pk]),
            "url_excluir": reverse("vinculo-excluir", args=[vinculo.pk]),
        }
        for vinculo in objetos
    ]
    return _mostrar_lista(
        request,
        "Vínculos",
        "Relacione cada aluno ao professor e ao responsável.",
        "vinculos",
        ["Aluno", "Professor", "Responsável", "Data", "Situação"],
        linhas,
        "vinculo-criar",
    )


def vinculo_criar(request):
    return _salvar(request, FormularioVinculo, "Novo vínculo", "vinculos", "vinculo-listar")


def vinculo_editar(request, pk):
    vinculo = get_object_or_404(Vinculo, pk=pk)
    return _salvar(request, FormularioVinculo, "Editar vínculo", "vinculos", "vinculo-listar", vinculo)


def vinculo_excluir(request, pk):
    return _excluir(request, Vinculo, pk, "Excluir vínculo", "vinculos", "vinculo-listar")


# Funcionalidade 3: metas, atividades, conteúdos e frequência.
def metas(request):
    objetos = Meta.objects.select_related("aluno", "professor")
    linhas = [
        {
            "valores": [meta.titulo, meta.aluno.nome_completo, meta.professor.nome_completo, _data(meta.data_prazo), meta.get_situacao_display()],
            "url_editar": reverse("meta-editar", args=[meta.pk]),
            "url_excluir": reverse("meta-excluir", args=[meta.pk]),
        }
        for meta in objetos
    ]
    return _mostrar_lista(
        request,
        "Metas",
        "Crie e acompanhe as metas dos alunos.",
        "metas",
        ["Meta", "Aluno", "Professor", "Prazo", "Situação"],
        linhas,
        "meta-criar",
    )


def meta_criar(request):
    return _salvar(request, FormularioMeta, "Nova meta", "metas", "meta-listar")


def meta_editar(request, pk):
    meta = get_object_or_404(Meta, pk=pk)
    return _salvar(request, FormularioMeta, "Editar meta", "metas", "meta-listar", meta)


def meta_excluir(request, pk):
    return _excluir(request, Meta, pk, "Excluir meta", "metas", "meta-listar")


def atividades(request):
    objetos = Atividade.objects.select_related("aluno", "professor", "meta")
    linhas = [
        {
            "valores": [atividade.titulo, atividade.aluno.nome_completo, atividade.professor.nome_completo, _data(atividade.data_entrega), atividade.get_situacao_display()],
            "url_editar": reverse("atividade-editar", args=[atividade.pk]),
            "url_excluir": reverse("atividade-excluir", args=[atividade.pk]),
        }
        for atividade in objetos
    ]
    return _mostrar_lista(
        request,
        "Atividades",
        "Cadastre as atividades atribuídas aos alunos.",
        "atividades",
        ["Atividade", "Aluno", "Professor", "Entrega", "Situação"],
        linhas,
        "atividade-criar",
    )


def atividade_criar(request):
    return _salvar(request, FormularioAtividade, "Nova atividade", "atividades", "atividade-listar")


def atividade_editar(request, pk):
    atividade = get_object_or_404(Atividade, pk=pk)
    return _salvar(
        request, FormularioAtividade, "Editar atividade", "atividades", "atividade-listar", atividade
    )


def atividade_excluir(request, pk):
    return _excluir(request, Atividade, pk, "Excluir atividade", "atividades", "atividade-listar")


def conteudos(request):
    objetos = Conteudo.objects.select_related("aluno", "professor", "atividade")
    linhas = [
        {
            "valores": [conteudo.titulo, conteudo.aluno.nome_completo, conteudo.professor.nome_completo, conteudo.tipo_conteudo or "—"],
            "url_editar": reverse("conteudo-editar", args=[conteudo.pk]),
            "url_excluir": reverse("conteudo-excluir", args=[conteudo.pk]),
        }
        for conteudo in objetos
    ]
    return _mostrar_lista(
        request,
        "Conteúdos",
        "Organize os materiais de apoio enviados aos alunos.",
        "conteudos",
        ["Conteúdo", "Aluno", "Professor", "Tipo"],
        linhas,
        "conteudo-criar",
    )


def conteudo_criar(request):
    return _salvar(request, FormularioConteudo, "Novo conteúdo", "conteudos", "conteudo-listar")


def conteudo_editar(request, pk):
    conteudo = get_object_or_404(Conteudo, pk=pk)
    return _salvar(request, FormularioConteudo, "Editar conteúdo", "conteudos", "conteudo-listar", conteudo)


def conteudo_excluir(request, pk):
    return _excluir(request, Conteudo, pk, "Excluir conteúdo", "conteudos", "conteudo-listar")


def frequencias(request):
    objetos = Frequencia.objects.select_related("aluno", "professor")
    linhas = [
        {
            "valores": [frequencia.aluno.nome_completo, frequencia.professor.nome_completo, _data(frequencia.data_acompanhamento), "Presente" if frequencia.compareceu else "Ausente", frequencia.observacao or "—"],
            "url_editar": reverse("frequencia-editar", args=[frequencia.pk]),
            "url_excluir": reverse("frequencia-excluir", args=[frequencia.pk]),
        }
        for frequencia in objetos
    ]
    return _mostrar_lista(
        request,
        "Frequência",
        "Registre a presença nos acompanhamentos.",
        "frequencias",
        ["Aluno", "Professor", "Data", "Situação", "Observação"],
        linhas,
        "frequencia-criar",
    )


def frequencia_criar(request):
    return _salvar(request, FormularioFrequencia, "Nova frequência", "frequencias", "frequencia-listar")


def frequencia_editar(request, pk):
    frequencia = get_object_or_404(Frequencia, pk=pk)
    return _salvar(
        request, FormularioFrequencia, "Editar frequência", "frequencias", "frequencia-listar", frequencia
    )


def frequencia_excluir(request, pk):
    return _excluir(request, Frequencia, pk, "Excluir frequência", "frequencias", "frequencia-listar")


# Painel individual do aluno, alimentado pelos dados cadastrados no banco.
def aluno_inicio(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    metas_aluno = aluno.metas.all()
    atividades_aluno = aluno.atividades.select_related("meta").all()
    metas_concluidas = metas_aluno.filter(situacao=Meta.Situacao.CONCLUIDA).count()
    atividades_concluidas = atividades_aluno.filter(situacao=Atividade.Situacao.CONCLUIDA).count()

    contexto = {
        "aluno": aluno,
        "metas_andamento": metas_aluno.filter(situacao=Meta.Situacao.EM_ANDAMENTO).count(),
        "metas_concluidas": metas_concluidas,
        "atividades": atividades_aluno.filter(situacao=Atividade.Situacao.PENDENTE)[:3],
        "pontos": min(100, metas_concluidas * 20 + atividades_concluidas * 10),
    }
    return render(request, "aplicacao/tela-inicial-aluno.html", contexto)
