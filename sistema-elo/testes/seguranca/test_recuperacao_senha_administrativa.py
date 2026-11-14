from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from aplicacao.servicos.duplo_fator import (
    COOKIE_CONFIAVEL, _digest, _assinatura_senha,
    codigo_totp, novo_segredo, cifrar_segredo, criar_codigos_recuperacao,
)
from aplicacao.models import Configuracao2FA, CodigoRecuperacao2FA, DispositivoConfiavel2FA


@override_settings(ELO_2FA_ATIVO=True)
class RecuperarSenhaAdminTestes(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            username='admin_recuperar', password='SenhaAnterior@785'
        )
        self.segredo = novo_segredo()
        self.config = Configuracao2FA.objects.create(
            conta=self.usuario, segredo_criptografado=cifrar_segredo(self.segredo),
            confirmada_em=timezone.now()
        )
        self.reserva = criar_codigos_recuperacao(self.usuario)[0]
        self.url = reverse('admin-recuperar-senha')
        self.cliente = Client()

    def dados(self, *, usuario='admin_recuperar', codigo=None, reserva=None, senha='SenhaNova@879'):
        return {
            'usuario': usuario,
            'codigo': codigo if codigo is not None else codigo_totp(
                self.segredo, int(timezone.now().timestamp()) // 30),
            'codigo_recuperacao': reserva if reserva is not None else self.reserva,
            'new_password1': senha, 'new_password2': senha,
        }

    def test_link_publico_sem_email(self):
        self.assertEqual(self.cliente.get(self.url).status_code, 200)
        self.assertContains(self.cliente.get(reverse('login')), reverse('recuperar-senha'))
        self.assertContains(self.cliente.get(reverse('recuperar-senha')), self.url)
        self.assertContains(self.cliente.get(self.url), 'Microsoft Authenticator')

    def test_redefine_sem_senha_atual_e_revoga_confianca(self):
        token = 'token-confiavel-antes-da-recuperacao'
        DispositivoConfiavel2FA.objects.create(
            conta=self.usuario, token_hash=_digest('navegador', token),
            assinatura_senha=_assinatura_senha(self.usuario),
            descricao='Navegador de teste',
            expira_em=timezone.now() + timedelta(days=30))
        versao = self.config.versao
        self.cliente.cookies[COOKIE_CONFIAVEL] = token
        resposta = self.cliente.post(self.url, self.dados())
        self.assertRedirects(resposta, reverse('login'), fetch_redirect_response=False)
        self.usuario.refresh_from_db()
        self.config.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaNova@879'))
        self.assertFalse(self.usuario.check_password('SenhaAnterior@785'))
        self.assertNotEqual(self.config.versao, versao)
        self.assertFalse(DispositivoConfiavel2FA.objects.filter(conta=self.usuario).exists())
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=self.usuario).count(), 7)
        self.assertEqual(resposta.cookies[COOKIE_CONFIAVEL].value, '')

    def test_nao_aceita_apenas_totp_sem_reserva(self):
        resposta = self.cliente.post(self.url, self.dados(reserva='A' * 20))
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAnterior@785'))
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=self.usuario).count(), 8)

    def test_nao_aceita_reserva_com_totp_errado(self):
        resposta = self.cliente.post(self.url, self.dados(codigo='000000'))
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAnterior@785'))
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=self.usuario).count(), 8)

    def test_nao_reutiliza_reserva_nem_totp(self):
        self.assertEqual(self.cliente.post(self.url, self.dados()).status_code, 302)
        resposta = self.cliente.post(self.url, self.dados(senha='SenhaOutra@879'))
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaNova@879'))

    def test_nao_aceita_outro_usuario(self):
        normal = get_user_model().objects.create_user(
            username='normal_recuperar', password='SenhaAnterior@785')
        resposta = self.cliente.post(self.url, self.dados(usuario=normal.username))
        self.assertEqual(resposta.status_code, 200)
        normal.refresh_from_db()
        self.assertTrue(normal.check_password('SenhaAnterior@785'))

    def test_nao_aceita_admin_sem_2fa(self):
        self.config.confirmada_em = None
        self.config.save(update_fields=['confirmada_em'])
        resposta = self.cliente.post(self.url, self.dados())
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAnterior@785'))

    def test_nova_senha_igual_a_antiga_e_ignorada(self):
        resposta = self.cliente.post(self.url, self.dados(senha='SenhaAnterior@785'))
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAnterior@785'))
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=self.usuario).count(), 8)

    def test_5_tentativas_erradas_bloqueiam_temp_e_nao_consumem_reserva(self):
        for _ in range(5):
            resposta = self.cliente.post(self.url, self.dados(reserva='B' * 20))
            self.assertEqual(resposta.status_code, 200)
        resposta = self.cliente.post(self.url, self.dados())
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAnterior@785'))
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=self.usuario).count(), 8)


@override_settings(ELO_2FA_ATIVO=True)
class RecuperarSenhaGestorTestes(TestCase):
    def criar(self, login, gestor):
        from aplicacao.models import Professor, Usuario
        conta = get_user_model().objects.create_user(username=login, password='SenhaAnterior@785')
        perfil = Usuario.objects.create(conta=conta, usuario=login, tipo_perfil='PROFESSOR', gestor=gestor,
                                        troca_senha_obrigatoria=False)
        Professor.objects.create(usuario=perfil, nome='Pessoa', sobrenome=login)
        segredo = novo_segredo()
        Configuracao2FA.objects.create(conta=conta, segredo_criptografado=cifrar_segredo(segredo),
                                       confirmada_em=timezone.now())
        return conta, segredo, criar_codigos_recuperacao(conta)[0]

    def enviar(self, login, segredo, reserva):
        return Client().post(reverse('admin-recuperar-senha'), {
            'usuario': login, 'codigo': codigo_totp(segredo, int(timezone.now().timestamp()) // 30),
            'codigo_recuperacao': reserva, 'new_password1': 'SenhaNova@879', 'new_password2': 'SenhaNova@879'})

    def test_gestor_recupera_senha(self):
        conta, segredo, reserva = self.criar('gestor.elo', gestor=True)
        resposta = self.enviar('gestor.elo', segredo, reserva)
        self.assertRedirects(resposta, reverse('login'), fetch_redirect_response=False)
        conta.refresh_from_db()
        self.assertTrue(conta.check_password('SenhaNova@879'))
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=conta).count(), 7)

    def test_professor_comum_nao_usa_recuperacao_administrativa(self):
        conta, segredo, reserva = self.criar('prof.comum', gestor=False)
        resposta = self.enviar('prof.comum', segredo, reserva)
        self.assertEqual(resposta.status_code, 200)
        conta.refresh_from_db()
        self.assertTrue(conta.check_password('SenhaAnterior@785'))
        self.assertEqual(CodigoRecuperacao2FA.objects.filter(conta=conta).count(), 8)
