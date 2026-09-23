#importacoes
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from .models import Aluno


#-------------------------------------------------------------------------------------

#perfil ativo
def perfil_ativo(user):
    if not user.is_authenticated or not user.is_active:
        return None
    try:
        perfil = user.perfil_elo
        pessoa = getattr(perfil, perfil.tipo_perfil.lower() + '_perfil')
        return perfil if pessoa.ativo else None
    except (ObjectDoesNotExist, AttributeError):
        return None


#-------------------------------------------------------------------------------------

#autenticacao do usuario
class BackendElo(ModelBackend):

    #-------------------------------------------------------------------------------------

    #autenticacao
    def authenticate(self, request, username=None, password=None, **kwargs):
        from .limite_login import autenticar_com_limite
        if password is None:
            return None
        autenticar = super().authenticate
        return autenticar_com_limite(request, username,
                                     lambda nome: autenticar(request, username=nome, password=password, **kwargs))

    #-------------------------------------------------------------------------------------

    #validacao da conta ativa
    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and (user.is_superuser or perfil_ativo(user) is not None)


#-------------------------------------------------------------------------------------

#alunos permitidos
def alunos_permitidos(perfil):
    if perfil.tipo_perfil == 'PROFESSOR':
        return Aluno.objects.all()
    if perfil.tipo_perfil == 'ALUNO':
        return Aluno.objects.filter(usuario=perfil)
    return Aluno.objects.filter(vinculo__responsavel__usuario=perfil, vinculo__ativo=True)


#-------------------------------------------------------------------------------------

#controle de acesso as paginas
class ControleAcesso:

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, get_response):
        self.get_response = get_response

    #-------------------------------------------------------------------------------------

    #processamento da requisicao
    def __call__(self, request):
        resposta = self.get_response(request)
        if resposta.status_code == 403:
            from .auditoria import registrar
            match = getattr(request, 'resolver_match', None)
            registrar('ACESSO_NEGADO', request=request, entidade='página',
                      detalhes='Rota: ' + (match.url_name or '') if match else 'Rota não identificada')
        return resposta

    #-------------------------------------------------------------------------------------

    #verificacao das permissoes da pagina
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match.app_name == 'admin':
            return None
        nome = match.url_name
        if nome in ('login', 'recuperar-senha', 'sobre'):
            return None
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if nome == 'logout':
            return None
        perfil = perfil_ativo(request.user)
        if perfil is None:
            raise PermissionDenied('Conta sem perfil ativo no ELO.')
        request.perfil_elo = perfil
        if nome == 'auditoria' and not (perfil.tipo_perfil == 'PROFESSOR' and perfil.professor_principal):
            raise PermissionDenied
        if nome in ('inicio', 'portal'):
            return None
        if nome == 'aluno-inicio':
            if not alunos_permitidos(perfil).filter(pk=view_kwargs['pk']).exists():
                raise PermissionDenied
            return None
        if perfil.tipo_perfil != 'PROFESSOR':
            raise PermissionDenied
        if nome in ('professor-criar', 'professor-editar', 'professor-excluir') and not perfil.professor_principal:
            raise PermissionDenied
#-------------------------------------------------------------------------------------
