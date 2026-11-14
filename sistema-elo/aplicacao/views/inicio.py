from datetime import datetime, time, timedelta
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from aplicacao.servicos.acesso import alunos_com_funcao, alunos_permitidos, id_seguro
from aplicacao.forms import FiltroAuditoria
from aplicacao.servicos.indicadores import dados_metas
from aplicacao.models import Aluno, Atividade, Professor, RegistroAuditoria
from aplicacao.views.cadastros import alunos


@require_GET
def pagina_inicial(request):
    perfil = request.perfil_elo
    eh_professor = perfil.tipo_perfil == 'PROFESSOR'
    gestor = eh_professor and perfil.gestor
    alunos = (alunos_com_funcao(perfil, Professor.Funcao.AEE)
              if eh_professor else alunos_permitidos(perfil))
    alunos = list(alunos.order_by('nome', 'sobrenome', 'pk'))
    aluno_id = request.GET.get('aluno')
    aluno = None
    if aluno_id is not None:
        identificador = id_seguro(aluno_id)
        aluno = next((item for item in alunos if item.pk == identificador), None)
        if aluno is None:
            raise PermissionDenied('Este aluno não está disponível para seu acompanhamento.')
    elif alunos:
        aluno = alunos[0]

    progresso = None
    if aluno is not None:
        contagens = Atividade.objects.filter(aluno=aluno).exclude(
            situacao=Atividade.Situacao.CANCELADA).aggregate(
                total=Count('pk'),
                realizadas=Count('pk', filter=Q(situacao=Atividade.Situacao.CONCLUIDA)),
                pendentes=Count('pk', filter=Q(situacao=Atividade.Situacao.PENDENTE)),
            )
        total = contagens['total']
        progresso = {
            **contagens,
            'percentual': round(100 * contagens['realizadas'] / total) if total else 0,
        }

    contexto = {
        'pagina_ativa': 'pagina-inicial',
        'gestor': gestor,
        'eh_professor': eh_professor,
        'eh_responsavel': perfil.tipo_perfil == 'RESPONSAVEL',
        'eh_aluno': perfil.tipo_perfil == 'ALUNO',
        'alunos_disponiveis': alunos,
        'mostrar_filtro_aluno': len(alunos) > 1 and perfil.tipo_perfil != 'ALUNO',
        'aluno_selecionado': aluno,
        'progresso': progresso,
    }
    if gestor:
        metas = dados_metas(perfil, {})['metas']
        contexto.update({
            'total_professores': Professor.objects.count(),
            'total_alunos': Aluno.objects.count(),
            'professores_ativos': Professor.objects.filter(ativo=True).count(),
            'metas_andamento': sum(m['estado'] == 'EM_ANDAMENTO' for m in metas),
            'atividades_pendentes': Atividade.objects.filter(
                situacao=Atividade.Situacao.PENDENTE).count(),
        })
    return render(request, 'aplicacao/paineis/pagina-inicial.html', contexto)


@require_GET
def auditoria(request):
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
    return render(request, 'aplicacao/auditoria/auditoria.html', {
        'formulario': formulario, 'pagina': Paginator(registros, 25).get_page(request.GET.get('pagina')),
        'filtros': parametros.urlencode(), 'pagina_ativa': 'auditoria', 'total_cadastrados': total_registros})
