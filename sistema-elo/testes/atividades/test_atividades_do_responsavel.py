from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from aplicacao.servicos import google_calendar as google
from aplicacao.models import (Atividade, ConexaoGoogle, SincronizacaoGoogle, SolicitacaoConclusao,
                              VinculoFamiliar)
from testes.base import CenarioTestCase


class AtividadesResponsavelLeituraTests(CenarioTestCase):
    def setUp(self):
        self.vinculo.mesclar_perfis = False
        self.vinculo.save(update_fields=['mesclar_perfis'])
        self.atividade_vinculada = self.atividade(titulo='Ler para a família',
            data_entrega=timezone.localdate() + timedelta(days=5))
        self.atividade_alheia = self.atividade(aluno=self.outro_aluno,
            titulo='Atividade confidencial de outro aluno',
            data_entrega=timezone.localdate() + timedelta(days=5))
        self.cliente_familia = self.cliente(self.responsavel)

    def test_cartao_de_familia_exibe_atividades_sem_aviso_desativado(self):
        resposta = self.cliente_familia.get(reverse('familia-estudantes'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, f'{reverse("minhas-atividades")}?aluno={self.aluno.pk}')
        self.assertContains(resposta, 'Ver atividades')
        self.assertNotContains(resposta, 'Acesso à área do aluno desativado')

    def test_lista_painel_menu_e_filtros_consultam_somente_vinculados(self):
        for url in (reverse('minhas-atividades'),
                    reverse('minhas-atividades') + f'?aluno={self.aluno.pk}'):
            resposta = self.cliente_familia.get(url)
            self.assertEqual(resposta.status_code, 200)
            self.assertContains(resposta, 'Ler para a família')
            self.assertNotContains(resposta, 'Atividade confidencial de outro aluno')
        self.assertEqual(self.cliente_familia.get(
            reverse('minhas-atividades') + f'?aluno={self.outro_aluno.pk}').status_code, 404)
        painel = self.cliente_familia.get(reverse('aluno-inicio', args=[self.aluno.pk]))
        self.assertEqual(painel.context['url_atividades'],
            f'{reverse("minhas-atividades")}?aluno={self.aluno.pk}')
        self.assertFalse(painel.context['pode_enviar_atividades'])
        self.assertContains(painel, 'Ver atividades')
        inicio = self.cliente_familia.get(reverse('pagina-inicial'))
        self.assertContains(inicio, reverse('minhas-atividades'))
        self.assertContains(inicio, 'Minhas atividades')

    def test_detalhe_somente_leitura_nao_mostra_formulario(self):
        resposta = self.cliente_familia.get(reverse('atividade-detalhe', args=[self.atividade_vinculada.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context['pode_enviar_atividade'])
        self.assertContains(resposta, 'Ler para a família')
        self.assertContains(resposta, 'Atividade do estudante')
        self.assertNotContains(resposta, 'form-envio-atividade')
        self.assertNotContains(resposta, 'Enviar atividade para avaliação')
        self.assertEqual(self.cliente_familia.get(
            reverse('atividade-detalhe', args=[self.atividade_alheia.pk])).status_code, 403)

    def test_servidor_recusa_envio_web_e_api_sem_mesclar(self):
        rota = reverse('atividade-enviar', args=[self.atividade_vinculada.pk])
        resposta = self.cliente_familia.post(rota, {'resposta_aluno': 'Tentativa direta'})
        self.assertEqual(resposta.status_code, 404)
        resposta_api = self.cliente_familia.post(
            reverse('api-solicitar-conclusao', args=[self.atividade_vinculada.pk]),
            {'resposta_aluno': 'Tentativa direta via API'})
        self.assertEqual(resposta_api.status_code, 404)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_anexos_do_aluno_vinculado_ficam_visiveis_mas_nao_os_de_outro(self):
        self.atividade_vinculada.material_apoio = SimpleUploadedFile(
            'material.pdf', b'%PDF-1.4\nmaterial de teste', content_type='application/pdf')
        self.atividade_vinculada.material_nome = 'material.pdf'
        self.atividade_vinculada.save()
        resposta = self.cliente_familia.get(reverse('atividade-material', args=[self.atividade_vinculada.pk]))
        self.assertEqual(resposta.status_code, 200)
        b''.join(resposta.streaming_content)
        self.assertEqual(self.cliente_familia.get(
            reverse('atividade-material', args=[self.atividade_alheia.pk])).status_code, 403)

    def test_mesclar_e_por_aluno_e_permite_enviar_apenas_no_habilitado(self):
        VinculoFamiliar.objects.create(aluno=self.outro_aluno,
            responsavel=self.responsavel, ativo=True, mesclar_perfis=True)
        resposta_primeiro = self.cliente_familia.get(reverse('atividade-detalhe', args=[self.atividade_vinculada.pk]))
        resposta_segundo = self.cliente_familia.get(reverse('atividade-detalhe', args=[self.atividade_alheia.pk]))
        self.assertFalse(resposta_primeiro.context['pode_enviar_atividade'])
        self.assertTrue(resposta_segundo.context['pode_enviar_atividade'])
        self.assertNotContains(resposta_primeiro, 'Enviar atividade para avaliação')
        self.assertContains(resposta_segundo, 'Enviar atividade para avaliação')
        self.assertEqual(self.cliente_familia.post(
            reverse('api-solicitar-conclusao', args=[self.atividade_vinculada.pk]),
            {'resposta_aluno': 'Indevida'}).status_code, 404)
        self.assertEqual(self.cliente_familia.post(
            reverse('api-solicitar-conclusao', args=[self.atividade_alheia.pk]),
            {'resposta_aluno': 'Com permissão'}).status_code, 201)

    def test_revogar_vinculo_remove_consulta_e_envio(self):
        self.vinculo.ativo = False
        self.vinculo.save(update_fields=['ativo'])
        self.assertEqual(self.cliente_familia.get(
            reverse('atividade-detalhe', args=[self.atividade_vinculada.pk])).status_code, 403)
        self.assertEqual(self.cliente_familia.post(
            reverse('api-solicitar-conclusao', args=[self.atividade_vinculada.pk]),
            {'resposta_aluno': 'Tentativa'}).status_code, 404)
        self.assertNotContains(self.cliente_familia.get(reverse('minhas-atividades')),
                               'Ler para a família')

    def test_google_agenda_disponivel_para_responsavel_sem_mesclar(self):
        lista = self.cliente_familia.get(reverse('minhas-atividades'))
        self.assertContains(lista, reverse('google-conectar'))
        self.assertContains(self.cliente_familia.get(reverse('meus-dados')), reverse('google-conectar'))
        conexao = ConexaoGoogle.objects.create(usuario=self.responsavel.usuario,
            identidade='familia-identidade', credenciais='credenciais-ficticias')
        with patch.object(google, 'enviar_atividade', return_value='evento-da-familia') as enviar:
            resposta = self.cliente_familia.post(reverse('google-sincronizar',
                                                       args=[self.atividade_vinculada.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(enviar.call_count, 1)
        self.assertTrue(SincronizacaoGoogle.objects.filter(usuario=conexao.usuario,
            atividade=self.atividade_vinculada).exists())
        with patch.object(google, 'enviar_atividade') as enviar:
            resposta = self.cliente_familia.post(reverse('google-sincronizar',
                                                       args=[self.atividade_alheia.pk]))
        self.assertEqual(resposta.status_code, 404)
        enviar.assert_not_called()
