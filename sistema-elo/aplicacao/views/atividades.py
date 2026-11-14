from datetime import datetime, time
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from aplicacao.servicos.acesso import alunos_com_funcao, id_seguro
from aplicacao.forms import FiltroAprovacoes, FormularioAtividade, FormularioMeta
from aplicacao.views.api import solicitacoes_permitidas
from aplicacao.models import Atividade, MetaAluno, Professor
from aplicacao.views.cadastros import alunos
from aplicacao.views.comum import _excluir, _salvar


def meta_criar(request):
    return _salvar(request, FormularioMeta, "Nova meta", "metas", "meta-listar", acesso_aee=True)


def meta_editar(request, pk):
    meta = get_object_or_404(MetaAluno, pk=pk)
    return _salvar(request, FormularioMeta, "Editar meta", "metas", "meta-listar", meta, acesso_aee=True)


def meta_excluir(request, pk):
    return _excluir(request, MetaAluno, pk, "Excluir meta", "metas", "meta-listar", acesso_aee=True)


@require_GET
@never_cache
def atividades(request, visao_padrao='todas'):
    perfil = request.perfil_elo
    if perfil.tipo_perfil != 'PROFESSOR':
        raise PermissionDenied
    visao = request.GET.get('filtro', visao_padrao)
    if visao not in {'todas', 'pendentes', 'aprovacoes', 'concluidas', 'canceladas', 'historico'}:
        visao = 'todas'

    alunos = alunos_com_funcao(perfil, Professor.Funcao.AEE)
    objetos = Atividade.objects.select_related('aluno', 'professor', 'disciplina')
    if not perfil.gestor:
        objetos = objetos.filter(aluno__in=alunos, professor__usuario=perfil)

    selecionado = request.GET.get('aluno', '').strip()
    if selecionado:
        objetos = objetos.filter(aluno_id=id_seguro(selecionado))

    pedidos = solicitacoes_permitidas(perfil)
    if selecionado:
        pedidos = pedidos.filter(aluno_id=id_seguro(selecionado))
    pendentes = pedidos.filter(situacao='PENDENTE').count()
    busca = request.GET.get('busca', '').strip()[:100]
    hoje = timezone.localdate()
    ano = request.GET.get('ano', '').strip()
    situacao = request.GET.get('situacao', '').strip()
    formulario_filtros = None

    if visao == 'aprovacoes':
        if situacao not in {'PENDENTE', 'APROVADA', 'RECUSADA', ''}:
            situacao = 'PENDENTE'
        elif 'situacao' not in request.GET:
            situacao = 'PENDENTE'
        if situacao:
            pedidos = pedidos.filter(situacao=situacao)
        for parte in busca.split():
            pedidos = pedidos.filter(Q(atividade__titulo__icontains=parte) |
                Q(aluno__nome__icontains=parte) | Q(aluno__sobrenome__icontains=parte))
        parametros = request.GET.copy()
        parametros.pop('pagina', None)
        parametros.setdefault('ordem', 'recentes')
        formulario_filtros = FiltroAprovacoes(parametros)
        if formulario_filtros.is_valid():
            filtros = formulario_filtros.cleaned_data
            if filtros['inicio']:
                pedidos = pedidos.filter(solicitado_em__gte=timezone.make_aware(
                    datetime.combine(filtros['inicio'], time.min)))
            if filtros['fim']:
                pedidos = pedidos.filter(solicitado_em__lte=timezone.make_aware(
                    datetime.combine(filtros['fim'], time.max)))
            pedidos = pedidos.order_by('solicitado_em', 'pk') if filtros['ordem'] == 'antigas' else pedidos.order_by('-solicitado_em', '-pk')
        else:
            pedidos = pedidos.none()
        pagina = Paginator(pedidos, 6).get_page(request.GET.get('pagina'))
    else:
        if visao == 'pendentes':
            objetos = objetos.filter(situacao='PENDENTE').exclude(
                pk__in=pedidos.filter(situacao='PENDENTE').values('atividade_id'))
        elif visao == 'concluidas':
            objetos = objetos.filter(situacao='CONCLUIDA')
        elif visao == 'canceladas':
            objetos = objetos.filter(situacao='CANCELADA')
        elif visao == 'historico':
            objetos = objetos.filter(Q(data_entrega__lt=hoje) |
                                     Q(situacao__in=['CONCLUIDA', 'CANCELADA']))
            if situacao not in ('PENDENTE', 'CONCLUIDA', 'CANCELADA'):
                situacao = ''
            if situacao:
                objetos = objetos.filter(situacao=situacao)
            if len(ano) == 4 and ano.isascii() and ano.isdigit() and 2000 <= int(ano) <= 2100:
                objetos = objetos.filter(Q(data_entrega__year=int(ano)) |
                    Q(data_entrega__isnull=True, criado_em__year=int(ano)))
            else:
                ano = ''

        for parte in busca.split():
            criterio = (Q(titulo__icontains=parte) | Q(aluno__nome__icontains=parte) |
                        Q(aluno__sobrenome__icontains=parte) | Q(disciplina__nome__icontains=parte))
            if visao != 'historico' and len(parte) >= 3:
                estados = [codigo for codigo, nome in Atividade.Situacao.choices
                           if parte.casefold() in nome.casefold()]
                criterio |= Q(situacao__in=estados)
                if parte.casefold() in 'sem conteúdo':
                    criterio |= Q(disciplina__isnull=True)
                try:
                    criterio |= Q(data_entrega=datetime.strptime(parte, '%d/%m/%Y').date())
                except ValueError:
                    pass
            objetos = objetos.filter(criterio)
        ordem = ('-data_entrega', '-criado_em', '-pk') if visao == 'historico' else ('data_entrega', 'titulo', 'pk')
        pagina = Paginator(objetos.order_by(*ordem), 12 if visao == 'historico' else 10).get_page(
            request.GET.get('pagina'))
        ids = {atividade.pk for atividade in pagina.object_list}
        ids_aguardando = set(pedidos.filter(situacao='PENDENTE', atividade_id__in=ids).values_list(
            'atividade_id', flat=True))
        for atividade in pagina.object_list:
            atividade.aguardando_aprovacao = atividade.pk in ids_aguardando

    parametros = request.GET.copy()
    parametros.pop('pagina', None)
    parametros['filtro'] = visao
    filtros_abas = QueryDict(mutable=True)
    if selecionado:
        filtros_abas['aluno'] = selecionado
    if busca:
        filtros_abas['busca'] = busca
    return render(request, 'aplicacao/atividades/atividades.html', {
        'filtros_abas': filtros_abas.urlencode(),
        'pagina_ativa': 'atividades', 'titulo': 'Atividades', 'visao': visao,
        'pagina': pagina, 'total_cadastrados': pagina.paginator.count,
        'busca': busca, 'alunos_disponiveis': alunos.order_by('nome', 'sobrenome', 'pk'),
        'aluno_id': selecionado, 'aluno_selecionado_pk': id_seguro(selecionado), 'pendentes': pendentes, 'situacao': situacao,
        'ano': ano, 'hoje': hoje, 'formulario_filtros': formulario_filtros,
        'filtros_paginacao': parametros.urlencode(),
    })


@require_GET
@never_cache
def atividades_historico(request):
    return atividades(request, visao_padrao='historico')


@require_GET
@never_cache
def aprovacoes(request):
    return atividades(request, visao_padrao='aprovacoes')


def atividade_criar(request):
    return _salvar(request, FormularioAtividade, "Nova atividade", "atividades", "atividade-listar", acesso_aee=True)


def atividade_editar(request, pk):
    atividade = get_object_or_404(Atividade, pk=pk)
    return _salvar(
        request, FormularioAtividade, "Editar atividade", "atividades", "atividade-listar", atividade, acesso_aee=True
    )


def atividade_excluir(request, pk):
    return _excluir(request, Atividade, pk, "Excluir atividade", "atividades", "atividade-listar", acesso_aee=True)
