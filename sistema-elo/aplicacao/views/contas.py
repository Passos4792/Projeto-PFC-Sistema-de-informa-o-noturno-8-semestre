from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, ImageOps, UnidentifiedImageError
from io import BytesIO
from uuid import uuid4
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from aplicacao.servicos.acesso import alunos_com_funcao
from aplicacao.servicos.autorizacao_menores import acesso_menor_autorizado, menor_de_12, menores_pendentes, alunos_menores_vinculados
from aplicacao.servicos.auditoria import registrar
from aplicacao.servicos.documentos_legais import DATA_VIGENCIA, documentos_aceitos, VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.servicos.duplo_fator import obter_configuracao, redefinir_segundo_fator
from aplicacao.forms import AceiteDocumentos, CadastroUsuario, RedefinicaoSenha, TrocaSenhaInicial
from aplicacao.models import Professor, Usuario, AutorizacaoAcessoMenor


@sensitive_post_parameters('old_password', 'new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def trocar_senha(request):
    perfil = getattr(request, 'perfil_elo', None)
    if request.user.is_superuser and (perfil is None or not perfil.troca_senha_obrigatoria):
        return redirect('admin-trocar-senha')
    obrigatoria = perfil.troca_senha_obrigatoria
    formulario = TrocaSenhaInicial(request.user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            conta = formulario.save()
            perfil.troca_senha_obrigatoria = False
            perfil.save(update_fields=['troca_senha_obrigatoria', 'atualizado_em'])
            registrar('SENHA', request=request, objeto=perfil,
                      detalhes='Senha inicial alterada pelo usuário.' if obrigatoria
                      else 'Senha alterada pelo próprio usuário.')
        update_session_auth_hash(request, conta)
        if not obrigatoria:
            messages.success(request, 'Senha alterada com sucesso.')
        return redirect('inicio' if obrigatoria else 'meus-dados')
    return render(request, 'aplicacao/contas/trocar-senha.html', {'formulario': formulario, 'obrigatoria': obrigatoria})


@sensitive_post_parameters('new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def redefinir_senha(request, pk):
    operador = request.perfil_elo
    if operador.tipo_perfil != Usuario.TipoPerfil.PROFESSOR:
        raise PermissionDenied
    tipos_permitidos = [Usuario.TipoPerfil.ALUNO, Usuario.TipoPerfil.RESPONSAVEL]
    if operador.gestor:
        tipos_permitidos.append(Usuario.TipoPerfil.PROFESSOR)
    perfil = get_object_or_404(
        Usuario.objects.select_related('conta'), pk=pk,
        tipo_perfil__in=tipos_permitidos, gestor=False,
        conta__isnull=False, conta__is_superuser=False,
    )
    pessoa = getattr(perfil, {'ALUNO': 'aluno_perfil', 'RESPONSAVEL': 'responsavel_perfil',
                              'PROFESSOR': 'professor_perfil'}[perfil.tipo_perfil])
    if not operador.gestor:
        if perfil.tipo_perfil != 'ALUNO' or not alunos_com_funcao(operador, Professor.Funcao.AEE).filter(pk=pessoa.pk).exists():
            raise PermissionDenied('Somente alunos sob sua função AEE podem ter acesso redefinido.')
    pagina_ativa = {'ALUNO': 'alunos', 'RESPONSAVEL': 'responsaveis', 'PROFESSOR': 'professores'}[perfil.tipo_perfil]
    rota = {'ALUNO': 'aluno-listar', 'RESPONSAVEL': 'responsavel-listar', 'PROFESSOR': 'professor-listar'}[perfil.tipo_perfil]
    formulario = RedefinicaoSenha(perfil.conta, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and formulario.is_valid():
        with transaction.atomic():
            formulario.save()
            perfil.troca_senha_obrigatoria = True
            perfil.save(update_fields=['troca_senha_obrigatoria', 'atualizado_em'])
            registrar('SENHA', request=request, objeto=perfil,
                      detalhes='Senha temporária redefinida pelo professor; troca obrigatória no próximo acesso.')
        messages.success(request, f'Senha temporária de {pessoa.nome_completo} redefinida. O usuário deverá trocá-la no próximo acesso.')
        return redirect(rota)
    return render(request, 'aplicacao/contas/redefinir-senha.html', {
        'formulario': formulario, 'pessoa': pessoa, 'perfil_alvo': perfil,
        'rota_voltar': rota, 'pagina_ativa': pagina_ativa,
    })


@require_http_methods(['GET', 'POST'])
def redefinir_segundo_fator_usuario(request, pk):
    operador = request.perfil_elo
    if operador.tipo_perfil != Usuario.TipoPerfil.PROFESSOR or not operador.gestor:
        raise PermissionDenied('Somente o gestor pode redefinir a autenticação em duas etapas.')
    perfil = get_object_or_404(
        Usuario.objects.select_related('conta'), pk=pk,
        tipo_perfil__in=[Usuario.TipoPerfil.PROFESSOR, Usuario.TipoPerfil.RESPONSAVEL],
        gestor=False, conta__isnull=False, conta__is_superuser=False,
    )
    pessoa = getattr(perfil, {'RESPONSAVEL': 'responsavel_perfil', 'PROFESSOR': 'professor_perfil'}[perfil.tipo_perfil])
    rota = {'RESPONSAVEL': 'responsavel-listar', 'PROFESSOR': 'professor-listar'}[perfil.tipo_perfil]
    pagina_ativa = {'RESPONSAVEL': 'responsaveis', 'PROFESSOR': 'professores'}[perfil.tipo_perfil]
    configurado = obter_configuracao(perfil.conta) is not None
    if request.method == 'POST':
        if not configurado:
            messages.info(request, f'{pessoa.nome_completo} ainda não configurou a autenticação em duas etapas.')
            return redirect(rota)
        redefinir_segundo_fator(perfil.conta)
        registrar('PERMISSAO', request=request, objeto=perfil,
                  detalhes='Autenticação em duas etapas redefinida pelo gestor; novo Authenticator '
                           'obrigatório no próximo acesso e sessões abertas encerradas.')
        messages.success(request, f'Autenticação em duas etapas de {pessoa.nome_completo} redefinida. '
                                  'No próximo acesso, o usuário deverá configurar um novo Authenticator.')
        return redirect(rota)
    return render(request, 'aplicacao/contas/redefinir-2fa.html', {
        'pessoa': pessoa, 'perfil_alvo': perfil, 'configurado': configurado,
        'rota_voltar': rota, 'pagina_ativa': pagina_ativa,
    })


def aceitar_termos(request):
    perfil = request.perfil_elo
    proximo = request.POST.get('next') or request.GET.get('next') or ''

    if perfil.tipo_perfil == 'ALUNO' and menor_de_12(perfil.aluno_perfil.data_nascimento):
        return redirect('inicio')  # middleware direciona para a espera se estiver bloqueado
    if documentos_aceitos(perfil):
        return redirect('inicio')

    formulario = AceiteDocumentos(request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        perfil.documentos_aceitos_em = timezone.now()
        perfil.versao_termos_aceita = VERSAO_TERMOS
        perfil.versao_privacidade_ciente = VERSAO_PRIVACIDADE
        perfil.save(update_fields=[
            'documentos_aceitos_em',
            'versao_termos_aceita',
            'versao_privacidade_ciente',
            'atualizado_em',
        ])

        registrar(
            'DOCUMENTOS',
            request=request,
            objeto=perfil,
            detalhes=f'Termos v{VERSAO_TERMOS}; Política v{VERSAO_PRIVACIDADE}',
        )

        # O aceite geral do responsável não gera autorização automática.
        # É necessária manifestação específica para cada criança vinculada.
        if perfil.tipo_perfil == 'RESPONSAVEL' and menores_pendentes(perfil):
            return redirect('autorizar-acesso-menor')

        if proximo and url_has_allowed_host_and_scheme(
            proximo, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(proximo)
        return redirect('inicio')

    return render(request, 'aplicacao/contas/aceitar-termos.html', {
        'documento': 'privacidade' if request.GET.get('documento') == 'privacidade' else 'termos',
        'formulario': formulario,
        'versao_termos': VERSAO_TERMOS,
        'versao_privacidade': VERSAO_PRIVACIDADE,
        'data_vigencia': DATA_VIGENCIA,
        'next': proximo,
    })


@require_GET
def aguardando_autorizacao(request):
    """Tela informativa para a criança sem acesso: nunca recebe formulário de aceite."""
    perfil = request.perfil_elo
    if perfil.tipo_perfil != 'ALUNO' or not menor_de_12(perfil.aluno_perfil.data_nascimento):
        return redirect('inicio')
    if acesso_menor_autorizado(perfil.aluno_perfil):
        return redirect('inicio')
    return render(request, 'aplicacao/contas/aguardando-autorizacao.html')


@require_http_methods(['GET', 'POST'])
def autorizar_acesso_menor(request):
    """Autorização individual, destacada e auditável para cada criança vinculada."""
    perfil = request.perfil_elo
    if perfil.tipo_perfil != 'RESPONSAVEL' or not documentos_aceitos(perfil):
        raise PermissionDenied('A autorização exige acesso de responsável e aceite vigente dos termos.')
    pendentes = menores_pendentes(perfil)
    vinculados = alunos_menores_vinculados(perfil)

    if request.method == 'POST':
        # Só aceitamos IDs de crianças atualmente vinculadas ao usuário autenticado.
        identificador = request.POST.get('aluno_id', '')
        acao = request.POST.get('acao', 'autorizar')
        if acao == 'revogar':
            aluno = next((item for item in vinculados if str(item.pk) == identificador), None)
            if aluno is None:
                messages.error(request, 'Criança não vinculada à sua conta.')
            else:
                with transaction.atomic():
                    eliminados, _ = AutorizacaoAcessoMenor.objects.filter(
                        aluno=aluno, responsavel=perfil.responsavel_perfil,
                    ).delete()
                    if eliminados:
                        registrar('DOCUMENTOS', request=request, entidade='Autorização de acesso de menor',
                                  objeto_id=str(aluno.pk), detalhes='Autorização específica revogada pelo responsável.')
                messages.success(request, f'Sua autorização de acesso de {aluno.nome_completo} foi revogada.')
                return redirect('autorizar-acesso-menor')
        elif acao == 'autorizar':
            aluno = next((item for item in pendentes if str(item.pk) == identificador), None)
            if aluno is None or request.POST.get('autorizo') != 'on':
                messages.error(request, 'Selecione uma criança vinculada e confirme expressamente a autorização.')
            else:
                with transaction.atomic():
                    autorizacao, _ = AutorizacaoAcessoMenor.objects.update_or_create(
                        aluno=aluno,
                        responsavel=perfil.responsavel_perfil,
                        defaults={
                            'versao_termos': VERSAO_TERMOS,
                            'versao_privacidade': VERSAO_PRIVACIDADE,
                            'autorizado_em': timezone.now(),
                        },
                    )
                    registrar('DOCUMENTOS', request=request, objeto=autorizacao,
                              detalhes=(f'Autorização específica de acesso: aluno #{aluno.pk}; '
                                        f'Termos v{VERSAO_TERMOS}; Política v{VERSAO_PRIVACIDADE}.'))
                messages.success(request, f'Acesso de {aluno.nome_completo} autorizado com sucesso.')
                return redirect('autorizar-acesso-menor')
        else:
            messages.error(request, 'Operação inválida.')

    ids_autorizados = set(AutorizacaoAcessoMenor.objects.filter(
        responsavel=perfil.responsavel_perfil,
        versao_termos=VERSAO_TERMOS,
        versao_privacidade=VERSAO_PRIVACIDADE,
        autorizado_em__gte=perfil.documentos_aceitos_em,
    ).values_list('aluno_id', flat=True))
    autorizados = [aluno for aluno in vinculados if aluno.pk in ids_autorizados]
    return render(request, 'aplicacao/contas/autorizar-acesso-menor.html', {
        'pendentes': pendentes,
        'autorizados': autorizados,
        'versao_termos': VERSAO_TERMOS,
        'versao_privacidade': VERSAO_PRIVACIDADE,
    })


def cadastrar(request):
    form = CadastroUsuario(request.POST or None, operador=request.perfil_elo)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            conta = form.save()
            registrar('CRIACAO', request=request, objeto=conta.perfil_elo)
            registrar('PERMISSAO', request=request, objeto=conta.perfil_elo,
                      detalhes='Perfil definido: ' + conta.perfil_elo.get_tipo_perfil_display())
        messages.success(request, 'Usuário criado com o nível de acesso selecionado.')
        return redirect('usuario-criar')
    return render(request, 'aplicacao/comum/formulario-padrao.html', {
        'formulario': form, 'titulo': 'Cadastrar usuário', 'pagina_ativa': 'usuarios', 'url_voltar': '/'})


def inicio(request):
    return redirect('pagina-inicial')


@require_GET
@never_cache
def meus_dados(request):
    from aplicacao.servicos import google_calendar as google
    from aplicacao.servicos.privacidade_contas import perfil_pode_encerrar_proprio
    perfil = request.perfil_elo
    # Acesso permanente à tela de autorização, para o responsável poder
    # revogar ou conceder novamente depois que o aviso da página inicial some.
    menores_vinculados = (alunos_menores_vinculados(perfil)
                          if perfil.tipo_perfil == 'RESPONSAVEL' and documentos_aceitos(perfil) else [])
    return render(request, 'aplicacao/contas/meus-dados.html', {
        'pagina_ativa': 'meus-dados',
        'pode_gerenciar_privacidade': perfil_pode_encerrar_proprio(perfil),
        'menores_vinculados': menores_vinculados,
        'google_configurado': google.configurado(),
    })


@require_GET
@never_cache
def foto_perfil(request):
    foto = request.perfil_elo.foto_perfil
    if not foto:
        raise Http404
    try:
        arquivo = foto.open('rb')
    except (OSError, ValueError):
        raise Http404 from None
    extensao = str(foto.name).lower().rsplit('.', 1)[-1]
    resposta = FileResponse(arquivo, content_type='image/png' if extensao == 'png' else 'image/jpeg')
    resposta['X-Content-Type-Options'] = 'nosniff'
    resposta['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return resposta


@require_POST
@never_cache
def alterar_foto_perfil(request):
    arquivo = request.FILES.get('foto')
    if not arquivo or arquivo.size > 2 * 1024 * 1024:
        messages.error(request, 'Escolha uma foto JPG ou PNG de até 2 MB.')
        return redirect('meus-dados')
    if not arquivo.name.lower().endswith(('.png', '.jpg', '.jpeg')):
        messages.error(request, 'Apenas arquivos JPG, JPEG ou PNG são permitidos.')
        return redirect('meus-dados')
    try:
        with Image.open(arquivo) as origem:
            if origem.format not in ('JPEG', 'PNG'):
                raise ValueError
            if origem.width > 6000 or origem.height > 6000:
                raise ValueError
            imagem = ImageOps.exif_transpose(origem)
            imagem.thumbnail((512, 512))
            if imagem.mode not in ('RGB', 'RGBA'):
                imagem = imagem.convert('RGBA' if imagem.info.get('transparency') is not None else 'RGB')
            formato = 'PNG' if origem.format == 'PNG' else 'JPEG'
            if formato == 'JPEG' and imagem.mode != 'RGB':
                imagem = imagem.convert('RGB')
            destino = BytesIO()
            imagem.save(destino, format=formato, optimize=True)
            dados = destino.getvalue()
        if len(dados) > 2 * 1024 * 1024:
            raise ValueError
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        messages.error(request, 'Não foi possível validar a imagem. Envie um JPG ou PNG válido.')
        return redirect('meus-dados')
    extensao = 'png' if formato == 'PNG' else 'jpg'
    perfil = request.perfil_elo
    antigo = perfil.foto_perfil.name
    perfil.foto_perfil.save(f'{uuid4().hex}.{extensao}', ContentFile(dados), save=False)
    perfil.save(update_fields=['foto_perfil', 'atualizado_em'])
    if antigo:
        transaction.on_commit(lambda: perfil.foto_perfil.storage.delete(antigo))
    registrar('EDICAO', request=request, objeto=perfil, detalhes='Foto de perfil atualizada.')
    messages.success(request, 'Foto de perfil atualizada.')
    return redirect('meus-dados')


@require_POST
@never_cache
def remover_foto_perfil(request):
    perfil = request.perfil_elo
    antigo = perfil.foto_perfil.name
    if antigo:
        armazenamento = perfil.foto_perfil.storage
        perfil.foto_perfil = ''
        perfil.save(update_fields=['foto_perfil', 'atualizado_em'])
        transaction.on_commit(lambda: armazenamento.delete(antigo))
        registrar('EDICAO', request=request, objeto=perfil, detalhes='Foto de perfil removida.')
    messages.success(request, 'A foto foi removida. Suas iniciais serão exibidas.')
    return redirect('meus-dados')

# As rotas permanecem agrupadas em `contas` para não alterar a organização de URLs.
from aplicacao.views.privacidade import (
    privacidade_conta, privacidade_gerenciar, privacidade_revogar, privacidade_excluir_menor, privacidade_excluir_minha,
    privacidade_exportar_menor, privacidade_exportar_minha,
)
