from datetime import timedelta
from unittest.mock import patch
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from aplicacao.models import RegistroAuditoria, SolicitacaoSenha
from testes.base import CenarioTestCase, SENHA


class RecuperacaoSenhaTests(CenarioTestCase):
    NOVA = 'Temporaria@98765'

    def enviar(self, usuario='ana'):
        return self.client.post(reverse('recuperar-senha'), {'usuario': usuario})

    def pedido(self):
        self.assertContains(self.enviar(), 'Solicitação recebida')
        return SolicitacaoSenha.objects.get()

    def atender(self, pedido, operador=None):
        return self.cliente(operador or self.professor).post(
            reverse('solicitacao-senha-atender', args=[pedido.pk]),
            {'new_password1': self.NOVA, 'new_password2': self.NOVA})

    def test_envio_publico_normaliza_usuario_e_nao_altera_senha(self):
        resposta = self.enviar(' ANA ')
        self.assertEqual(resposta.status_code, 200)
        pedido = SolicitacaoSenha.objects.get()
        self.assertEqual(pedido.aluno_id, self.aluno.pk)
        self.assertEqual(pedido.professor_id, self.professor.pk)
        self.assertEqual(pedido.situacao, 'PENDENTE')
        self.assertTrue(self.aluno.usuario.conta.check_password(SENHA))

    def test_conta_inexistente_tem_a_mesma_confirmacao_publica(self):
        for usuario in ('ana', 'naoexiste', 'ana'):
            with self.subTest(usuario=usuario):
                resposta = self.enviar(usuario)
                self.assertContains(resposta, 'Solicitação recebida')
                self.assertNotContains(resposta, self.aluno.nome_completo)
        self.assertEqual(SolicitacaoSenha.objects.count(), 1)

    def test_usuario_e_obrigatorio(self):
        resposta = self.enviar('')
        self.assertTrue(resposta.context['formulario'].errors)
        self.assertFalse(SolicitacaoSenha.objects.exists())

    def test_vinculo_ou_aluno_inativo_impede_pedido(self):
        self.vinculo.ativo = False
        self.vinculo.save()
        self.enviar()
        self.assertFalse(SolicitacaoSenha.objects.exists())
        self.vinculo.ativo = True
        self.vinculo.save()
        self.aluno.ativo = False
        self.aluno.save()
        self.enviar()
        self.assertFalse(SolicitacaoSenha.objects.exists())

    def test_origem_e_guardada_como_hash(self):
        pedido = self.pedido()
        self.assertEqual(len(pedido.origem_hash), 64)
        self.assertNotIn('127.0.0.1', pedido.origem_hash)
        self.assertNotIn('ana', pedido.origem_hash)

    def test_csrf_obrigatorio_no_formulario_publico(self):
        cliente = Client(enforce_csrf_checks=True)
        self.assertEqual(cliente.post(reverse('recuperar-senha'), {'usuario': 'ana'}).status_code, 403)
        cliente.get(reverse('recuperar-senha'))
        resposta = cliente.post(reverse('recuperar-senha'),
            {'usuario': 'ana', 'csrfmiddlewaretoken': cliente.cookies['csrftoken'].value})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(SolicitacaoSenha.objects.count(), 1)

    def test_atendimento_invalida_sessao_antiga_e_exige_troca(self):
        antigo = self.cliente(self.aluno)
        pedido = self.pedido()
        self.assertEqual(self.atender(pedido).status_code, 302)
        pedido.refresh_from_db()
        self.aluno.usuario.refresh_from_db()
        self.assertEqual(pedido.situacao, 'ATENDIDA')
        self.assertIsNotNone(pedido.atendida_em)
        self.assertTrue(self.aluno.usuario.troca_senha_obrigatoria)
        self.assertTrue(self.aluno.usuario.conta.check_password(self.NOVA))
        self.assertIn('/login/', antigo.get(reverse('meta-listar')).url)
        novo = Client()
        self.assertTrue(novo.login(username='ana', password=self.NOVA))
        self.assertRedirects(novo.get(reverse('meta-listar')), reverse('trocar-senha'),
                             fetch_redirect_response=False)

    def test_senha_fraca_nao_atende_pedido(self):
        pedido = self.pedido()
        resposta = self.cliente(self.professor).post(
            reverse('solicitacao-senha-atender', args=[pedido.pk]),
            {'new_password1': '123', 'new_password2': '123'})
        self.assertTrue(resposta.context['formulario'].errors)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')

    def test_get_nao_redefine_senha(self):
        pedido = self.pedido()
        resposta = self.cliente(self.professor).get(reverse('solicitacao-senha-atender', args=[pedido.pk]))
        self.assertEqual(resposta.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')
        self.assertTrue(self.aluno.usuario.conta.check_password(SENHA))

    def test_aluno_e_responsavel_nao_acessam_fila_nem_atendimento(self):
        pedido = self.pedido()
        for pessoa in (self.aluno, self.responsavel):
            cliente = self.cliente(pessoa)
            with self.subTest(perfil=pessoa.usuario.tipo_perfil):
                self.assertEqual(cliente.get(reverse('solicitacao-senha-listar')).status_code, 403)
                self.assertEqual(cliente.post(reverse('solicitacao-senha-atender', args=[pedido.pk]),
                    {'new_password1': self.NOVA, 'new_password2': self.NOVA}).status_code, 403)

    def test_outro_professor_nao_recebe_nem_atende_pedido(self):
        pedido = self.pedido()
        cliente = self.cliente(self.outro_professor)
        self.assertNotContains(cliente.get(reverse('solicitacao-senha-listar')), self.aluno.nome_completo)
        self.assertEqual(self.atender(pedido, self.outro_professor).status_code, 404)

    def test_vinculo_desativado_apos_envio_impede_atendimento(self):
        pedido = self.pedido()
        self.vinculo.ativo = False
        self.vinculo.save()
        self.assertEqual(self.atender(pedido).status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')
        self.assertTrue(self.aluno.usuario.conta.check_password(SENHA))

    def test_repetir_atendimento_nao_muda_novamente_a_senha(self):
        pedido = self.pedido()
        self.atender(pedido)
        resposta = self.cliente(self.professor).post(
            reverse('solicitacao-senha-atender', args=[pedido.pk]),
            {'new_password1': 'OutraSenha@98765', 'new_password2': 'OutraSenha@98765'})
        self.assertEqual(resposta.status_code, 302)
        self.aluno.usuario.conta.refresh_from_db()
        self.assertTrue(self.aluno.usuario.conta.check_password(self.NOVA))

    def test_falha_de_auditoria_reverte_atendimento(self):
        pedido = self.pedido()
        cliente = self.cliente(self.professor)
        with patch('aplicacao.views.senhas.registrar', side_effect=RuntimeError('falha simulada')):
            with self.assertRaises(RuntimeError):
                cliente.post(reverse('solicitacao-senha-atender', args=[pedido.pk]),
                             {'new_password1': self.NOVA, 'new_password2': self.NOVA})
        pedido.refresh_from_db()
        self.aluno.usuario.conta.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')
        self.assertTrue(self.aluno.usuario.conta.check_password(SENHA))

    def test_auditoria_nao_armazena_senha_temporaria(self):
        pedido = self.pedido()
        self.atender(pedido)
        self.assertTrue(RegistroAuditoria.objects.filter(acao='SENHA').exists())
        self.assertNotIn(self.NOVA, str(list(RegistroAuditoria.objects.values())))

    def test_limite_de_cinco_pedidos_por_origem_na_janela(self):
        self.enviar()
        origem = SolicitacaoSenha.objects.get().origem_hash
        SolicitacaoSenha.objects.all().update(situacao='ATENDIDA', atendida_em=timezone.now())
        for _ in range(4):
            SolicitacaoSenha.objects.create(aluno=self.aluno, professor=self.professor,
                situacao='ATENDIDA', origem_hash=origem, atendida_em=timezone.now())
        self.enviar()
        self.assertEqual(SolicitacaoSenha.objects.count(), 5)
        SolicitacaoSenha.objects.update(criada_em=timezone.now() - timedelta(minutes=31))
        self.enviar()
        self.assertEqual(SolicitacaoSenha.objects.filter(situacao='PENDENTE').count(), 1)
