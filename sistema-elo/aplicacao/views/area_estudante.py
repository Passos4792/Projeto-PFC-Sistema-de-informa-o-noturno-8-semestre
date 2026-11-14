import secrets
import time
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST
from rest_framework.exceptions import ValidationError as ErroFormulario
from aplicacao.servicos import google_calendar as google
from aplicacao.servicos.sincronizacao_automatica import sincronizar_usuario
from aplicacao.servicos.acesso import alunos_area_estudante, alunos_atividades_visiveis, id_seguro, pode_gerenciar_pedagogia
from aplicacao.views.api import EntregaIndisponivel, registrar_entrega_atividade
from aplicacao.servicos.auditoria import registrar
from aplicacao.models import Atividade, ConexaoGoogle, SincronizacaoGoogle, SolicitacaoConclusao


def conferir_perfil(request):
    if request.perfil_elo.tipo_perfil not in ('ALUNO', 'RESPONSAVEL'):
        raise PermissionDenied


def _ultima_solicitacao(atividade):
    return (SolicitacaoConclusao.objects.filter(atividade=atividade)
            .select_related('solicitante', 'professor').first())


@require_GET
@never_cache
def atividade_detalhe(request, pk):
    perfil = request.perfil_elo
    atividade = get_object_or_404(
        Atividade.objects.select_related('aluno', 'professor', 'disciplina'), pk=pk)
    eh_professor = perfil.tipo_perfil == 'PROFESSOR'
    if eh_professor:
        if not (perfil.gestor or (
                atividade.professor.usuario_id == perfil.pk
                and pode_gerenciar_pedagogia(perfil, atividade.aluno_id))):
            raise PermissionDenied
    else:
        conferir_perfil(request)
        if not alunos_atividades_visiveis(perfil).filter(pk=atividade.aluno_id).exists():
            raise PermissionDenied
    pode_enviar_atividade = not eh_professor and alunos_area_estudante(perfil).filter(
        pk=atividade.aluno_id).exists()
    ultima = _ultima_solicitacao(atividade)
    conexao = None if eh_professor else ConexaoGoogle.objects.filter(usuario=perfil).first()
    sincronizado = None
    if conexao:
        sincronizado = SincronizacaoGoogle.objects.filter(
            usuario=perfil, atividade=atividade, identidade=conexao.identidade
        ).values_list('sincronizado_em', flat=True).first()
    voltar_historico = eh_professor and request.GET.get('origem') == 'historico'
    voltar = 'atividade-listar' if eh_professor else 'minhas-atividades'
    pagina_entregas = None
    if eh_professor:
        pagina_entregas = Paginator(SolicitacaoConclusao.objects.filter(atividade=atividade)
                                   .select_related('solicitante', 'professor')
                                   .order_by('-solicitado_em', '-pk'), 10).get_page(request.GET.get('pagina'))
    return render(request, 'aplicacao/atividades/atividade-detalhe.html', {
        'pagina_ativa': 'atividades' if eh_professor else 'minhas-atividades',
        'atividade': atividade, 'ultima': ultima, 'eh_professor': eh_professor,
        'pode_enviar_atividade': pode_enviar_atividade,
        'entregas': pagina_entregas.object_list if pagina_entregas else [],
        'pagina_entregas': pagina_entregas,
        'rota_voltar': voltar, 'voltar_historico': voltar_historico, 'google_conectado': bool(conexao),
        'google_configurado': google.configurado() if not eh_professor else False,
        'google_sincronizado_em': sincronizado,
    })


@require_GET
@never_cache
def minhas_atividades(request):
    conferir_perfil(request)
    visiveis = alunos_atividades_visiveis(request.perfil_elo)
    atividades = Atividade.objects.filter(aluno__in=visiveis).select_related('aluno', 'professor', 'disciplina')
    aluno_id = request.GET.get('aluno', '')
    if aluno_id:
        aluno = get_object_or_404(visiveis, pk=id_seguro(aluno_id))
        atividades = atividades.filter(aluno=aluno)
    total = atividades.count()
    visao = request.GET.get('filtro', 'todas')
    if visao not in {'todas', 'pendentes', 'avaliacao', 'concluidas', 'canceladas'}:
        visao = 'todas'
    em_avaliacao = SolicitacaoConclusao.objects.filter(situacao='PENDENTE').values('atividade_id')
    if visao == 'pendentes':
        atividades = atividades.filter(situacao='PENDENTE').exclude(pk__in=em_avaliacao)
    elif visao == 'avaliacao':
        atividades = atividades.filter(situacao='PENDENTE', pk__in=em_avaliacao)
    elif visao == 'concluidas':
        atividades = atividades.filter(situacao='CONCLUIDA')
    elif visao == 'canceladas':
        atividades = atividades.filter(situacao='CANCELADA')
    busca = request.GET.get('busca', '').strip()[:100]
    for parte in busca.split():
        atividades = atividades.filter(Q(titulo__icontains=parte) | Q(aluno__nome__icontains=parte)
                                      | Q(aluno__sobrenome__icontains=parte)
                                      | Q(disciplina__nome__icontains=parte))
    pagina = Paginator(atividades.order_by('data_entrega', 'pk'), 10).get_page(request.GET.get('pagina'))
    itens = list(pagina.object_list)
    ids = [atividade.pk for atividade in itens]
    conexao = ConexaoGoogle.objects.filter(usuario=request.perfil_elo).first()
    sincronizadas = {}
    if conexao and ids:
        sincronizadas = dict(SincronizacaoGoogle.objects.filter(
            usuario=request.perfil_elo, identidade=conexao.identidade,
            sincronizado_em__isnull=False, atividade_id__in=ids).values_list('atividade_id', 'sincronizado_em'))
    ultimas = {}
    for solicitacao in SolicitacaoConclusao.objects.filter(atividade__in=itens).select_related('professor'):
        ultimas.setdefault(solicitacao.atividade_id, solicitacao)
    for atividade in itens:
        atividade.google_sincronizado_em = sincronizadas.get(atividade.pk)
        atividade.ultima_solicitacao = ultimas.get(atividade.pk)
    filtros = request.GET.copy()
    filtros.pop('pagina', None)
    filtros_abas = filtros.copy()
    filtros_abas.pop('filtro', None)
    return render(request, 'aplicacao/atividades/minhas-atividades.html', {
        'visao': visao, 'filtros_abas': filtros_abas.urlencode(),
        'pagina_ativa': 'minhas-atividades', 'atividades': itens, 'pagina': pagina,
        'filtros_paginacao': filtros.urlencode(), 'total_cadastrados': total,
        'busca': busca, 'google_conectado': bool(conexao), 'google_configurado': google.configurado(),
    })


@require_POST
@never_cache
def enviar_atividade(request, pk):
    conferir_perfil(request)

    dados = request.POST.copy()
    if 'anexo' in request.FILES:
        dados['anexo'] = request.FILES['anexo']
    else:
        dados.pop('anexo', None)

    try:
        registrar_entrega_atividade(request, pk, dados)
    except ErroFormulario as erro:
        def mensagens(valor):
            if isinstance(valor, dict):
                return ' '.join(mensagens(item) for item in valor.values())
            if isinstance(valor, (list, tuple)):
                return ' '.join(mensagens(item) for item in valor)
            return str(valor)
        messages.error(request, mensagens(erro.detail))
    except EntregaIndisponivel as erro:
        messages.warning(request, str(erro))
    else:
        messages.success(request, 'Atividade enviada com sucesso! Aguardando avaliação do professor.')
    return redirect('atividade-detalhe', pk=pk)


@require_POST
@never_cache
def conectar(request):
    conferir_perfil(request)
    if not google.configurado():
        messages.info(request, 'A conexão com o Google Agenda ainda está sendo preparada pelo administrador.')
        return redirect('minhas-atividades')
    return redirect(google.iniciar_oauth(request, origem=request.POST.get('origem', 'atividades')))


@require_GET
@never_cache
@sensitive_variables()
def retorno(request):
    conferir_perfil(request)
    fluxo = request.session.pop('google_oauth', {})
    destino = 'meus-dados' if fluxo.get('origem') == 'perfil' else 'minhas-atividades'
    recebido = request.GET.get('state', '')
    valido = (fluxo.get('usuario') == request.user.pk and recebido and
              secrets.compare_digest(fluxo.get('state', ''), recebido) and
              0 <= time.time() - fluxo.get('criado', 0) < 600)
    if not valido:
        messages.error(request, 'A conexão expirou ou não pôde ser confirmada. Inicie novamente pelo botão Conectar.')
        return redirect(destino)
    if request.GET.get('error'):
        messages.info(request, 'A conexão com o Google foi cancelada. Você pode continuar usando as atividades normalmente.')
        return redirect(destino)
    if not google.configurado() or not request.GET.get('code'):
        messages.error(request, 'Não foi possível concluir a conexão com o Google.')
        return redirect(destino)
    try:
        conexao_anterior = ConexaoGoogle.objects.filter(usuario=request.perfil_elo).first()
        identidade, credenciais = google.trocar_codigo(request.GET['code'], fluxo['verifier'],
                                                       conexao_anterior, fluxo.get('conta_google'))
        with transaction.atomic():
            ConexaoGoogle.objects.update_or_create(usuario=request.perfil_elo, defaults={
                'identidade': identidade, 'credenciais': credenciais,
            })
            registrar('EDICAO', request=request, entidade='Google Agenda', detalhes='Conta conectada ao calendário.')
        quantas, falhas = sincronizar_usuario(request.perfil_elo)
        messages.success(request, f'Google Agenda conectado! {quantas} atividade(s) futura(s) sincronizada(s). As próximas serão enviadas automaticamente.')
        if falhas:
            messages.warning(request, f'{falhas} atividade(s) não puderam ser sincronizadas agora. Verifique sua conexão Google.')
    except google.PermissaoCalendarioPendente as exc:
        if not fluxo.get('conta_google'):
            return redirect(google.iniciar_oauth(request, conta_google=exc.identidade, origem=fluxo.get('origem', 'atividades')))
        messages.error(request, str(exc))
    except google.GoogleErro as exc:
        messages.error(request, str(exc))
    return redirect(destino)


@require_POST
def sincronizar(request, pk):
    conferir_perfil(request)
    atividade = get_object_or_404(Atividade.objects.select_related('aluno'), pk=pk,
                                 aluno__in=alunos_atividades_visiveis(request.perfil_elo))
    if not atividade.data_entrega or atividade.situacao == 'CANCELADA':
        messages.info(request, 'Só é possível sincronizar atividades com data de entrega e que não estejam canceladas.')
        return redirect('minhas-atividades')
    if not google.configurado():
        messages.info(request, 'A conexão com o Google Agenda ainda não está disponível.')
        return redirect('minhas-atividades')
    try:
        conexao = ConexaoGoogle.objects.filter(usuario=request.perfil_elo).first()
        if not conexao:
            raise google.ReconectarGoogle('Conecte sua conta Google antes de sincronizar.')
        anterior = SincronizacaoGoogle.objects.filter(
            usuario=request.perfil_elo, atividade=atividade, identidade=conexao.identidade).first()
        evento = google.enviar_atividade(
            conexao, atividade,
            anterior.evento_id if anterior else google.evento_id(request.perfil_elo, conexao.identidade, atividade))
        with transaction.atomic():
            SincronizacaoGoogle.objects.update_or_create(
                usuario=request.perfil_elo, atividade=atividade, identidade=conexao.identidade,
                defaults={'evento_id': evento, 'sincronizado_em': timezone.now()},
            )
            registrar('EDICAO', request=request, objeto=atividade, detalhes='Atividade sincronizada com o Google Agenda pelo usuário.')
        messages.success(request, f'Google confirmou: “{atividade.titulo}” em '
                         f'{atividade.data_entrega:%d/%m/%Y}, no calendário principal da conta conectada.')
    except google.ReconectarGoogle as exc:
        ConexaoGoogle.objects.filter(usuario=request.perfil_elo).delete()
        messages.warning(request, str(exc))
    except google.GoogleErro as exc:
        messages.error(request, str(exc))
    return redirect('minhas-atividades')


@require_POST
def desconectar(request):
    conferir_perfil(request)
    request.session.pop('google_oauth', None)
    revogada = True
    with transaction.atomic():
        conexao = ConexaoGoogle.objects.select_for_update().filter(usuario=request.perfil_elo).first()
        if conexao:
            try:
                google.revogar(conexao)
            except google.GoogleErro:
                revogada = False
            conexao.delete()
            registrar('EDICAO', request=request, entidade='Google Agenda', detalhes='Conexão com o calendário removida.')
    messages.success(request, 'Conta desconectada do ELO. Os eventos já enviados permanecem no Google Agenda.')
    if not revogada:
        messages.warning(request, 'Não foi possível revogar a autorização no Google. Remova também o acesso do ELO nas conexões da sua Conta Google.')
    return redirect('meus-dados' if request.POST.get('origem') == 'perfil' else 'minhas-atividades')
