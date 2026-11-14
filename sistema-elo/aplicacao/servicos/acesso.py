from urllib.parse import urlencode
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from aplicacao.servicos.auditoria import registrar, registrar_consulta
from aplicacao.servicos.documentos_legais import documentos_aceitos
from aplicacao.servicos.duplo_fator import exige_segundo_fator, obter_configuracao, segundo_fator_verificado
from aplicacao.servicos.limite_login import autenticar_com_limite
from aplicacao.models import Aluno, Professor


ROTAS_PUBLICAS = frozenset({
    'login', 'recuperar-senha', 'admin-recuperar-senha', 'sobre', 'politica-privacidade', 'termos-uso', 'privacidade-aluno',
})

ROTAS_SEGUNDO_FATOR = frozenset({'2fa-configurar', '2fa-verificar', '2fa-seguranca', '2fa-revogar', 'admin-trocar-senha', 'admin-trocar-senha-nativo'})

ROTAS_DOCUMENTOS = frozenset({
    'documentos-lista', 'documento-criar', 'documento-editar', 'documento-detalhe', 'documento-pdf', 'documento-publicar',
    'relatorio-criar', 'relatorio-editar', 'relatorio-detalhe', 'relatorio-pdf', 'relatorio-publicar',
})

ROTAS_ESTUDANTES = frozenset({'familia-estudantes', 'profissional-estudantes'})

ROTAS_VINCULOS = frozenset({
    'vinculos-profissionais', 'vinculos-familiares',
    'vinculo-listar', 'vinculo-criar', 'vinculo-editar', 'vinculo-excluir',
})

ROTAS_ADMINISTRACAO = frozenset({
    'usuario-criar', 'auditoria', 'usuario-redefinir-2fa',
    'professor-listar', 'professor-criar', 'professor-editar', 'professor-excluir',
    'aluno-criar', 'aluno-criar-sem-login', 'aluno-editar', 'aluno-excluir', 'aluno-documentos-pdf',
    'responsavel-listar', 'responsavel-criar', 'responsavel-editar', 'responsavel-excluir',
})

ROTAS_AEE = frozenset({
    'meta-criar', 'meta-editar', 'meta-excluir',
    'atividade-listar', 'atividade-historico', 'atividade-criar', 'atividade-editar', 'atividade-excluir',
    'aprovacoes',
})

ROTAS_SOLICITACOES_SENHA = frozenset({'solicitacao-senha-listar', 'solicitacao-senha-atender'})
ROTAS_ACESSO_ALUNOS = ROTAS_SOLICITACOES_SENHA | {'aluno-listar', 'usuario-redefinir-senha', 'usuario-ativar-acesso'}
ROTAS_PAINEIS = frozenset({'meta-listar'})
ROTAS_CONTA = frozenset({'meus-dados', 'foto-perfil', 'foto-perfil-alterar', 'foto-perfil-remover', 'pagina-inicial'})

ROTAS_AREA_ESTUDANTE = frozenset({
    'minhas-atividades', 'atividade-enviar',
    'google-conectar', 'google-retorno', 'google-sincronizar', 'google-desconectar',
})

ROTAS_ATIVIDADE = frozenset({'atividade-detalhe', 'atividade-material', 'entrega-anexo'})


def id_seguro(valor):
    valor = str(valor or '').strip()
    return int(valor) if valor.isascii() and valor.isdigit() and len(valor) <= 18 else 0


def eh_gestor(perfil):
    return perfil.tipo_perfil == 'PROFESSOR' and perfil.gestor


def perfil_ativo(user):
    if not user.is_authenticated or not user.is_active:
        return None
    try:
        perfil = user.perfil_elo
        pessoa = getattr(perfil, perfil.tipo_perfil.lower() + '_perfil')
        return perfil if pessoa.ativo else None
    except (ObjectDoesNotExist, AttributeError):
        return None


def _login_gravado(nome):
    from django.contrib.auth import get_user_model
    contas = list(get_user_model().objects.filter(username__iexact=nome).values_list('username', flat=True)[:2])
    return contas[0] if len(contas) == 1 else nome


class BackendElo(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if password is None:
            return None
        autenticar = super().authenticate
        return autenticar_com_limite(request, username,
                                     lambda nome: autenticar(request, username=_login_gravado(nome),
                                                             password=password, **kwargs))

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and (user.is_superuser or perfil_ativo(user) is not None)


def alunos_permitidos(perfil):
    if perfil.tipo_perfil == 'PROFESSOR':
        if perfil.gestor:
            return Aluno.objects.all()
        return Aluno.objects.filter(
            Q(vinculos_profissionais__professor__usuario=perfil,
              vinculos_profissionais__ativo=True,
              vinculos_profissionais__data_inicio__lte=timezone.localdate()) &
            (Q(vinculos_profissionais__data_fim__isnull=True) |
             Q(vinculos_profissionais__data_fim__gte=timezone.localdate())) |
            Q(vinculo__professor__usuario=perfil, vinculo__ativo=True)
        ).distinct()
    if perfil.tipo_perfil == 'ALUNO':
        return Aluno.objects.filter(usuario=perfil)
    return Aluno.objects.filter(
        Q(vinculo__responsavel__usuario=perfil, vinculo__ativo=True) |
        Q(vinculos_familiares__responsavel__usuario=perfil, vinculos_familiares__ativo=True)
    ).distinct()


def alunos_com_funcao(perfil, funcao):
    if perfil.tipo_perfil != 'PROFESSOR':
        return Aluno.objects.none()
    if perfil.gestor:
        return Aluno.objects.all()
    hoje = timezone.localdate()
    atribuicao = (
        Q(vinculos_profissionais__professor__usuario=perfil,
          vinculos_profissionais__funcao=funcao,
          vinculos_profissionais__ativo=True,
          vinculos_profissionais__data_inicio__lte=hoje)
        & (Q(vinculos_profissionais__data_fim__isnull=True)
           | Q(vinculos_profissionais__data_fim__gte=hoje))
    )
    if funcao == Professor.Funcao.AEE:
        atribuicao |= Q(vinculo__professor__usuario=perfil, vinculo__ativo=True,
                        vinculo__data_vinculo__lte=hoje)
    return Aluno.objects.filter(atribuicao).distinct()


def funcoes_no_aluno(perfil, aluno_id):
    if perfil.tipo_perfil != 'PROFESSOR':
        return set()
    if perfil.gestor:
        return set(Professor.Funcao.values)
    return {f for f in Professor.Funcao.values
            if alunos_com_funcao(perfil, f).filter(pk=aluno_id).exists()}


def pode_gerenciar_pedagogia(perfil, aluno_id):
    return (perfil.tipo_perfil == 'PROFESSOR' and
            alunos_com_funcao(perfil, Professor.Funcao.AEE).filter(pk=aluno_id).exists())


def alunos_area_estudante(perfil):
    if perfil.tipo_perfil == 'ALUNO':
        return Aluno.objects.filter(usuario=perfil)
    if perfil.tipo_perfil == 'RESPONSAVEL':
        return Aluno.objects.filter(
            Q(vinculo__responsavel__usuario=perfil, vinculo__ativo=True,
              vinculo__mesclar_perfis=True) |
            Q(vinculos_familiares__responsavel__usuario=perfil,
              vinculos_familiares__ativo=True, vinculos_familiares__mesclar_perfis=True)
        ).distinct()
    return Aluno.objects.none()


def alunos_atividades_visiveis(perfil):
    if perfil.tipo_perfil in ('ALUNO', 'RESPONSAVEL'):
        return alunos_permitidos(perfil)
    return Aluno.objects.none()


def profissional_pode_editar(perfil, aluno_id):
    return pode_gerenciar_pedagogia(perfil, aluno_id)


class ControleAcesso:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        registrar_consulta(request, resposta)
        if resposta.status_code == 403:
            match = getattr(request, 'resolver_match', None)
            registrar('ACESSO_NEGADO', request=request, entidade='página',
                      detalhes='Rota: ' + (match.url_name or '') if match else 'Rota não identificada')
        if getattr(request, 'user', None) is not None and request.user.is_authenticated:
            add_never_cache_headers(resposta)
        return resposta

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        nome = match.url_name

        if match.app_name == 'admin':
            if request.user.is_authenticated and request.user.is_staff:
                if not segundo_fator_verificado(request):
                    configuracao = obter_configuracao(request.user)
                    destino = '2fa-verificar' if configuracao and configuracao.confirmada_em else '2fa-configurar'
                    return redirect(destino)
                if (request.user.is_superuser and nome == 'auth_user_password_change'
                        and str(view_kwargs.get('id') or view_kwargs.get('object_id') or '') == str(request.user.pk)):
                    return redirect('admin-trocar-senha')
            return None

        if nome in ROTAS_PUBLICAS:
            return None
        if nome and nome.startswith('api-') and not request.user.is_authenticated:
            return None
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if nome == 'logout':
            return None

        perfil = perfil_ativo(request.user)
        if perfil is None and not request.user.is_staff:
            if nome and nome.startswith('api-'):
                return None
            raise PermissionDenied('Conta sem perfil ativo no ELO.')
        if perfil is not None:
            request.perfil_elo = perfil

        if perfil is not None and perfil.troca_senha_obrigatoria:
            if nome and nome.startswith('api-'):
                return None
            if nome == 'trocar-senha':
                return None
            return redirect('trocar-senha')

        if exige_segundo_fator(request.user, perfil):
            configuracao = obter_configuracao(request.user)
            if not segundo_fator_verificado(request, configuracao):
                destino = '2fa-verificar' if configuracao and configuracao.confirmada_em else '2fa-configurar'
                if nome in ('2fa-configurar', '2fa-verificar'):
                    return None
                if nome and nome.startswith('api-'):
                    return JsonResponse({'detail': 'Conclua a autenticação em duas etapas para acessar a API.'}, status=403)
                url = reverse(destino) + '?' + urlencode({'next': request.get_full_path()})
                return redirect(url)

        if nome in ROTAS_SEGUNDO_FATOR:
            return None
        if nome and nome.startswith('api-'):
            return None
        if nome == 'trocar-senha':
            return None
        if perfil is None:
            raise PermissionDenied('Conta técnica restrita à administração.')

        if nome == 'aceitar-termos':
            return None
        if not documentos_aceitos(perfil):
            destino = reverse('aceitar-termos') + '?' + urlencode({'next': request.get_full_path()})
            return redirect(destino)

        if nome in ROTAS_CONTA:
            return None
        if nome in ROTAS_DOCUMENTOS:
            if perfil.tipo_perfil == 'ALUNO':
                raise PermissionDenied('Documentos e relatórios são exclusivos dos responsáveis.')
            return None
        if nome in ROTAS_ESTUDANTES:
            return None
        if nome in ROTAS_VINCULOS:
            if not eh_gestor(perfil):
                raise PermissionDenied
            return None
        if nome in ROTAS_ADMINISTRACAO and not eh_gestor(perfil):
            raise PermissionDenied('Somente o gestor administra esses cadastros.')
        if nome in ROTAS_AEE:
            if perfil.tipo_perfil != 'PROFESSOR' or not alunos_com_funcao(perfil, Professor.Funcao.AEE).exists():
                raise PermissionDenied('Somente AEE de aluno vinculado pode acessar o acompanhamento.')
            return None
        if nome in ROTAS_ACESSO_ALUNOS:
            if perfil.tipo_perfil != 'PROFESSOR':
                raise PermissionDenied
            if (not perfil.gestor and nome not in ROTAS_SOLICITACOES_SENHA
                    and not alunos_com_funcao(perfil, Professor.Funcao.AEE).exists()):
                raise PermissionDenied('Somente o AEE pode administrar o acesso de alunos vinculados.')
            return None
        if nome in ('inicio', 'pagina-inicial'):
            return None
        if nome in ROTAS_PAINEIS:
            if perfil.tipo_perfil == 'PROFESSOR' and not alunos_com_funcao(perfil, Professor.Funcao.AEE).exists():
                raise PermissionDenied('Acompanhantes não acessam metas e atividades pedagógicas.')
            return None
        if nome in ROTAS_AREA_ESTUDANTE:
            if perfil.tipo_perfil not in ('ALUNO', 'RESPONSAVEL'):
                raise PermissionDenied
            return None
        if nome in ROTAS_ATIVIDADE:
            return None
        if nome == 'aluno-inicio':
            alunos = (alunos_com_funcao(perfil, Professor.Funcao.AEE)
                      if perfil.tipo_perfil == 'PROFESSOR' else alunos_permitidos(perfil))
            if not alunos.filter(pk=view_kwargs['pk']).exists():
                raise PermissionDenied
            return None
        if perfil.tipo_perfil != 'PROFESSOR':
            raise PermissionDenied
        if not perfil.gestor:
            raise PermissionDenied('Rota administrativa sem permissão específica.')
