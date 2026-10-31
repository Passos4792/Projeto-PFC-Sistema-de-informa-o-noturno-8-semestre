#importacoes
from decimal import Decimal
from collections import defaultdict
from django import forms
from django.db.models import Count, Q
from django.utils import timezone
from .acesso import alunos_permitidos
from .models import Atividade, Disciplina, Meta, SolicitacaoConclusao


#-------------------------------------------------------------------------------------

#filtros compartilhados pelas paginas e pela API
class FiltroPainel(forms.Form):
    aluno = forms.ModelChoiceField(queryset=None, required=False, label='Aluno')
    periodo = forms.ChoiceField(required=False, label='Período da meta',
        choices=[('', 'Todos os períodos')] + list(Meta.Periodo.choices))
    inicio = forms.DateField(required=False, label='Entregas a partir de',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fim = forms.DateField(required=False, label='Entregas até',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    busca = forms.CharField(required=False, max_length=100, label='Pesquisar')

    #-------------------------------------------------------------------------------------

    #somente alunos que o perfil pode consultar
    def __init__(self, *args, perfil, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['aluno'].queryset = alunos_permitidos(perfil)
        self.fields['aluno'].empty_label = 'Todos os alunos permitidos'
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'

    #-------------------------------------------------------------------------------------

    #validacao do intervalo de entregas
    def clean(self):
        dados = super().clean()
        if dados.get('inicio') and dados.get('fim') and dados['inicio'] > dados['fim']:
            raise forms.ValidationError('A data inicial não pode ser posterior à data final.')
        return dados


#-------------------------------------------------------------------------------------

#frequencia calculada diretamente no banco, sem carregar outras areas
def dados_frequencia(perfil, filtros):
    hoje = timezone.localdate()
    alunos = alunos_permitidos(perfil)
    if filtros.get('aluno'):
        alunos = alunos.filter(pk=filtros['aluno'].pk)
    alunos = list(alunos.only('pk', 'nome', 'sobrenome', 'frequencia_minima').order_by('nome', 'sobrenome', 'pk'))
    #O banco conta por aluno; nao carrega atividades, metas ou solicitacoes na memoria.
    contagens = Atividade.objects.filter(aluno_id__in=[a.pk for a in alunos]).exclude(
        situacao='CANCELADA').order_by().values('aluno_id').annotate(
            total=Count('pk'),
            realizadas=Count('pk', filter=Q(situacao='CONCLUIDA')),
            pendentes=Count('pk', filter=Q(situacao='PENDENTE')),
            consideradas=Count('pk', filter=Q(situacao='CONCLUIDA') | Q(data_entrega__lte=hoje)),
            futuras=Count('pk', filter=Q(situacao='PENDENTE', data_entrega__gt=hoje)),
            sem_prazo=Count('pk', filter=Q(situacao='PENDENTE', data_entrega__isnull=True)))
    por_aluno = {item['aluno_id']: item for item in contagens}
    resumo = {'alunos': len(alunos), 'atividades': 0, 'realizadas': 0, 'pendentes': 0}
    frequencias = []
    for aluno in alunos:
        numeros = por_aluno.get(aluno.pk, {})
        total = numeros.get('total', 0)
        realizadas = numeros.get('realizadas', 0)
        consideradas = numeros.get('consideradas', 0)
        percentual = Decimal(realizadas * 100) / consideradas if consideradas else None
        resumo['atividades'] += total
        resumo['realizadas'] += realizadas
        resumo['pendentes'] += numeros.get('pendentes', 0)
        frequencias.append({'aluno_id': aluno.pk, 'aluno': aluno.nome_completo, 'total': total,
            'consideradas': consideradas, 'realizadas': realizadas,
            'atual': float(round(percentual, 2)) if percentual is not None else None,
            'minima': float(aluno.frequencia_minima) if aluno.frequencia_minima is not None else None,
            'atingiu': percentual >= aluno.frequencia_minima if percentual is not None and aluno.frequencia_minima is not None else None,
            'futuras': numeros.get('futuras', 0), 'sem_prazo': numeros.get('sem_prazo', 0)})
    return {'hoje': hoje.isoformat(), 'frequencias': frequencias, 'resumo': resumo}


#-------------------------------------------------------------------------------------

#conteudos contados no banco, respeitando os alunos permitidos
def dados_conteudos(perfil, filtros):
    alunos = alunos_permitidos(perfil)
    if filtros.get('aluno'):
        alunos = alunos.filter(pk=filtros['aluno'].pk)
    atividades = Atividade.objects.filter(aluno__in=alunos)
    contagens = atividades.exclude(situacao='CANCELADA').order_by().values('disciplina_id').annotate(
        total=Count('pk'), realizadas=Count('pk', filter=Q(situacao='CONCLUIDA')),
        pendentes=Count('pk', filter=Q(situacao='PENDENTE')))
    por_conteudo = {item['disciplina_id']: item for item in contagens}
    disciplinas = Disciplina.objects.order_by('nome', 'pk')
    if perfil.tipo_perfil != 'PROFESSOR':
        disciplinas = disciplinas.filter(pk__in=atividades.order_by().values('disciplina_id'))
    conteudos = []
    for disciplina in disciplinas:
        numeros = por_conteudo.get(disciplina.pk, {})
        conteudos.append({'id': disciplina.pk, 'nome': disciplina.nome, 'descricao': disciplina.descricao,
            'ativo': disciplina.ativo, 'total': numeros.get('total', 0),
            'realizadas': numeros.get('realizadas', 0), 'pendentes': numeros.get('pendentes', 0)})
    if None in por_conteudo:
        numeros = por_conteudo[None]
        conteudos.append({'id': None, 'nome': 'Sem conteúdo definido', 'descricao': 'Atividades anteriores ao catálogo.',
            'ativo': True, 'total': numeros['total'], 'realizadas': numeros['realizadas'], 'pendentes': numeros['pendentes']})
    return {'hoje': timezone.localdate().isoformat(), 'conteudos': conteudos,
        'resumo': {'alunos': alunos.count(), 'atividades': sum(c['total'] for c in conteudos),
            'realizadas': sum(c['realizadas'] for c in conteudos),
            'pendentes': sum(c['pendentes'] for c in conteudos)}}


#-------------------------------------------------------------------------------------

#indicadores completos das demais telas de acompanhamento
def dados_metas(perfil, filtros):
    return dados_painel(perfil, filtros, somente_metas=True)


#-------------------------------------------------------------------------------------

#calculo compartilhado do progresso, com consulta reduzida para a tela de metas
def dados_painel(perfil, filtros, somente_metas=False):
    hoje = timezone.localdate()
    alunos = alunos_permitidos(perfil).select_related('usuario')
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
    metas = list(Meta.objects.filter(aluno_id__in=ids).select_related('aluno', 'disciplina', 'professor'))
    solicitacoes = [] if somente_metas else list(SolicitacaoConclusao.objects.filter(aluno_id__in=ids, atividade__aluno_id__in=ids)
                        .select_related('atividade', 'aluno', 'solicitante', 'professor'))
    recentes = {}
    for solicitacao in solicitacoes:
        recentes.setdefault(solicitacao.atividade_id, solicitacao)

    #as metas usam o periodo completo; filtros de entregas afetam atividades e frequencia
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
                if a.data_entrega and meta.data_inicio <= a.data_entrega <= meta.data_prazo
                and (not meta.disciplina_id or a.disciplina_id == meta.disciplina_id)]
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
            'conteudo': meta.disciplina.nome if meta.disciplina_id else 'Todos os conteúdos',
            'periodo': meta.periodo, 'periodo_nome': meta.get_periodo_display(),
            'inicio': meta.data_inicio.isoformat(), 'fim': meta.data_prazo.isoformat() if meta.data_prazo else None,
            'inicio_formatado': meta.data_inicio.strftime('%d/%m/%Y'),
            'fim_formatado': meta.data_prazo.strftime('%d/%m/%Y') if meta.data_prazo else '',
            'alvo': meta.quantidade_alvo, 'realizadas': realizadas, 'atribuidas': len(relacionadas),
            'percentual': min(100, round(realizadas * 100 / meta.quantidade_alvo)),
            'estado': estado, 'estado_nome': {'CANCELADA': 'Cancelada', 'ALCANCADA': 'Alcançada',
                'FUTURA': 'Planejada', 'ENCERRADA': 'Prazo encerrado', 'EM_ANDAMENTO': 'Em andamento'}[estado]})
    if somente_metas:
        periodos = [{'codigo': codigo, 'nome': nome,
            'total': sum(m['periodo'] == codigo and m['estado'] != 'CANCELADA' for m in progresso_metas),
            'alcancadas': sum(m['periodo'] == codigo and m['estado'] == 'ALCANCADA' for m in progresso_metas)}
            for codigo, nome in Meta.Periodo.choices if codigo != 'PERSONALIZADO']
        return {'hoje': hoje.isoformat(), 'metas': progresso_metas, 'periodos': periodos}
    for chave, comparar in [('inicio', lambda d, limite: d >= limite), ('fim', lambda d, limite: d <= limite)]:
        if filtros.get(chave):
            atividades = [a for a in atividades if a.data_entrega and comparar(a.data_entrega, filtros[chave])]
    validas = [a for a in atividades if a.situacao != 'CANCELADA']
    frequencias = []
    for aluno in alunos:
        todas = [a for a in validas if a.aluno_id == aluno.pk]
        consideradas = [a for a in todas if a.situacao == 'CONCLUIDA' or (a.data_entrega and a.data_entrega <= hoje)]
        realizadas = sum(a.situacao == 'CONCLUIDA' for a in consideradas)
        percentual = Decimal(realizadas * 100) / len(consideradas) if consideradas else None
        frequencias.append({'aluno_id': aluno.pk, 'aluno': aluno.nome_completo, 'total': len(todas),
            'consideradas': len(consideradas), 'realizadas': realizadas,
            'atual': float(round(percentual, 2)) if percentual is not None else None,
            'minima': float(aluno.frequencia_minima) if aluno.frequencia_minima is not None else None,
            'atingiu': percentual >= aluno.frequencia_minima if percentual is not None and aluno.frequencia_minima is not None else None,
            'futuras': sum(a.situacao != 'CONCLUIDA' and bool(a.data_entrega) and a.data_entrega > hoje for a in todas),
            'sem_prazo': sum(a.situacao != 'CONCLUIDA' and not a.data_entrega for a in todas)})
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
        progresso_metas = [m for m in progresso_metas if termo in (m['titulo'] + ' ' + m['aluno'] + ' ' + m['conteudo']).casefold()]
        conteudos = [c for c in conteudos if termo in c['nome'].casefold()]
        lista_atividades = [a for a in lista_atividades if termo in (a['titulo'] + ' ' + a['aluno'] + ' ' + a['conteudo']).casefold()]
        frequencias = [f for f in frequencias if termo in f['aluno'].casefold()]
    periodos = [{'codigo': codigo, 'nome': nome, 'total': sum(m['periodo'] == codigo and m['estado'] != 'CANCELADA' for m in progresso_metas),
        'alcancadas': sum(m['periodo'] == codigo and m['estado'] == 'ALCANCADA' for m in progresso_metas)}
        for codigo, nome in Meta.Periodo.choices if codigo != 'PERSONALIZADO']
    return {'hoje': hoje.isoformat(), 'metas': progresso_metas, 'periodos': periodos,
        'conteudos': conteudos, 'frequencias': frequencias, 'atividades': lista_atividades,
        'resumo': {'alunos': len(alunos), 'metas': sum(m['estado'] != 'CANCELADA' for m in progresso_metas),
            'metas_alcancadas': sum(m['estado'] == 'ALCANCADA' for m in progresso_metas),
            'atividades': len(validas), 'realizadas': sum(a.situacao == 'CONCLUIDA' for a in validas),
            'pendentes': sum(a.situacao == 'PENDENTE' for a in validas),
            'aprovacoes': sum(s.situacao == 'PENDENTE' for s in solicitacoes)}}
