from django.test import SimpleTestCase
from django.urls import reverse
from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS


class PoliticasEcaDigitalTests(SimpleTestCase):
    def test_politica_publica_trata_de_criancas_e_limites(self):
        resposta = self.client.get(reverse('politica-privacidade'))
        self.assertEqual(resposta.status_code, 200)
        for trecho in ('ECA Digital', 'cinco anos', 'exclusão física automática',
                       'Resolução CD/ANPD', 'relatório formal de impacto'):
            self.assertContains(resposta, trecho)

    def test_termos_publicos_descrevem_gestor_e_retencao(self):
        resposta = self.client.get(reverse('termos-uso'))
        self.assertEqual(resposta.status_code, 200)
        for trecho in ('professor gestor', 'cinco anos', 'não realiza eliminação física automática',
                       'crianças e adolescentes', 'Lei Felca'):
            self.assertContains(resposta, trecho)

    def test_resumo_aluno_esclarece_apagamento(self):
        resposta = self.client.get(reverse('privacidade-aluno'))
        self.assertContains(resposta, 'não apaga automaticamente')
