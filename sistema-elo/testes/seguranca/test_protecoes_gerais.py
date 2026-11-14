from datetime import timedelta
from io import StringIO
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings, RequestFactory
from django.urls import reverse
from django.utils import timezone
from aplicacao import urls
from aplicacao.servicos import acesso
from aplicacao.servicos.limite_login import ip_cliente
from aplicacao.models import (Aluno, DocumentoPedagogico, LimiteLogin, RegistroAuditoria, SolicitacaoConclusao, Usuario,
                              Vinculo)
from testes.base import CenarioTestCase, pessoa, SENHA


PDF = b'%PDF-1.4 conteudo de teste'


class AcessoAposVinculoTests(CenarioTestCase):
    def test_professor_sem_vinculo_nao_ve_detalhe_nem_resposta_do_aluno(self):
        atividade = self.atividade(tipo_entrega='ENVIO')
        SolicitacaoConclusao.objects.create(atividade=atividade, aluno=self.aluno,
                                            resposta_aluno='resposta privada do aluno')
        Vinculo.objects.filter(pk=self.vinculo.pk).update(ativo=False)
        resposta = self.cliente(self.professor).get(reverse('atividade-detalhe', args=[atividade.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.assertNotContains(resposta, 'resposta privada do aluno', status_code=403)

    def test_professor_com_vinculo_continua_vendo_detalhe(self):
        atividade = self.atividade()
        resposta = self.cliente(self.professor).get(reverse('atividade-detalhe', args=[atividade.pk]))
        self.assertEqual(resposta.status_code, 200)


    def test_todas_as_rotas_estao_classificadas_no_controle_de_acesso(self):
        classificadas = set().union(*(valor for nome, valor in vars(acesso).items() if nome.startswith('ROTAS_')))
        classificadas |= {'inicio', 'logout', 'trocar-senha', 'aceitar-termos', 'aluno-inicio'}
        faltando = [rota.name for rota in urls.urlpatterns
                    if rota.name and not rota.name.startswith('api-') and rota.name not in classificadas]
        self.assertEqual(faltando, [])
        from configuracao import urls as urls_projeto
        existentes = {rota.name for rota in urls.urlpatterns} | {
            rota.name for rota in urls_projeto.urlpatterns if getattr(rota, 'name', None)}
        self.assertEqual(sorted(classificadas - existentes), [])


class ExclusaoDeContasTests(CenarioTestCase):
    def test_excluir_aluno_remove_tambem_a_conta_de_login(self):
        novo = pessoa('zeca')
        conta_id = novo.usuario.conta_id
        resposta = self.cliente(self.gestor).post(reverse('aluno-excluir', args=[novo.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Aluno.objects.filter(pk=novo.pk).exists())
        self.assertFalse(Usuario.objects.filter(usuario='zeca').exists())
        self.assertFalse(get_user_model().objects.filter(pk=conta_id).exists())

    def test_excluir_aluno_sem_login_continua_funcionando(self):
        perfil = Usuario.objects.create(usuario='sem.login', tipo_perfil='ALUNO')
        aluno = Aluno.objects.create(usuario=perfil, nome='Sem', sobrenome='Login')
        self.cliente(self.gestor).post(reverse('aluno-excluir', args=[aluno.pk]))
        self.assertFalse(Usuario.objects.filter(pk=perfil.pk).exists())


class ParametrosInvalidosTests(CenarioTestCase):
    def test_aluno_nao_numerico_ao_criar_meta_nao_gera_erro_500(self):
        resposta = self.cliente(self.professor).post(
            reverse('meta-criar'), {'aluno': 'abc', 'professor': self.professor.pk})
        self.assertEqual(resposta.status_code, 403)

    def test_vinculo_familiar_nao_numerico_retorna_404(self):
        resposta = self.cliente(self.gestor).post(
            reverse('vinculo-listar'), {'acao': 'alternar_familiar', 'vinculo_id': 'abc'})
        self.assertEqual(resposta.status_code, 404)

    def test_identificador_gigante_nao_gera_erro_500(self):
        cliente = self.cliente(self.gestor)
        for rota in ('atividade-listar', 'atividade-historico', 'documentos-lista'):
            with self.subTest(rota=rota):
                resposta = cliente.get(reverse(rota), {'aluno': '9' * 30})
                self.assertIn(resposta.status_code, (200, 404))

    def test_id_seguro(self):
        self.assertEqual(acesso.id_seguro('15'), 15)
        for valor in ('abc', '', None, '9' * 30, '-1', '１２'):
            self.assertEqual(acesso.id_seguro(valor), 0)


class SessaoECabecalhosTests(CenarioTestCase):
    def test_sessao_expira_ao_fechar_e_em_oito_horas(self):
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 8 * 60 * 60)

    def test_paginas_recebem_politica_de_conteudo(self):
        resposta = self.cliente(self.gestor).get(reverse('pagina-inicial'))
        politica = resposta.headers['Content-Security-Policy']
        self.assertIn("script-src 'self'", politica)
        self.assertIn("frame-ancestors 'none'", politica)

    def test_templates_nao_usam_scripts_embutidos(self):
        pasta = settings.BASE_DIR / 'templates'
        for arquivo in pasta.rglob('*.html'):
            texto = arquivo.read_text(encoding='utf-8')
            with self.subTest(arquivo=arquivo.name):
                for atributo in ('onclick=', 'onchange=', 'onsubmit=', '<script>'):
                    self.assertNotIn(atributo, texto)

    def test_api_tem_limite_de_requisicoes(self):
        self.assertIn('rest_framework.throttling.UserRateThrottle',
                      settings.REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'])


class TrocaVoluntariaDeSenhaTests(CenarioTestCase):
    NOVA = 'Outra-senha-pessoal@7731'

    def test_usuario_troca_a_propria_senha_sem_obrigacao(self):
        cliente = self.cliente(self.responsavel)
        self.assertEqual(cliente.get(reverse('trocar-senha')).status_code, 200)
        resposta = cliente.post(reverse('trocar-senha'), {
            'old_password': SENHA, 'new_password1': self.NOVA, 'new_password2': self.NOVA})
        self.assertRedirects(resposta, reverse('meus-dados'), fetch_redirect_response=False)
        conta = get_user_model().objects.get(pk=self.responsavel.usuario.conta_id)
        self.assertTrue(conta.check_password(self.NOVA))
        self.assertTrue(RegistroAuditoria.objects.filter(
            acao='SENHA', detalhes__contains='próprio usuário').exists())

    def test_senha_atual_errada_nao_altera(self):
        resposta = self.cliente(self.responsavel).post(reverse('trocar-senha'), {
            'old_password': 'errada', 'new_password1': self.NOVA, 'new_password2': self.NOVA})
        self.assertEqual(resposta.status_code, 200)
        conta = get_user_model().objects.get(pk=self.responsavel.usuario.conta_id)
        self.assertTrue(conta.check_password(SENHA))


@override_settings(LOGIN_MAX_FALHAS=3, LOGIN_MAX_FALHAS_USUARIO=6, LOGIN_MAX_FALHAS_IP=50,
                   LOGIN_BLOQUEIO_SEGUNDOS=60)
class BloqueioDeLoginTests(CenarioTestCase):
    def _falhar(self, ip, vezes):
        for _ in range(vezes):
            self.client.post(reverse('login'), {'username': 'ana', 'password': 'incorreta'}, REMOTE_ADDR=ip)

    def test_falhas_de_outro_ip_nao_bloqueiam_o_aluno(self):
        self._falhar('203.0.113.7', 3)
        self.client.post(reverse('login'), {'username': 'ana', 'password': SENHA}, REMOTE_ADDR='198.51.100.2')
        self.assertIn('_auth_user_id', self.client.session)

    def test_muitas_falhas_de_varios_ips_ainda_bloqueiam_a_conta(self):
        for indice in range(6):
            self._falhar(f'203.0.113.{indice}', 1)
        self.client.post(reverse('login'), {'username': 'ana', 'password': SENHA}, REMOTE_ADDR='198.51.100.2')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_ip_do_proxy_so_e_usado_quando_configurado(self):
        request = RequestFactory().get('/', REMOTE_ADDR='10.0.0.1',
                                       HTTP_X_FORWARDED_FOR='198.51.100.9, 203.0.113.4')
        self.assertEqual(ip_cliente(request), '10.0.0.1')
        with override_settings(CONFIAR_PROXY=True):
            self.assertEqual(ip_cliente(request), '203.0.113.4')


class RetirarDaFamiliaTests(CenarioTestCase):
    def setUp(self):
        self.documento = DocumentoPedagogico.objects.create(
            aluno=self.aluno, professor=self.professor, tipo='PEI', ano_letivo=2026,
            bimestre=1, campos={}, situacao='PUBLICADO')

    def test_gestor_retira_documento_publicado(self):
        url = reverse('documento-publicar', args=[self.documento.pk])
        resposta = self.cliente(self.gestor).post(url, {'acao': 'RETIRAR'})
        self.assertEqual(resposta.status_code, 302)
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.situacao, 'FINALIZADO')
        resposta = self.cliente(self.responsavel).get(reverse('documento-detalhe', args=[self.documento.pk]))
        self.assertEqual(resposta.status_code, 403)

    def test_outro_professor_nao_retira(self):
        url = reverse('documento-publicar', args=[self.documento.pk])
        resposta = self.cliente(self.professor).post(url, {'acao': 'RETIRAR'})
        self.assertEqual(resposta.status_code, 403)
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.situacao, 'PUBLICADO')


class BuscaDeAtividadesTests(CenarioTestCase):
    def test_termo_curto_nao_retorna_todas_as_atividades(self):
        self.atividade(titulo='Leitura')
        self.atividade(titulo='Operações')
        cliente = self.cliente(self.gestor)
        curto = cliente.get(reverse('atividade-listar'), {'busca': 'nd'})
        self.assertEqual(list(curto.context['pagina'].object_list), [])
        situacao = cliente.get(reverse('atividade-listar'), {'busca': 'pendente'})
        self.assertEqual(len(situacao.context['pagina'].object_list), 2)


class ArquivosEnviadosTests(CenarioTestCase):
    def test_excluir_atividade_apaga_o_material_do_disco(self):
        atividade = self.atividade(material_apoio=SimpleUploadedFile('apoio.pdf', PDF))
        caminho = atividade.material_apoio.path
        self.assertTrue(os.path.exists(caminho))
        with self.captureOnCommitCallbacks(execute=True):
            atividade.delete()
        self.assertFalse(os.path.exists(caminho))

    def test_trocar_material_apaga_o_arquivo_anterior(self):
        atividade = self.atividade(material_apoio=SimpleUploadedFile('apoio.pdf', PDF))
        antigo = atividade.material_apoio.path
        atividade.material_apoio = SimpleUploadedFile('novo.pdf', PDF)
        with self.captureOnCommitCallbacks(execute=True):
            atividade.save()
        self.assertFalse(os.path.exists(antigo))
        self.assertTrue(os.path.exists(atividade.material_apoio.path))

    def test_excluir_entrega_apaga_o_anexo(self):
        atividade = self.atividade(tipo_entrega='ENVIO')
        entrega = SolicitacaoConclusao.objects.create(
            atividade=atividade, aluno=self.aluno, anexo=SimpleUploadedFile('resposta.pdf', PDF))
        caminho = entrega.anexo.path
        with self.captureOnCommitCallbacks(execute=True):
            atividade.delete()
        self.assertFalse(os.path.exists(caminho))


class LimpezaDeRegistrosTests(CenarioTestCase):
    def test_remove_controles_de_login_vencidos_e_mantem_os_recentes(self):
        antigo = timezone.now() - timedelta(days=2)
        LimiteLogin.objects.create(chave='a' * 64, falhas=2, inicio=antigo)
        LimiteLogin.objects.create(chave='b' * 64, falhas=2, inicio=timezone.now())
        call_command('limpar_registros', stdout=StringIO())
        self.assertEqual(list(LimiteLogin.objects.values_list('chave', flat=True)), ['b' * 64])

    def test_auditoria_so_e_removida_quando_solicitado(self):
        registro = RegistroAuditoria.objects.create(autor='teste', acao='CONSULTA')
        RegistroAuditoria.objects.filter(pk=registro.pk).update(criado_em=timezone.now() - timedelta(days=400))
        call_command('limpar_registros', stdout=StringIO())
        self.assertTrue(RegistroAuditoria.objects.filter(pk=registro.pk).exists())
        call_command('limpar_registros', auditoria_dias=365, stdout=StringIO())
        self.assertFalse(RegistroAuditoria.objects.filter(pk=registro.pk).exists())

    def test_simular_nao_remove(self):
        LimiteLogin.objects.create(chave='c' * 64, falhas=1, inicio=timezone.now() - timedelta(days=2))
        call_command('limpar_registros', simular=True, stdout=StringIO())
        self.assertTrue(LimiteLogin.objects.filter(chave='c' * 64).exists())
