from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from aplicacao.servicos.acesso import id_seguro
from aplicacao.servicos.auditoria import registrar
from aplicacao.forms import FichaVinculos, FormularioVinculoFamiliar
from aplicacao.models import Aluno, Vinculo, VinculoFamiliar, VinculoProfissional


def _dados_ficha(aluno):
    vinculo = Vinculo.objects.filter(aluno=aluno).select_related('professor', 'responsavel').first()
    adicionais = VinculoProfissional.objects.filter(aluno=aluno, ativo=True).select_related('professor')
    por_funcao = {}
    for item in adicionais:
        if item.data_inicio <= timezone.localdate() and (item.data_fim is None or item.data_fim >= timezone.localdate()):
            por_funcao.setdefault(item.funcao, item.professor)
    return {
        'aluno': aluno,
        'responsavel': vinculo.responsavel_id if vinculo else None,
        'professor_aee': vinculo.professor_id if vinculo else (por_funcao.get('AEE').pk if 'AEE' in por_funcao else None),
        'professor_regente': por_funcao.get('REGENTE').pk if 'REGENTE' in por_funcao else None,
        'professor_acompanhante': por_funcao.get('ACOMPANHANTE').pk if 'ACOMPANHANTE' in por_funcao else None,
        'data_vinculo': vinculo.data_vinculo if vinculo else timezone.localdate(),
        'ativo': vinculo.ativo if vinculo else True,
        'mesclar_perfis': vinculo.mesclar_perfis if vinculo else False,
    }


def _atribuir_profissional(aluno, funcao, professor, data_inicio, ativo):
    atual = (VinculoProfissional.objects.select_for_update()
             .filter(aluno=aluno, funcao=funcao))
    for item in atual:
        if professor and item.professor_id == professor.pk:
            item.ativo = ativo
            item.data_fim = None
            item.data_inicio = data_inicio
        else:
            item.ativo = False
            if not item.data_fim:
                item.data_fim = timezone.localdate()
        item.save(update_fields=['ativo', 'data_fim', 'data_inicio'])
    if professor and not atual.filter(professor=professor).exists():
        VinculoProfissional.objects.create(aluno=aluno, professor=professor, funcao=funcao,
                                          data_inicio=data_inicio, ativo=ativo)


def _resumos(alunos):
    alunos = list(alunos)
    principais = {v.aluno_id: v for v in Vinculo.objects.filter(aluno__in=alunos)
                  .select_related('responsavel', 'professor')}
    resultados = []
    hoje = timezone.localdate()
    for aluno in alunos:
        principal = principais.get(aluno.pk)
        equipe = {'REGENTE': [], 'ACOMPANHANTE': [], 'AEE': []}
        for profissional in aluno.vinculos_profissionais.all():
            if profissional.data_inicio <= hoje and (not profissional.data_fim or profissional.data_fim >= hoje):
                equipe[profissional.funcao].append(profissional.professor)
        resultados.append({
            'aluno': aluno, 'principal': principal,
            'aee': principal.professor if principal and principal.ativo else (equipe['AEE'][0] if equipe['AEE'] else None),
            'regentes': equipe['REGENTE'], 'acompanhantes': equipe['ACOMPANHANTE'],
            'familiares': list(aluno.vinculos_familiares.all()),
        })
    return resultados


@require_http_methods(['GET', 'POST'])
def vinculos_unificados(request):
    perfil = request.perfil_elo
    if perfil.tipo_perfil != 'PROFESSOR' or not perfil.gestor:
        raise PermissionDenied('Somente o gestor pode editar vínculos.')

    if request.method == 'GET' and request.resolver_match.url_name == 'vinculo-listar' and not request.GET.get('aluno'):
        busca = request.GET.get('busca', '').strip()
        alunos = Aluno.objects.filter(
            Q(vinculo__isnull=False) | Q(vinculos_profissionais__isnull=False) |
            Q(vinculos_familiares__isnull=False)).distinct()
        total = alunos.count()
        for parte in busca.split():
            alunos = alunos.filter(Q(nome__icontains=parte) | Q(sobrenome__icontains=parte))
        alunos = alunos.select_related('usuario').prefetch_related(
            Prefetch('vinculos_profissionais', queryset=VinculoProfissional.objects.filter(ativo=True).select_related('professor')),
            Prefetch('vinculos_familiares', queryset=VinculoFamiliar.objects.filter(ativo=True).select_related('responsavel')),
        ).order_by('nome', 'sobrenome', 'pk')
        pagina = Paginator(alunos, 10).get_page(request.GET.get('pagina'))
        filtros = request.GET.copy()
        filtros.pop('pagina', None)
        registrar('CONSULTA', request=request, entidade='Vínculos dos alunos',
                  detalhes=f'Página: {pagina.number}; pesquisa: {"sim" if busca else "não"}.')
        return render(request, 'aplicacao/vinculos/vinculos-lista.html', {
            'pagina_ativa': 'vinculos', 'fichas': _resumos(pagina), 'pagina': pagina,
            'total_cadastrados': total, 'busca': busca, 'filtros_paginacao': filtros.urlencode()})

    selecionado_id = request.POST.get('aluno') if request.method == 'POST' else request.GET.get('aluno')
    selecionado = Aluno.objects.filter(pk=id_seguro(selecionado_id)).first() if selecionado_id else None
    inicial = _dados_ficha(selecionado) if selecionado else {}
    acao = request.POST.get('acao', 'salvar_ficha')
    formulario = FichaVinculos(request.POST if request.method == 'POST' and acao == 'salvar_ficha' else None, initial=inicial)
    familiar_form = None

    if request.method == 'POST' and acao == 'salvar_ficha' and formulario.is_valid():
        dados = formulario.cleaned_data
        aluno = dados['aluno']
        with transaction.atomic():
            Vinculo.objects.select_for_update().filter(aluno=aluno).exists()
            Vinculo.objects.update_or_create(aluno=aluno, defaults={
                'professor': dados['professor_aee'], 'responsavel': dados['responsavel'],
                'data_vinculo': dados['data_vinculo'], 'ativo': dados['ativo'],
                'mesclar_perfis': dados['mesclar_perfis']})
            _atribuir_profissional(aluno, 'REGENTE', dados['professor_regente'],
                                   dados['data_vinculo'], dados['ativo'])
            _atribuir_profissional(aluno, 'ACOMPANHANTE', dados['professor_acompanhante'],
                                   dados['data_vinculo'], dados['ativo'])
            registrar('PERMISSAO', request=request, entidade='Vínculos do aluno', objeto_id=str(aluno.pk),
                      detalhes=('Ficha atualizada. Acesso integrado do responsável principal: '
                                + ('ativado' if dados['mesclar_perfis'] else 'desativado')))
        messages.success(request, f'Vínculos de {aluno.nome_completo} atualizados com sucesso.')
        return redirect('vinculo-listar')

    if request.method == 'POST' and acao == 'adicionar_familiar':
        familiar_form = FormularioVinculoFamiliar(request.POST, auto_id="id_adicional_%s")
        if familiar_form.is_valid():
            novo = familiar_form.save(commit=False)
            principal = Vinculo.objects.filter(aluno=novo.aluno).first()
            if principal and principal.responsavel_id == novo.responsavel_id:
                familiar_form.add_error('responsavel', 'Este responsável já é o principal do aluno.')
            else:
                with transaction.atomic():
                    VinculoFamiliar.objects.update_or_create(
                        aluno=novo.aluno, responsavel=novo.responsavel,
                        defaults={'ativo': novo.ativo, 'mesclar_perfis': novo.mesclar_perfis})
                    registrar('PERMISSAO', request=request, entidade='Vínculo familiar',
                              objeto_id=str(novo.aluno_id), detalhes='Responsável adicional atualizado.')
                messages.success(request, 'Responsável adicional vinculado.')
                return redirect('vinculo-listar')

    if request.method == 'POST' and acao == 'alternar_familiar':
        item = get_object_or_404(VinculoFamiliar, pk=id_seguro(request.POST.get('vinculo_id')))
        with transaction.atomic():
            item.mesclar_perfis = request.POST.get('mesclar_perfis') == 'on'
            item.save(update_fields=['mesclar_perfis'])
            registrar('PERMISSAO', request=request, objeto=item,
                      detalhes='Acesso integrado do responsável adicional alterado.')
        messages.success(request, 'Acesso integrado atualizado.')
        return redirect('vinculo-listar')

    if familiar_form is None:
        familiar_form = FormularioVinculoFamiliar(auto_id="id_adicional_%s")

    return render(request, 'aplicacao/vinculos/vinculos-unificados.html', {
        'titulo': 'Vínculos dos alunos', 'pagina_ativa': 'vinculos',
        'formulario': formulario, 'familiar_form': familiar_form,
        'selecionado': selecionado})
