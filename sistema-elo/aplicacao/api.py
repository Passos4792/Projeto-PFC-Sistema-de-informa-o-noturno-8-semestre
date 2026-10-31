#importacoes
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from .acesso import alunos_permitidos, perfil_ativo
from .auditoria import registrar
from .documentos_legais import documentos_aceitos
from .indicadores import FiltroPainel, dados_painel, dados_frequencia, dados_conteudos, dados_metas
from .models import Atividade, Meta, SolicitacaoConclusao


#-------------------------------------------------------------------------------------

#a API exige as mesmas etapas e permissoes das paginas do ELO
class AcessoElo(BasePermission):
    message = 'Entre no ELO e conclua a troca de senha e o aceite dos documentos.'

    def has_permission(self, request, view):
        perfil = perfil_ativo(request.user)
        if perfil is None or perfil.troca_senha_obrigatoria or not documentos_aceitos(perfil):
            return False
        request.perfil_elo = perfil
        return True


#-------------------------------------------------------------------------------------

#base autenticada sem cache de dados pessoais
@method_decorator(never_cache, name='dispatch')
class ApiElo(APIView):
    permission_classes = [AcessoElo]


#-------------------------------------------------------------------------------------

#indicadores autorizados para os graficos e paineis
class PainelApi(ApiElo):
    def get(self, request):
        secao = request.query_params.get('secao')
        parametros = request.query_params.copy()
        if secao in ('frequencias', 'conteudos'):
            for campo in ('busca', 'inicio', 'fim', 'periodo'):
                parametros.pop(campo, None)
        if secao == 'metas':
            for campo in ('busca', 'inicio', 'fim'):
                parametros.pop(campo, None)
        formulario = FiltroPainel(parametros, perfil=request.perfil_elo)
        if not formulario.is_valid():
            return Response({'erros': formulario.errors}, status=400)
        calcular = {'frequencias': dados_frequencia, 'conteudos': dados_conteudos, 'metas': dados_metas}.get(secao, dados_painel)
        return Response(calcular(request.perfil_elo, formulario.cleaned_data))


#-------------------------------------------------------------------------------------

#opcoes de metas do aluno para o formulario de atividade
class MetasAlunoApi(ApiElo):
    def get(self, request, aluno_id):
        aluno = get_object_or_404(alunos_permitidos(request.perfil_elo), pk=aluno_id)
        metas = Meta.objects.filter(aluno=aluno).exclude(situacao='CANCELADA')
        return Response([{'id': m.pk, 'titulo': m.titulo, 'disciplina': m.disciplina_id} for m in metas])


#-------------------------------------------------------------------------------------

#validacao da mensagem de solicitacao
class SolicitarSerializer(serializers.Serializer):
    mensagem = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


#-------------------------------------------------------------------------------------

#solicitacao de conclusao feita pelo aluno ou responsavel vinculado
class SolicitarConclusaoApi(ApiElo):
    def post(self, request, pk):
        perfil = request.perfil_elo
        if perfil.tipo_perfil not in ('ALUNO', 'RESPONSAVEL'):
            return Response({'erro': 'Somente aluno ou responsável pode enviar uma solicitação.'}, status=403)
        formulario = SolicitarSerializer(data=request.data)
        formulario.is_valid(raise_exception=True)
        with transaction.atomic():
            atividade = get_object_or_404(Atividade.objects.select_for_update(), pk=pk,
                                         aluno__in=alunos_permitidos(perfil))
            if atividade.situacao != 'PENDENTE':
                return Response({'erro': 'Esta atividade não está pendente.'}, status=409)
            if atividade.solicitacoes.filter(situacao='PENDENTE').exists():
                return Response({'erro': 'Já existe uma solicitação aguardando o professor.'}, status=409)
            solicitacao = SolicitacaoConclusao.objects.create(atividade=atividade, aluno=atividade.aluno,
                solicitante=perfil, mensagem=formulario.validated_data['mensagem'])
            registrar('SOLICITACAO', request=request, objeto=solicitacao,
                      detalhes='Conclusão solicitada para avaliação do professor. Perfil: ' + perfil.get_tipo_perfil_display() + '.')
        return Response({'mensagem': 'Solicitação enviada. A realização contará após a aprovação do professor.'}, status=201)


#-------------------------------------------------------------------------------------

#validacao da decisao do professor
class DecisaoSerializer(serializers.Serializer):
    decisao = serializers.ChoiceField(choices=['APROVADA', 'RECUSADA'])
    resposta = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')

    def validate(self, dados):
        if dados['decisao'] == 'RECUSADA' and not dados['resposta'].strip():
            raise serializers.ValidationError({'resposta': 'Explique o que o aluno precisa revisar.'})
        return dados


#-------------------------------------------------------------------------------------

#fila restrita ao professor da atividade e ao professor principal
def solicitacoes_permitidas(perfil):
    registros = SolicitacaoConclusao.objects.select_related('atividade', 'aluno', 'solicitante', 'professor')
    if not perfil.professor_principal:
        registros = registros.filter(atividade__professor__usuario=perfil)
    return registros


#-------------------------------------------------------------------------------------

#aprovacao ou recusa, com transacao para impedir decisoes duplicadas
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
            #revalida a atribuicao depois de adquirir o bloqueio
            if not perfil.professor_principal and atividade.professor.usuario_id != perfil.pk:
                return Response({'erro': 'A atividade foi atribuída a outro professor.'}, status=403)
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
