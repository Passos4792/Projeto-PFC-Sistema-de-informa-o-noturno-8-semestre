from datetime import date, datetime, timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.models import Aluno, DocumentoPedagogico, Professor, RelatorioPedagogico, Usuario


class RetencaoHistoricoPedagogicoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def criar_pessoa(nome, tipo, modelo, gestor=False):
            login = get_user_model().objects.create_user(username=nome, password='Senha-Ficticia-2026!')
            perfil = Usuario.objects.create(
                usuario=nome, conta=login, tipo_perfil=tipo,
                gestor=gestor, troca_senha_obrigatoria=False,
                documentos_aceitos_em=timezone.now(), versao_termos_aceita=VERSAO_TERMOS,
                versao_privacidade_ciente=VERSAO_PRIVACIDADE,
            )
            return modelo.objects.create(nome='Nome', sobrenome=nome, usuario=perfil)

        cls.gestor = criar_pessoa('gestor-guarda', 'PROFESSOR', Professor, gestor=True)
        cls.outro = criar_pessoa('outro-professor-guarda', 'PROFESSOR', Professor)
        cls.aluno = criar_pessoa('aluno-guarda', 'ALUNO', Aluno)
        cls.documento = DocumentoPedagogico.objects.create(
            aluno=cls.aluno, professor=cls.gestor, tipo='PEI', ano_letivo=2026,
            campos={'conteudos': 'Alfabetização com apoio visual'}, situacao='RASCUNHO')
        cls.documento2 = DocumentoPedagogico.objects.create(
            aluno=cls.aluno, professor=cls.gestor, tipo='PAEE', ano_letivo=2026,
            campos={'objetivos': 'Coordenação motora'}, situacao='FINALIZADO')
        cls.relatorio = RelatorioPedagogico.objects.create(
            aluno=cls.aluno, professor=cls.outro, titulo='Relatório de rotina',
            relato='Evolução com recursos de acessibilidade.', situacao='PUBLICADO')

    def entrar(self, pessoa):
        self.client.force_login(pessoa.usuario.conta)

    def inativar(self):
        aluno = Aluno.objects.get(pk=self.aluno.pk)
        aluno.ativo = False
        aluno.save()
        return aluno

    def test_inativacao_via_formulario_mostra_download_e_registra_data(self):
        self.entrar(self.gestor)
        resposta = self.client.post(reverse('aluno-editar', args=[self.aluno.pk]), {
            'nome': 'Nome', 'sobrenome': 'aluno-guarda',
            'nome_usuario': 'aluno-guarda', 'data_nascimento': '',
        })
        self.assertRedirects(resposta, reverse('aluno-editar', args=[self.aluno.pk]))
        aluno = Aluno.objects.get(pk=self.aluno.pk)
        self.assertFalse(aluno.ativo)
        self.assertIsNotNone(aluno.inativado_em)
        resposta = self.client.get(reverse('aluno-editar', args=[self.aluno.pk]))
        self.assertContains(resposta, 'Baixar em PDF relatórios e documentos')
        self.assertContains(resposta, '5 anos após o aluno ficar inativo')
        self.assertContains(resposta, aluno.documentos_disponiveis_ate.strftime('%d/%m/%Y'))

    def test_download_dados_de_todos_os_registros_sem_alterar_original(self):
        self.inativar()
        self.entrar(self.gestor)
        url = reverse('aluno-documentos-pdf', args=[self.aluno.pk])
        with patch('aplicacao.views.cadastros.gerar_pdf_prontuario_aluno', return_value=b'%PDF-fake') as gerador:
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta['Content-Type'], 'application/pdf')
            self.assertIn('no-store', resposta['Cache-Control'])
            documentos, relatorios = gerador.call_args.args[1:]
            self.assertEqual({d.pk for d in documentos}, {self.documento.pk, self.documento2.pk})
            self.assertEqual([r.pk for r in relatorios], [self.relatorio.pk])
        self.assertEqual(self.client.get(url).content[:4], b'%PDF')
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.situacao, 'RASCUNHO')
        self.assertEqual(self.documento.campos['conteudos'], 'Alfabetização com apoio visual')

    def test_nao_exporta_aluno_ativo_ou_por_profissional_nao_gestor(self):
        url = reverse('aluno-documentos-pdf', args=[self.aluno.pk])
        self.entrar(self.gestor)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.inativar()
        self.entrar(self.outro)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.entrar(self.aluno)
        self.assertNotEqual(self.client.get(url).status_code, 200)

    def test_prazo_cinco_anos_vence_e_bloqueia_exportacoes_individuais(self):
        aluno = self.inativar()
        hoje = timezone.localdate()
        try:
            corte = hoje.replace(year=hoje.year - 5)
        except ValueError:
            corte = date(hoje.year - 5, 2, 28)
        inicio = timezone.make_aware(datetime.combine(corte, datetime.min.time()))
        Aluno.objects.filter(pk=aluno.pk).update(inativado_em=inicio)
        aluno.refresh_from_db()
        self.assertTrue(aluno.documentos_em_prazo)
        self.entrar(self.gestor)
        url = reverse('aluno-documentos-pdf', args=[aluno.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

        Aluno.objects.filter(pk=aluno.pk).update(inativado_em=inicio - timedelta(days=1))
        aluno.refresh_from_db()
        self.assertFalse(aluno.documentos_em_prazo)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse('documento-pdf', args=[self.documento.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-pdf', args=[self.relatorio.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('documentos-lista')), 'Plano Educacional Individualizado')
        self.assertNotContains(self.client.get(reverse('aluno-editar', args=[aluno.pk])),
                               'Baixar em PDF relatórios e documentos')

    def test_reativacao_encerra_janela_e_nova_inativacao_reinicia(self):
        aluno = self.inativar()
        primeiro = aluno.inativado_em
        aluno.nome = 'Nome alterado'
        aluno.save()
        self.assertEqual(Aluno.objects.get(pk=aluno.pk).inativado_em, primeiro)
        aluno.ativo = True
        aluno.save()
        self.assertIsNone(aluno.inativado_em)
        aluno.ativo = False
        aluno.save()
        self.assertIsNotNone(aluno.inativado_em)
        self.assertTrue(aluno.documentos_em_prazo)

    def test_nao_permita_editar_documento_de_aluno_inativado(self):
        self.inativar()
        self.entrar(self.gestor)
        resposta = self.client.get(reverse('documento-editar', args=[self.documento.pk]))
        self.assertEqual(resposta.status_code, 403)

    def test_politica_versao_e_prazo_divulgados(self):
        resposta = self.client.get(reverse('politica-privacidade'))
        self.assertContains(resposta, 'cinco anos')
        self.assertContains(resposta, 'exclusão física automática')
        self.assertContains(resposta, VERSAO_PRIVACIDADE)
