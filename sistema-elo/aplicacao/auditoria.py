"""Registro de eventos com metadados mínimos, sem conteúdo de formulários."""


from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.utils.crypto import salted_hmac
from .models import RegistroAuditoria


def registrar(acao, request=None, objeto=None, autor=None, entidade='', objeto_id='', detalhes=''):
    usuario = autor if autor is not None else getattr(request, 'user', None)
    identificado = usuario is not None and usuario.is_authenticated
    if objeto is not None:
        nomes = {'meta': 'Meta', 'atividade': 'Atividade', 'disciplina': 'Conteúdo curricular',
                 'solicitacaoconclusao': 'Solicitação de conclusão'}
        entidade = nomes.get(objeto._meta.model_name, objeto._meta.verbose_name)
        referencias = []
        for campo, rotulo in [('aluno_id', 'Aluno'), ('professor_id', 'Professor'), ('atividade_id', 'Atividade')]:
            valor = getattr(objeto, campo, None)
            if valor is not None:
                referencias.append(f'{rotulo} #{valor}')
        detalhes = '; '.join(referencias + ([detalhes] if detalhes else []))
    return RegistroAuditoria.objects.create(
        autor_id_original=usuario.pk if identificado else None,
        autor=usuario.get_username()[:150] if identificado else (
            'Não autenticado' if request else 'Comando local'),
        acao=acao, entidade=entidade,
        objeto_id=str(objeto.pk) if objeto is not None else str(objeto_id),
        detalhes=detalhes[:500])


# Não incluir textos livres ou senhas nos detalhes de auditoria.
def detalhes_formulario(formulario):
    permitidos = {'situacao', 'periodo', 'quantidade_alvo', 'data_entrega', 'data_inicio',
                  'data_prazo', 'ativo', 'aluno', 'professor', 'responsavel', 'disciplina', 'meta'}
    def apresentar(valor):
        if valor is None or valor == '':
            return 'não definido'
        if hasattr(valor, 'pk'):
            return str(valor.pk)
        return str(valor)
    alteracoes = []
    for nome in formulario.changed_data:
        rotulo = formulario.fields[nome].label or nome
        if nome in permitidos:
            anterior = apresentar(formulario.initial.get(nome))
            atual = apresentar(formulario.cleaned_data.get(nome))
            alteracoes.append(f'{rotulo}: {anterior} → {atual}')
        else:
            alteracoes.append(f'{rotulo}: alterado')
    return '; '.join(alteracoes) or 'Registro salvo sem alteração de campos.'


def registrar_consulta(request, resposta):
    if request.method != 'GET' or resposta.status_code != 200 or not request.user.is_authenticated:
        return
    match = getattr(request, 'resolver_match', None)
    if not match:
        return
    telas = {'pagina-inicial': 'Página inicial', 'aluno-listar': 'Alunos', 'professor-listar': 'Professores',
        'responsavel-listar': 'Responsáveis', 'vinculo-listar': 'Vínculos', 'aluno-inicio': 'Acompanhamento do aluno',
        'meta-listar': 'Metas', 'atividade-listar': 'Atividades', 'minhas-atividades': 'Minhas atividades',
        'conteudo-listar': 'Conteúdos', 'frequencia-listar': 'Frequência', 'aprovacoes': 'Aprovações',
        'api-painel': 'Indicadores pela API', 'api-metas-aluno': 'Metas do aluno pela API'}
    entidade = telas.get(match.url_name)
    if not entidade:
        return
    filtros = [rotulo for campo, rotulo in [('aluno', 'aluno'), ('busca', 'pesquisa'),
        ('periodo', 'período'), ('situacao', 'situação'), ('inicio', 'data inicial'), ('fim', 'data final'),
        ('ordem', 'ordenação')] if request.GET.get(campo)]
    detalhes = ['Visualização da tela.']
    if filtros:
        detalhes.append('Filtros: ' + ', '.join(filtros) + '.')
    for campo, rotulo in [('aluno', 'Aluno'), ('pagina', 'Página')]:
        valor = request.GET.get(campo, '')
        if valor.isascii() and valor.isdigit() and len(valor) <= 10:
            detalhes.append(f'{rotulo}: {valor}.')
    alvo = match.kwargs.get('pk') or match.kwargs.get('aluno_id') or ''
    registrar('CONSULTA', request=request, entidade=entidade, objeto_id=alvo, detalhes=' '.join(detalhes))


@receiver(user_logged_in, dispatch_uid='elo.auditoria.login')
def registrar_login(sender, request, user, **kwargs):
    registrar('LOGIN', request=request, autor=user)


@receiver(user_logged_out, dispatch_uid='elo.auditoria.saida')
def registrar_saida(sender, request, user, **kwargs):
    if user is not None:
        registrar('SAIDA', request=request, autor=user)


@receiver(user_login_failed, dispatch_uid='elo.auditoria.falha')
def registrar_falha(sender, credentials, request, **kwargs):
    # Não registrar credentials: pode conter senha e outros segredos.
    import unicodedata
    nome = unicodedata.normalize('NFKC', str(credentials.get('username', ''))).strip().lower()
    referencia = salted_hmac('elo.auditoria.tentativa', nome).hexdigest()
    bloqueado = bool(getattr(request, 'login_espera', 0))
    registrar('BLOQUEIO_LOGIN' if bloqueado else 'FALHA_LOGIN', request=request,
              entidade='tentativa de login', objeto_id=referencia)

