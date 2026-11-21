"""Regressões de encerramento voluntário, autorização principal e PDF do titular."""
from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from aplicacao.models import (
    Aluno, AutorizacaoAcessoMenor, DocumentoPedagogico, RegistroAuditoria,
    RelatorioPedagogico, Vinculo, VinculoFamiliar,
)
from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from testes.base import CenarioTestCase, SENHA, pessoa


class PrivacidadeContasTests(CenarioTestCase):
    def setUp(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 11, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        self.url = reverse('privacidade-gerenciar')

    def _confirmar(self, **dados):
        return {'senha': SENHA, 'confirmacao': 'ENCERRAR', 'confirmo': 'on', **dados}

    def _autorizar(self):
        return AutorizacaoAcessoMenor.objects.create(
            aluno=self.aluno, responsavel=self.responsavel,
            versao_termos=VERSAO_TERMOS, versao_privacidade=VERSAO_PRIVACIDADE,
            autorizado_em=timezone.now(),
        )

    def test_responsavel_principal_ve_apenas_criancas_e_pdf(self):
        resposta = self.cliente(self.responsavel).get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, self.aluno.nome_completo)
        self.assertContains(resposta, reverse('privacidade-exportar-menor', args=[self.aluno.pk]))
        self.assertNotContains(resposta, self.outro_aluno.nome_completo)
        pdf = self.cliente(self.responsavel).get(reverse('privacidade-exportar-menor', args=[self.aluno.pk]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertEqual(pdf['Cache-Control'], 'no-store, no-cache, must-revalidate, private')

    def test_responsavel_secundario_nao_pode_apagar_crianca(self):
        segundo = pessoa('secundario', 'RESPONSAVEL')
        VinculoFamiliar.objects.create(aluno=self.aluno, responsavel=segundo)
        cliente = self.cliente(segundo)
        self.assertNotContains(cliente.get(self.url), self.aluno.nome_completo)
        self.assertEqual(cliente.get(reverse('privacidade-exportar-menor', args=[self.aluno.pk])).status_code, 404)
        self.assertEqual(cliente.post(reverse('privacidade-excluir-menor', args=[self.aluno.pk]),
                                     self._confirmar()).status_code, 404)
        self.aluno.refresh_from_db()
        self.assertTrue(self.aluno.ativo)
        self.assertIsNotNone(self.aluno.usuario.conta_id)

    def test_nao_pode_encerrar_aluno_com_12_anos(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 12, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        cliente = self.cliente(self.responsavel)
        self.assertNotContains(cliente.get(self.url), self.aluno.nome_completo)
        self.assertEqual(cliente.get(reverse('privacidade-excluir-menor', args=[self.aluno.pk])).status_code, 403)

    def test_senha_checkbox_e_confirmacao_sao_obrigatorios(self):
        cliente = self.cliente(self.responsavel)
        url = reverse('privacidade-excluir-menor', args=[self.aluno.pk])
        for campos in (
            {'senha': 'errada', 'confirmacao': 'ENCERRAR', 'confirmo': 'on'},
            {'senha': SENHA, 'confirmacao': 'OUTRA', 'confirmo': 'on'},
            {'senha': SENHA, 'confirmacao': 'ENCERRAR'},
        ):
            self.assertEqual(cliente.post(url, campos).status_code, 200)
        self.aluno.refresh_from_db()
        self.assertTrue(self.aluno.ativo)

    def test_encerrar_crianca_desativa_login_vinculos_e_preserva_documentos(self):
        self._autorizar()
        documento = DocumentoPedagogico.objects.create(
            aluno=self.aluno, professor=self.professor, tipo='PEI', ano_letivo=2026,
            campos={'objetivo': 'Registros pedagógicos preservados'}, situacao='PUBLICADO',
        )
        id_conta = self.aluno.usuario.conta_id
        cliente = self.cliente(self.responsavel)
        url = reverse('privacidade-excluir-menor', args=[self.aluno.pk])
        self.assertEqual(cliente.post(url, self._confirmar()).status_code, 302)
        self.aluno.refresh_from_db()
        self.aluno.usuario.refresh_from_db()
        self.vinculo.refresh_from_db()
        self.assertFalse(self.aluno.ativo)
        self.assertFalse(self.vinculo.ativo)
        self.assertIsNotNone(self.aluno.inativado_em)
        self.assertIsNone(self.aluno.usuario.conta_id)
        self.assertIsNotNone(self.aluno.usuario.conta_encerrada_em)
        self.assertFalse(get_user_model().objects.filter(pk=id_conta).exists())
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(aluno=self.aluno).exists())
        self.assertTrue(DocumentoPedagogico.objects.filter(pk=documento.pk).exists())
        self.assertEqual(cliente.get(self.url).status_code, 200)  # adulto mantém sua conta
        self.assertTrue(RegistroAuditoria.objects.filter(acao='EXCLUSAO', objeto_id=str(self.aluno.usuario.pk)).exists())

    def test_encerramento_do_responsavel_nao_apaga_aluno(self):
        self._autorizar()
        cliente = self.cliente(self.responsavel)
        resposta = cliente.post(reverse('privacidade-excluir-minha'), self._confirmar())
        self.assertRedirects(resposta, reverse('login'), fetch_redirect_response=False)
        self.responsavel.refresh_from_db()
        self.responsavel.usuario.refresh_from_db()
        self.aluno.refresh_from_db()
        self.vinculo.refresh_from_db()
        self.assertFalse(self.responsavel.ativo)
        self.assertIsNone(self.responsavel.usuario.conta_id)
        self.assertFalse(self.vinculo.ativo)
        self.assertTrue(self.aluno.ativo)
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(aluno=self.aluno).exists())
        self.assertRedirects(cliente.get(self.url), reverse('login') + '?next=' + self.url,
                             fetch_redirect_response=False)

    def test_aluno_maior_12_baixa_pdf_e_encerra_so_a_propria_conta(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 13, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        self.meta()
        self.atividade()
        cliente = self.cliente(self.aluno)
        self.assertContains(cliente.get(self.url), 'Baixar meus dados em PDF')
        pdf = cliente.get(reverse('privacidade-exportar-minha'))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        resposta = cliente.post(reverse('privacidade-excluir-minha'), self._confirmar())
        self.assertEqual(resposta.status_code, 302)
        self.aluno.refresh_from_db()
        self.assertFalse(self.aluno.ativo)
        self.assertTrue(self.responsavel.ativo)

    def test_menor_de_12_nao_pode_encerrar_sua_propria_conta(self):
        self._autorizar()
        cliente = self.cliente(self.aluno)
        self.assertEqual(cliente.get(self.url).status_code, 403)
        self.assertEqual(cliente.post(reverse('privacidade-excluir-minha'), self._confirmar()).status_code, 403)
        self.assertEqual(cliente.get(reverse('privacidade-exportar-minha')).status_code, 403)

    def test_sem_nascimento_nao_pode_burlar_regra_de_idade(self):
        self.aluno.data_nascimento = None
        self.aluno.save(update_fields=['data_nascimento'])
        cliente = self.cliente(self.aluno)
        self.assertEqual(cliente.get(self.url).status_code, 403)
        self.assertEqual(cliente.post(reverse('privacidade-excluir-minha'), self._confirmar()).status_code, 403)

    def test_professor_nao_encerrar_contas_por_esta_area(self):
        cliente = self.cliente(self.professor)
        self.assertEqual(cliente.get(self.url).status_code, 403)
        self.assertEqual(cliente.post(reverse('privacidade-excluir-minha'), self._confirmar()).status_code, 403)
        self.assertEqual(cliente.post(reverse('privacidade-excluir-menor', args=[self.aluno.pk]),
                                     self._confirmar()).status_code, 403)

    def test_exportacao_nao_divulga_documentos_internos(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 13, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        DocumentoPedagogico.objects.create(
            aluno=self.aluno, professor=self.professor, tipo='PEI', ano_letivo=2026,
            campos={'objetivo': 'rascunho interno'}, situacao='RASCUNHO',
        )
        RelatorioPedagogico.objects.create(
            aluno=self.aluno, professor=self.professor, titulo='Observações internas',
            relato='Texto interno', situacao='FINALIZADO',
        )
        pdf = self.cliente(self.aluno).get(reverse('privacidade-exportar-minha'))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        # A função de exportação do titular lista somente os publicados.
        from unittest.mock import patch
        with patch('aplicacao.servicos.privacidade_contas.gerar_pdf_prontuario_aluno', return_value=b'%PDF-mock') as gerar:
            self.cliente(self.aluno).get(reverse('privacidade-exportar-minha'))
            self.assertEqual(gerar.call_args.args[1], [])
            self.assertEqual(gerar.call_args.args[2], [])
