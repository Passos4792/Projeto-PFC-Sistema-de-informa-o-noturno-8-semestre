"""Regras simples das telas das funcionalidades 2 e 3."""


from datetime import datetime, time, timedelta

from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET
from .auditoria import registrar, detalhes_formulario
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


def _mostrar_lista(request, titulo, subtitulo, pagina_ativa, cabecalhos, linhas, rota_novo, busca=None, total_cadastrados=None, pagina=None):
    """Reutiliza a mesma estrutura visual nas listas simples do projeto."""

    if total_cadastrados is None:
        total_cadastrados = len(linhas)
    if busca is None:
        busca = request.GET.get('busca', '').strip()
        partes = busca.casefold().split()
        linhas = [linha for linha in linhas if all(
            parte in ' '.join(str(valor) for valor in linha['valores']).casefold()
            for parte in partes)]
    filtros = request.GET.copy()
    filtros.pop('pagina', None)
    return render(
        request,
        "aplicacao/lista-padrao.html",
        {
            "titulo": titulo,
            "subtitulo": subtitulo,
            "pagina_ativa": pagina_ativa,
            "cabecalhos": cabecalhos,
            "linhas": linhas,
            "url_novo": reverse(rota_novo) if rota_novo else None,
            "busca_habilitada": busca is not None,
            "busca": busca or '',
            "total_cadastrados": total_cadastrados,
            "pagina": pagina,
            "filtros_paginacao": filtros.urlencode(),
        },
    )


@transaction.atomic
def _salvar(request, formulario_classe, titulo, pagina_ativa, rota_sucesso, instancia=None):
    """Cria ou atualiza um registro usando um ModelForm."""

    if instancia is not None and request.method == 'POST':
        instancia = get_object_or_404(type(instancia).objects.select_for_update(), pk=instancia.pk)
    formulario = formulario_classe(request.POST if request.method == 'POST' else None, instance=instancia)
    if not instancia and request.method != 'POST':
        if 'professor' in formulario.fields:
            formulario.initial['professor'] = request.perfil_elo.professor_perfil.pk
        if 'data_inicio' in formulario.fields:
            formulario.initial['data_inicio'] = timezone.localdate()

    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            objeto = formulario.save()
            registrar('EDICAO' if instancia is not None else 'CRIACAO', request=request,
                      objeto=objeto, detalhes=detalhes_formulario(formulario))
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


@require_GET
def auditoria(request):
    from .models import RegistroAuditoria
    from .forms import FiltroAuditoria
    formulario = FiltroAuditoria(request.GET)
    registros = RegistroAuditoria.objects.all()
    total_registros = registros.count()
    if formulario.is_valid():
        filtros = formulario.cleaned_data
        if filtros['acao']:
            registros = registros.filter(acao=filtros['acao'])
        if filtros['autor']:
            registros = registros.filter(autor__icontains=filtros['autor'])
        if filtros['inicio']:

            inicio = timezone.make_aware(datetime.combine(filtros['inicio'], time.min))
            registros = registros.filter(criado_em__gte=inicio)
        if filtros['fim']:

            fim = timezone.make_aware(datetime.combine(filtros['fim'], time.min)) + timedelta(days=1)
            registros = registros.filter(criado_em__lt=fim)
    else:
        registros = registros.none()
    parametros = request.GET.copy()
    parametros.pop('pagina', None)
    parametros.pop('busca', None)
    return render(request, 'aplicacao/auditoria.html', {
        'formulario': formulario, 'pagina': Paginator(registros, 25).get_page(request.GET.get('pagina')),
        'filtros': parametros.urlencode(), 'pagina_ativa': 'auditoria', 'total_cadastrados': total_registros})


def pagina_inicial(request):
    from .indicadores import dados_painel
    metas = dados_painel(request.perfil_elo, {})['metas']
    return render(request, 'aplicacao/pagina-inicial.html', {
        'pagina_ativa': 'pagina-inicial',
        'total_professores': Professor.objects.count(),
        'total_alunos': Aluno.objects.count(),
        'professores_ativos': Professor.objects.filter(ativo=True).count(),
        'metas_andamento': sum(m['estado'] == 'EM_ANDAMENTO' for m in metas),
        'atividades_pendentes': Atividade.objects.filter(situacao=Atividade.Situacao.PENDENTE).count(),
    })


def professores(request):
    termo = request.GET.get("busca", "").strip()
    lista = Professor.objects.select_related('usuario').annotate(
        quantidade_alunos=Count("vinculos", filter=Q(vinculos__ativo=True))
    )

    if termo:
        lista = lista.filter(
            Q(nome__icontains=termo)
            | Q(sobrenome__icontains=termo)
            | Q(usuario__usuario__icontains=termo)
        )

    pagina = Paginator(lista.order_by('nome', 'sobrenome', 'pk'), 10).get_page(request.GET.get('pagina'))
    filtros = request.GET.copy()
    filtros.pop('pagina', None)
    contexto = {
        "pagina_ativa": "professores",
        "professores": pagina.object_list,
        "pagina": pagina,
        "filtros_paginacao": filtros.urlencode(),
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
    if professor.usuario.professor_principal:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('A conta principal deve ser administrada pelo responsável técnico.')
    return _salvar(request, FormularioProfessor, "Editar professor", "professores", "professor-listar", professor)


def professor_excluir(request, pk):
    return _excluir(request, Professor, pk, "Excluir professor", "professores", "professor-listar")


def _buscar_pessoas(modelo, termo):
    pessoas = modelo.objects.select_related('usuario')
    for parte in termo.split():
        pessoas = pessoas.filter(Q(nome__icontains=parte) | Q(sobrenome__icontains=parte))
    return pessoas


def alunos(request):
    busca = request.GET.get('busca', '').strip()
    pagina = Paginator(_buscar_pessoas(Aluno, busca).order_by('nome', 'sobrenome', 'pk'), 10).get_page(request.GET.get('pagina'))
    linhas = [
        {
            "valores": [aluno.nome_completo, aluno.usuario, _data(aluno.data_nascimento), _texto_ativo(aluno.ativo)],
            "url_editar": reverse("aluno-editar", args=[aluno.pk]),
            "url_excluir": reverse("aluno-excluir", args=[aluno.pk]),
            "url_senha": reverse('usuario-redefinir-senha', args=[aluno.usuario_id]) if aluno.usuario.conta_id else None,
            "url_extra": reverse("aluno-inicio", args=[aluno.pk]),
            "texto_extra": "Ver painel",
        }
        for aluno in pagina
    ]
    return _mostrar_lista(
        request,
        "Alunos",
        "Consulte e gerencie os alunos acompanhados.",
        "alunos",
        ["Aluno", "Usuário", "Nascimento", "Situação"],
        linhas,
        None,
        busca=busca,
        total_cadastrados=Aluno.objects.count(),
        pagina=pagina,
    )


def aluno_criar(request):
    return _salvar(request, FormularioAluno, "Novo aluno", "alunos", "aluno-listar")


def aluno_editar(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    return _salvar(request, FormularioAluno, "Editar aluno", "alunos", "aluno-listar", aluno)


def aluno_excluir(request, pk):
    return _excluir(request, Aluno, pk, "Excluir aluno", "alunos", "aluno-listar")


def responsaveis(request):
    busca = request.GET.get('busca', '').strip()
    pagina = Paginator(_buscar_pessoas(Responsavel, busca).order_by('nome', 'sobrenome', 'pk'), 10).get_page(request.GET.get('pagina'))
    linhas = [
        {
            "valores": [responsavel.nome_completo, responsavel.usuario, _texto_ativo(responsavel.ativo)],
            "url_editar": reverse("responsavel-editar", args=[responsavel.pk]),
            "url_excluir": reverse("responsavel-excluir", args=[responsavel.pk]),
            "url_senha": reverse('usuario-redefinir-senha', args=[responsavel.usuario_id]) if responsavel.usuario.conta_id else None,
        }
        for responsavel in pagina
    ]
    return _mostrar_lista(
        request,
        "Responsáveis",
        "Consulte e gerencie os responsáveis pelos alunos.",
        "responsaveis",
        ["Responsável", "Usuário", "Situação"],
        linhas,
        None,
        busca=busca,
        total_cadastrados=Responsavel.objects.count(),
        pagina=pagina,
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
    total = objetos.count()
    busca = request.GET.get('busca', '').strip()
    for parte in busca.split():
        criterio = (Q(aluno__nome__icontains=parte) | Q(aluno__sobrenome__icontains=parte)
                    | Q(professor__nome__icontains=parte) | Q(professor__sobrenome__icontains=parte)
                    | Q(responsavel__nome__icontains=parte) | Q(responsavel__sobrenome__icontains=parte))
        situacoes = [valor for valor in (True, False) if parte.casefold() in _texto_ativo(valor).casefold()]
        criterio |= Q(ativo__in=situacoes)
        try:
            criterio |= Q(data_vinculo=datetime.strptime(parte, '%d/%m/%Y').date())
        except ValueError:
            pass
        objetos = objetos.filter(criterio)
    pagina = Paginator(objetos.order_by('aluno__nome', 'aluno__sobrenome', 'pk'), 10).get_page(request.GET.get('pagina'))
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
        for vinculo in pagina
    ]
    return _mostrar_lista(
        request,
        "Vínculos",
        "Relacione cada aluno ao professor e ao responsável.",
        "vinculos",
        ["Aluno", "Professor", "Responsável", "Data", "Situação"],
        linhas,
        "vinculo-criar",
        busca=busca,
        total_cadastrados=total,
        pagina=pagina,
    )


def vinculo_criar(request):
    return _salvar(request, FormularioVinculo, "Novo vínculo", "vinculos", "vinculo-listar")


def vinculo_editar(request, pk):
    vinculo = get_object_or_404(Vinculo, pk=pk)
    return _salvar(request, FormularioVinculo, "Editar vínculo", "vinculos", "vinculo-listar", vinculo)


def vinculo_excluir(request, pk):
    return _excluir(request, Vinculo, pk, "Excluir vínculo", "vinculos", "vinculo-listar")


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
    objetos = Atividade.objects.select_related("aluno", "disciplina")
    aluno_id = request.GET.get('aluno', '')
    if aluno_id:
        objetos = objetos.filter(aluno_id=aluno_id if aluno_id.isdigit() else 0)
    total = objetos.count()
    busca = request.GET.get('busca', '').strip()

    for parte in busca.split():
        criterio = (Q(titulo__icontains=parte) | Q(aluno__nome__icontains=parte)
                    | Q(aluno__sobrenome__icontains=parte) | Q(disciplina__nome__icontains=parte))
        situacoes = [codigo for codigo, nome in Atividade.Situacao.choices if parte.casefold() in nome.casefold()]
        criterio |= Q(situacao__in=situacoes)
        if parte.casefold() in 'sem conteúdo':
            criterio |= Q(disciplina__isnull=True)
        try:
            criterio |= Q(data_entrega=datetime.strptime(parte, '%d/%m/%Y').date())
        except ValueError:
            pass
        objetos = objetos.filter(criterio)
    pagina = Paginator(objetos.order_by('data_entrega', 'titulo', 'pk'), 10).get_page(request.GET.get('pagina'))
    linhas = [
        {
            "valores": [atividade.titulo, atividade.aluno.nome_completo, atividade.disciplina or "Sem conteúdo", _data(atividade.data_entrega), atividade.get_situacao_display()],
            "url_editar": reverse("atividade-editar", args=[atividade.pk]),
            "url_excluir": reverse("atividade-excluir", args=[atividade.pk]),
        }
        for atividade in pagina
    ]
    return _mostrar_lista(
        request,
        "Atividades",
        "Cadastre as atividades atribuídas aos alunos.",
        "atividades",
        ["Atividade", "Aluno", "Conteúdo", "Entrega", "Situação"],
        linhas,
        "atividade-criar",
        busca=busca,
        total_cadastrados=total,
        pagina=pagina,
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
            "url_editar": reverse("conteudo-anterior-editar", args=[conteudo.pk]),
            "url_excluir": reverse("conteudo-anterior-excluir", args=[conteudo.pk]),
        }
        for conteudo in objetos
    ]
    return _mostrar_lista(
        request,
        "Registros anteriores de conteúdos",
        "Materiais da versão anterior, preservados para consulta.",
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

