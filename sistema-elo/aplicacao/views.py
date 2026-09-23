"""Regras simples das telas das funcionalidades 2 e 3."""

#importacoes
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET
from .auditoria import registrar
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


#-------------------------------------------------------------------------------------

#texto ativo
def _texto_ativo(valor):
    """Transforma True e False em um texto mais fácil de entender."""

    return "Ativo" if valor else "Inativo"


#-------------------------------------------------------------------------------------

#data
def _data(valor):
    """Formata uma data ou apresenta um traço quando ela não existir."""

    return valor.strftime("%d/%m/%Y") if valor else "—"


#-------------------------------------------------------------------------------------

#mostrar lista
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


#-------------------------------------------------------------------------------------

#salvar
def _salvar(request, formulario_classe, titulo, pagina_ativa, rota_sucesso, instancia=None):
    """Cria ou atualiza um registro usando um ModelForm."""

    formulario = formulario_classe(request.POST or None, instance=instancia)

    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            objeto = formulario.save()
            registrar('EDICAO' if instancia is not None else 'CRIACAO', request=request,
                      objeto=objeto, detalhes='Campos: ' + ', '.join(formulario.changed_data))
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


#-------------------------------------------------------------------------------------

#excluir
def _excluir(request, modelo, pk, titulo, pagina_ativa, rota_sucesso):
    """Mostra uma confirmação antes de excluir um registro."""

    objeto = get_object_or_404(modelo, pk=pk)
    if modelo == Professor and objeto.usuario.professor_principal:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('O professor principal não pode ser excluído por esta tela.')

    if request.method == "POST":
        try:
            with transaction.atomic():
                registrar('EXCLUSAO', request=request, objeto=objeto)
                objeto.delete()
            messages.success(request, "Registro excluído com sucesso.")
        except ProtectedError:
            messages.error(
                request, "Este registro possui outros dados vinculados e não pode ser excluído.")
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

#-------------------------------------------------------------------------------------

#auditoria
@require_GET
def auditoria(request):
    from .models import RegistroAuditoria
    from .forms import FiltroAuditoria
    formulario = FiltroAuditoria(request.GET)
    registros = RegistroAuditoria.objects.all()
    if formulario.is_valid():
        filtros = formulario.cleaned_data
        if filtros['acao']:
            registros = registros.filter(acao=filtros['acao'])
        if filtros['autor']:
            registros = registros.filter(autor__icontains=filtros['autor'])
        if filtros['inicio']:
            registros = registros.filter(criado_em__date__gte=filtros['inicio'])
        if filtros['fim']:
            registros = registros.filter(criado_em__date__lte=filtros['fim'])
    else:
        registros = registros.none()
    parametros = request.GET.copy()
    parametros.pop('pagina', None)
    return render(request, 'aplicacao/auditoria.html', {
        'formulario': formulario, 'pagina': Paginator(registros, 25).get_page(request.GET.get('pagina')),
        'filtros': parametros.urlencode(), 'pagina_ativa': 'auditoria'})


#-------------------------------------------------------------------------------------

#professores
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


#-------------------------------------------------------------------------------------

#professor criar
def professor_criar(request):
    return _salvar(request, FormularioProfessor, "Novo professor", "professores", "professor-listar")


#-------------------------------------------------------------------------------------

#professor editar
def professor_editar(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    if professor.usuario.professor_principal:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('A conta principal deve ser administrada pelo responsável técnico.')
    return _salvar(request, FormularioProfessor, "Editar professor", "professores", "professor-listar", professor)


#-------------------------------------------------------------------------------------

#professor excluir
def professor_excluir(request, pk):
    return _excluir(request, Professor, pk, "Excluir professor", "professores", "professor-listar")


# Funcionalidade 2: alunos, responsáveis e vínculos.

#-------------------------------------------------------------------------------------

#alunos
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


#-------------------------------------------------------------------------------------

#aluno criar
def aluno_criar(request):
    return _salvar(request, FormularioAluno, "Novo aluno", "alunos", "aluno-listar")


#-------------------------------------------------------------------------------------

#aluno editar
def aluno_editar(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    return _salvar(request, FormularioAluno, "Editar aluno", "alunos", "aluno-listar", aluno)


#-------------------------------------------------------------------------------------

#aluno excluir
def aluno_excluir(request, pk):
    return _excluir(request, Aluno, pk, "Excluir aluno", "alunos", "aluno-listar")


#-------------------------------------------------------------------------------------

#responsaveis
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


#-------------------------------------------------------------------------------------

#responsavel criar
def responsavel_criar(request):
    return _salvar(request, FormularioResponsavel, "Novo responsável", "responsaveis", "responsavel-listar")


#-------------------------------------------------------------------------------------

#responsavel editar
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


#-------------------------------------------------------------------------------------

#responsavel excluir
def responsavel_excluir(request, pk):
    return _excluir(
        request, Responsavel, pk, "Excluir responsável", "responsaveis", "responsavel-listar"
    )


#-------------------------------------------------------------------------------------

#vinculos
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


#-------------------------------------------------------------------------------------

#vinculo criar
def vinculo_criar(request):
    return _salvar(request, FormularioVinculo, "Novo vínculo", "vinculos", "vinculo-listar")


#-------------------------------------------------------------------------------------

#vinculo editar
def vinculo_editar(request, pk):
    vinculo = get_object_or_404(Vinculo, pk=pk)
    return _salvar(request, FormularioVinculo, "Editar vínculo", "vinculos", "vinculo-listar", vinculo)


#-------------------------------------------------------------------------------------

#vinculo excluir
def vinculo_excluir(request, pk):
    return _excluir(request, Vinculo, pk, "Excluir vínculo", "vinculos", "vinculo-listar")


# Funcionalidade 3: metas, atividades, conteúdos e frequência.

#-------------------------------------------------------------------------------------

#metas
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


#-------------------------------------------------------------------------------------

#meta criar
def meta_criar(request):
    return _salvar(request, FormularioMeta, "Nova meta", "metas", "meta-listar")


#-------------------------------------------------------------------------------------

#meta editar
def meta_editar(request, pk):
    meta = get_object_or_404(Meta, pk=pk)
    return _salvar(request, FormularioMeta, "Editar meta", "metas", "meta-listar", meta)


#-------------------------------------------------------------------------------------

#meta excluir
def meta_excluir(request, pk):
    return _excluir(request, Meta, pk, "Excluir meta", "metas", "meta-listar")


#-------------------------------------------------------------------------------------

#atividades
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


#-------------------------------------------------------------------------------------

#atividade criar
def atividade_criar(request):
    return _salvar(request, FormularioAtividade, "Nova atividade", "atividades", "atividade-listar")


#-------------------------------------------------------------------------------------

#atividade editar
def atividade_editar(request, pk):
    atividade = get_object_or_404(Atividade, pk=pk)
    return _salvar(
        request, FormularioAtividade, "Editar atividade", "atividades", "atividade-listar", atividade
    )


#-------------------------------------------------------------------------------------

#atividade excluir
def atividade_excluir(request, pk):
    return _excluir(request, Atividade, pk, "Excluir atividade", "atividades", "atividade-listar")


#-------------------------------------------------------------------------------------

#conteudos
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


#-------------------------------------------------------------------------------------

#conteudo criar
def conteudo_criar(request):
    return _salvar(request, FormularioConteudo, "Novo conteúdo", "conteudos", "conteudo-listar")


#-------------------------------------------------------------------------------------

#conteudo editar
def conteudo_editar(request, pk):
    conteudo = get_object_or_404(Conteudo, pk=pk)
    return _salvar(request, FormularioConteudo, "Editar conteúdo", "conteudos", "conteudo-listar", conteudo)


#-------------------------------------------------------------------------------------

#conteudo excluir
def conteudo_excluir(request, pk):
    return _excluir(request, Conteudo, pk, "Excluir conteúdo", "conteudos", "conteudo-listar")


#-------------------------------------------------------------------------------------

#frequencias
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


#-------------------------------------------------------------------------------------

#frequencia criar
def frequencia_criar(request):
    return _salvar(request, FormularioFrequencia, "Nova frequência", "frequencias", "frequencia-listar")


#-------------------------------------------------------------------------------------

#frequencia editar
def frequencia_editar(request, pk):
    frequencia = get_object_or_404(Frequencia, pk=pk)
    return _salvar(
        request, FormularioFrequencia, "Editar frequência", "frequencias", "frequencia-listar", frequencia
    )


#-------------------------------------------------------------------------------------

#frequencia excluir
def frequencia_excluir(request, pk):
    return _excluir(request, Frequencia, pk, "Excluir frequência", "frequencias", "frequencia-listar")


# Painel individual do aluno, alimentado pelos dados cadastrados no banco.

#-------------------------------------------------------------------------------------

#aluno inicio
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
#-------------------------------------------------------------------------------------
