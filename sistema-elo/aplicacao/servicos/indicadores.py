from collections import defaultdict
from django.db.models import Q
from django.utils import timezone
from aplicacao.servicos.acesso import alunos_com_funcao, alunos_permitidos
from aplicacao.models import Atividade, Disciplina, MetaAluno, Professor, SolicitacaoConclusao


def resumo_periodos(metas):
    return [{'codigo': codigo, 'nome': nome,
             'total': sum(m['periodo'] == codigo and m['estado'] != 'CANCELADA' for m in metas),
             'alcancadas': sum(m['periodo'] == codigo and m['estado'] == 'ALCANCADA' for m in metas)}
            for codigo, nome in MetaAluno.Periodo.choices if codigo != 'PERSONALIZADO']


def dados_metas(perfil, filtros):
    return dados_painel(perfil, filtros, somente_metas=True)


def dados_painel(perfil, filtros, somente_metas=False):
    hoje = timezone.localdate()
    alunos = (alunos_com_funcao(perfil, Professor.Funcao.AEE)
              if perfil.tipo_perfil == 'PROFESSOR' else alunos_permitidos(perfil)).select_related('usuario')
    if filtros.get('aluno'):
        alunos = alunos.filter(pk=filtros['aluno'].pk)
    alunos = list(alunos)
    ids = [a.pk for a in alunos]
    consulta_atividades = Atividade.objects.filter(aluno_id__in=ids)
    if somente_metas:
        consulta_atividades = consulta_atividades.only('aluno_id', 'meta_id', 'data_entrega', 'situacao', 'disciplina_id').order_by()
    else:
        consulta_atividades = consulta_atividades.select_related('aluno', 'disciplina', 'professor')
    atividades = list(consulta_atividades)
    metas = list(MetaAluno.objects.filter(aluno_id__in=ids).select_related('aluno', 'professor'))
    solicitacoes = [] if somente_metas else list(SolicitacaoConclusao.objects.filter(aluno_id__in=ids, atividade__aluno_id__in=ids)
                        .select_related('atividade', 'aluno', 'solicitante', 'professor'))
    recentes = {}
    for solicitacao in solicitacoes:
        recentes.setdefault(solicitacao.atividade_id, solicitacao)

    progresso_metas = []
    por_aluno, por_meta = defaultdict(list), defaultdict(list)
    for atividade in atividades:
        if atividade.situacao != 'CANCELADA':
            por_aluno[atividade.aluno_id].append(atividade)
            por_meta[atividade.meta_id].append(atividade)
    for meta in metas:
        if filtros.get('periodo') and meta.periodo != filtros['periodo']:
            continue
        if meta.periodo == 'PERSONALIZADO':
            relacionadas = por_meta[meta.pk]
        else:
            relacionadas = [a for a in por_aluno[meta.aluno_id]
                if a.data_entrega and meta.data_inicio <= a.data_entrega <= meta.data_prazo]
        realizadas = sum(a.situacao == 'CONCLUIDA' for a in relacionadas)
        alcancada = realizadas >= meta.quantidade_alvo
        if meta.periodo == 'PERSONALIZADO':
            alcancada = meta.situacao == 'CONCLUIDA'
        estado = ('CANCELADA' if meta.situacao == 'CANCELADA' else 'ALCANCADA' if alcancada
                  else 'FUTURA' if meta.data_inicio > hoje else 'ENCERRADA'
                  if meta.data_prazo and meta.data_prazo < hoje else 'EM_ANDAMENTO')
        progresso_metas.append({
            'id': meta.pk, 'titulo': meta.titulo, 'descricao': meta.descricao,
            'aluno_id': meta.aluno_id, 'aluno': meta.aluno.nome_completo,
            'periodo': meta.periodo, 'periodo_nome': meta.get_periodo_display(),
            'inicio': meta.data_inicio.isoformat(), 'fim': meta.data_prazo.isoformat() if meta.data_prazo else None,
            'inicio_formatado': meta.data_inicio.strftime('%d/%m/%Y'),
            'fim_formatado': meta.data_prazo.strftime('%d/%m/%Y') if meta.data_prazo else '',
            'alvo': meta.quantidade_alvo, 'realizadas': realizadas, 'atribuidas': len(relacionadas),
            'percentual': min(100, round(realizadas * 100 / meta.quantidade_alvo)),
            'estado': estado, 'estado_nome': {'CANCELADA': 'Cancelada', 'ALCANCADA': 'Alcançada',
                'FUTURA': 'Planejada', 'ENCERRADA': 'Prazo encerrado', 'EM_ANDAMENTO': 'Em andamento'}[estado]})
    if somente_metas:
        return {'hoje': hoje.isoformat(), 'metas': progresso_metas, 'periodos': resumo_periodos(progresso_metas)}
    for chave, comparar in [('inicio', lambda d, limite: d >= limite), ('fim', lambda d, limite: d <= limite)]:
        if filtros.get(chave):
            atividades = [a for a in atividades if a.data_entrega and comparar(a.data_entrega, filtros[chave])]
    validas = [a for a in atividades if a.situacao != 'CANCELADA']
    disciplinas = Disciplina.objects.all()
    if perfil.tipo_perfil != 'PROFESSOR':
        disciplinas = disciplinas.filter(pk__in={a.disciplina_id for a in atividades if a.disciplina_id})
    conteudos = []
    for disciplina in disciplinas:
        itens = [a for a in validas if a.disciplina_id == disciplina.pk]
        conteudos.append({'id': disciplina.pk, 'nome': disciplina.nome, 'descricao': disciplina.descricao,
            'ativo': disciplina.ativo, 'total': len(itens),
            'realizadas': sum(a.situacao == 'CONCLUIDA' for a in itens),
            'pendentes': sum(a.situacao == 'PENDENTE' for a in itens)})
    antigos = [a for a in validas if a.disciplina_id is None]
    if antigos:
        conteudos.append({'id': None, 'nome': 'Sem conteúdo definido', 'descricao': 'Atividades anteriores ao catálogo.',
            'ativo': True, 'total': len(antigos), 'realizadas': sum(a.situacao == 'CONCLUIDA' for a in antigos),
            'pendentes': sum(a.situacao == 'PENDENTE' for a in antigos)})
    lista_atividades = []
    for atividade in atividades:
        ultima = recentes.get(atividade.pk)
        lista_atividades.append({'id': atividade.pk, 'titulo': atividade.titulo, 'descricao': atividade.descricao,
            'aluno': atividade.aluno.nome_completo, 'aluno_id': atividade.aluno_id,
            'conteudo': atividade.disciplina.nome if atividade.disciplina_id else 'Sem conteúdo definido',
            'entrega': atividade.data_entrega.isoformat() if atividade.data_entrega else None,
            'situacao': atividade.situacao, 'situacao_nome': atividade.get_situacao_display(),
            'solicitacao': ultima.situacao if ultima else None, 'resposta': ultima.resposta if ultima else '',
            'atrasada': atividade.situacao == 'PENDENTE' and bool(atividade.data_entrega) and atividade.data_entrega < hoje})
    termo = filtros.get('busca', '').casefold()
    if termo:
        progresso_metas = [m for m in progresso_metas if termo in (m['titulo'] + ' ' + m['aluno']).casefold()]
        conteudos = [c for c in conteudos if termo in c['nome'].casefold()]
        lista_atividades = [a for a in lista_atividades if termo in (a['titulo'] + ' ' + a['aluno'] + ' ' + a['conteudo']).casefold()]
    periodos = resumo_periodos(progresso_metas)
    return {'hoje': hoje.isoformat(), 'metas': progresso_metas, 'periodos': periodos,
        'conteudos': conteudos, 'atividades': lista_atividades,
        'resumo': {'alunos': len(alunos), 'metas': sum(m['estado'] != 'CANCELADA' for m in progresso_metas),
            'metas_alcancadas': sum(m['estado'] == 'ALCANCADA' for m in progresso_metas),
            'atividades': len(validas), 'realizadas': sum(a.situacao == 'CONCLUIDA' for a in validas),
            'pendentes': sum(a.situacao == 'PENDENTE' for a in validas),
            'aprovacoes': sum(s.situacao == 'PENDENTE' for s in solicitacoes)}}
