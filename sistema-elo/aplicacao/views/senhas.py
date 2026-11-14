from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods
from aplicacao.servicos.acesso import alunos_com_funcao
from aplicacao.servicos.auditoria import registrar
from aplicacao.forms import PedidoRecuperacaoForm, RedefinicaoSenha
from aplicacao.servicos.limite_login import ip_cliente
from aplicacao.models import (Aluno, Professor, Responsavel, SolicitacaoSenha, Usuario,
                     Vinculo, VinculoFamiliar, VinculoProfissional)


def _professor_logado(request):
    perfil = getattr(request, 'perfil_elo', None)
    if not perfil or perfil.tipo_perfil != Usuario.TipoPerfil.PROFESSOR:
        raise PermissionDenied
    return perfil


def _pessoa_e_rota(perfil):
    if perfil.tipo_perfil == Usuario.TipoPerfil.ALUNO:
        return perfil.aluno_perfil, 'aluno-listar', 'alunos'
    if perfil.tipo_perfil == Usuario.TipoPerfil.RESPONSAVEL:
        return perfil.responsavel_perfil, 'responsavel-listar', 'responsaveis'
    raise PermissionDenied


def _conta_para_formulario(perfil, pessoa):
    if perfil.conta_id:
        return perfil.conta, False
    conta = get_user_model()(username=perfil.usuario, first_name=pessoa.nome,
                            last_name=pessoa.sobrenome, is_active=pessoa.ativo)
    return conta, True


def _salvar_senha(perfil, pessoa, formulario, request, *, somente_nova=False):
    perfil = Usuario.objects.select_for_update().select_related('conta').get(pk=perfil.pk)
    if not pessoa.ativo:
        raise PermissionDenied('O cadastro está inativo.')
    if somente_nova and perfil.conta_id:
        return False
    if perfil.conta_id:
        if formulario.user.pk != perfil.conta_id:
            return False
    elif formulario.user.pk or get_user_model().objects.filter(username__iexact=perfil.usuario).exists():
        return False
    conta = formulario.save()
    perfil.conta = conta
    perfil.troca_senha_obrigatoria = True
    perfil.save(update_fields=['conta', 'troca_senha_obrigatoria', 'atualizado_em'])
    registrar('SENHA', request=request, objeto=perfil,
              detalhes='Professor configurou senha temporária; troca obrigatória no próximo login.')
    return True


def _alunos_do_responsavel(responsavel):
    return Aluno.objects.filter(ativo=True).filter(
        Q(vinculo__responsavel=responsavel, vinculo__ativo=True)
        | Q(vinculos_familiares__responsavel=responsavel,
            vinculos_familiares__ativo=True)
    ).distinct()


def _aee_do_aluno(aluno):
    hoje = timezone.localdate()
    legado = (Vinculo.objects.select_related('professor__usuario').filter(
        aluno=aluno, ativo=True, data_vinculo__lte=hoje,
        professor__ativo=True, professor__usuario__conta__isnull=False,
    ).order_by('pk').first())
    if legado:
        return legado.professor
    profissional = (VinculoProfissional.objects.select_related('professor').filter(
        aluno=aluno, ativo=True, funcao=Professor.Funcao.AEE,
        data_inicio__lte=hoje, professor__ativo=True,
        professor__usuario__conta__isnull=False,
    ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=hoje)).order_by('pk').first())
    return profissional.professor if profissional else None


def _alvo_por_usuario(nome):
    perfil = Usuario.objects.select_related('conta').filter(usuario__iexact=nome).first()
    if not perfil or perfil.gestor or (perfil.conta_id and (perfil.conta.is_superuser or not perfil.conta.is_active)):
        return None, None, None
    try:
        pessoa = getattr(perfil, {'ALUNO': 'aluno_perfil', 'RESPONSAVEL': 'responsavel_perfil',
                                  'PROFESSOR': 'professor_perfil'}[perfil.tipo_perfil])
    except (KeyError, AttributeError):
        return None, None, None
    if not pessoa.ativo:
        return None, None, None
    if perfil.tipo_perfil == 'ALUNO':
        aluno = pessoa
        if not Vinculo.objects.filter(aluno=aluno, ativo=True).exists() and not VinculoProfissional.objects.filter(
                aluno=aluno, ativo=True).exists():
            return None, None, None
    elif perfil.tipo_perfil == 'RESPONSAVEL':
        aluno = _alunos_do_responsavel(pessoa).order_by('pk').first()
        if not aluno:
            return None, None, None
    else:
        aluno = None
    return perfil, pessoa, aluno


def pedidos_permitidos(operador):
    pedidos = SolicitacaoSenha.objects.select_related(
        'usuario_alvo', 'aluno__usuario', 'professor',
        'usuario_alvo__aluno_perfil', 'usuario_alvo__responsavel_perfil',
        'usuario_alvo__professor_perfil',
    )
    if operador.tipo_perfil != Usuario.TipoPerfil.PROFESSOR:
        return pedidos.none()
    if operador.gestor:
        return pedidos
    alunos = alunos_com_funcao(operador, Professor.Funcao.AEE)
    responsaveis = Responsavel.objects.filter(
        Q(vinculos__aluno__in=alunos, vinculos__ativo=True)
        | Q(vinculos_familiares__aluno__in=alunos, vinculos_familiares__ativo=True)
    ).values('usuario_id')
    return pedidos.filter(
        Q(aluno__in=alunos, usuario_alvo__isnull=True)
        | Q(aluno__in=alunos, usuario_alvo__tipo_perfil='ALUNO')
        | Q(usuario_alvo_id__in=responsaveis, usuario_alvo__tipo_perfil='RESPONSAVEL')
    ).distinct()


def _pessoa_do_pedido(pedido):
    perfil = pedido.usuario_alvo or (pedido.aluno.usuario if pedido.aluno_id else None)
    if perfil is None:
        raise PermissionDenied('Solicitação sem usuário associado.')
    if perfil.tipo_perfil == 'PROFESSOR':
        pessoa = perfil.professor_perfil
    elif perfil.tipo_perfil == 'RESPONSAVEL':
        pessoa = perfil.responsavel_perfil
    else:
        pessoa = perfil.aluno_perfil
    return perfil, pessoa


@require_http_methods(['GET', 'POST'])
def solicitar_senha(request):
    formulario = PedidoRecuperacaoForm(request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        nome = formulario.cleaned_data['usuario']
        origem = salted_hmac('elo.pedidos.senha', ip_cliente(request), algorithm='sha256').hexdigest()
        agora = timezone.now()
        with transaction.atomic():
            perfil, pessoa, aluno = _alvo_por_usuario(nome)
            if perfil:
                perfil = Usuario.objects.select_for_update().get(pk=perfil.pk)
                limite = SolicitacaoSenha.objects.filter(
                    origem_hash=origem, criada_em__gte=agora-timedelta(minutes=30)).count() >= 5
                pendente_do_alvo = Q(usuario_alvo=perfil)
                if perfil.tipo_perfil == Usuario.TipoPerfil.ALUNO:
                    pendente_do_alvo |= Q(usuario_alvo__isnull=True, aluno=aluno)
                pendente = SolicitacaoSenha.objects.filter(
                    situacao='PENDENTE').filter(pendente_do_alvo).exists()
                if not limite and not pendente:
                    destinatario = _aee_do_aluno(aluno) if aluno else None
                    pedido = SolicitacaoSenha.objects.create(
                        usuario_alvo=perfil, aluno=aluno, professor=destinatario,
                        origem_hash=origem,
                    )
                    registrar('SENHA', request=request, entidade='solicitacao_senha', objeto=pedido,
                              detalhes='Solicitação de recuperação de acesso registrada.')
        return render(request, 'aplicacao/contas/recuperar-senha.html', {'enviado': True})
    return render(request, 'aplicacao/contas/recuperar-senha.html', {'formulario': formulario})


@require_GET
def lista_solicitacoes(request):
    perfil = _professor_logado(request)
    pedidos = pedidos_permitidos(perfil)
    total = pedidos.count()
    visao = request.GET.get('filtro', 'todas')
    if visao not in {'todas', 'pendentes', 'atendidas'}:
        visao = 'todas'
    if visao != 'todas':
        pedidos = pedidos.filter(situacao='PENDENTE' if visao == 'pendentes' else 'ATENDIDA')
    busca = request.GET.get('busca', '').strip()[:100]
    for parte in busca.split():
        criterio = Q(usuario_alvo__usuario__icontains=parte)
        for relacao in ('usuario_alvo__aluno_perfil', 'usuario_alvo__responsavel_perfil',
                        'usuario_alvo__professor_perfil'):
            criterio |= Q(**{relacao + '__nome__icontains': parte}) | Q(**{relacao + '__sobrenome__icontains': parte})
        criterio |= Q(usuario_alvo__isnull=True) & (
            Q(aluno__nome__icontains=parte) | Q(aluno__sobrenome__icontains=parte)
            | Q(aluno__usuario__usuario__icontains=parte))
        pedidos = pedidos.filter(criterio)
    pagina = Paginator(pedidos.order_by('situacao', '-criada_em', '-pk'), 15).get_page(request.GET.get('pagina'))
    filtros = request.GET.copy()
    filtros.pop('pagina', None)
    return render(request, 'aplicacao/contas/solicitacoes-senha.html', {
        'pedidos': pagina.object_list, 'pagina': pagina,
        'pagina_ativa': 'solicitacoes-senha', 'total_cadastrados': total,
        'visao': visao, 'busca': busca, 'filtros_paginacao': filtros.urlencode(),
    })


@sensitive_post_parameters('new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def atender_solicitacao(request, pk):
    operador = _professor_logado(request)
    try:
        pedido = pedidos_permitidos(operador).get(pk=pk)
    except SolicitacaoSenha.DoesNotExist:
        anteriormente_designado = SolicitacaoSenha.objects.filter(
            pk=pk, professor__usuario=operador,
        ).filter(Q(usuario_alvo__tipo_perfil='ALUNO') | Q(usuario_alvo__isnull=True)).exists()
        if anteriormente_designado and not operador.gestor:
            raise PermissionDenied('O aluno não possui mais vínculo AEE ativo com este professor.')
        raise Http404
    perfil_alvo, pessoa = _pessoa_do_pedido(pedido)
    if pedido.situacao != SolicitacaoSenha.Situacao.PENDENTE:
        messages.info(request, 'Esta solicitação já foi atendida.')
        return redirect('solicitacao-senha-listar')
    if not pessoa.ativo or (perfil_alvo.conta_id and perfil_alvo.conta.is_superuser):
        raise PermissionDenied('A conta não pode ser redefinida.')
    if perfil_alvo.pk == operador.pk:
        raise PermissionDenied('Não é permitido redefinir a própria senha por uma solicitação.')
    conta, is_ativacao = _conta_para_formulario(perfil_alvo, pessoa)
    formulario = RedefinicaoSenha(conta, request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            pedido = SolicitacaoSenha.objects.select_for_update().get(pk=pk)
            if not pedidos_permitidos(operador).filter(pk=pedido.pk).exists():
                raise PermissionDenied('O vínculo com este usuário foi desativado.')
            if pedido.situacao != SolicitacaoSenha.Situacao.PENDENTE:
                messages.info(request, 'Esta solicitação já foi atendida.')
                return redirect('solicitacao-senha-listar')
            perfil_alvo, pessoa = _pessoa_do_pedido(pedido)
            if not pessoa.ativo or perfil_alvo.pk == operador.pk:
                raise PermissionDenied('Solicitação sem permissão para atendimento.')
            if not _salvar_senha(perfil_alvo, pessoa, formulario, request):
                formulario.add_error(None, 'O acesso foi alterado por outra operação. Atualize a página e tente novamente.')
            else:
                pedido.situacao = SolicitacaoSenha.Situacao.ATENDIDA
                pedido.atendida_em = timezone.now()
                pedido.save(update_fields=['situacao', 'atendida_em'])
                messages.success(request, 'Solicitação atendida. Confirme a identidade do usuário antes de fornecer a senha temporária.')
                return redirect('solicitacao-senha-listar')
    return render(request, 'aplicacao/contas/redefinir-senha.html', {
        'formulario': formulario, 'pessoa': pessoa, 'perfil_alvo': perfil_alvo,
        'rota_voltar': 'solicitacao-senha-listar', 'pagina_ativa': 'solicitacoes-senha',
        'solicitacao': pedido, 'is_ativacao': is_ativacao,
    })


@sensitive_post_parameters('new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def ativar_acesso(request, pk):
    operador = _professor_logado(request)
    perfil_alvo = get_object_or_404(
        Usuario.objects.select_related('conta'), pk=pk,
        tipo_perfil__in=[Usuario.TipoPerfil.ALUNO, Usuario.TipoPerfil.RESPONSAVEL],
        conta__isnull=True,
    )
    pessoa, rota, pagina = _pessoa_e_rota(perfil_alvo)
    if not operador.gestor:
        if perfil_alvo.tipo_perfil != Usuario.TipoPerfil.ALUNO or not alunos_com_funcao(
                operador, Professor.Funcao.AEE).filter(pk=pessoa.pk).exists():
            raise PermissionDenied('Apenas aluno vinculado em sua função AEE.')
    if not pessoa.ativo:
        raise PermissionDenied('O cadastro está inativo.')
    conta, _ = _conta_para_formulario(perfil_alvo, pessoa)
    formulario = RedefinicaoSenha(conta, request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            if _salvar_senha(perfil_alvo, pessoa, formulario, request, somente_nova=True):
                criterio = Q(usuario_alvo=perfil_alvo)
                if perfil_alvo.tipo_perfil == Usuario.TipoPerfil.ALUNO:
                    criterio |= Q(usuario_alvo__isnull=True, aluno=pessoa)
                SolicitacaoSenha.objects.filter(
                    situacao=SolicitacaoSenha.Situacao.PENDENTE
                ).filter(criterio).update(
                    situacao=SolicitacaoSenha.Situacao.ATENDIDA, atendida_em=timezone.now())
                messages.success(request, f'Acesso de {pessoa.nome_completo} ativado. Oriente a troca de senha no primeiro login.')
                return redirect(rota)
            formulario.add_error(None, 'A conta já foi ativada ou o nome de usuário está em uso. Atualize a página.')
    return render(request, 'aplicacao/contas/redefinir-senha.html', {
        'formulario': formulario, 'pessoa': pessoa, 'perfil_alvo': perfil_alvo,
        'rota_voltar': rota, 'pagina_ativa': pagina, 'is_ativacao': True,
    })
