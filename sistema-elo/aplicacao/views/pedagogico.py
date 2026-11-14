from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from aplicacao.servicos.acesso import alunos_com_funcao, alunos_permitidos, funcoes_no_aluno, id_seguro
from aplicacao.servicos.auditoria import registrar
from aplicacao.servicos.exportacao_pdf import gerar_pdf_registro
from aplicacao.forms import FormularioVinculoFamiliar, FormularioVinculoProfissional
from aplicacao.forms.documentos import CAMPOS_DOCUMENTOS, FormularioCabecalhoDocumento, FormularioRelatorio
from aplicacao.models import (Aluno, DocumentoPedagogico, Professor, RelatorioPedagogico, VinculoFamiliar,
                     VinculoProfissional)


def eh_professor(perfil):
    return perfil.tipo_perfil == 'PROFESSOR'


def _exigir_gestor(perfil):
    if not (eh_professor(perfil) and perfil.gestor):
        raise PermissionDenied


def _alunos_profissional(perfil):
    if not eh_professor(perfil):
        raise PermissionDenied
    return alunos_permitidos(perfil)


def _verificacao_professor(perfil, aluno_id):
    if not _alunos_profissional(perfil).filter(pk=aluno_id).exists():
        raise PermissionDenied('O estudante não está vinculado ao profissional.')


def _alunos_documento(perfil, tipo):
    if not eh_professor(perfil):
        raise PermissionDenied
    if perfil.gestor:
        return Aluno.objects.all()
    aee = alunos_com_funcao(perfil, Professor.Funcao.AEE)
    if tipo == 'PEI':
        regente = alunos_com_funcao(perfil, Professor.Funcao.REGENTE)
        return Aluno.objects.filter(Q(pk__in=aee) | Q(pk__in=regente)).distinct()
    if tipo in ('ESTUDO', 'PAEE'):
        return aee
    return Aluno.objects.none()


def _documento_autorizado(perfil, obj):
    if not obj.aluno.ativo and not obj.aluno.documentos_em_prazo:
        raise PermissionDenied('O prazo de disponibilização do registro pedagógico terminou.')
    if eh_professor(perfil):
        _verificacao_professor(perfil, obj.aluno_id)
        if perfil.gestor:
            return
        if isinstance(obj, DocumentoPedagogico):
            if not _alunos_documento(perfil, obj.tipo).filter(pk=obj.aluno_id).exists():
                raise PermissionDenied('Sua função neste aluno não permite consultar este documento.')
        elif obj.professor.usuario_id != perfil.pk:
            raise PermissionDenied('Relatórios de outros profissionais não estão disponíveis neste perfil.')
        return
    if perfil.tipo_perfil != 'RESPONSAVEL':
        raise PermissionDenied('Documentos e relatórios são exclusivos dos responsáveis.')
    if obj.situacao != obj.Situacao.PUBLICADO or not alunos_permitidos(perfil).filter(pk=obj.aluno_id).exists():
        raise PermissionDenied('Documento não disponibilizado para esta conta.')


def _pode_editar(perfil, obj):
    if not obj.aluno.ativo or not eh_professor(perfil):
        return False
    if perfil.gestor:
        return True
    if obj.professor.usuario_id != perfil.pk or not _alunos_profissional(perfil).filter(pk=obj.aluno_id).exists():
        return False
    return (not isinstance(obj, DocumentoPedagogico) or
            _alunos_documento(perfil, obj.tipo).filter(pk=obj.aluno_id).exists())


def _tipo_permitido(perfil, tipo):
    return eh_professor(perfil) and tipo in CAMPOS_DOCUMENTOS and _alunos_documento(perfil, tipo).filter(ativo=True).exists()


@require_GET
def familia_estudantes(request):
    perfil = request.perfil_elo
    if perfil.tipo_perfil != 'RESPONSAVEL':
        raise PermissionDenied
    pagina = Paginator(alunos_permitidos(perfil).order_by('nome', 'sobrenome', 'pk'), 9).get_page(
        request.GET.get('pagina'))
    return render(request, 'aplicacao/pedagogico/familia-estudantes.html', {
        'alunos': pagina.object_list, 'pagina': pagina, 'pagina_ativa': 'familia'})


@require_GET
def profissional_estudantes(request):
    perfil = request.perfil_elo
    pagina = Paginator(_alunos_profissional(perfil).order_by('nome', 'sobrenome', 'pk'), 9).get_page(
        request.GET.get('pagina'))
    alunos = list(pagina.object_list)
    for aluno in alunos:
        funcoes = funcoes_no_aluno(perfil, aluno.pk)
        aluno.funcoes_no_elo = ', '.join(Professor.Funcao(valor).label for valor in sorted(funcoes))
        aluno.pode_gerenciar = 'AEE' in funcoes
    return render(request, 'aplicacao/pedagogico/profissional-estudantes.html', {
        'alunos': alunos, 'pagina': pagina, 'pagina_ativa': 'profissional-estudantes'})


@require_http_methods(['GET', 'POST'])
def vinculos_profissionais(request):
    _exigir_gestor(request.perfil_elo)
    form = FormularioVinculoProfissional(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                obj = form.save()
                registrar('PERMISSAO', request=request, objeto=obj, detalhes='Vínculo profissional criado.')
            messages.success(request, 'Vínculo profissional cadastrado.')
            return redirect('vinculos-profissionais')
        except (IntegrityError, ValidationError):
            form.add_error(None, 'Este vínculo já existe ou seus dados não são válidos.')
    return render(request, 'aplicacao/vinculos/vinculos-adicionais.html', {
        'formulario': form, 'titulo': 'Vínculos profissionais',
        'descricao': 'Associe professor do AEE, regente ou acompanhante aos alunos. A função é definida para cada aluno.',
        'pagina': Paginator(VinculoProfissional.objects.select_related('aluno', 'professor')
                            .order_by('aluno__nome', 'professor__nome', 'pk'), 20).get_page(request.GET.get('pagina')),
        'familia': False, 'pagina_ativa': 'vinculos-profissionais'})


@require_http_methods(['GET', 'POST'])
def vinculos_familiares(request):
    _exigir_gestor(request.perfil_elo)
    form = FormularioVinculoFamiliar(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                obj = form.save()
                registrar('PERMISSAO', request=request, objeto=obj, detalhes='Vínculo familiar adicional criado.')
            messages.success(request, 'Responsável vinculado ao aluno.')
            return redirect('vinculos-familiares')
        except IntegrityError:
            form.add_error(None, 'Este familiar já está vinculado a este aluno.')
    return render(request, 'aplicacao/vinculos/vinculos-adicionais.html', {
        'formulario': form, 'titulo': 'Vínculos familiares',
        'descricao': 'Um mesmo responsável pode acompanhar mais de um aluno, sem o estudante precisar de e-mail ou senha.',
        'pagina': Paginator(VinculoFamiliar.objects.select_related('aluno', 'responsavel')
                            .order_by('aluno__nome', 'responsavel__nome', 'pk'), 20).get_page(request.GET.get('pagina')),
        'familia': True, 'pagina_ativa': 'vinculos-familiares'})


@require_GET
def documentos_lista(request):
    perfil = request.perfil_elo
    if perfil.tipo_perfil not in ('PROFESSOR', 'RESPONSAVEL'):
        raise PermissionDenied('Documentos e relatórios são exclusivos dos responsáveis.')
    alunos = alunos_permitidos(perfil)
    hoje = timezone.localdate()
    try:
        corte = hoje.replace(year=hoje.year - 5)
    except ValueError:
        from datetime import date
        corte = date(hoje.year - 5, 3, 1)
    dentro_do_prazo = Q(aluno__ativo=True) | Q(aluno__inativado_em__date__gte=corte)
    docs = DocumentoPedagogico.objects.filter(dentro_do_prazo, aluno__in=alunos).select_related('aluno', 'professor')
    rels = RelatorioPedagogico.objects.filter(dentro_do_prazo, aluno__in=alunos).select_related('aluno', 'professor')
    if eh_professor(perfil) and not perfil.gestor:
        ids_aee = alunos_com_funcao(perfil, Professor.Funcao.AEE)
        ids_regente = alunos_com_funcao(perfil, Professor.Funcao.REGENTE)
        docs = docs.filter(Q(aluno__in=ids_aee) | Q(tipo='PEI', aluno__in=ids_regente))
        rels = rels.filter(professor__usuario=perfil)
    if not eh_professor(perfil):
        docs = docs.filter(situacao='PUBLICADO')
        rels = rels.filter(situacao='PUBLICADO')
    aluno_id = request.GET.get('aluno', '').strip()
    if aluno_id:
        aluno = get_object_or_404(alunos, pk=id_seguro(aluno_id))
        docs = docs.filter(aluno=aluno)
        rels = rels.filter(aluno=aluno)
    total = docs.count() + rels.count()
    visao = request.GET.get('filtro', 'todos')
    situacoes = {'rascunhos': 'RASCUNHO', 'finalizados': 'FINALIZADO', 'publicados': 'PUBLICADO'}
    if not eh_professor(perfil) or visao not in situacoes:
        visao = 'todos'
    else:
        docs = docs.filter(situacao=situacoes[visao])
        rels = rels.filter(situacao=situacoes[visao])
    busca = request.GET.get('busca', '').strip()[:100]
    for parte in busca.split():
        tipos = [codigo for codigo, nome in DocumentoPedagogico.Tipo.choices if parte.casefold() in nome.casefold()]
        criterio = (Q(aluno__nome__icontains=parte) | Q(aluno__sobrenome__icontains=parte) | Q(tipo__in=tipos))
        if parte.isascii() and parte.isdigit() and len(parte) == 4:
            criterio |= Q(ano_letivo=int(parte))
        docs = docs.filter(criterio)
        rels = rels.filter(Q(titulo__icontains=parte) | Q(aluno__nome__icontains=parte)
                           | Q(aluno__sobrenome__icontains=parte))
    pagina_documentos = Paginator(docs.order_by('-criado_em', '-pk'), 8).get_page(
        request.GET.get('pagina_documentos'))
    pagina_relatorios = Paginator(rels.order_by('-criado_em', '-pk'), 8).get_page(
        request.GET.get('pagina_relatorios'))
    filtros_documentos = request.GET.copy()
    filtros_documentos.pop('pagina_documentos', None)
    filtros_relatorios = request.GET.copy()
    filtros_relatorios.pop('pagina_relatorios', None)
    filtros_abas = request.GET.copy()
    for chave in ('filtro', 'pagina_documentos', 'pagina_relatorios'):
        filtros_abas.pop(chave, None)
    return render(request, 'aplicacao/pedagogico/documentos-pedagogicos.html', {
        'visao': visao, 'busca': busca, 'total_cadastrados': total, 'filtros_abas': filtros_abas.urlencode(),
        'documentos': pagina_documentos.object_list, 'relatorios': pagina_relatorios.object_list,
        'pagina_documentos': pagina_documentos, 'pagina_relatorios': pagina_relatorios,
        'filtros_documentos': filtros_documentos.urlencode(),
        'filtros_relatorios': filtros_relatorios.urlencode(), 'alunos': alunos,
        'eh_professor': eh_professor(perfil), 'pagina_ativa': 'documentos',
        'pode_pei': eh_professor(perfil) and _alunos_documento(perfil, 'PEI').exists(),
        'pode_paee': eh_professor(perfil) and _alunos_documento(perfil, 'PAEE').exists(),
    })


@require_http_methods(['GET', 'POST'])
def documento_criar(request, tipo):
    perfil = request.perfil_elo
    if tipo not in CAMPOS_DOCUMENTOS or not _tipo_permitido(perfil, tipo):
        raise PermissionDenied('Este perfil não pode preencher esse modelo.')
    formulario = FormularioCabecalhoDocumento(request.POST or None, alunos=_alunos_documento(perfil, tipo).filter(ativo=True), tipo=tipo)
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            doc = DocumentoPedagogico.objects.create(
                aluno=formulario.cleaned_data['aluno'], professor=perfil.professor_perfil,
                tipo=tipo, ano_letivo=formulario.cleaned_data['ano_letivo'],
                bimestre=formulario.cleaned_data.get('bimestre'), campos=formulario.respostas())
            registrar('CRIACAO', request=request, objeto=doc, detalhes='Documento pedagógico em rascunho.')
        messages.success(request, 'Documento salvo como rascunho. Ele ainda não está visível à família.')
        return redirect('documento-detalhe', pk=doc.pk)
    return render(request, 'aplicacao/pedagogico/formulario-documento.html', {
        'formulario': formulario, 'tipo_nome': DocumentoPedagogico.Tipo(tipo).label,
        'pagina_ativa': 'documentos', 'titulo': 'Novo documento pedagógico'})


@require_http_methods(['GET', 'POST'])
def documento_editar(request, pk):
    perfil = request.perfil_elo
    doc = get_object_or_404(DocumentoPedagogico, pk=pk)
    _documento_autorizado(perfil, doc)
    if not _pode_editar(perfil, doc) or doc.situacao != doc.Situacao.RASCUNHO:
        raise PermissionDenied('Apenas o autor pode editar rascunhos.')
    formulario = FormularioCabecalhoDocumento(
        request.POST or None, alunos=_alunos_documento(perfil, doc.tipo), tipo=doc.tipo,
        valores=doc.campos, initial={'aluno': doc.aluno_id, 'ano_letivo': doc.ano_letivo, 'bimestre': doc.bimestre})
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            doc.aluno = formulario.cleaned_data['aluno']
            doc.ano_letivo = formulario.cleaned_data['ano_letivo']
            doc.bimestre = formulario.cleaned_data.get('bimestre')
            doc.campos = formulario.respostas()
            doc.save()
            registrar('EDICAO', request=request, objeto=doc, detalhes='Rascunho pedagógico atualizado.')
        messages.success(request, 'Rascunho atualizado.')
        return redirect('documento-detalhe', pk=doc.pk)
    return render(request, 'aplicacao/pedagogico/formulario-documento.html', {
        'formulario': formulario, 'tipo_nome': doc.get_tipo_display(),
        'pagina_ativa': 'documentos', 'titulo': 'Editar documento pedagógico'})


@require_GET
def documento_detalhe(request, pk):
    doc = get_object_or_404(DocumentoPedagogico.objects.select_related('aluno', 'professor'), pk=pk)
    _documento_autorizado(request.perfil_elo, doc)
    linhas = [(rotulo, doc.campos.get(chave, '')) for chave, rotulo in CAMPOS_DOCUMENTOS[doc.tipo]]
    return render(request, 'aplicacao/pedagogico/documento-detalhe.html', {
        'item': doc, 'linhas': linhas, 'documento': True, 'pagina_ativa': 'documentos',
        'pode_editar': _pode_editar(request.perfil_elo, doc) and doc.situacao == 'RASCUNHO',
        'pode_publicar': _pode_editar(request.perfil_elo, doc) and doc.situacao != 'PUBLICADO',
        'pode_retirar': request.perfil_elo.gestor and doc.situacao == 'PUBLICADO'})


@never_cache
@require_GET
def documento_pdf(request, pk):
    doc = get_object_or_404(DocumentoPedagogico.objects.select_related('aluno', 'professor'), pk=pk)
    _documento_autorizado(request.perfil_elo, doc)
    linhas = [(rotulo, doc.campos.get(chave, '')) for chave, rotulo in CAMPOS_DOCUMENTOS[doc.tipo]]
    conteudo = gerar_pdf_registro(doc, linhas, documento=True)
    resposta = HttpResponse(conteudo, content_type='application/pdf')
    resposta['Content-Disposition'] = f'attachment; filename="elo-{doc.tipo.lower()}-{doc.pk}.pdf"'
    return resposta


@require_POST
def documento_publicar(request, pk):
    doc = get_object_or_404(DocumentoPedagogico, pk=pk)
    if not _pode_editar(request.perfil_elo, doc):
        raise PermissionDenied
    acao = request.POST.get('acao')
    if acao not in ('FINALIZADO', 'PUBLICADO', 'RETIRAR'):
        raise PermissionDenied
    if acao == 'RETIRAR' and not request.perfil_elo.gestor:
        raise PermissionDenied
    with transaction.atomic():
        obj = DocumentoPedagogico.objects.select_for_update().get(pk=pk)
        if acao == 'RETIRAR':
            if obj.situacao != 'PUBLICADO':
                raise PermissionDenied
            obj.situacao = 'FINALIZADO'
            obj.save(update_fields=['situacao', 'atualizado_em'])
            registrar('EDICAO', request=request, objeto=obj,
                      detalhes='Documento retirado da consulta da família.')
        else:
            if obj.situacao == 'PUBLICADO':
                raise PermissionDenied
            obj.situacao = acao
            obj.save(update_fields=['situacao', 'atualizado_em'])
            registrar('EDICAO', request=request, objeto=obj, detalhes='Estado do documento: ' + acao)
    messages.success(request, 'Documento atualizado.')
    return redirect('documento-detalhe', pk=pk)


@require_http_methods(['GET', 'POST'])
def relatorio_criar(request):
    perfil = request.perfil_elo
    formulario = FormularioRelatorio(request.POST or None, alunos=_alunos_profissional(perfil).filter(ativo=True))
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            rel = formulario.save(commit=False)
            rel.professor = perfil.professor_perfil
            rel.save()
            registrar('CRIACAO', request=request, objeto=rel, detalhes='Relatório livre criado em rascunho.')
        messages.success(request, 'Relatório salvo como rascunho.')
        return redirect('relatorio-detalhe', pk=rel.pk)
    return render(request, 'aplicacao/pedagogico/formulario-documento.html', {
        'formulario': formulario, 'tipo_nome': 'Relatório pedagógico descritivo',
        'pagina_ativa': 'documentos', 'titulo': 'Novo relatório'})


@require_http_methods(['GET', 'POST'])
def relatorio_editar(request, pk):
    perfil = request.perfil_elo
    rel = get_object_or_404(RelatorioPedagogico, pk=pk)
    _documento_autorizado(perfil, rel)
    if not _pode_editar(perfil, rel) or rel.situacao != 'RASCUNHO':
        raise PermissionDenied
    formulario = FormularioRelatorio(request.POST or None, instance=rel, alunos=_alunos_profissional(perfil))
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            formulario.save()
            registrar('EDICAO', request=request, objeto=rel, detalhes='Relatório atualizado.')
        messages.success(request, 'Relatório atualizado.')
        return redirect('relatorio-detalhe', pk=rel.pk)
    return render(request, 'aplicacao/pedagogico/formulario-documento.html', {
        'formulario': formulario, 'tipo_nome': 'Relatório pedagógico descritivo',
        'pagina_ativa': 'documentos', 'titulo': 'Editar relatório'})


@require_GET
def relatorio_detalhe(request, pk):
    rel = get_object_or_404(RelatorioPedagogico.objects.select_related('aluno', 'professor'), pk=pk)
    _documento_autorizado(request.perfil_elo, rel)
    return render(request, 'aplicacao/pedagogico/documento-detalhe.html', {
        'item': rel, 'documento': False, 'pagina_ativa': 'documentos',
        'linhas': [('Período', rel.periodo), ('Relato pedagógico', rel.relato)],
        'pode_editar': _pode_editar(request.perfil_elo, rel) and rel.situacao == 'RASCUNHO',
        'pode_publicar': _pode_editar(request.perfil_elo, rel) and rel.situacao != 'PUBLICADO',
        'pode_retirar': request.perfil_elo.gestor and rel.situacao == 'PUBLICADO'})


@never_cache
@require_GET
def relatorio_pdf(request, pk):
    rel = get_object_or_404(RelatorioPedagogico.objects.select_related('aluno', 'professor'), pk=pk)
    _documento_autorizado(request.perfil_elo, rel)
    linhas = [('Período', rel.periodo), ('Relato pedagógico', rel.relato)]
    conteudo = gerar_pdf_registro(rel, linhas, documento=False)
    resposta = HttpResponse(conteudo, content_type='application/pdf')
    resposta['Content-Disposition'] = f'attachment; filename="elo-relatorio-{rel.pk}.pdf"'
    return resposta


@require_POST
def relatorio_publicar(request, pk):
    rel = get_object_or_404(RelatorioPedagogico, pk=pk)
    if not _pode_editar(request.perfil_elo, rel):
        raise PermissionDenied
    acao = request.POST.get('acao')
    if acao not in ('FINALIZADO', 'PUBLICADO', 'RETIRAR'):
        raise PermissionDenied
    if acao == 'RETIRAR' and not request.perfil_elo.gestor:
        raise PermissionDenied
    with transaction.atomic():
        obj = RelatorioPedagogico.objects.select_for_update().get(pk=pk)
        if acao == 'RETIRAR':
            if obj.situacao != 'PUBLICADO':
                raise PermissionDenied
            obj.situacao = 'FINALIZADO'
            obj.save(update_fields=['situacao', 'atualizado_em'])
            registrar('EDICAO', request=request, objeto=obj,
                      detalhes='Relatório retirado da consulta da família.')
        else:
            if obj.situacao == 'PUBLICADO':
                raise PermissionDenied
            obj.situacao = acao
            obj.save(update_fields=['situacao', 'atualizado_em'])
            registrar('EDICAO', request=request, objeto=obj, detalhes='Estado do relatório: ' + acao)
    messages.success(request, 'Relatório atualizado.')
    return redirect('relatorio-detalhe', pk=pk)
