"""Exportação de dados e encerramento voluntário de contas de acesso.

Os registros pedagógicos têm outras pessoas envolvidas e restrições de
integridade (FKs PROTECT); o encerramento remove credenciais e dados de acesso,
mas não faz purga irreversível do prontuário escolar ou da auditoria.
"""
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from aplicacao.models import (
    Aluno, AutorizacaoAcessoMenor, ConexaoGoogle, DocumentoPedagogico,
    RelatorioPedagogico, Responsavel, SincronizacaoGoogle, SolicitacaoSenha,
    Usuario, Vinculo, VinculoFamiliar, VinculoProfissional,
)
from aplicacao.servicos.auditoria import registrar
from aplicacao.servicos.autorizacao_menores import menor_de_12
from aplicacao.servicos.exportacao_pdf import gerar_pdf_dados_responsavel, gerar_pdf_prontuario_aluno


def perfil_pode_encerrar_proprio(perfil):
    if perfil.conta_encerrada_em:
        return False
    if perfil.tipo_perfil == Usuario.TipoPerfil.RESPONSAVEL:
        return True
    if perfil.tipo_perfil == Usuario.TipoPerfil.ALUNO:
        nascimento = perfil.aluno_perfil.data_nascimento
        return nascimento is not None and not menor_de_12(nascimento)
    return False


def criancas_do_responsavel_principal(perfil):
    """Exclui responsáveis secundários e vínculos inativos, mesmo se associados."""
    if perfil.tipo_perfil != Usuario.TipoPerfil.RESPONSAVEL:
        return []
    consulta = (Aluno.objects.filter(
        ativo=True, vinculo__ativo=True, vinculo__responsavel__usuario=perfil,
        vinculo__responsavel__ativo=True,
    ).select_related('usuario').order_by('nome', 'sobrenome', 'pk'))
    return [aluno for aluno in consulta if menor_de_12(aluno.data_nascimento)]


def crianca_principal_ou_404(perfil, aluno_id):
    if perfil.tipo_perfil != Usuario.TipoPerfil.RESPONSAVEL or perfil.conta_encerrada_em:
        raise PermissionDenied('Somente o responsável pode administrar o acesso da criança.')
    aluno = get_object_or_404(
        Aluno.objects.select_related('usuario'), pk=aluno_id, ativo=True,
        vinculo__ativo=True, vinculo__responsavel__usuario=perfil,
        vinculo__responsavel__ativo=True,
    )
    if not menor_de_12(aluno.data_nascimento):
        raise PermissionDenied('A exclusão pelo responsável principal é restrita a menores de 12 anos.')
    return aluno


def pdf_aluno_para_titular(aluno):
    """Não publica rascunhos ou registros internos só por causa de uma exportação.

    É possível solicitar os demais dados ao controlador. Materiais/entregas
    anexados não são incorporados ao PDF, mas sua existência é informada.
    """
    documentos = list(DocumentoPedagogico.objects.filter(
        aluno=aluno, situacao=DocumentoPedagogico.Situacao.PUBLICADO,
    ).select_related('professor').order_by('ano_letivo', 'tipo', 'pk'))
    relatorios = list(RelatorioPedagogico.objects.filter(
        aluno=aluno, situacao=RelatorioPedagogico.Situacao.PUBLICADO,
    ).select_related('professor').order_by('data_referencia', 'pk'))
    metas = list(aluno.metas.all().order_by('data_inicio', 'pk'))
    atividades = list(aluno.atividades.prefetch_related('solicitacoes').all().order_by('criado_em', 'pk'))
    return gerar_pdf_prontuario_aluno(
        aluno, documentos, relatorios, exportacao_titular=True,
        metas=metas, atividades=atividades,
    )


def pdf_proprio(perfil):
    if not perfil_pode_encerrar_proprio(perfil):
        raise PermissionDenied('A exportação individual desta conta não está disponível.')
    if perfil.tipo_perfil == 'ALUNO':
        return pdf_aluno_para_titular(perfil.aluno_perfil)
    return gerar_pdf_dados_responsavel(perfil.responsavel_perfil)


@transaction.atomic
def encerrar_conta(perfil_id, request, *, aluno_id=None):
    """Bloqueia e remove credenciais; preserva o histórico escolar vinculado.

    `aluno_id` só pode ser usado pelo responsável *principal* de criança < 12.
    Permissões são revalidadas dentro da transação para evitar alteração do
    vínculo ou idade entre a tela de confirmação e o POST.
    """
    operador = Usuario.objects.select_for_update().select_related('conta').get(pk=perfil_id)
    if operador.conta_encerrada_em or operador.conta_id != request.user.pk:
        raise PermissionDenied('A conta não está mais ativa.')

    if aluno_id is None:
        if not perfil_pode_encerrar_proprio(operador):
            raise PermissionDenied('Esta conta não pode ser encerrada por este fluxo.')
        alvo = operador
        pessoa = (operador.aluno_perfil if operador.tipo_perfil == 'ALUNO'
                  else operador.responsavel_perfil)
    else:
        if operador.tipo_perfil != 'RESPONSAVEL':
            raise PermissionDenied
        # Lock do vínculo principal antes de modificar a conta da criança.
        vinculo = get_object_or_404(
            Vinculo.objects.select_for_update().select_related('aluno__usuario'),
            aluno_id=aluno_id, responsavel__usuario=operador, responsavel__ativo=True,
            ativo=True, aluno__ativo=True,
        )
        pessoa = vinculo.aluno
        if not menor_de_12(pessoa.data_nascimento):
            raise PermissionDenied('A criança já completou 12 anos.')
        alvo = Usuario.objects.select_for_update().select_related('conta').get(pk=pessoa.usuario_id)
        if alvo.conta_encerrada_em:
            raise PermissionDenied('A conta já foi encerrada.')

    if alvo.conta_id:
        # Invalida logins e sessões inclusive em outros dispositivos.
        conta = alvo.conta
        conta.is_active = False
        conta.save(update_fields=['is_active'])
    else:
        conta = None  # Aluno sem credenciais também pode ter acesso encerrado.

    if isinstance(pessoa, Aluno):
        pessoa.ativo = False
        pessoa.save(update_fields=['ativo', 'atualizado_em'])  # registra inativado_em
        Vinculo.objects.filter(aluno=pessoa, ativo=True).update(ativo=False)
        VinculoFamiliar.objects.filter(aluno=pessoa, ativo=True).update(ativo=False)
        VinculoProfissional.objects.filter(aluno=pessoa, ativo=True).update(ativo=False)
        AutorizacaoAcessoMenor.objects.filter(aluno=pessoa).delete()
    else:
        pessoa.ativo = False
        pessoa.save(update_fields=['ativo', 'atualizado_em'])
        Vinculo.objects.filter(responsavel=pessoa, ativo=True).update(ativo=False)
        VinculoFamiliar.objects.filter(responsavel=pessoa, ativo=True).update(ativo=False)
        AutorizacaoAcessoMenor.objects.filter(responsavel=pessoa).delete()

    SolicitacaoSenha.objects.filter(usuario_alvo=alvo, situacao='PENDENTE').update(
        situacao='ATENDIDA', atendida_em=timezone.now(),
    )
    SincronizacaoGoogle.objects.filter(usuario=alvo).delete()
    ConexaoGoogle.objects.filter(usuario=alvo).delete()

    nome_foto = alvo.foto_perfil.name
    armazenamento = alvo.foto_perfil.storage if nome_foto else None
    alvo.conta = None
    alvo.usuario = f'conta-encerrada-{alvo.pk}-{uuid4().hex[:16]}'
    alvo.conta_encerrada_em = timezone.now()
    alvo.foto_perfil = ''
    alvo.save(update_fields=['conta', 'usuario', 'conta_encerrada_em', 'foto_perfil', 'atualizado_em'])

    registrar('EXCLUSAO', request=request, entidade='Encerramento de conta de acesso',
              objeto_id=str(alvo.pk),
              detalhes=('Conta encerrada por responsável principal; ' if aluno_id is not None
                        else 'Conta encerrada pelo próprio titular; ') +
                       'login e credenciais eliminados; históricos escolares sujeitos à retenção.')
    if conta is not None:
        conta.delete()
    if nome_foto:
        transaction.on_commit(lambda: armazenamento.delete(nome_foto))
    return pessoa.nome_completo
