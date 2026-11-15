from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from .auditoria import registrar
from .contas import RedefinicaoSenha
from .models import Aluno, SolicitacaoSenha, Usuario, Vinculo


class PedidoRecuperacaoForm(forms.Form):
    usuario = forms.CharField(
        label='Nome de usuário do aluno', max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'campo-formulario', 'autocomplete': 'username',
            'placeholder': 'Digite seu usuário',
        }),
    )

    def clean_usuario(self):
        return self.cleaned_data['usuario'].strip().lower()


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
    conta = get_user_model()(
        username=perfil.usuario, first_name=pessoa.nome,
        last_name=pessoa.sobrenome, is_active=pessoa.ativo,
    )
    return conta, True


def _salvar_senha(perfil, pessoa, formulario, request, *, somente_nova=False):
    # A linha de perfil bloqueada impede criação simultânea da conta por dois professores.
    perfil = Usuario.objects.select_for_update().select_related('conta').get(pk=perfil.pk)
    if not pessoa.ativo:
        raise PermissionDenied('O cadastro está inativo.')
    if somente_nova and perfil.conta_id:
        return False
    if perfil.conta_id:
        if formulario.user.pk != perfil.conta_id:
            return False
    else:
        if formulario.user.pk or get_user_model().objects.filter(username__iexact=perfil.usuario).exists():
            return False
    conta = formulario.save()
    perfil.conta = conta
    perfil.troca_senha_obrigatoria = True
    perfil.save(update_fields=['conta', 'troca_senha_obrigatoria', 'atualizado_em'])
    registrar('SENHA', request=request, objeto=perfil,
              detalhes='Professor configurou senha temporária; troca obrigatória no próximo login.')
    return True


@require_http_methods(['GET', 'POST'])
def solicitar_senha(request):
    formulario = PedidoRecuperacaoForm(request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        nome = formulario.cleaned_data['usuario']
        ip = request.META.get('REMOTE_ADDR', '')
        origem = salted_hmac('elo.pedidos.senha', ip, algorithm='sha256').hexdigest()
        agora = timezone.now()
        # A resposta pública é sempre idêntica, inclusive para usuário inexistente.
        with transaction.atomic():
            aluno = Aluno.objects.filter(
                usuario__usuario__iexact=nome,
                usuario__tipo_perfil=Usuario.TipoPerfil.ALUNO,
                ativo=True,
            ).first()
            if aluno:
                aluno = Aluno.objects.select_for_update().get(pk=aluno.pk)
                vinculo = Vinculo.objects.select_related('professor').filter(
                    aluno=aluno, ativo=True, professor__ativo=True,
                    professor__usuario__conta__isnull=False,
                ).first()
                limite = SolicitacaoSenha.objects.filter(
                    origem_hash=origem, criada_em__gte=agora-timedelta(minutes=30)
                ).count() >= 5
                existente = SolicitacaoSenha.objects.filter(
                    aluno=aluno, situacao=SolicitacaoSenha.Situacao.PENDENTE
                ).exists()
                if vinculo and not limite and not existente:
                    pedido = SolicitacaoSenha.objects.create(
                        aluno=aluno, professor=vinculo.professor, origem_hash=origem,
                    )
                    registrar('SENHA', request=request, entidade='solicitacao_senha', objeto=pedido,
                              detalhes='Solicitação de recuperação de acesso registrada.')
        return render(request, 'aplicacao/recuperar-senha.html', {'enviado': True})
    return render(request, 'aplicacao/recuperar-senha.html', {'formulario': formulario})


@require_GET
def lista_solicitacoes(request):
    perfil = _professor_logado(request)
    pedidos = SolicitacaoSenha.objects.select_related('aluno', 'professor', 'aluno__usuario').filter(
        professor__usuario=perfil,
    ).order_by('situacao', '-criada_em')[:150]
    return render(request, 'aplicacao/solicitacoes-senha.html', {
        'pedidos': pedidos,
        'pagina_ativa': 'solicitacoes-senha',
    })


@sensitive_post_parameters('new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def atender_solicitacao(request, pk):
    perfil_professor = _professor_logado(request)
    pedido = get_object_or_404(
        SolicitacaoSenha.objects.select_related('aluno__usuario__conta', 'professor'),
        pk=pk, professor__usuario=perfil_professor,
    )
    if pedido.situacao != SolicitacaoSenha.Situacao.PENDENTE:
        messages.info(request, 'Esta solicitação já foi atendida.')
        return redirect('solicitacao-senha-listar')
    if not Vinculo.objects.filter(aluno=pedido.aluno, professor=pedido.professor, ativo=True).exists():
        raise PermissionDenied('O aluno não possui mais vínculo ativo com este professor.')
    if not pedido.aluno.ativo or not pedido.professor.ativo:
        raise PermissionDenied('O aluno ou professor está inativo.')
    perfil_alvo = pedido.aluno.usuario
    conta, is_ativacao = _conta_para_formulario(perfil_alvo, pedido.aluno)
    formulario = RedefinicaoSenha(conta, request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            pedido = SolicitacaoSenha.objects.select_for_update().get(pk=pedido.pk)
            if pedido.situacao != SolicitacaoSenha.Situacao.PENDENTE:
                messages.info(request, 'Esta solicitação já foi atendida.')
                return redirect('solicitacao-senha-listar')
            if not Vinculo.objects.filter(aluno=pedido.aluno, professor=pedido.professor, ativo=True).exists():
                raise PermissionDenied('O vínculo do aluno foi desativado.')
            if not _salvar_senha(perfil_alvo, pedido.aluno, formulario, request):
                formulario.add_error(None, 'O acesso foi alterado por outra operação. Atualize a página e tente novamente.')
            else:
                pedido.situacao = SolicitacaoSenha.Situacao.ATENDIDA
                pedido.atendida_em = timezone.now()
                pedido.save(update_fields=['situacao', 'atendida_em'])
                messages.success(request, 'Solicitação atendida. Informe a senha temporária ao aluno após confirmar sua identidade.')
                return redirect('solicitacao-senha-listar')
    return render(request, 'aplicacao/redefinir-senha.html', {
        'formulario': formulario, 'pessoa': pedido.aluno, 'perfil_alvo': perfil_alvo,
        'rota_voltar': 'solicitacao-senha-listar', 'pagina_ativa': 'solicitacoes-senha',
        'solicitacao': pedido, 'is_ativacao': is_ativacao,
    })


@sensitive_post_parameters('new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def ativar_acesso(request, pk):
    _professor_logado(request)
    perfil_alvo = get_object_or_404(
        Usuario.objects.select_related('conta'), pk=pk,
        tipo_perfil__in=[Usuario.TipoPerfil.ALUNO, Usuario.TipoPerfil.RESPONSAVEL],
        conta__isnull=True,
    )
    pessoa, rota, pagina = _pessoa_e_rota(perfil_alvo)
    if not pessoa.ativo:
        raise PermissionDenied('O cadastro está inativo.')
    conta, _ = _conta_para_formulario(perfil_alvo, pessoa)
    formulario = RedefinicaoSenha(conta, request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            if _salvar_senha(perfil_alvo, pessoa, formulario, request, somente_nova=True):
                if perfil_alvo.tipo_perfil == Usuario.TipoPerfil.ALUNO:
                    SolicitacaoSenha.objects.filter(
                        aluno=pessoa, professor__usuario=request.perfil_elo,
                        situacao=SolicitacaoSenha.Situacao.PENDENTE,
                    ).update(situacao=SolicitacaoSenha.Situacao.ATENDIDA, atendida_em=timezone.now())
                messages.success(request, f'Acesso de {pessoa.nome_completo} ativado. Oriente a troca de senha no primeiro login.')
                return redirect(rota)
            formulario.add_error(None, 'A conta já foi ativada ou o nome de usuário está em uso. Atualize a página.')
    return render(request, 'aplicacao/redefinir-senha.html', {
        'formulario': formulario, 'pessoa': pessoa, 'perfil_alvo': perfil_alvo,
        'rota_voltar': rota, 'pagina_ativa': pagina, 'is_ativacao': True,
    })
