"""Área de privacidade e encerramento de contas (não confundir com purga escolar)."""
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods
from aplicacao.models import AutorizacaoAcessoMenor, Usuario
from aplicacao.servicos.autorizacao_menores import alunos_menores_vinculados
from aplicacao.servicos.documentos_legais import MARCADOR_REVOGACAO, documentos_aceitos
from aplicacao.servicos.auditoria import registrar
from aplicacao.servicos.privacidade_contas import (
    crianca_principal_ou_404, criancas_do_responsavel_principal,
    encerrar_conta, pdf_aluno_para_titular, pdf_proprio,
    perfil_pode_encerrar_proprio,
)


def _resposta_pdf(conteudo, nome):
    resposta = HttpResponse(conteudo, content_type='application/pdf')
    resposta['Content-Disposition'] = f'attachment; filename="{nome}"'
    resposta['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    resposta['Pragma'] = 'no-cache'
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta


@never_cache
@require_GET
def privacidade_conta(request):
    perfil = request.perfil_elo
    if not perfil_pode_encerrar_proprio(perfil):
        raise PermissionDenied('Esta conta não tem acesso à área de encerramento.')
    return render(request, 'aplicacao/contas/privacidade-conta.html', {
        'pagina_ativa': 'meus-dados',
    })


@never_cache
@require_GET
def privacidade_gerenciar(request):
    perfil = request.perfil_elo
    if not perfil_pode_encerrar_proprio(perfil):
        raise PermissionDenied('Esta conta não tem acesso à área de dados.')
    return render(request, 'aplicacao/contas/privacidade-gerenciar.html', {
        'pagina_ativa': 'meus-dados',
        'criancas_principais': criancas_do_responsavel_principal(perfil),
    })


@sensitive_post_parameters('senha')
@never_cache
@require_http_methods(['GET', 'POST'])
def privacidade_revogar(request):
    """Revogação explícita de aceite; não encerra conta nem apaga histórico.

    O responsável bloqueia o próprio acesso e o de crianças < 12 vinculadas.
    O marcador permanece no perfil adulto e impede outro aceite de responsável
    de reativar a criança enquanto a revogação estiver ativa.
    """
    perfil = request.perfil_elo
    if not perfil_pode_encerrar_proprio(perfil):
        raise PermissionDenied('Esta conta não pode revogar seus documentos por este fluxo.')
    if not documentos_aceitos(perfil):
        return redirect('aceitar-termos')
    erro = None
    if request.method == 'POST':
        if not request.user.check_password(request.POST.get('senha') or ''):
            erro = 'Senha incorreta. Informe a senha atual da sua conta.'
        elif request.POST.get('confirmacao', '').strip().upper() != 'REVOGAR':
            erro = 'Digite REVOGAR para confirmar.'
        elif request.POST.get('confirmo') != 'on':
            erro = 'Marque a confirmação antes de continuar.'
        else:
            with transaction.atomic():
                alvo = Usuario.objects.select_for_update().get(pk=perfil.pk)
                if alvo.conta_id != request.user.pk or alvo.conta_encerrada_em:
                    raise PermissionDenied('Conta indisponível para revogação.')
                if not documentos_aceitos(alvo):
                    return redirect('aceitar-termos')
                filhos_ids = []
                if alvo.tipo_perfil == 'RESPONSAVEL':
                    filhos_ids = [aluno.pk for aluno in alunos_menores_vinculados(alvo)]
                    # Cada adulto é titular de sua autorização específica.
                    # Outras autorizações são preservadas, mas o marcador de
                    # revogação bloqueia a criança enquanto ele estiver revogado.
                    AutorizacaoAcessoMenor.objects.filter(
                        responsavel=alvo.responsavel_perfil,
                        aluno_id__in=filhos_ids,
                    ).delete()
                alvo.documentos_aceitos_em = None
                alvo.versao_termos_aceita = MARCADOR_REVOGACAO
                alvo.versao_privacidade_ciente = MARCADOR_REVOGACAO
                alvo.save(update_fields=[
                    'documentos_aceitos_em', 'versao_termos_aceita',
                    'versao_privacidade_ciente', 'atualizado_em',
                ])
                registrar('DOCUMENTOS', request=request, objeto=alvo,
                          detalhes=f'Revogação explícita dos documentos; menores vinculados bloqueados: {len(filhos_ids)}.')
            logout(request)
            messages.success(request, 'Revogação registrada. Seu acesso e o das crianças menores vinculadas '
                                      'estão suspensos até a regularização dos documentos e autorizações.')
            return redirect('login')
    return render(request, 'aplicacao/contas/privacidade-revogar.html', {
        'pagina_ativa': 'meus-dados', 'erro': erro,
    })


@never_cache
@require_GET
def privacidade_exportar_minha(request):
    perfil = request.perfil_elo
    conteudo = pdf_proprio(perfil)
    registrar('CONSULTA', request=request, entidade='Exportação de dados da própria conta',
              objeto_id=str(perfil.pk), detalhes='PDF para exercício dos direitos do titular.')
    return _resposta_pdf(conteudo, f'elo-dados-minha-conta-{perfil.pk}.pdf')


@never_cache
@require_GET
def privacidade_exportar_menor(request, pk):
    aluno = crianca_principal_ou_404(request.perfil_elo, pk)
    conteudo = pdf_aluno_para_titular(aluno)
    registrar('CONSULTA', request=request, entidade='Exportação de dados de criança',
              objeto_id=str(aluno.pk), detalhes='PDF entregue ao responsável principal vinculado.')
    return _resposta_pdf(conteudo, f'elo-dados-aluno-{aluno.pk}.pdf')


def _validar_confirmacao(request):
    if not request.user.check_password(request.POST.get('senha') or ''):
        return 'Senha incorreta. Informe a senha atual da sua conta.'
    if request.POST.get('confirmacao', '').strip().upper() != 'ENCERRAR':
        return 'Digite ENCERRAR para confirmar.'
    if request.POST.get('confirmo') != 'on':
        return 'Marque a confirmação de que compreendeu as consequências.'
    return None


@sensitive_post_parameters('senha')
@never_cache
@require_http_methods(['GET', 'POST'])
def privacidade_excluir_minha(request):
    perfil = request.perfil_elo
    if not perfil_pode_encerrar_proprio(perfil):
        raise PermissionDenied('Esta conta não pode ser encerrada pelo titular neste fluxo.')
    if request.method == 'POST':
        erro = _validar_confirmacao(request)
        if not erro:
            encerrar_conta(perfil.pk, request)
            logout(request)
            messages.success(request, 'Sua conta de acesso ao ELO foi encerrada. O histórico escolar '
                                      'que exige retenção continua protegido no sistema.')
            return redirect('login')
    else:
        erro = None
    return render(request, 'aplicacao/contas/confirmar-encerramento.html', {
        'pagina_ativa': 'meus-dados', 'erro': erro,
        'nome_alvo': request.perfil_elo.usuario,
        'conta_propria': True,
        'url_exportacao': 'privacidade-exportar-minha',
        'criancas_principais': criancas_do_responsavel_principal(perfil),
    })


@sensitive_post_parameters('senha')
@never_cache
@require_http_methods(['GET', 'POST'])
def privacidade_excluir_menor(request, pk):
    aluno = crianca_principal_ou_404(request.perfil_elo, pk)
    if request.method == 'POST':
        erro = _validar_confirmacao(request)
        if not erro:
            nome = encerrar_conta(request.perfil_elo.pk, request, aluno_id=aluno.pk)
            messages.success(request, f'A conta de acesso de {nome} foi encerrada. '
                                      'O histórico escolar permanece sob guarda da instituição.')
            return redirect('privacidade-gerenciar')
    else:
        erro = None
    return render(request, 'aplicacao/contas/confirmar-encerramento.html', {
        'pagina_ativa': 'meus-dados', 'erro': erro,
        'nome_alvo': aluno.nome_completo, 'aluno': aluno,
        'conta_propria': False, 'url_exportacao': 'privacidade-exportar-menor',
    })
