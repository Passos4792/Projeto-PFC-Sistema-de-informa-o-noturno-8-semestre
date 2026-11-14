from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from aplicacao.servicos.acesso import alunos_com_funcao, id_seguro, pode_gerenciar_pedagogia
from aplicacao.servicos.auditoria import detalhes_formulario, registrar
from aplicacao.models import Aluno, Configuracao2FA, Professor


def _tem_segundo_fator():
    return Exists(Configuracao2FA.objects.filter(conta_id=OuterRef('usuario__conta_id')))


def _texto_ativo(valor):
    return "Ativo" if valor else "Inativo"


def _data(valor):
    return valor.strftime("%d/%m/%Y") if valor else "—"


def _mostrar_lista(request, titulo, subtitulo, pagina_ativa, cabecalhos, linhas, rota_novo, busca=None, total_cadastrados=None, pagina=None):
    if total_cadastrados is None:
        total_cadastrados = len(linhas)
    if busca is None:
        busca = request.GET.get('busca', '').strip()
        partes = busca.casefold().split()
        linhas = [linha for linha in linhas if all(
            parte in ' '.join(str(valor) for valor in linha['valores']).casefold()
            for parte in partes)]
    if pagina is None:
        pagina = Paginator(linhas, 10).get_page(request.GET.get('pagina'))
        linhas = pagina.object_list
    filtros = request.GET.copy()
    filtros.pop('pagina', None)
    return render(
        request,
        "aplicacao/comum/lista-padrao.html",
        {
            "titulo": titulo,
            "subtitulo": subtitulo,
            "pagina_ativa": pagina_ativa,
            "cabecalhos": cabecalhos,
            "linhas": linhas,
            "url_novo": reverse(rota_novo) if rota_novo else None,
            "busca_habilitada": busca is not None,
            "busca": busca or '',
            "total_cadastrados": total_cadastrados,
            "pagina": pagina,
            "filtros_paginacao": filtros.urlencode(),
        },
    )


@transaction.atomic
def _salvar(request, formulario_classe, titulo, pagina_ativa, rota_sucesso, instancia=None, acesso_aee=False):
    perfil = request.perfil_elo
    alunos_aee = None
    if acesso_aee and not perfil.gestor:
        alunos_aee = alunos_com_funcao(perfil, Professor.Funcao.AEE)
        if not alunos_aee.exists():
            raise PermissionDenied('Sem vínculo AEE ativo.')
        if instancia and (not pode_gerenciar_pedagogia(perfil, instancia.aluno_id) or
                          instancia.professor.usuario_id != perfil.pk):
            raise PermissionDenied('Este registro pertence a outro profissional ou aluno.')
        if request.method == 'POST' and (
            not alunos_aee.filter(pk=id_seguro(request.POST.get('aluno'))).exists() or
            str(request.POST.get('professor')) != str(perfil.professor_perfil.pk)
        ):
            raise PermissionDenied('Selecione somente seu aluno AEE e sua própria conta.')
    if instancia is not None and request.method == 'POST':
        instancia = get_object_or_404(type(instancia).objects.select_for_update(), pk=instancia.pk)
    formulario = formulario_classe(request.POST if request.method == 'POST' else None,
                                  request.FILES if request.method == 'POST' else None, instance=instancia)
    if alunos_aee is not None:
        formulario.fields['aluno'].queryset = alunos_aee
        formulario.fields['professor'].queryset = Professor.objects.filter(pk=perfil.professor_perfil.pk)
    if not instancia and request.method != 'POST':
        if 'professor' in formulario.fields:
            formulario.initial['professor'] = request.perfil_elo.professor_perfil.pk
        if 'data_inicio' in formulario.fields:
            formulario.initial['data_inicio'] = timezone.localdate()

    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            objeto = formulario.save()
            registrar('EDICAO' if instancia is not None else 'CRIACAO', request=request,
                      objeto=objeto, detalhes=detalhes_formulario(formulario))
            if getattr(formulario, 'conteudo_criado', None):
                registrar('CRIACAO', request=request, objeto=formulario.conteudo_criado,
                          detalhes=f'Conteúdo curricular criado: {formulario.conteudo_criado.nome}.')
        messages.success(request, "Registro salvo com sucesso.")
        if isinstance(objeto, Aluno) and instancia is not None and 'ativo' in formulario.changed_data and not objeto.ativo:
            messages.info(request, "Aluno inativado. O PDF de relatórios e documentos está disponível abaixo do cadastro.")
            return redirect('aluno-editar', pk=objeto.pk)
        return redirect(rota_sucesso)

    return render(
        request,
        "aplicacao/comum/formulario-padrao.html",
        {
            "formulario": formulario,
            "titulo": titulo,
            "pagina_ativa": pagina_ativa,
            "url_voltar": reverse(rota_sucesso),
            "arquivo_aluno": instancia if isinstance(instancia, Aluno) and not instancia.ativo else None,
        },
    )


def _excluir(request, modelo, pk, titulo, pagina_ativa, rota_sucesso, acesso_aee=False):
    objeto = get_object_or_404(modelo, pk=pk)
    perfil = request.perfil_elo
    if acesso_aee and not perfil.gestor and (
        not pode_gerenciar_pedagogia(perfil, objeto.aluno_id) or
        objeto.professor.usuario_id != perfil.pk
    ):
        raise PermissionDenied('Registro fora do seu vínculo AEE.')
    if modelo == Professor and objeto.usuario.gestor:
        raise PermissionDenied('O gestor não pode ser excluído por esta tela.')

    if request.method == "POST":
        try:
            with transaction.atomic():
                registrar('EXCLUSAO', request=request, objeto=objeto)
                objeto.delete()
            messages.success(request, "Registro excluído com sucesso.")
        except ProtectedError:
            messages.error(
                request, "Este registro possui outros dados vinculados e não pode ser excluído.")
        return redirect(rota_sucesso)

    return render(
        request,
        "aplicacao/comum/confirmar-exclusao.html",
        {
            "objeto": objeto,
            "titulo": titulo,
            "pagina_ativa": pagina_ativa,
            "url_voltar": reverse(rota_sucesso),
        },
    )


def _buscar_pessoas(modelo, termo):
    pessoas = modelo.objects.select_related('usuario')
    for parte in termo.split():
        pessoas = pessoas.filter(Q(nome__icontains=parte) | Q(sobrenome__icontains=parte))
    return pessoas
