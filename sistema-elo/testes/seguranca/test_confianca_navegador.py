from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from aplicacao.models import Configuracao2FA, DispositivoConfiavel2FA, Professor, Usuario
from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.servicos.duplo_fator import (COOKIE_CONFIAVEL, _digest, cifrar_segredo, codigo_totp,
                                            novo_segredo)


@override_settings(ELO_2FA_ATIVO=True)
class ConfiancaNavegadorFluxoReal(TestCase):
    """Fluxo completo com login por senha (sem force_login), como no site publicado."""

    senha = 'SenhaTeste@478'

    def setUp(self):
        self.conta = get_user_model().objects.create_user(username='prof.confia', password=self.senha)
        perfil = Usuario.objects.create(conta=self.conta, usuario='prof.confia', tipo_perfil='PROFESSOR',
                                        troca_senha_obrigatoria=False, documentos_aceitos_em=timezone.now(),
                                        versao_termos_aceita=VERSAO_TERMOS,
                                        versao_privacidade_ciente=VERSAO_PRIVACIDADE)
        Professor.objects.create(usuario=perfil, nome='Prof', sobrenome='Confia')
        self.segredo = novo_segredo()
        Configuracao2FA.objects.create(conta=self.conta, segredo_criptografado=cifrar_segredo(self.segredo),
                                       confirmada_em=timezone.now())

    def _entrar(self, cliente):
        resposta = cliente.post(reverse('login'), {'username': 'prof.confia', 'password': self.senha})
        self.assertEqual(resposta.status_code, 302)

    def _codigo(self):
        return codigo_totp(self.segredo, int(timezone.now().timestamp()) // 30)

    def test_navegador_confiavel_dispensa_codigo_no_proximo_login(self):
        cliente = Client()
        self._entrar(cliente)
        self.assertTrue(cliente.get(reverse('meus-dados'))['Location'].startswith(reverse('2fa-verificar')))
        resposta = cliente.post(reverse('2fa-verificar'), {'codigo': self._codigo(), 'confiar': 'sim'})
        self.assertIn(COOKIE_CONFIAVEL, resposta.cookies)
        cliente.post(reverse('logout'))

        self._entrar(cliente)
        self.assertEqual(cliente.get(reverse('meus-dados')).status_code, 200)

    def test_confianca_sobrevive_a_atualizacao_do_hash_da_senha(self):
        cliente = Client()
        self._entrar(cliente)
        cliente.post(reverse('2fa-verificar'), {'codigo': self._codigo(), 'confiar': 'sim'})
        cliente.post(reverse('logout'))

        # Simula um navegador confiado quando o hash tinha menos iterações (outra versão
        # do Django). No próximo login o Django regrava o hash da mesma senha.
        hash_antigo = PBKDF2PasswordHasher().encode(self.senha, 'saltantigo1234567890ab', iterations=500)
        get_user_model().objects.filter(pk=self.conta.pk).update(password=hash_antigo)
        DispositivoConfiavel2FA.objects.filter(conta=self.conta).update(
            assinatura_senha=_digest('senha-do-dispositivo', hash_antigo))

        self._entrar(cliente)
        self.assertNotEqual(get_user_model().objects.get(pk=self.conta.pk).password, hash_antigo)
        self.assertEqual(cliente.get(reverse('meus-dados')).status_code, 200)

    def test_troca_de_senha_pelo_titular_ainda_invalida_confianca(self):
        cliente = Client()
        self._entrar(cliente)
        cliente.post(reverse('2fa-verificar'), {'codigo': self._codigo(), 'confiar': 'sim'})
        cliente.post(reverse('logout'))

        self.senha = 'OutraSenha@9183'
        self.conta.set_password(self.senha)
        self.conta.save()
        self._entrar(cliente)
        self.assertTrue(cliente.get(reverse('meus-dados'))['Location'].startswith(reverse('2fa-verificar')))
