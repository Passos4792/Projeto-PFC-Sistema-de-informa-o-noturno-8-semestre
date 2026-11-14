import unicodedata
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from django.utils.crypto import salted_hmac
from aplicacao.models import RegistroAuditoria


def _identificar(objeto, excluido):
    prefixo = 'Excluído: ' if excluido else ''
    if hasattr(objeto, 'nome_completo'):
        login = getattr(getattr(objeto, 'usuario', None), 'usuario', '')
        return f'{prefixo}{objeto.nome_completo}' + (f' (usuário: {login})' if login else '')
    if objeto._meta.model_name == 'usuario':
        return f'{prefixo}usuário {objeto.usuario} ({objeto.get_tipo_perfil_display()})'
    if excluido:
        return f'{prefixo}{getattr(objeto, "titulo", None) or objeto}'[:200]
    return ''


def _ip_da_requisicao(request):
    if request is None:
        return None
    from aplicacao.servicos.limite_login import ip_cliente
    ip = (ip_cliente(request) or '').strip()
    try:
        validate_ipv46_address(ip)
    except ValidationError:
        return None
    return ip


def registrar(acao, request=None, objeto=None, autor=None, entidade='', objeto_id='', detalhes=''):
    usuario = autor if autor is not None else getattr(request, 'user', None)
    identificado = usuario is not None and usuario.is_authenticated
    if objeto is not None:
        nomes = {'meta': 'Meta', 'metaaluno': 'Meta', 'atividade': 'Atividade', 'disciplina': 'Conteúdo curricular',
                 'solicitacaoconclusao': 'Solicitação de conclusão'}
        entidade = nomes.get(objeto._meta.model_name, objeto._meta.verbose_name)
        referencias = []
        for campo, rotulo in [('aluno_id', 'Aluno'), ('professor_id', 'Professor'), ('atividade_id', 'Atividade')]:
            valor = getattr(objeto, campo, None)
            if valor is not None:
                referencias.append(f'{rotulo} #{valor}')
        referencias.insert(0, _identificar(objeto, acao == 'EXCLUSAO'))
        detalhes = '; '.join(r for r in referencias + [detalhes] if r)
    return RegistroAuditoria.objects.create(
        autor_id_original=usuario.pk if identificado else None,
        autor=usuario.get_username()[:150] if identificado else (
            'Não autenticado' if request else 'Comando local'),
        acao=acao, entidade=entidade,
        objeto_id=str(objeto.pk) if objeto is not None else str(objeto_id),
        detalhes=detalhes[:500], ip=_ip_da_requisicao(request))


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
        'atividade-historico': 'Atividades (histórico)', 'aprovacoes': 'Atividades (aprovações)',
        'api-painel': 'Indicadores pela API', 'api-metas-aluno': 'Metas do aluno pela API',
        'documentos-lista': 'Documentos e relatórios',
        'documento-detalhe': 'Documento pedagógico', 'documento-pdf': 'Documento pedagógico (PDF)',
        'relatorio-detalhe': 'Relatório pedagógico', 'relatorio-pdf': 'Relatório pedagógico (PDF)',
        'atividade-detalhe': 'Atividade', 'atividade-material': 'Material da atividade (arquivo)',
        'entrega-anexo': 'Anexo de entrega (arquivo)', 'solicitacao-senha-listar': 'Solicitações de senha',
        'familia-estudantes': 'Estudantes vinculados (família)',
        'profissional-estudantes': 'Estudantes vinculados (profissional)'}
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


def referencia_tentativa(nome):
    nome = unicodedata.normalize('NFKC', str(nome or '')).strip().lower()
    return salted_hmac('elo.auditoria.tentativa', nome).hexdigest()


@receiver(user_logged_in, dispatch_uid='elo.auditoria.login')
def registrar_login(sender, request, user, **kwargs):
    registrar('LOGIN', request=request, autor=user)


@receiver(user_logged_out, dispatch_uid='elo.auditoria.saida')
def registrar_saida(sender, request, user, **kwargs):
    if user is not None:
        registrar('SAIDA', request=request, autor=user)


@receiver(user_login_failed, dispatch_uid='elo.auditoria.falha')
def registrar_falha(sender, credentials, request, **kwargs):
    referencia = referencia_tentativa(credentials.get('username', ''))
    bloqueado = bool(getattr(request, 'login_espera', 0))
    registrar('BLOQUEIO_LOGIN' if bloqueado else 'FALHA_LOGIN', request=request,
              entidade='tentativa de login', objeto_id=referencia)
