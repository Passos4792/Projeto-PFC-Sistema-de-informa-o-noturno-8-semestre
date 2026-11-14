from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.models import (Aluno, DocumentoPedagogico, Professor,
                              RelatorioPedagogico, Responsavel, Usuario, Vinculo)


class TestesExportacaoPDF(TestCase):
    @classmethod
    def setUpTestData(cls):
        def pessoa(login, tipo, modelo, gestor=False):
            conta = get_user_model().objects.create_user(username=login, password='Senha#Teste2026')
            usuario = Usuario.objects.create(
                usuario=login, conta=conta, tipo_perfil=tipo,
                gestor=gestor, troca_senha_obrigatoria=False,
                documentos_aceitos_em=timezone.now(),
                versao_termos_aceita=VERSAO_TERMOS,
                versao_privacidade_ciente=VERSAO_PRIVACIDADE,
            )
            return modelo.objects.create(usuario=usuario, nome='Nome', sobrenome=login)

        cls.gestor = pessoa('pdf-gestor', 'PROFESSOR', Professor, gestor=True)
        cls.aee = pessoa('pdf-aee', 'PROFESSOR', Professor)
        cls.outro_professor = pessoa('pdf-externo', 'PROFESSOR', Professor)
        cls.aluno = pessoa('pdf-aluno', 'ALUNO', Aluno)
        cls.outro_aluno = pessoa('pdf-outro-aluno', 'ALUNO', Aluno)
        cls.familiar = pessoa('pdf-familia', 'RESPONSAVEL', Responsavel)
        cls.familiar_externo = pessoa('pdf-familia-externa', 'RESPONSAVEL', Responsavel)
        Vinculo.objects.create(aluno=cls.aluno, professor=cls.aee,
                               responsavel=cls.familiar, data_vinculo=date(2026, 11, 1))
        cls.pei = DocumentoPedagogico.objects.create(
            aluno=cls.aluno, professor=cls.aee, tipo='PEI', ano_letivo=2026,
            bimestre=2, campos={'conteudos': 'Leitura com apoio visual',
                                'estrategias': 'Texto com <script> e & caracteres'},
        )
        cls.paee = DocumentoPedagogico.objects.create(
            aluno=cls.aluno, professor=cls.aee, tipo='PAEE', ano_letivo=2026,
            campos={'habilidades': 'Comunicação e autonomia'},
        )
        cls.estudo = DocumentoPedagogico.objects.create(
            aluno=cls.aluno, professor=cls.aee, tipo='ESTUDO', ano_letivo=2026,
            campos={'sintese': 'Síntese do estudo'},
        )
        cls.relatorio = RelatorioPedagogico.objects.create(
            aluno=cls.aluno, professor=cls.aee, titulo='Relatório de novembro',
            periodo='Novembro', relato='Avanços observados\nCom apoio individual.',
            data_referencia=date(2026, 11, 10),
        )

    def entrar(self, pessoa):
        self.client.force_login(pessoa.usuario.conta)

    def pdf(self, nome, item):
        return self.client.get(reverse(nome, args=[item.pk]))

    def assert_pdf(self, resposta, arquivo):
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertTrue(resposta.content.startswith(b'%PDF-'))
        self.assertGreater(len(resposta.content), 1000)
        self.assertIn(arquivo, resposta['Content-Disposition'])
        self.assertIn('attachment', resposta['Content-Disposition'])
        self.assertIn('no-store', resposta['Cache-Control'])

    def test_gestor_pode_exportar_pei_paee_estudo_e_relatorio_em_rascunho(self):
        self.entrar(self.gestor)
        for registro in (self.pei, self.paee, self.estudo):
            with self.subTest(tipo=registro.tipo):
                self.assert_pdf(self.pdf('documento-pdf', registro),
                                f'elo-{registro.tipo.lower()}-{registro.pk}.pdf')
        self.assert_pdf(self.pdf('relatorio-pdf', self.relatorio),
                        f'elo-relatorio-{self.relatorio.pk}.pdf')

    def test_professor_vinculado_pode_exportar_seus_documentos(self):
        self.entrar(self.aee)
        self.assert_pdf(self.pdf('documento-pdf', self.paee), 'elo-paee-')
        self.assert_pdf(self.pdf('relatorio-pdf', self.relatorio), 'elo-relatorio-')

    def test_responsavel_so_pode_exportar_publicados_do_aluno_vinculado(self):
        self.entrar(self.familiar)
        self.assertEqual(self.pdf('documento-pdf', self.pei).status_code, 403)
        self.assertEqual(self.pdf('relatorio-pdf', self.relatorio).status_code, 403)
        self.pei.situacao = 'PUBLICADO'
        self.pei.save(update_fields=['situacao'])
        self.relatorio.situacao = 'PUBLICADO'
        self.relatorio.save(update_fields=['situacao'])
        self.assert_pdf(self.pdf('documento-pdf', self.pei), 'elo-pei-')
        self.assert_pdf(self.pdf('relatorio-pdf', self.relatorio), 'elo-relatorio-')

        self.entrar(self.familiar_externo)
        self.assertEqual(self.pdf('documento-pdf', self.pei).status_code, 403)
        self.assertEqual(self.pdf('relatorio-pdf', self.relatorio).status_code, 403)

    def test_estudante_e_professor_sem_vinculo_nao_podem_exportar(self):
        for pessoa in (self.aluno, self.outro_professor):
            with self.subTest(pessoa=pessoa.usuario.usuario):
                self.entrar(pessoa)
                self.assertEqual(self.pdf('documento-pdf', self.pei).status_code, 403)
                self.assertEqual(self.pdf('relatorio-pdf', self.relatorio).status_code, 403)

    def test_desativar_vinculo_revoga_exportacao(self):
        self.pei.situacao = 'PUBLICADO'
        self.pei.save(update_fields=['situacao'])
        self.entrar(self.familiar)
        self.assertEqual(self.pdf('documento-pdf', self.pei).status_code, 200)
        vinculo = Vinculo.objects.get(aluno=self.aluno)
        vinculo.ativo = False
        vinculo.save(update_fields=['ativo'])
        self.assertEqual(self.pdf('documento-pdf', self.pei).status_code, 403)

    def test_get_obrigatorio_e_login_obrigatorio(self):
        url = reverse('documento-pdf', args=[self.pei.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.entrar(self.aee)
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_botoes_pdf_nas_paginas_de_detalhe_para_quem_pode_ver(self):
        self.entrar(self.aee)
        self.assertContains(self.client.get(reverse('documento-detalhe', args=[self.pei.pk])),
                            reverse('documento-pdf', args=[self.pei.pk]))
        self.assertContains(self.client.get(reverse('relatorio-detalhe', args=[self.relatorio.pk])),
                            reverse('relatorio-pdf', args=[self.relatorio.pk]))
        self.pei.situacao = 'PUBLICADO'
        self.pei.save(update_fields=['situacao'])
        self.entrar(self.familiar)
        self.assertContains(self.client.get(reverse('documento-detalhe', args=[self.pei.pk])),
                            'Baixar PDF')

    def test_pdf_nao_modifica_situacao_ou_conteudo(self):
        self.entrar(self.aee)
        self.pdf('documento-pdf', self.pei)
        self.pdf('relatorio-pdf', self.relatorio)
        self.pei.refresh_from_db()
        self.relatorio.refresh_from_db()
        self.assertEqual(self.pei.situacao, 'RASCUNHO')
        self.assertEqual(self.relatorio.situacao, 'RASCUNHO')
        self.assertEqual(self.pei.campos['estrategias'], 'Texto com <script> e & caracteres')
