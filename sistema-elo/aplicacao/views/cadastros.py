from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from aplicacao.servicos.acesso import alunos_com_funcao
from aplicacao.servicos.auditoria import registrar
from aplicacao.forms import FormularioAluno, FormularioProfessor, FormularioResponsavel, FormularioVinculo
from aplicacao.servicos.exportacao_pdf import gerar_pdf_prontuario_aluno
from aplicacao.models import Aluno, Atividade, MetaAluno, Professor, Responsavel, Vinculo
from aplicacao.views.comum import _buscar_pessoas, _data, _excluir, _mostrar_lista, _salvar, _tem_segundo_fator, _texto_ativo


def professores(request):
    termo = request.GET.get("busca", "").strip()
    lista = Professor.objects.select_related('usuario', 'usuario__conta').annotate(
        quantidade_alunos=Count("vinculos", filter=Q(vinculos__ativo=True)),
        tem_2fa=_tem_segundo_fator(),
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
        "metas_andamento": MetaAluno.objects.filter(situacao=MetaAluno.Situacao.EM_ANDAMENTO).count(),
        "atividades_pendentes": Atividade.objects.filter(situacao=Atividade.Situacao.PENDENTE).count(),
    }
    return render(request, "aplicacao/cadastros/tela-professores.html", contexto)


def professor_editar(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    if professor.usuario.gestor:
        raise PermissionDenied('A conta do gestor deve ser administrada pelo responsável técnico.')
    return _salvar(request, FormularioProfessor, "Editar professor", "professores", "professor-listar", professor)


def professor_excluir(request, pk):
    return _excluir(request, Professor, pk, "Excluir professor", "professores", "professor-listar")


def alunos(request):
    busca = request.GET.get('busca', '').strip()
    consulta = _buscar_pessoas(Aluno, busca).filter(
        pk__in=alunos_com_funcao(request.perfil_elo, Professor.Funcao.AEE))
    pagina = Paginator(consulta.order_by('nome', 'sobrenome', 'pk'), 10).get_page(request.GET.get('pagina'))
    linhas = [
        {
            "valores": [aluno.nome_completo, aluno.usuario, _data(aluno.data_nascimento), _texto_ativo(aluno.ativo)],
            "url_editar": reverse("aluno-editar", args=[aluno.pk]) if request.perfil_elo.gestor else None,
            "url_excluir": reverse("aluno-excluir", args=[aluno.pk]) if request.perfil_elo.gestor else None,
            "url_senha": reverse('usuario-redefinir-senha', args=[aluno.usuario_id]) if aluno.usuario.conta_id else None,
            "url_ativar": reverse('usuario-ativar-acesso', args=[aluno.usuario_id]) if not aluno.usuario.conta_id and aluno.ativo else None,
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
        total_cadastrados=consulta.count(),
        pagina=pagina,
    )


def aluno_criar(request):
    return _salvar(request, FormularioAluno, "Novo aluno sem login próprio", "alunos", "aluno-listar")


def aluno_editar(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    return _salvar(request, FormularioAluno, "Editar aluno", "alunos", "aluno-listar", aluno)


@never_cache
@require_GET
def aluno_documentos_pdf(request, pk):
    perfil = request.perfil_elo
    if perfil.tipo_perfil != 'PROFESSOR' or not perfil.gestor:
        raise PermissionDenied('Somente o gestor pode exportar o histórico completo do aluno.')
    aluno = get_object_or_404(Aluno, pk=pk)
    if not aluno.documentos_em_prazo:
        raise PermissionDenied('O histórico completo só é exportado enquanto o aluno está inativo e dentro do prazo de cinco anos.')
    from aplicacao.models import DocumentoPedagogico, RelatorioPedagogico
    documentos = list(DocumentoPedagogico.objects.filter(aluno=aluno).select_related('professor')
                      .order_by('ano_letivo', 'tipo', 'pk'))
    relatorios = list(RelatorioPedagogico.objects.filter(aluno=aluno).select_related('professor')
                      .order_by('data_referencia', 'pk'))
    conteudo = gerar_pdf_prontuario_aluno(aluno, documentos, relatorios)
    registrar('CONSULTA', request=request, entidade='Exportação de histórico pedagógico',
              objeto_id=str(aluno.pk),
              detalhes=f'PDF consolidado: {len(documentos)} documentos; {len(relatorios)} relatórios.')
    resposta = HttpResponse(conteudo, content_type='application/pdf')
    resposta['Content-Disposition'] = f'attachment; filename="elo-historico-pedagogico-aluno-{aluno.pk}.pdf"'
    resposta['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta


def aluno_excluir(request, pk):
    return _excluir(request, Aluno, pk, "Excluir aluno", "alunos", "aluno-listar")


def responsaveis(request):
    busca = request.GET.get('busca', '').strip()
    pagina = Paginator(_buscar_pessoas(Responsavel, busca).annotate(tem_2fa=_tem_segundo_fator())
                       .order_by('nome', 'sobrenome', 'pk'), 10).get_page(request.GET.get('pagina'))
    linhas = [
        {
            "valores": [responsavel.nome_completo, responsavel.usuario, _texto_ativo(responsavel.ativo)],
            "url_editar": reverse("responsavel-editar", args=[responsavel.pk]),
            "url_excluir": reverse("responsavel-excluir", args=[responsavel.pk]),
            "url_senha": reverse('usuario-redefinir-senha', args=[responsavel.usuario_id]) if responsavel.usuario.conta_id else None,
            "url_2fa": reverse('usuario-redefinir-2fa', args=[responsavel.usuario_id]) if responsavel.tem_2fa else None,
            "url_ativar": reverse('usuario-ativar-acesso', args=[responsavel.usuario_id]) if not responsavel.usuario.conta_id and responsavel.ativo else None,
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


def vinculo_editar(request, pk):
    vinculo = get_object_or_404(Vinculo, pk=pk)
    return _salvar(request, FormularioVinculo, "Editar vínculo", "vinculos", "vinculo-listar", vinculo)


def vinculo_excluir(request, pk):
    return _excluir(request, Vinculo, pk, "Excluir vínculo", "vinculos", "vinculo-listar")
