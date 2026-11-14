from pathlib import Path
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from aplicacao.servicos.acesso import alunos_atividades_visiveis, pode_gerenciar_pedagogia
from aplicacao.models import Atividade, SolicitacaoConclusao, Usuario


def _autorizar(request, atividade):
    perfil = request.perfil_elo
    if perfil.tipo_perfil == Usuario.TipoPerfil.PROFESSOR:
        if perfil.gestor or (atividade.professor.usuario_id == perfil.pk
                                           and pode_gerenciar_pedagogia(perfil, atividade.aluno_id)):
            return
    elif alunos_atividades_visiveis(perfil).filter(pk=atividade.aluno_id).exists():
        return
    raise PermissionDenied('Você não tem permissão para consultar este anexo.')


def _responder(arquivo, nome):
    if not arquivo:
        raise Http404('Arquivo não encontrado.')
    try:
        resposta = FileResponse(arquivo.open('rb'), as_attachment=True,
                                filename=Path(nome or arquivo.name).name,
                                content_type='application/octet-stream')
    except (FileNotFoundError, OSError):
        raise Http404('Arquivo indisponível.')
    resposta['Cache-Control'] = 'private, no-store'
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta


@require_GET
@never_cache
def baixar_material(request, pk):
    atividade = get_object_or_404(Atividade, pk=pk)
    _autorizar(request, atividade)
    return _responder(atividade.material_apoio, atividade.material_nome)


@require_GET
@never_cache
def baixar_entrega(request, pk):
    entrega = get_object_or_404(SolicitacaoConclusao.objects.select_related('atividade__professor'), pk=pk)
    _autorizar(request, entrega.atividade)
    return _responder(entrega.anexo, entrega.anexo_nome)
