from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.models import Aluno, DocumentoPedagogico, Professor, RelatorioPedagogico, Usuario


class TestesVisualDocumentos(TestCase):
    def setUp(self):
        def criar(username, perfil, cls, gestor=False):
            conta = get_user_model().objects.create_user(username=username, password='SenhaTeste#2026')
            usuario = Usuario.objects.create(
                usuario=username, conta=conta, tipo_perfil=perfil, gestor=gestor,
                troca_senha_obrigatoria=False, documentos_aceitos_em=timezone.now(),
                versao_termos_aceita=VERSAO_TERMOS, versao_privacidade_ciente=VERSAO_PRIVACIDADE,
            )
            return cls.objects.create(usuario=usuario, nome='Teste', sobrenome=username)
        self.professor = criar('gestor-doc-layout', 'PROFESSOR', Professor, gestor=True)
        self.aluno = criar('aluno-doc-layout', 'ALUNO', Aluno)
        self.client.force_login(self.professor.usuario.conta)
        self.pei = DocumentoPedagogico.objects.create(
            aluno=self.aluno, professor=self.professor, tipo='PEI', ano_letivo=2026,
            campos={'conteudos': 'Leitura', 'estrategias': 'Texto de exemplo'},
        )
        self.relatorio = RelatorioPedagogico.objects.create(
            aluno=self.aluno, professor=self.professor, titulo='Relatório teste',
            periodo='1º bimestre', relato='Evolução pedagógica', data_referencia=date(2026, 11, 12),
        )

    def test_pei_exibe_campos_com_espacamento_e_dialogo_personalizado(self):
        resposta = self.client.get(reverse('documento-detalhe', args=[self.pei.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'elo-documento-detalhe')
        self.assertContains(resposta, 'elo-documento-campos')
        self.assertContains(resposta, 'elo-dialogo-confirmacao')
        self.assertContains(resposta, 'data-rotulo-confirmacao="Sim, disponibilizar"')
        self.assertContains(resposta, 'Leitura')

    def test_relatorio_exibe_o_mesmo_layout(self):
        resposta = self.client.get(reverse('relatorio-detalhe', args=[self.relatorio.pk]))
        self.assertContains(resposta, 'elo-documento-detalhe')
        self.assertContains(resposta, 'Evolução pedagógica')
        self.assertContains(resposta, 'elo-dialogo-confirmacao')

    def test_documento_publicado_mostra_confirmacao_de_retirada(self):
        self.pei.situacao = 'PUBLICADO'
        self.pei.save(update_fields=['situacao'])
        resposta = self.client.get(reverse('documento-detalhe', args=[self.pei.pk]))
        self.assertContains(resposta, 'data-titulo-confirmacao="Retirar da família?"')
        self.assertContains(resposta, 'value="RETIRAR"')
        self.assertNotContains(resposta, 'value="PUBLICADO"')

    def test_publicacao_continua_sendo_post_e_altera_situacao(self):
        resposta = self.client.post(reverse('documento-publicar', args=[self.pei.pk]), {'acao': 'PUBLICADO'})
        self.assertEqual(resposta.status_code, 302)
        self.pei.refresh_from_db()
        self.assertEqual(self.pei.situacao, 'PUBLICADO')
