
from datetime import datetime, time
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from .acesso import alunos_permitidos
from .api import solicitacoes_permitidas
from .auditoria import registrar
from .forms import FormularioDisciplina, FormularioFrequenciaMinima, FiltroAprovacoes
from .indicadores import FiltroPainel, dados_painel, dados_frequencia, dados_conteudos, dados_metas
from .models import Aluno, Conteudo, Disciplina


def mostrar_painel(request, secao, aluno=None):
    parametros = request.GET.copy()
    if secao in ('frequencias', 'conteudos'):
        for campo in ('busca', 'inicio', 'fim', 'periodo'):
            parametros.pop(campo, None)
    if secao == 'metas':
        for campo in ('busca', 'inicio', 'fim'):
            parametros.pop(campo, None)
    if aluno:
        parametros['aluno'] = str(aluno.pk)
    formulario = FiltroPainel(parametros, perfil=request.perfil_elo)
    valido = formulario.is_valid()
    calcular = {'frequencias': dados_frequencia, 'conteudos': dados_conteudos, 'metas': dados_metas}.get(secao, dados_painel)
    dados = calcular(request.perfil_elo, formulario.cleaned_data) if valido else None

    frequencias_lista = dados.get('frequencias', []) if dados else []
    conteudos_lista = dados.get('conteudos', []) if dados else []
    pagina_conteudos = None
    metas_lista = dados.get('metas', []) if dados else []
    pagina_metas = None
    pagina_frequencias = None
    filtros_paginacao = parametros.copy()
    filtros_paginacao.pop('pagina', None)
    if secao == 'frequencias' and dados:
        pagina_frequencias = Paginator(frequencias_lista, 10).get_page(request.GET.get('pagina'))
        frequencias_lista = pagina_frequencias.object_list
    if secao == 'conteudos' and dados:
        pagina_conteudos = Paginator(conteudos_lista, 10).get_page(request.GET.get('pagina'))
        conteudos_lista = pagina_conteudos.object_list
    if secao == 'metas' and dados:
        pagina_metas = Paginator(metas_lista, 10).get_page(request.GET.get('pagina'))
        metas_lista = pagina_metas.object_list
    titulos = {'metas': 'Metas', 'conteudos': 'Conteúdos', 'frequencias': 'Frequência',
               'acompanhamento': 'Acompanhamento'}
    return render(request, 'aplicacao/painel-acompanhamento.html', {
        'titulo': titulos[secao], 'secao': secao, 'pagina_ativa': secao, 'dados': dados,
        'frequencias_lista': frequencias_lista, 'pagina_frequencias': pagina_frequencias,
        'conteudos_lista': conteudos_lista, 'pagina_conteudos': pagina_conteudos,
        'metas_lista': metas_lista, 'pagina_metas': pagina_metas,
        'painel_individual': secao in ('frequencias', 'conteudos', 'metas'),
        'mostrar_grafico_individual': bool(dados and formulario.cleaned_data.get('aluno')),
        'filtros_paginacao': filtros_paginacao.urlencode(),
        'formulario': formulario, 'professor': request.perfil_elo.tipo_perfil == 'PROFESSOR',
        'aluno': aluno, 'api_url': reverse('api-painel') + '?' + parametros.urlencode(),
        'tem_conteudos_anteriores': Conteudo.objects.exists() if secao in ('conteudos', 'acompanhamento') and request.perfil_elo.tipo_perfil == 'PROFESSOR' else False,
    }, status=200 if valido else 400)


def metas(request):
    return mostrar_painel(request, 'metas')


def conteudos(request):
    return mostrar_painel(request, 'conteudos')


def frequencias(request):
    return mostrar_painel(request, 'frequencias')


def aluno_inicio(request, pk):
    aluno = get_object_or_404(alunos_permitidos(request.perfil_elo), pk=pk)
    return mostrar_painel(request, 'acompanhamento', aluno=aluno)


def conteudo_criar(request):
    from .views import _salvar
    return _salvar(request, FormularioDisciplina, 'Novo conteúdo', 'conteudos', 'conteudo-listar')


def conteudo_editar(request, pk):
    from .views import _salvar
    return _salvar(request, FormularioDisciplina, 'Editar conteúdo', 'conteudos', 'conteudo-listar',
                   get_object_or_404(Disciplina, pk=pk))


def conteudo_excluir(request, pk):
    from .views import _excluir
    return _excluir(request, Disciplina, pk, 'Excluir conteúdo', 'conteudos', 'conteudo-listar')


def frequencia_configurar(request, pk=None):
    if request.perfil_elo.tipo_perfil != 'PROFESSOR':
        raise PermissionDenied
    aluno = get_object_or_404(Aluno, pk=pk) if pk else None
    formulario = FormularioFrequenciaMinima(request.POST if request.method == 'POST' else None,
        initial={'aluno': aluno, 'frequencia_minima': aluno.frequencia_minima if aluno else None})
    if aluno:
        formulario.fields['aluno'].disabled = True
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            alvo = Aluno.objects.select_for_update().get(pk=formulario.cleaned_data['aluno'].pk)
            minimo_anterior = alvo.frequencia_minima
            alvo.frequencia_minima = formulario.cleaned_data['frequencia_minima']
            alvo.save(update_fields=['frequencia_minima', 'atualizado_em'])
            anterior = f'{minimo_anterior}%' if minimo_anterior is not None else 'não definida'
            atual = f'{alvo.frequencia_minima}%' if alvo.frequencia_minima is not None else 'não definida'
            registrar('FREQUENCIA', request=request, objeto=alvo,
                      detalhes=f'Frequência mínima: {anterior} → {atual}.')
        messages.success(request, 'Frequência mínima atualizada.')
        return redirect('frequencia-listar')
    return render(request, 'aplicacao/formulario-padrao.html', {'formulario': formulario,
        'titulo': 'Definir frequência mínima', 'pagina_ativa': 'frequencias',
        'url_voltar': reverse('frequencia-listar')})


def aprovacoes(request):
    if request.perfil_elo.tipo_perfil != 'PROFESSOR':
        raise PermissionDenied
    from django.core.paginator import Paginator
    registros = solicitacoes_permitidas(request.perfil_elo)
    estado = request.GET.get('situacao', 'PENDENTE')
    if estado not in ('PENDENTE', 'APROVADA', 'RECUSADA', ''):
        estado = 'PENDENTE'
    total = registros.filter(situacao='PENDENTE').count()
    if estado:
        registros = registros.filter(situacao=estado)
    busca = request.GET.get('busca', '').strip()
    if busca:
        from django.db.models import Q
        registros = registros.filter(Q(atividade__titulo__icontains=busca) | Q(aluno__nome__icontains=busca)
                                      | Q(aluno__sobrenome__icontains=busca))
    parametros = request.GET.copy()
    parametros.pop('pagina', None)
    parametros.setdefault('ordem', 'recentes')
    formulario = FiltroAprovacoes(parametros)
    if formulario.is_valid():
        filtros = formulario.cleaned_data

        if filtros['inicio']:
            registros = registros.filter(solicitado_em__gte=timezone.make_aware(
                datetime.combine(filtros['inicio'], time.min)))
        if filtros['fim']:
            registros = registros.filter(solicitado_em__lte=timezone.make_aware(
                datetime.combine(filtros['fim'], time.max)))
        registros = registros.order_by('solicitado_em', 'pk') if filtros['ordem'] == 'antigas' else registros.order_by('-solicitado_em', '-pk')
    else:
        registros = registros.none()
    return render(request, 'aplicacao/aprovacoes.html', {
        'formulario_filtros': formulario,
        'pagina': Paginator(registros, 6).get_page(request.GET.get('pagina')), 'pendentes': total,
        'situacao': estado, 'busca': busca, 'filtros': parametros.urlencode(), 'pagina_ativa': 'aprovacoes'})
