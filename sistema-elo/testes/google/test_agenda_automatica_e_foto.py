from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from aplicacao.servicos import google_calendar as google
from aplicacao.models import Atividade, ConexaoGoogle, SincronizacaoGoogle
from aplicacao.servicos.sincronizacao_automatica import sincronizar_atividade, sincronizar_usuario
from testes.base import CenarioTestCase


class PerfilEloTests(CenarioTestCase):
    def test_menu_perfil_tem_iniciais_e_sair_separado(self):
        resposta = self.cliente(self.aluno).get(reverse('pagina-inicial'))
        self.assertContains(resposta, 'AT')
        self.assertContains(resposta, reverse('meus-dados'))
        self.assertContains(resposta, reverse('trocar-senha'))
        self.assertContains(resposta, 'Sair da conta')

    def test_meus_dados_e_atividades_tem_conectar_google(self):
        cliente = self.cliente(self.aluno)
        self.assertContains(cliente.get(reverse('meus-dados')), reverse('google-conectar'))
        self.assertContains(cliente.get(reverse('minhas-atividades')), reverse('google-conectar'))

    def test_upload_foto_privada_e_rejeicao_de_extensao(self):
        cliente = self.cliente(self.aluno)
        with TemporaryDirectory() as pasta, override_settings(MEDIA_ROOT=pasta):
            ruim = SimpleUploadedFile('foto.pdf', b'%PDF-1.4', content_type='application/pdf')
            cliente.post(reverse('foto-perfil-alterar'), {'foto': ruim})
            self.aluno.usuario.refresh_from_db()
            self.assertFalse(self.aluno.usuario.foto_perfil)
            buffer = BytesIO()
            Image.new('RGB', (100, 120), 'blue').save(buffer, format='JPEG')
            arquivo = SimpleUploadedFile('foto.jpg', buffer.getvalue(), content_type='image/jpeg')
            resposta = cliente.post(reverse('foto-perfil-alterar'), {'foto': arquivo})
            self.assertEqual(resposta.status_code, 302)
            self.aluno.usuario.refresh_from_db()
            self.assertTrue(self.aluno.usuario.foto_perfil.name.endswith('.jpg'))
            resposta_foto = cliente.get(reverse('foto-perfil'))
            self.assertEqual(resposta_foto.status_code, 200)
            self.assertEqual(resposta_foto['Content-Type'], 'image/jpeg')
            b''.join(resposta_foto.streaming_content)
            self.assertEqual(self.cliente(self.outro_aluno).get(reverse('foto-perfil')).status_code, 404)
            cliente.post(reverse('foto-perfil-remover'))
            self.aluno.usuario.refresh_from_db()
            self.assertFalse(self.aluno.usuario.foto_perfil)


class AgendaAutomaticaTests(CenarioTestCase):
    def conectar(self, pessoa):
        return ConexaoGoogle.objects.create(usuario=pessoa.usuario, identidade=f'identidade-{pessoa.pk}',
                                            credenciais='credenciais-ficticias')

    def test_criacao_edicao_cancelamento_enviam_a_aluno_e_responsavel_sem_duplicar(self):
        self.conectar(self.aluno)
        self.conectar(self.responsavel)
        self.vinculo.mesclar_perfis = False
        self.vinculo.save()
        with patch.object(google, 'enviar_atividade', side_effect=lambda conexao, atividade, ident: ident) as enviar:
            with self.captureOnCommitCallbacks(execute=True):
                atividade = self.atividade(data_entrega=timezone.localdate() + timedelta(days=2))
            self.assertEqual(SincronizacaoGoogle.objects.filter(atividade=atividade).count(), 2)
            ids_antes = dict(SincronizacaoGoogle.objects.filter(atividade=atividade).values_list('usuario_id','evento_id'))
            self.assertEqual(enviar.call_count, 2)
            with self.captureOnCommitCallbacks(execute=True):
                atividade.titulo = 'Novo nome'
                atividade.data_entrega += timedelta(days=1)
                atividade.save()
            self.assertEqual(SincronizacaoGoogle.objects.filter(atividade=atividade).count(), 2)
            self.assertEqual(dict(SincronizacaoGoogle.objects.filter(atividade=atividade).values_list('usuario_id','evento_id')), ids_antes)
            self.assertEqual(enviar.call_count, 4)
        with patch.object(google, 'excluir_evento') as excluir:
            with self.captureOnCommitCallbacks(execute=True):
                atividade.situacao = 'CANCELADA'
                atividade.save()
            self.assertEqual(excluir.call_count, 2)
            self.assertFalse(SincronizacaoGoogle.objects.filter(atividade=atividade).exists())

    def test_atividade_de_outro_aluno_nao_vao_para_contas_sem_vinculo(self):
        self.conectar(self.aluno)
        self.conectar(self.responsavel)
        atividade = self.atividade(aluno=self.outro_aluno, data_entrega=timezone.localdate() + timedelta(days=3))
        with patch.object(google, 'enviar_atividade') as enviar:
            sincronizar_atividade(atividade.pk)
        enviar.assert_not_called()

    def test_conexao_posterior_envia_atividades_existentes(self):
        atividade = self.atividade(data_entrega=timezone.localdate() + timedelta(days=5))
        self.conectar(self.responsavel)
        with patch.object(google, 'enviar_atividade', side_effect=lambda conexao, atividade, identificador: identificador):
            quantas, erros = sincronizar_usuario(self.responsavel.usuario)
        self.assertEqual((quantas, erros), (1, 0))
        self.assertTrue(SincronizacaoGoogle.objects.filter(atividade=atividade, usuario=self.responsavel.usuario).exists())

    def test_exclusao_remove_eventos_ja_enviados(self):
        self.conectar(self.aluno)
        atividade = self.atividade(data_entrega=timezone.localdate() + timedelta(days=1))
        SincronizacaoGoogle.objects.create(usuario=self.aluno.usuario, atividade=atividade,
                                            identidade=f'identidade-{self.aluno.pk}', evento_id='eloeventoid')
        with patch.object(google, 'excluir_evento') as excluir:
            with self.captureOnCommitCallbacks(execute=True):
                atividade.delete()
        excluir.assert_called_once()

    def test_conexao_pelo_perfil_retorna_ao_perfil(self):
        cliente = self.cliente(self.aluno)
        resposta = cliente.post(reverse('google-conectar'), {'origem': 'perfil'})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(cliente.session['google_oauth']['origem'], 'perfil')
        fluxo = cliente.session['google_oauth']
        with patch.object(google, 'trocar_codigo', return_value=('hash', 'cifrado')):
            resposta = cliente.get(reverse('google-retorno'), {'state': fluxo['state'], 'code':'codigo'})
        self.assertRedirects(resposta, reverse('meus-dados'), fetch_redirect_response=False)
        self.assertTrue(ConexaoGoogle.objects.filter(usuario=self.aluno.usuario).exists())
