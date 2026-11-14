import base64
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.servicos.duplo_fator import (COOKIE_CONFIAVEL, cifrar_segredo, codigo_totp,
                                   obter_configuracao, novo_segredo)
from aplicacao.models import (Aluno, CodigoRecuperacao2FA, Configuracao2FA,
                              DispositivoConfiavel2FA, Professor, Responsavel, Usuario)


@override_settings(ELO_2FA_ATIVO=True)
class Autenticacao2FATestCase(TestCase):
    def setUp(self):
        usuario_modelo = get_user_model()
        self.professor_login = usuario_modelo.objects.create_user(username='profa', password='SenhaTeste@478')
        self.responsavel_login = usuario_modelo.objects.create_user(username='responsavel', password='SenhaTeste@478')
        self.aluno_login = usuario_modelo.objects.create_user(username='aluno', password='SenhaTeste@478')
        for login, tipo, modelo in [(self.professor_login, 'PROFESSOR', Professor),
                                    (self.responsavel_login, 'RESPONSAVEL', Responsavel),
                                    (self.aluno_login, 'ALUNO', Aluno)]:
            perfil = Usuario.objects.create(conta=login, usuario=login.username, tipo_perfil=tipo,
                troca_senha_obrigatoria=False, documentos_aceitos_em=timezone.now(),
                versao_termos_aceita=VERSAO_TERMOS, versao_privacidade_ciente=VERSAO_PRIVACIDADE)
            modelo.objects.create(usuario=perfil, nome='Pessoa', sobrenome='Teste',
                                  **({'data_nascimento': timezone.localdate() - timedelta(days=365*10)} if tipo == 'ALUNO' else {}))

    def _cliente(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente

    def _ativar(self, usuario):
        segredo = novo_segredo()
        configuracao = Configuracao2FA.objects.create(conta=usuario,
            segredo_criptografado=cifrar_segredo(segredo), confirmada_em=timezone.now())
        return segredo, configuracao

    def test_professor_e_responsavel_precisam_configurar_mas_aluno_nao(self):
        for usuario in (self.professor_login, self.responsavel_login):
            with self.subTest(usuario=usuario):
                cliente = self._cliente(usuario)
                resposta = cliente.get(reverse('meus-dados'))
                self.assertRedirects(resposta, reverse('2fa-configurar') + '?next=%2Fmeus-dados%2F',
                                     fetch_redirect_response=False)
        cliente = self._cliente(self.aluno_login)
        self.assertEqual(cliente.get(reverse('meus-dados')).status_code, 200)
        self.assertEqual(cliente.get(reverse('2fa-configurar')).status_code, 403)

    def test_qr_configuracao_e_primeiro_codigo(self):
        cliente = self._cliente(self.professor_login)
        resposta = cliente.get(reverse('2fa-configurar'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Microsoft Authenticator')
        self.assertContains(resposta, 'data:image/png;base64,')
        configuracao = obter_configuracao(self.professor_login)
        self.assertNotIn('secret=', configuracao.segredo_criptografado)
        from aplicacao.servicos.duplo_fator import decifrar_segredo
        codigo = codigo_totp(decifrar_segredo(configuracao.segredo_criptografado), int(timezone.now().timestamp())//30)
        resposta = cliente.post(reverse('2fa-configurar'), {'codigo': codigo, 'confiar': 'sim'})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Códigos de recuperação')
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=self.professor_login).count(), 8)
        self.assertIn(COOKIE_CONFIAVEL, resposta.cookies)
        self.assertEqual(cliente.get(reverse('meus-dados')).status_code, 200)

    def test_bloqueia_api_e_relatorio_sem_segundo_fator(self):
        cliente = self._cliente(self.professor_login)
        resposta = cliente.get(reverse('documentos-lista'))
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.url.startswith(reverse('2fa-configurar')))
        resposta_api = cliente.get(reverse('api-painel'))
        self.assertEqual(resposta_api.status_code, 403)
        self.assertIn('autenticação em duas etapas', resposta_api.json()['detail'])

    def test_login_em_outro_navegador_pede_codigo_e_confianca_funciona(self):
        segredo, config = self._ativar(self.responsavel_login)
        c1 = self._cliente(self.responsavel_login)
        self.assertEqual(c1.get(reverse('meus-dados')).status_code, 302)
        codigo = codigo_totp(segredo, int(timezone.now().timestamp())//30)
        resposta = c1.post(reverse('2fa-verificar'), {'codigo': codigo, 'confiar': 'sim'})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(c1.get(reverse('meus-dados')).status_code, 200)
        cookie = resposta.cookies[COOKIE_CONFIAVEL]
        c2 = self._cliente(self.responsavel_login)
        c2.cookies[COOKIE_CONFIAVEL] = cookie.value
        self.assertEqual(c2.get(reverse('meus-dados')).status_code, 200)
        c3 = self._cliente(self.responsavel_login)
        self.assertEqual(c3.get(reverse('meus-dados')).status_code, 302)
        self.assertTrue(c3.get(reverse('meus-dados'))['Location'].startswith(reverse('2fa-verificar')))

    def test_reset_senha_invalida_dispositivo(self):
        segredo, config = self._ativar(self.professor_login)
        c1 = self._cliente(self.professor_login)
        codigo = codigo_totp(segredo, int(timezone.now().timestamp())//30)
        resposta = c1.post(reverse('2fa-verificar'), {'codigo': codigo, 'confiar': 'sim'})
        token = resposta.cookies[COOKIE_CONFIAVEL].value
        self.professor_login.set_password('SenhaNova@479')
        self.professor_login.save()
        c2 = self._cliente(self.professor_login)
        c2.cookies[COOKIE_CONFIAVEL] = token
        self.assertTrue(c2.get(reverse('meus-dados'))['Location'].startswith(reverse('2fa-verificar')))

    def test_codigo_repetido_e_rejeitado(self):
        segredo, config = self._ativar(self.professor_login)
        from aplicacao.servicos.duplo_fator import validar_codigo
        codigo = codigo_totp(segredo, int(timezone.now().timestamp())//30)
        self.assertTrue(validar_codigo(self.professor_login, codigo))
        self.assertFalse(validar_codigo(self.professor_login, codigo))

    def test_restricao_superusuario_admin(self):
        admin = get_user_model().objects.create_superuser('admin_elo', password='SenhaTeste@478')
        cliente = self._cliente(admin)
        self.assertEqual(cliente.get('/admin/').status_code, 302)
        self.assertEqual(cliente.get('/seguranca/configurar/').status_code, 200)

    def test_revogacao_navegadores(self):
        segredo, config = self._ativar(self.responsavel_login)
        cliente = self._cliente(self.responsavel_login)
        codigo = codigo_totp(segredo, int(timezone.now().timestamp())//30)
        cliente.post(reverse('2fa-verificar'), {'codigo': codigo, 'confiar': 'sim'})
        self.assertEqual(DispositivoConfiavel2FA.objects.filter(conta=self.responsavel_login).count(), 1)
        self.assertEqual(cliente.post(reverse('2fa-revogar')).status_code, 302)
        self.assertFalse(DispositivoConfiavel2FA.objects.filter(conta=self.responsavel_login).exists())


class CodigoTotpRFC(TestCase):
    def test_vetor_rfc_6238_sha1(self):
        segredo = base64.b32encode(b'12345678901234567890').decode()
        self.assertEqual(codigo_totp(segredo, 59//30), '287082')


@override_settings(ELO_2FA_ATIVO=True)
class ProtecoesAdicionais2FA(TestCase):
    def setUp(self):
        self.professor = get_user_model().objects.create_user(username='prof-rec', password='Teste@4829')
        perfil = Usuario.objects.create(conta=self.professor, usuario='prof-rec', tipo_perfil='PROFESSOR',
            troca_senha_obrigatoria=False, documentos_aceitos_em=timezone.now(),
            versao_termos_aceita=VERSAO_TERMOS, versao_privacidade_ciente=VERSAO_PRIVACIDADE)
        Professor.objects.create(usuario=perfil, nome='Prof', sobrenome='Teste')
        self.segredo = novo_segredo()
        self.configuracao = Configuracao2FA.objects.create(
            conta=self.professor, segredo_criptografado=cifrar_segredo(self.segredo),
            confirmada_em=timezone.now())

    def test_codigo_de_recuperacao_e_consumido_e_nao_pode_ser_reutilizado(self):
        from aplicacao.servicos.duplo_fator import criar_codigos_recuperacao, validar_codigo
        recuperacao = criar_codigos_recuperacao(self.professor)
        self.assertEqual(len(recuperacao), 8)
        self.assertTrue(validar_codigo(self.professor, recuperacao[0]))
        self.assertFalse(validar_codigo(self.professor, recuperacao[0]))
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=self.professor).count(), 7)

    def test_cinco_falhas_bloqueiam_inclusive_um_codigo_valido(self):
        from aplicacao.servicos.duplo_fator import validar_codigo
        for _ in range(5):
            self.assertFalse(validar_codigo(self.professor, '00000x'))
        self.configuracao.refresh_from_db()
        self.assertGreater(self.configuracao.bloqueado_ate, timezone.now())
        valido = codigo_totp(self.segredo, int(timezone.now().timestamp()) // 30)
        self.assertFalse(validar_codigo(self.professor, valido))

    def test_cookie_invalido_nao_autoriza_acesso(self):
        cliente = Client()
        cliente.force_login(self.professor)
        cliente.cookies[COOKIE_CONFIAVEL] = 'cookie-inventado'
        self.assertTrue(cliente.get(reverse('meus-dados'))['Location'].startswith(reverse('2fa-verificar')))

    def test_superusuario_sem_perfil_consegue_gerenciar_2fa(self):
        admin = get_user_model().objects.create_superuser('admin_teste', password='Teste@4829')
        cliente = Client()
        cliente.force_login(admin)
        resposta = cliente.get(reverse('2fa-configurar'))
        self.assertEqual(resposta.status_code, 200)
        configuracao = obter_configuracao(admin)
        from aplicacao.servicos.duplo_fator import decifrar_segredo
        token = codigo_totp(decifrar_segredo(configuracao.segredo_criptografado),
                            int(timezone.now().timestamp()) // 30)
        resposta = cliente.post(reverse('2fa-configurar'), {'codigo': token})
        self.assertContains(resposta, '/admin/')
        self.assertEqual(cliente.get(reverse('2fa-seguranca')).status_code, 200)
        self.assertEqual(cliente.get('/admin/').status_code, 200)
