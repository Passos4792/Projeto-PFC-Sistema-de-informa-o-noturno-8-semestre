from datetime import date, timedelta
from io import BytesIO
from PIL import Image
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings, TestCase
from django.urls import reverse
from django.utils import timezone
from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.forms import FormularioAtividade
from aplicacao.models import (Aluno, Atividade, Disciplina, Professor, Responsavel, SolicitacaoConclusao, Usuario, Vinculo)


class TestesEntregaAtividades(TestCase):
    def setUp(self):
        self.arquivos = TemporaryDirectory()
        self.addCleanup(self.arquivos.cleanup)
        self._ajuste = override_settings(MEDIA_ROOT=self.arquivos.name)
        self._ajuste.enable()
        self.addCleanup(self._ajuste.disable)
        self.professor = self._pessoa('professor-elo', 'PROFESSOR', Professor)
        self.responsavel = self._pessoa('familia-elo', 'RESPONSAVEL', Responsavel)
        self.outra_familia = self._pessoa('outra-familia', 'RESPONSAVEL', Responsavel)
        self.aluno = self._pessoa('aluno-elo', 'ALUNO', Aluno)
        self.outro_aluno = self._pessoa('outro-aluno', 'ALUNO', Aluno)
        self.conteudo = Disciplina.objects.create(nome='Linguagem')
        Vinculo.objects.create(aluno=self.aluno, professor=self.professor, responsavel=self.responsavel,
                               data_vinculo=date(2026, 11, 10), ativo=True, mesclar_perfis=True)
        Vinculo.objects.create(aluno=self.outro_aluno, professor=self.professor,
                               responsavel=self.outra_familia, data_vinculo=date(2026, 11, 10), ativo=True, mesclar_perfis=True)
        self.atividade = Atividade.objects.create(
            aluno=self.aluno, professor=self.professor, disciplina=self.conteudo,
            titulo='Meu cotidiano', descricao='Descreva sua rotina com ajuda da família.',
            data_entrega=date(2026, 12, 1), tipo_entrega=Atividade.TipoEntrega.ENVIO)

    def _pessoa(self, identificador, tipo, modelo):
        conta = get_user_model().objects.create_user(username=identificador, password='SenhaForte-12345!')
        usuario = Usuario.objects.create(
            conta=conta, usuario=identificador, tipo_perfil=tipo, troca_senha_obrigatoria=False,
            documentos_aceitos_em=timezone.now(), versao_termos_aceita=VERSAO_TERMOS,
            versao_privacidade_ciente=VERSAO_PRIVACIDADE,
        )
        return modelo.objects.create(usuario=usuario, nome='Nome', sobrenome=identificador)

    def test_formulario_de_criacao_propõe_envio_e_cobra_descricao(self):
        formulario = FormularioAtividade()
        self.assertEqual(formulario.fields['tipo_entrega'].initial, Atividade.TipoEntrega.ENVIO)
        self.assertTrue(formulario.fields['descricao'].required)

    def test_aluno_pode_entregar_resposta_escrita_e_professor_aprovar(self):
        self.client.force_login(self.aluno.usuario.conta)
        url = reverse('api-solicitar-conclusao', args=[self.atividade.pk])
        resposta = self.client.post(url, {'resposta_aluno': 'Minha rotina começou com café.'})
        self.assertEqual(resposta.status_code, 201)
        entrega = SolicitacaoConclusao.objects.get()
        self.assertIn('café', entrega.resposta_aluno)
        self.atividade.refresh_from_db()
        self.assertEqual(self.atividade.situacao, 'PENDENTE')
        self.client.force_login(self.professor.usuario.conta)
        decisao = self.client.patch(reverse('api-decidir-conclusao', args=[entrega.pk]),
                                   data='{"decisao": "APROVADA"}', content_type='application/json')
        self.assertEqual(decisao.status_code, 200)
        self.atividade.refresh_from_db()
        self.assertEqual(self.atividade.situacao, 'CONCLUIDA')

    def test_entrega_por_responsavel_sem_login_da_crianca(self):
        self.client.force_login(self.responsavel.usuario.conta)
        resposta = self.client.post(reverse('api-solicitar-conclusao', args=[self.atividade.pk]),
                                   {'resposta_aluno': 'Resposta auxiliada pelo responsável.'})
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(SolicitacaoConclusao.objects.get().solicitante, self.responsavel.usuario)

    def test_envio_exige_texto_ou_anexo(self):
        self.client.force_login(self.aluno.usuario.conta)
        resposta = self.client.post(reverse('api-solicitar-conclusao', args=[self.atividade.pk]),
                                   {'mensagem': 'Atividade realizada.'})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_anexo_pdf_eh_privado_e_tem_download_controlado(self):
        self.client.force_login(self.responsavel.usuario.conta)
        arquivo = SimpleUploadedFile('minha-atividade.pdf', b'%PDF-1.4\nexemplo seguro', content_type='application/pdf')
        resposta = self.client.post(reverse('api-solicitar-conclusao', args=[self.atividade.pk]),
                                   {'anexo': arquivo})
        self.assertEqual(resposta.status_code, 201, resposta.content)
        entrega = SolicitacaoConclusao.objects.get()
        self.assertNotIn('minha-atividade.pdf', entrega.anexo.name)
        caminho = reverse('entrega-anexo', args=[entrega.pk])
        download = self.client.get(caminho)
        try:
            self.assertEqual(download.status_code, 200)
            self.assertTrue(b''.join(download.streaming_content).startswith(b'%PDF-'))
        finally:
            b''.join(download.streaming_content)
        self.client.force_login(self.professor.usuario.conta)
        download = self.client.get(caminho)
        try:
            self.assertEqual(download.status_code, 200)
            self.assertTrue(b''.join(download.streaming_content).startswith(b'%PDF-'))
        finally:
            b''.join(download.streaming_content)
        self.client.force_login(self.outra_familia.usuario.conta)
        self.assertEqual(self.client.get(caminho).status_code, 403)

    def test_arquivo_invalido_nao_cria_entrega(self):
        self.client.force_login(self.aluno.usuario.conta)
        arquivo = SimpleUploadedFile('falso.pdf', b'conteudo invalido', content_type='application/pdf')
        resposta = self.client.post(reverse('api-solicitar-conclusao', args=[self.atividade.pk]),
                                   {'anexo': arquivo})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_atividade_presencial_mantem_solicitacao_sem_anexo(self):
        self.atividade.tipo_entrega = Atividade.TipoEntrega.REGISTRO
        self.atividade.save(update_fields=['tipo_entrega'])
        self.client.force_login(self.responsavel.usuario.conta)
        resposta = self.client.post(reverse('api-solicitar-conclusao', args=[self.atividade.pk]),
                                   {'mensagem': 'Foi feita com o professor.'})
        self.assertEqual(resposta.status_code, 201)

    def test_aluno_de_outra_familia_nao_envia_nem_acessa_material(self):
        self.client.force_login(self.outra_familia.usuario.conta)
        self.assertEqual(self.client.post(reverse('api-solicitar-conclusao', args=[self.atividade.pk]),
                                          {'resposta_aluno': 'Acesso indevido'}).status_code, 404)
        self.assertEqual(self.client.get(reverse('atividade-material', args=[self.atividade.pk])).status_code, 403)

    def test_material_de_apoio_criado_pelo_professor_eh_baixado_por_aluno_vinculado(self):
        self.client.force_login(self.professor.usuario.conta)
        arquivo = SimpleUploadedFile('orientacoes.pdf', b'%PDF-1.7\nexemplo', content_type='application/pdf')
        resposta = self.client.post(reverse('atividade-criar'), {
            'aluno': str(self.aluno.pk), 'professor': str(self.professor.pk),
            'disciplina': str(self.conteudo.pk), 'titulo': 'Atividade com orientações',
            'descricao': 'Orientações detalhadas para a realização.',
            'tipo_entrega': 'ENVIO', 'situacao': 'PENDENTE', 'data_entrega': '2026-12-10',
            'material_apoio': arquivo,
        })
        self.assertEqual(resposta.status_code, 302)
        nova = Atividade.objects.get(titulo='Atividade com orientações')
        self.assertEqual(nova.material_nome, 'orientacoes.pdf')
        caminho = reverse('atividade-material', args=[nova.pk])
        self.client.force_login(self.aluno.usuario.conta)
        download = self.client.get(caminho)
        try:
            self.assertEqual(download.status_code, 200)
            self.assertTrue(b''.join(download.streaming_content).startswith(b'%PDF-'))
        finally:
            b''.join(download.streaming_content)
        self.client.force_login(self.outra_familia.usuario.conta)
        self.assertEqual(self.client.get(caminho).status_code, 403)

    def test_aluno_sem_login_consegue_enviar_por_meio_da_conta_do_responsavel(self):
        self.aluno.usuario.conta = None
        self.aluno.usuario.save(update_fields=['conta'])
        self.client.force_login(self.responsavel.usuario.conta)
        self.assertEqual(self.client.get(reverse('minhas-atividades')).status_code, 200)
        resposta = self.client.post(reverse('api-solicitar-conclusao', args=[self.atividade.pk]),
                                   {'resposta_aluno': 'Registro feito pelo responsável.'})
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(SolicitacaoConclusao.objects.get().solicitante, self.responsavel.usuario)

    def test_pagina_mostra_campo_de_resposta_e_anexo_em_atividade_com_envio(self):
        self.client.force_login(self.aluno.usuario.conta)
        lista = self.client.get(reverse('minhas-atividades'))
        self.assertContains(lista, reverse('atividade-detalhe', args=[self.atividade.pk]))
        resposta = self.client.get(reverse('atividade-detalhe', args=[self.atividade.pk]))
        self.assertContains(resposta, 'name="resposta_aluno"')
        self.assertContains(resposta, 'name="anexo"')
        self.assertContains(resposta, 'Descreva sua rotina')

    def test_formulario_html_envia_somente_texto_e_mostra_confirmacao(self):
        self.client.force_login(self.aluno.usuario.conta)
        resposta = self.client.post(reverse('atividade-enviar', args=[self.atividade.pk]), {
            'resposta_aluno': 'Minha resposta somente em texto.',
            'mensagem': '',
        }, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Atividade enviada com sucesso')
        self.assertEqual(SolicitacaoConclusao.objects.count(), 1)
        self.assertEqual(SolicitacaoConclusao.objects.get().resposta_aluno, 'Minha resposta somente em texto.')

    def test_formulario_html_envia_somente_anexo_e_responsavel_pode_enviar(self):
        self.client.force_login(self.responsavel.usuario.conta)
        imagem = BytesIO()
        Image.new('RGB', (2, 2), color='white').save(imagem, format='PNG')
        arquivo = SimpleUploadedFile('foto.png', imagem.getvalue(), content_type='image/png')
        resposta = self.client.post(reverse('atividade-enviar', args=[self.atividade.pk]), {'anexo': arquivo}, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Atividade enviada com sucesso')
        solicitacao = SolicitacaoConclusao.objects.get()
        self.assertEqual(solicitacao.solicitante, self.responsavel.usuario)
        self.assertEqual(solicitacao.anexo_nome, 'foto.png')
        self.assertEqual(solicitacao.resposta_aluno, '')

    def test_atividade_antiga_presencial_permite_resposta_e_anexo(self):
        self.atividade.tipo_entrega = Atividade.TipoEntrega.REGISTRO
        self.atividade.save(update_fields=['tipo_entrega'])
        self.client.force_login(self.aluno.usuario.conta)
        pagina = self.client.get(reverse('atividade-detalhe', args=[self.atividade.pk]))
        self.assertContains(pagina, 'name="resposta_aluno"')
        self.assertContains(pagina, 'name="anexo"')
        self.assertContains(pagina, reverse('atividade-enviar', args=[self.atividade.pk]))
        resposta = self.client.post(reverse('atividade-enviar', args=[self.atividade.pk]), {
            'resposta_aluno': 'Respondi mesmo sendo atividade antiga.',
        }, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(SolicitacaoConclusao.objects.get().resposta_aluno,
                         'Respondi mesmo sendo atividade antiga.')

    def test_envio_html_sem_resposta_nem_anexo_nao_cria_entrega_para_tipo_envio(self):
        self.client.force_login(self.aluno.usuario.conta)
        resposta = self.client.post(reverse('atividade-enviar', args=[self.atividade.pk]), {}, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Escreva uma resposta ou envie um arquivo')
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_entrega_html_sem_duplicidade_apos_primeiro_envio(self):
        self.client.force_login(self.aluno.usuario.conta)
        url = reverse('atividade-enviar', args=[self.atividade.pk])
        self.client.post(url, {'resposta_aluno': 'Primeiro envio'})
        resposta = self.client.post(url, {'resposta_aluno': 'Segundo envio'}, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Já existe uma entrega aguardando avaliação')
        self.assertEqual(SolicitacaoConclusao.objects.count(), 1)

    def test_outra_familia_nao_consegue_enviar_pelo_formulario_html(self):
        self.client.force_login(self.outra_familia.usuario.conta)
        resposta = self.client.post(reverse('atividade-enviar', args=[self.atividade.pk]), {
            'resposta_aluno': 'Tentativa não autorizada',
        })
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_formulario_html_com_csrf_obrigatorio(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.aluno.usuario.conta)
        resposta = cliente.post(reverse('atividade-enviar', args=[self.atividade.pk]), {
            'resposta_aluno': 'Sem token',
        })
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_padrao_novas_atividades_eh_envio(self):
        self.assertEqual(Atividade._meta.get_field('tipo_entrega').default, 'ENVIO')


class TestesHistoricoAtividades(TestCase):
    setUp = TestesEntregaAtividades.setUp
    _pessoa = TestesEntregaAtividades._pessoa

    def test_lista_de_aluno_mostra_tabela_e_detalhe(self):
        self.client.force_login(self.aluno.usuario.conta)
        resposta = self.client.get(reverse('minhas-atividades'))
        self.assertContains(resposta, 'Suas atividades')
        self.assertContains(resposta, 'elo-tabela-atividades')
        self.assertContains(resposta, reverse('atividade-detalhe', args=[self.atividade.pk]))
        detalhe = self.client.get(reverse('atividade-detalhe', args=[self.atividade.pk]))
        self.assertContains(detalhe, 'O que fazer?')
        self.assertContains(detalhe, 'Descreva sua rotina')
        self.assertContains(detalhe, 'Enviar atividade para avaliação')

    def test_historico_inclui_concluidas_canceladas_e_atrasadas(self):
        passada = Atividade.objects.create(
            aluno=self.aluno, professor=self.professor, titulo='Atividade de outubro',
            descricao='Teste', data_entrega=timezone.localdate() - timedelta(days=30), situacao='PENDENTE')
        concluida = Atividade.objects.create(
            aluno=self.aluno, professor=self.professor, titulo='Atividade concluida',
            descricao='Teste', data_entrega=timezone.localdate() + timedelta(days=30), situacao='CONCLUIDA')
        self.client.force_login(self.professor.usuario.conta)
        with self.settings(USE_TZ=True):
            resposta = self.client.get(reverse('atividade-historico'))
        self.assertContains(resposta, passada.titulo)
        self.assertContains(resposta, concluida.titulo)
        if self.atividade.data_entrega >= timezone.localdate():
            self.assertNotContains(resposta, self.atividade.titulo)
        self.assertContains(resposta, reverse('atividade-detalhe', args=[passada.pk]))

    def test_professor_acessa_resposta_antiga(self):
        self.atividade.situacao = 'CONCLUIDA'
        self.atividade.save()
        SolicitacaoConclusao.objects.create(atividade=self.atividade, aluno=self.aluno,
            solicitante=self.responsavel.usuario, resposta_aluno='Relato de realização do aluno.',
            situacao='APROVADA', professor=self.professor)
        self.client.force_login(self.professor.usuario.conta)
        pagina = self.client.get(reverse('atividade-detalhe', args=[self.atividade.pk]) + '?origem=historico')
        self.assertContains(pagina, 'Relato de realização do aluno.')
        self.assertContains(pagina, 'Voltar ao histórico')

    def test_familia_nao_acessa_historico_professor(self):
        self.client.force_login(self.responsavel.usuario.conta)
        self.assertEqual(self.client.get(reverse('atividade-historico')).status_code, 403)
        outra = Atividade.objects.create(aluno=self.outro_aluno, professor=self.professor,
            titulo='Atividade privada', descricao='Restrita')
        self.assertEqual(self.client.get(reverse('atividade-detalhe', args=[outra.pk])).status_code, 403)

    def test_professor_ve_somente_atividades_que_cadastrou(self):
        outro_professor = self._pessoa('professor-2', 'PROFESSOR', Professor)
        outra_atividade = Atividade.objects.create(
            aluno=self.outro_aluno, professor=outro_professor,
            titulo='Relato de outro professor', situacao='CONCLUIDA')
        minha_antiga = Atividade.objects.create(
            aluno=self.aluno, professor=self.professor,
            titulo='Relato do professor', situacao='CONCLUIDA')
        self.client.force_login(self.professor.usuario.conta)
        resposta = self.client.get(reverse('atividade-historico'))
        self.assertContains(resposta, minha_antiga.titulo)
        self.assertNotContains(resposta, outra_atividade.titulo)
        self.assertEqual(self.client.get(reverse('atividade-detalhe', args=[outra_atividade.pk])).status_code, 403)

    def test_busca_e_filtros_no_historico(self):
        antiga = Atividade.objects.create(aluno=self.aluno, professor=self.professor,
            titulo='Avaliação antiga', data_entrega=date(2025, 8, 12), situacao='CONCLUIDA')
        self.client.force_login(self.professor.usuario.conta)
        pagina = self.client.get(reverse('atividade-historico'), {
            'ano': '2025', 'situacao': 'CONCLUIDA', 'busca': 'Avaliação'})
        self.assertContains(pagina, antiga.titulo)
        pagina = self.client.get(reverse('atividade-historico'), {
            'ano': '2024', 'situacao': 'CONCLUIDA', 'busca': 'Avaliação'})
        self.assertNotContains(pagina, antiga.titulo)
