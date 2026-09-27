#importacoes
import secrets
import time

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST

from . import google_calendar as google
from .acesso import alunos_permitidos
from .auditoria import registrar
from .models import Atividade, ConexaoGoogle, SincronizacaoGoogle


#-------------------------------------------------------------------------------------

#verificacao do perfil para acesso ao calendario
def conferir_perfil(request):
    if request.perfil_elo.tipo_perfil not in ('ALUNO', 'RESPONSAVEL'):
        raise PermissionDenied


#-------------------------------------------------------------------------------------

#listagem e pesquisa das atividades do usuario
@require_GET
def minhas_atividades(request):
    conferir_perfil(request)
    atividades = Atividade.objects.filter(aluno__in=alunos_permitidos(request.perfil_elo)).select_related('aluno', 'professor')
    total = atividades.count()
    busca = request.GET.get('busca', '').strip()
    for parte in busca.split():
        atividades = atividades.filter(Q(titulo__icontains=parte) | Q(aluno__nome__icontains=parte)
                                      | Q(aluno__sobrenome__icontains=parte))
    conexao = ConexaoGoogle.objects.filter(usuario=request.perfil_elo).first()
    sincronizadas = {}
    if conexao:
        sincronizadas = dict(SincronizacaoGoogle.objects.filter(
            usuario=request.perfil_elo, identidade=conexao.identidade,
            sincronizado_em__isnull=False).values_list('atividade_id', 'sincronizado_em'))
    itens = list(atividades)
    for atividade in itens:
        atividade.google_sincronizado_em = sincronizadas.get(atividade.pk)
    return render(request, 'aplicacao/minhas-atividades.html', {
        'pagina_ativa': 'minhas-atividades', 'atividades': itens, 'total_cadastrados': total,
        'busca': busca, 'google_conectado': bool(conexao), 'google_configurado': google.configurado(),
    })


#-------------------------------------------------------------------------------------

#conexao da conta Google
@require_POST
@never_cache
def conectar(request):
    conferir_perfil(request)
    if not google.configurado():
        messages.info(request, 'A conexão com o Google Agenda ainda está sendo preparada pelo administrador.')
        return redirect('minhas-atividades')
    return redirect(google.iniciar_oauth(request))


#-------------------------------------------------------------------------------------

#retorno da autorizacao do Google
@require_GET
@never_cache
@sensitive_variables()
def retorno(request):
    conferir_perfil(request)
    fluxo = request.session.pop('google_oauth', {})
    recebido = request.GET.get('state', '')
    valido = (fluxo.get('usuario') == request.user.pk and recebido and
              secrets.compare_digest(fluxo.get('state', ''), recebido) and
              0 <= time.time() - fluxo.get('criado', 0) < 600)
    if not valido:
        messages.error(request, 'A conexão expirou ou não pôde ser confirmada. Inicie novamente pelo botão Conectar.')
        return redirect('minhas-atividades')
    if request.GET.get('error'):
        messages.info(request, 'A conexão com o Google foi cancelada. Você pode continuar usando as atividades normalmente.')
        return redirect('minhas-atividades')
    if not google.configurado() or not request.GET.get('code'):
        messages.error(request, 'Não foi possível concluir a conexão com o Google.')
        return redirect('minhas-atividades')
    try:
        identidade, credenciais = google.trocar_codigo(request.GET['code'], fluxo['verifier'])
        with transaction.atomic():
            ConexaoGoogle.objects.update_or_create(usuario=request.perfil_elo, defaults={
                'identidade': identidade, 'credenciais': credenciais,
            })
            registrar('EDICAO', request=request, entidade='Google Agenda', detalhes='Conta conectada ao calendário.')
        messages.success(request, 'Google Agenda conectado. Escolha as atividades que deseja sincronizar.')
    except google.GoogleErro as exc:
        messages.error(request, str(exc))
    return redirect('minhas-atividades')


#-------------------------------------------------------------------------------------

#sincronizacao da atividade com o Google Agenda
@require_POST
def sincronizar(request, pk):
    conferir_perfil(request)
    atividade = get_object_or_404(Atividade.objects.select_related('aluno'), pk=pk,
                                 aluno__in=alunos_permitidos(request.perfil_elo))
    if not atividade.data_entrega or atividade.situacao == 'CANCELADA':
        messages.info(request, 'Só é possível sincronizar atividades com data de entrega e que não estejam canceladas.')
        return redirect('minhas-atividades')
    if not google.configurado():
        messages.info(request, 'A conexão com o Google Agenda ainda não está disponível.')
        return redirect('minhas-atividades')
    try:
        with transaction.atomic():
            conexao = ConexaoGoogle.objects.select_for_update().filter(usuario=request.perfil_elo).first()
            if not conexao:
                raise google.ReconectarGoogle('Conecte sua conta Google antes de sincronizar.')
            sync, _ = SincronizacaoGoogle.objects.get_or_create(
                usuario=request.perfil_elo, atividade=atividade, identidade=conexao.identidade,
                defaults={'evento_id': google.evento_id(request.perfil_elo, conexao.identidade, atividade)},
            )
            sync.evento_id = google.enviar_atividade(conexao, atividade, sync.evento_id)
            sync.sincronizado_em = timezone.now()
            sync.save(update_fields=['evento_id', 'sincronizado_em'])
            registrar('EDICAO', request=request, objeto=atividade, detalhes='Atividade sincronizada com o Google Agenda pelo usuário.')
        messages.success(request, 'Atividade sincronizada no seu calendário principal do Google.')
    except google.ReconectarGoogle as exc:
        ConexaoGoogle.objects.filter(usuario=request.perfil_elo).delete()
        messages.warning(request, str(exc))
    except google.GoogleErro:
        messages.error(request, 'Não foi possível sincronizar agora. Tente novamente; se continuar, reconecte sua conta Google.')
    return redirect('minhas-atividades')


#-------------------------------------------------------------------------------------

#desconexao da conta Google
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
    return redirect('minhas-atividades')
