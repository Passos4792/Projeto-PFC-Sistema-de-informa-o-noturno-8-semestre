from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aplicacao.servicos.duplo_fator import (
    COOKIE_CONFIAVEL, SESSAO_VERIFICADA, _assinatura_senha, _digest,
    cifrar_segredo, codigo_totp, criar_codigos_recuperacao, novo_segredo,
)
from aplicacao.models import Configuracao2FA, DispositivoConfiavel2FA


@override_settings(ELO_2FA_ATIVO=True)
class SenhaAdminAuthenticatorTestes(TestCase):
    def setUp(self):
        self.senha_atual = 'SenhaAtual@479'
        self.senha_nova = 'SenhaNova@987'
        self.admin = get_user_model().objects.create_superuser(
            username='admin_troca_auth', password=self.senha_atual,
        )
        self.segredo = novo_segredo()
        self.config = Configuracao2FA.objects.create(
            conta=self.admin, segredo_criptografado=cifrar_segredo(self.segredo),
            confirmada_em=timezone.now(),
        )
        self.cliente = Client()
        self.cliente.force_login(self.admin)
        sessao = self.cliente.session
        sessao[SESSAO_VERIFICADA] = f'{self.admin.pk}:{self.config.versao}'
        sessao.save()

    def _codigo(self, instante=None):
        instante = instante or timezone.now()
        return codigo_totp(self.segredo, int(instante.timestamp()) // 30)

    def _dados(self, *, senha_atual=None, senha_nova=None, codigo=None):
        senha_nova = senha_nova or self.senha_nova
        return {'old_password': senha_atual or self.senha_atual,
                'new_password1': senha_nova, 'new_password2': senha_nova,
                'codigo': codigo if codigo is not None else self._codigo()}

    def test_administrador_acessa_pela_rota_do_elo_e_link_nativo_admin(self):
        for rota in (reverse('admin-trocar-senha'), reverse('admin:password_change')):
            with self.subTest(rota=rota):
                resposta = self.cliente.get(rota)
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, 'Alterar senha do administrador')
                self.assertContains(resposta, 'Código atual do Microsoft Authenticator')
        resposta = self.cliente.get(reverse('2fa-seguranca'))
        self.assertContains(resposta, reverse('admin-trocar-senha'))
        self.assertRedirects(self.cliente.get(reverse('trocar-senha')),
                             reverse('admin-trocar-senha'), fetch_redirect_response=False)

    def test_troca_valida_altera_senha_e_revoga_navegadores(self):
        token = 'token-de-um-navegador-confiavel'
        DispositivoConfiavel2FA.objects.create(
            conta=self.admin, token_hash=_digest('navegador', token),
            assinatura_senha=_assinatura_senha(self.admin),
            descricao='Navegador de testes',
            expira_em=timezone.now() + timedelta(days=30),
        )
        self.cliente.cookies[COOKIE_CONFIAVEL] = token
        resposta = self.cliente.post(reverse('admin:password_change'), self._dados())
        self.assertRedirects(resposta, reverse('admin:index'), fetch_redirect_response=False)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(self.senha_nova))
        self.assertFalse(self.admin.check_password(self.senha_atual))
        self.assertFalse(DispositivoConfiavel2FA.objects.filter(conta=self.admin).exists())
        self.assertIn(COOKIE_CONFIAVEL, resposta.cookies)
        self.assertEqual(resposta.cookies[COOKIE_CONFIAVEL].value, '')
        self.assertEqual(self.cliente.get(reverse('admin:index')).status_code, 200)

    def test_outro_atalho_nativo_de_troca_da_propria_senha_e_redirecionado(self):
        resposta = self.cliente.get(f'/admin/auth/user/{self.admin.pk}/password/')
        self.assertRedirects(resposta, reverse('admin-trocar-senha'),
                             fetch_redirect_response=False)

    def test_codigo_incorreto_nao_muda_senha(self):
        resposta = self.cliente.post(reverse('admin-trocar-senha'),
                                     self._dados(codigo='abcdef'))
        self.assertEqual(resposta.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(self.senha_atual))

    def test_senha_atual_incorreta_nao_consume_totp(self):
        codigo = self._codigo()
        resposta = self.cliente.post(reverse('admin-trocar-senha'),
                                     self._dados(senha_atual='OutraSenha@987', codigo=codigo))
        self.assertEqual(resposta.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(self.senha_atual))
        self.config.refresh_from_db()
        self.assertEqual(self.config.ultimo_intervalo, -1)

    def test_rejeita_codigo_ja_utilizado_e_codigo_de_recuperacao(self):
        from aplicacao.servicos.duplo_fator import validar_codigo
        codigo = self._codigo()
        self.assertTrue(validar_codigo(self.admin, codigo))
        resposta = self.cliente.post(reverse('admin-trocar-senha'), self._dados(codigo=codigo))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'já utilizado')
        recuperacao = criar_codigos_recuperacao(self.admin)[0]
        resposta = self.cliente.post(reverse('admin-trocar-senha'), self._dados(codigo=recuperacao))
        self.assertEqual(resposta.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(self.senha_atual))

    def test_exige_authenticator_configurado_e_sessao_verificada(self):
        sessao = self.cliente.session
        sessao.pop(SESSAO_VERIFICADA, None)
        sessao.save()
        resposta = self.cliente.get(reverse('admin-trocar-senha'))
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.url.startswith(reverse('2fa-verificar')))
        self.config.confirmada_em = None
        self.config.save(update_fields=['confirmada_em'])
        resposta = self.cliente.get(reverse('admin-trocar-senha'))
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.url.startswith(reverse('2fa-configurar')))

    def test_professor_ou_usuario_comum_nao_pode_acessar(self):
        for tipo in ('normal', 'staff'):
            with self.subTest(tipo=tipo):
                usuario = get_user_model().objects.create_user(
                    username=f'teste_{tipo}', password='SenhaTeste@123',
                    is_staff=tipo == 'staff',
                )
                cliente = Client()
                cliente.force_login(usuario)
                if usuario.is_staff:
                    config = Configuracao2FA.objects.create(
                        conta=usuario, segredo_criptografado=cifrar_segredo(novo_segredo()),
                        confirmada_em=timezone.now(),
                    )
                    sessao = cliente.session
                    sessao[SESSAO_VERIFICADA] = f'{usuario.pk}:{config.versao}'
                    sessao.save()
                resposta = cliente.get(reverse('admin-trocar-senha'))
                self.assertIn(resposta.status_code, (302, 403))
                if resposta.status_code == 302:
                    self.assertIn('/login/', resposta.url)
