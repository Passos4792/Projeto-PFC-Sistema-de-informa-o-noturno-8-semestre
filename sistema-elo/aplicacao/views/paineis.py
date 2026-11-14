from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from aplicacao.servicos.acesso import alunos_area_estudante, alunos_atividades_visiveis, alunos_com_funcao, alunos_permitidos
from aplicacao.forms import FiltroPainel
from aplicacao.servicos.indicadores import dados_metas, dados_painel, resumo_periodos
from aplicacao.models import Professor


ABAS_METAS = [('todas', 'Todas'), ('EM_ANDAMENTO', 'Em andamento'), ('ALCANCADA', 'Alcançadas'),
              ('FUTURA', 'Planejadas'), ('ENCERRADA', 'Prazo encerrado'), ('CANCELADA', 'Canceladas')]


def mostrar_painel(request, secao, aluno=None):
    parametros = request.GET.copy()
    if secao == 'metas':
        for campo in ('inicio', 'fim'):
            parametros.pop(campo, None)
        if parametros.get('busca'):
            parametros['busca'] = parametros['busca'].strip()[:100]
    if aluno:
        parametros['aluno'] = str(aluno.pk)
    formulario = FiltroPainel(parametros, perfil=request.perfil_elo)
    valido = formulario.is_valid()
    calcular = dados_metas if secao == 'metas' else dados_painel
    dados = calcular(request.perfil_elo, formulario.cleaned_data) if valido else None

    conteudos_lista = dados.get('conteudos', []) if dados else []
    estado_metas = request.GET.get('estado', 'todas')
    if estado_metas not in dict(ABAS_METAS):
        estado_metas = 'todas'
    termos = parametros.get('busca', '').casefold().split() if secao == 'metas' else []
    if secao == 'metas' and dados and termos:
        encontradas = [m for m in dados['metas'] if all(
            termo in f"{m['titulo']} {m['aluno']}".casefold() for termo in termos)]
        dados = {**dados, 'metas': encontradas, 'periodos': resumo_periodos(encontradas)}
    metas_lista = dados.get('metas', []) if dados else []
    if secao == 'metas' and estado_metas != 'todas':
        metas_lista = [m for m in metas_lista if m['estado'] == estado_metas]
    total_metas = len(metas_lista)
    pagina_metas = None
    filtros_paginacao = parametros.copy()
    filtros_paginacao.pop('pagina', None)
    filtros_abas = filtros_paginacao.copy()
    filtros_abas.pop('estado', None)
    if dados:
        pagina_metas = Paginator(metas_lista, 10).get_page(request.GET.get('pagina'))
        metas_lista = pagina_metas.object_list
    pagina_conteudos = None
    filtros_conteudos = parametros.copy()
    filtros_conteudos.pop('pagina_conteudos', None)
    if secao == 'acompanhamento' and dados:
        pagina_conteudos = Paginator(conteudos_lista, 10).get_page(request.GET.get('pagina_conteudos'))
        conteudos_lista = pagina_conteudos.object_list
    aluno_atividades = aluno or (formulario.cleaned_data.get('aluno') if valido else None)
    area_permitida = alunos_atividades_visiveis(request.perfil_elo)
    envio_permitido = alunos_area_estudante(request.perfil_elo)
    if aluno_atividades:
        area_permitida = area_permitida.filter(pk=aluno_atividades.pk)
        envio_permitido = envio_permitido.filter(pk=aluno_atividades.pk)
    pode_enviar_atividades = envio_permitido.exists()
    url_atividades = None
    if area_permitida.exists():
        url_atividades = reverse('minhas-atividades')
        if aluno_atividades:
            url_atividades += f'?aluno={aluno_atividades.pk}'

    titulos = {'metas': 'Metas', 'acompanhamento': 'Acompanhamento'}
    return render(request, 'aplicacao/paineis/painel-acompanhamento.html', {
        'url_atividades': url_atividades, 'pode_enviar_atividades': pode_enviar_atividades,
        'titulo': titulos[secao], 'secao': secao, 'pagina_ativa': secao, 'dados': dados,
        'conteudos_lista': conteudos_lista,
        'metas_lista': metas_lista, 'pagina_metas': pagina_metas, 'total_metas': total_metas,
        'abas_metas': ABAS_METAS, 'estado_metas': estado_metas, 'filtros_abas': filtros_abas.urlencode(),
        'filtro_metas_ativo': bool(termos) or estado_metas != 'todas',
        'pagina_conteudos': pagina_conteudos, 'filtros_conteudos': filtros_conteudos.urlencode(),
        'painel_individual': secao == 'metas',
        'mostrar_grafico_individual': bool(dados and (
            formulario.cleaned_data.get('aluno')
            or (secao == 'metas' and request.perfil_elo.tipo_perfil == 'PROFESSOR'))),
        'busca_metas': parametros.get('busca', '') if secao == 'metas' else '',
        'filtros_paginacao': filtros_paginacao.urlencode(),
        'formulario': formulario, 'professor': request.perfil_elo.tipo_perfil == 'PROFESSOR',
        'gestor': request.perfil_elo.gestor,
        'aluno': aluno, 'api_url': reverse('api-painel') + '?' + parametros.urlencode()
    }, status=200 if valido else 400)


def aluno_inicio(request, pk):
    permitidos = (alunos_com_funcao(request.perfil_elo, Professor.Funcao.AEE)
                  if request.perfil_elo.tipo_perfil == 'PROFESSOR' else alunos_permitidos(request.perfil_elo))
    aluno = get_object_or_404(permitidos, pk=pk)
    return mostrar_painel(request, 'acompanhamento', aluno=aluno)


def metas(request):
    return mostrar_painel(request, 'metas')
