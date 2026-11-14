from datetime import timedelta

from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from aplicacao.servicos.duplo_fator import cifrar_segredo, criar_codigos_recuperacao, novo_segredo
from aplicacao.models import (CodigoRecuperacao2FA, Configuracao2FA, DispositivoConfiavel2FA,
                              RegistroAuditoria)
from testes.base import SENHA, CenarioTestCase


class RedefinirSegundoFatorTests(CenarioTestCase):
    def ativar_2fa(self, pessoa):
        conta = pessoa.usuario.conta
        Configuracao2FA.objects.create(conta=conta, segredo_criptografado=cifrar_segredo(novo_segredo()),
                                       confirmada_em=timezone.now())
        criar_codigos_recuperacao(conta)
        DispositivoConfiavel2FA.objects.create(conta=conta, token_hash=f'{conta.pk:064d}', assinatura_senha='y' * 64,
                                               expira_em=timezone.now() + timedelta(days=30))
        return conta

    def url(self, pessoa):
        return reverse('usuario-redefinir-2fa', args=[pessoa.usuario_id])

    def test_gestor_redefine_2fa_de_professor_e_responsavel(self):
        for pessoa, rota in ((self.professor, 'professor-listar'), (self.responsavel, 'responsavel-listar')):
            with self.subTest(perfil=pessoa.usuario.tipo_perfil):
                conta = self.ativar_2fa(pessoa)
                cliente = self.cliente(self.gestor)
                self.assertContains(cliente.get(self.url(pessoa)), 'Redefinir autenticação em duas etapas')
                resposta = cliente.post(self.url(pessoa))
                self.assertRedirects(resposta, reverse(rota), fetch_redirect_response=False)
                self.assertFalse(Configuracao2FA.objects.filter(conta=conta).exists())
                self.assertFalse(CodigoRecuperacao2FA.objects.filter(conta=conta).exists())
                self.assertFalse(DispositivoConfiavel2FA.objects.filter(conta=conta).exists())
                self.assertTrue(RegistroAuditoria.objects.filter(
                    acao='PERMISSAO', objeto_id=str(pessoa.usuario_id)).exists())

    def test_botao_aparece_somente_para_quem_tem_2fa(self):
        self.ativar_2fa(self.professor)
        self.ativar_2fa(self.responsavel)
        cliente = self.cliente(self.gestor)
        self.assertContains(cliente.get(reverse('professor-listar')), self.url(self.professor))
        self.assertNotContains(cliente.get(reverse('professor-listar')), self.url(self.outro_professor))
        self.assertContains(cliente.get(reverse('responsavel-listar')), self.url(self.responsavel))

    def test_somente_gestor_pode_redefinir(self):
        conta = self.ativar_2fa(self.outro_professor)
        for pessoa in (self.professor, self.aluno, self.responsavel):
            with self.subTest(perfil=pessoa.usuario.tipo_perfil):
                resposta = self.cliente(pessoa).post(self.url(self.outro_professor))
                self.assertIn(resposta.status_code, (302, 403))
                self.assertTrue(Configuracao2FA.objects.filter(conta=conta).exists())

    def test_nao_redefine_aluno_nem_gestor(self):
        for pessoa in (self.aluno, self.gestor):
            with self.subTest(usuario=pessoa.usuario.usuario):
                self.assertEqual(self.cliente(self.gestor).post(self.url(pessoa)).status_code, 404)

    def test_get_nao_altera_nada(self):
        conta = self.ativar_2fa(self.professor)
        self.cliente(self.gestor).get(self.url(self.professor))
        self.assertTrue(Configuracao2FA.objects.filter(conta=conta).exists())

    def test_sessoes_abertas_sao_encerradas(self):
        self.ativar_2fa(self.professor)
        cliente_antigo = Client()
        self.assertTrue(cliente_antigo.login(username='professor', password=SENHA))
        self.assertEqual(cliente_antigo.get(reverse('meus-dados')).status_code, 200)
        self.cliente(self.gestor).post(self.url(self.professor))
        self.assertIn('/login/', cliente_antigo.get(reverse('meus-dados')).url)

    def test_proximo_acesso_exige_novo_authenticator(self):
        self.ativar_2fa(self.professor)
        self.cliente(self.gestor).post(self.url(self.professor))
        with override_settings(ELO_2FA_ATIVO=True):
            cliente = Client()
            self.assertTrue(cliente.login(username='professor', password=SENHA))
            resposta = cliente.get(reverse('meus-dados'))
            self.assertRedirects(resposta, reverse('2fa-configurar') + '?next=%2Fmeus-dados%2F',
                                 fetch_redirect_response=False)
            self.assertEqual(cliente.get(reverse('2fa-configurar')).status_code, 200)
