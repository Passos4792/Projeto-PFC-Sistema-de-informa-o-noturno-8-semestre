from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from aplicacao.servicos.acesso import (alunos_area_estudante, alunos_com_funcao, alunos_permitidos, perfil_ativo,
                     pode_gerenciar_pedagogia)
from aplicacao.servicos.arquivos import validar_anexo_pedagogico
from aplicacao.servicos.auditoria import registrar
from aplicacao.servicos.documentos_legais import documentos_aceitos
from aplicacao.servicos.duplo_fator import exige_segundo_fator, segundo_fator_verificado
from aplicacao.forms import FiltroPainel
from aplicacao.servicos.indicadores import dados_metas, dados_painel
from aplicacao.models import Atividade, MetaAluno, Professor, SolicitacaoConclusao


class AcessoElo(BasePermission):
    message = 'Entre no ELO e conclua a troca de senha e o aceite dos documentos.'

    def has_permission(self, request, view):
        perfil = perfil_ativo(request.user)
        if perfil is None or perfil.troca_senha_obrigatoria or not documentos_aceitos(perfil):
            return False
        if exige_segundo_fator(request.user, perfil) and not segundo_fator_verificado(request):
            return False
        request.perfil_elo = perfil
        return True


@method_decorator(never_cache, name='dispatch')
class ApiElo(APIView):
    permission_classes = [AcessoElo]


class PainelApi(ApiElo):
    def get(self, request):
        perfil = request.perfil_elo
        if perfil.tipo_perfil == 'PROFESSOR' and not alunos_com_funcao(perfil, Professor.Funcao.AEE).exists():
            return Response({'erro': 'Esta função não tem acesso aos indicadores pedagógicos.'}, status=403)
        secao = request.query_params.get('secao')
        if secao not in (None, '', 'acompanhamento', 'metas'):
            return Response({'erro': 'Painel indisponível.'}, status=400)
        parametros = request.query_params.copy()
        if secao == 'metas':
            for campo in ('busca', 'inicio', 'fim'):
                parametros.pop(campo, None)
        formulario = FiltroPainel(parametros, perfil=request.perfil_elo)
        if not formulario.is_valid():
            return Response({'erros': formulario.errors}, status=400)
        calcular = dados_metas if secao == 'metas' else dados_painel
        return Response(calcular(request.perfil_elo, formulario.cleaned_data))


class MetasAlunoApi(ApiElo):
    def get(self, request, aluno_id):
        perfil = request.perfil_elo
        permitidos = (alunos_com_funcao(perfil, Professor.Funcao.AEE)
                      if perfil.tipo_perfil == 'PROFESSOR' else alunos_permitidos(perfil))
        aluno = get_object_or_404(permitidos, pk=aluno_id)
        metas = MetaAluno.objects.filter(aluno=aluno).exclude(situacao='CANCELADA')
        return Response([{'id': m.pk, 'titulo': m.titulo} for m in metas])


class SolicitarSerializer(serializers.Serializer):
    mensagem = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    resposta_aluno = serializers.CharField(max_length=10000, required=False, allow_blank=True, default='')
    anexo = serializers.FileField(required=False, allow_empty_file=False)

    def validate_anexo(self, arquivo):
        try:
            validar_anexo_pedagogico(arquivo)
        except DjangoValidationError as erro:
            raise serializers.ValidationError(erro.messages)
        return arquivo

    def validate(self, dados):
        atividade = self.context['atividade']
        if atividade.tipo_entrega == Atividade.TipoEntrega.ENVIO and not (
                dados.get('resposta_aluno', '').strip() or dados.get('anexo')):
            raise serializers.ValidationError({'resposta_aluno': 'Escreva uma resposta ou envie um arquivo.'})
        return dados


class EntregaIndisponivel(Exception):
    pass


def registrar_entrega_atividade(request, pk, dados):
    perfil = request.perfil_elo
    with transaction.atomic():
        atividade = get_object_or_404(
            Atividade.objects.select_for_update(), pk=pk,
            aluno__in=alunos_area_estudante(perfil),
        )
        if atividade.situacao != Atividade.Situacao.PENDENTE:
            raise EntregaIndisponivel('Esta atividade não está pendente.')
        if atividade.solicitacoes.filter(situacao='PENDENTE').exists():
            raise EntregaIndisponivel('Já existe uma entrega aguardando avaliação do professor.')
        formulario = SolicitarSerializer(data=dados, context={'atividade': atividade})
        formulario.is_valid(raise_exception=True)
        anexo = formulario.validated_data.get('anexo')
        solicitacao = SolicitacaoConclusao.objects.create(
            atividade=atividade, aluno=atividade.aluno, solicitante=perfil,
            mensagem=formulario.validated_data['mensagem'],
            resposta_aluno=formulario.validated_data['resposta_aluno'].strip(),
            anexo=anexo, anexo_nome=anexo.name[:255] if anexo else '',
        )
        registrar(
            'SOLICITACAO', request=request, objeto=solicitacao,
            detalhes='Conclusão solicitada para avaliação do professor. Perfil: '
                     + perfil.get_tipo_perfil_display() + '.',
        )
    return solicitacao


class SolicitarConclusaoApi(ApiElo):
    def post(self, request, pk):
        if request.perfil_elo.tipo_perfil not in ('ALUNO', 'RESPONSAVEL'):
            return Response({'erro': 'Somente aluno ou responsável pode enviar uma solicitação.'}, status=403)
        try:
            registrar_entrega_atividade(request, pk, request.data)
        except EntregaIndisponivel as erro:
            return Response({'erro': str(erro)}, status=409)
        return Response({'mensagem': 'Atividade enviada. A realização contará após a aprovação do professor.'}, status=201)


class DecisaoSerializer(serializers.Serializer):
    decisao = serializers.ChoiceField(choices=['APROVADA', 'RECUSADA'])
    resposta = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')

    def validate(self, dados):
        if dados['decisao'] == 'RECUSADA' and not dados['resposta'].strip():
            raise serializers.ValidationError({'resposta': 'Explique o que o aluno precisa revisar.'})
        return dados


def solicitacoes_permitidas(perfil):
    registros = SolicitacaoConclusao.objects.select_related('atividade', 'aluno', 'solicitante', 'professor')
    if perfil.tipo_perfil != 'PROFESSOR':
        return registros.none()
    if not perfil.gestor:
        registros = registros.filter(atividade__professor__usuario=perfil,
                                    aluno__in=alunos_com_funcao(perfil, Professor.Funcao.AEE))
    return registros


class DecidirConclusaoApi(ApiElo):
    def patch(self, request, pk):
        perfil = request.perfil_elo
        if perfil.tipo_perfil != 'PROFESSOR':
            return Response({'erro': 'A avaliação deve ser realizada pelo professor.'}, status=403)
        formulario = DecisaoSerializer(data=request.data)
        formulario.is_valid(raise_exception=True)
        alvo = get_object_or_404(solicitacoes_permitidas(perfil), pk=pk)
        with transaction.atomic():
            atividade = Atividade.objects.select_for_update().get(pk=alvo.atividade_id)
            if not perfil.gestor and (
                atividade.professor.usuario_id != perfil.pk or
                not pode_gerenciar_pedagogia(perfil, atividade.aluno_id)
            ):
                return Response({'erro': 'Sem função AEE ativa para esta atividade.'}, status=403)
            solicitacao = SolicitacaoConclusao.objects.select_for_update().get(pk=pk)
            if solicitacao.situacao != 'PENDENTE' or atividade.situacao != 'PENDENTE' or atividade.aluno_id != solicitacao.aluno_id:
                return Response({'erro': 'Esta solicitação já foi analisada ou a atividade foi alterada.'}, status=409)
            solicitacao.situacao = formulario.validated_data['decisao']
            solicitacao.resposta = formulario.validated_data['resposta']
            solicitacao.professor = perfil.professor_perfil
            solicitacao.respondido_em = timezone.now()
            solicitacao.save(update_fields=['situacao', 'resposta', 'professor', 'respondido_em'])
            if solicitacao.situacao == 'APROVADA':
                atividade.situacao = 'CONCLUIDA'
                atividade.save(update_fields=['situacao', 'atualizado_em'])
                registrar('EDICAO', request=request, objeto=atividade, detalhes='Conclusão aprovada pelo professor.')
            registrar('APROVACAO' if solicitacao.situacao == 'APROVADA' else 'RECUSA', request=request, objeto=solicitacao,
                      detalhes='Solicitação ' + solicitacao.get_situacao_display().lower() + '.')
        return Response({'mensagem': 'Solicitação aprovada.' if solicitacao.situacao == 'APROVADA'
                         else 'Solicitação recusada. A orientação ficará disponível ao aluno e ao responsável.'})
