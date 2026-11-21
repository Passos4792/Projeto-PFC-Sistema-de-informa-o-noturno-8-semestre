"""Regressões do cancelamento automático/manual de pedidos de senha."""
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from aplicacao.models import RegistroAuditoria, SolicitacaoSenha
from testes.base import CenarioTestCase, SENHA


@override_settings(ELO_2FA_ATIVO=False)
class CancelarSolicitacaoTests(CenarioTestCase):
    def pedido(self, usuario):
        resposta = self.client.post(reverse('recuperar-senha'), {'usuario': usuario})
        self.assertEqual(resposta.status_code, 200)
        return SolicitacaoSenha.objects.latest('pk')

    def login_normal(self, username, senha=SENHA):
        return self.client.post(reverse('login'), {'username': username, 'password': senha})

    def test_aluno_que_lembra_senha_cancela_pedido_sem_alterar_senha(self):
        pedido = self.pedido('ana')
        self.assertEqual(self.login_normal('ana').status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.CANCELADA)
        self.assertIsNotNone(pedido.atendida_em)
        self.assertTrue(self.aluno.usuario.conta.check_password(SENHA))
        operador = self.cliente(self.gestor)
        self.assertEqual(operador.post(reverse('solicitacao-senha-atender', args=[pedido.pk]),
                                     {'new_password1': 'NovaSenhaNaoUsar123!',
                                      'new_password2': 'NovaSenhaNaoUsar123!'}).status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.CANCELADA)
        self.assertTrue(self.aluno.usuario.conta.check_password(SENHA))
        self.assertTrue(RegistroAuditoria.objects.filter(
            entidade='solicitacao_senha', objeto_id=str(pedido.pk), acao='SENHA').exists())

    def test_responsavel_e_professor_tambem_cancelam_ao_entrar(self):
        for username in ('responsavel', 'professor'):
            with self.subTest(perfil=username):
                self.client.logout()
                pedido = self.pedido(username)
                self.assertEqual(self.login_normal(username).status_code, 302)
                pedido.refresh_from_db()
                self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.CANCELADA)

    def test_senha_incorreta_nao_cancela_pedido(self):
        pedido = self.pedido('ana')
        self.assertEqual(self.login_normal('ana', 'SenhaErrada999!').status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.PENDENTE)

    def test_login_de_outra_pessoa_nao_cancela_o_pedido(self):
        pedido = self.pedido('ana')
        self.assertEqual(self.login_normal('bruno').status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.PENDENTE)

    def test_pedido_atendido_nao_e_reclassificado(self):
        pedido = self.pedido('ana')
        pedido.situacao = SolicitacaoSenha.Situacao.ATENDIDA
        pedido.atendida_em = timezone.now()
        pedido.save(update_fields=['situacao', 'atendida_em'])
        self.assertEqual(self.login_normal('ana').status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.ATENDIDA)

    def test_pedido_legado_sem_usuario_alvo_tambem_e_cancelado(self):
        legado = SolicitacaoSenha.objects.create(
            aluno=self.aluno, professor=self.professor,
            usuario_alvo=None, situacao=SolicitacaoSenha.Situacao.PENDENTE)
        self.assertEqual(self.login_normal('ana').status_code, 302)
        legado.refresh_from_db()
        self.assertEqual(legado.situacao, SolicitacaoSenha.Situacao.CANCELADA)

    def test_professor_vinculado_pode_negar_pedido_de_aluno(self):
        pedido = self.pedido('ana')
        url = reverse('solicitacao-senha-negar', args=[pedido.pk])
        resposta = self.cliente(self.professor).post(url)
        self.assertEqual(resposta.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.NEGADA)
        self.assertIsNotNone(pedido.atendida_em)
        self.assertTrue(self.aluno.usuario.conta.check_password(SENHA))
        self.assertEqual(self.cliente(self.professor).get(
            reverse('solicitacao-senha-atender', args=[pedido.pk])).status_code, 302)

    def test_gestor_pode_negar_professor_mas_colega_nao(self):
        pedido = self.pedido('professor')
        url = reverse('solicitacao-senha-negar', args=[pedido.pk])
        self.assertEqual(self.cliente(self.outro_professor).post(url).status_code, 404)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.PENDENTE)
        self.assertEqual(self.cliente(self.gestor).post(url).status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.NEGADA)

    def test_nao_pode_negar_pedido_por_get_e_repeticao_nao_altera_historico(self):
        pedido = self.pedido('ana')
        url = reverse('solicitacao-senha-negar', args=[pedido.pk])
        operador = self.cliente(self.gestor)
        self.assertEqual(operador.get(url).status_code, 405)
        self.assertEqual(operador.post(url).status_code, 302)
        pedido.refresh_from_db()
        resolvido = pedido.atendida_em
        self.assertEqual(operador.post(url).status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.atendida_em, resolvido)
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.NEGADA)

    def test_usuario_nao_pode_negar_pedido_de_terceiro(self):
        pedido = self.pedido('ana')
        self.assertEqual(self.cliente(self.responsavel).post(
            reverse('solicitacao-senha-negar', args=[pedido.pk])).status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.PENDENTE)

    def test_lista_distingue_cancelados_e_negados(self):
        pedido = self.pedido('ana')
        self.assertEqual(self.login_normal('ana').status_code, 302)
        cliente = self.cliente(self.gestor)
        self.assertContains(cliente.get(reverse('solicitacao-senha-listar')+'?filtro=canceladas'), 'Cancelada')
        self.assertNotContains(cliente.get(reverse('solicitacao-senha-listar')+'?filtro=pendentes'),
                               'ana Teste')
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.CANCELADA)


class CancelarSomenteApos2FATests(CenarioTestCase):
    @override_settings(ELO_2FA_ATIVO=True)
    def test_professor_precisa_confirmar_2fa_antes_de_cancelar(self):
        from aplicacao.servicos.duplo_fator import (
            codigo_totp, decifrar_segredo, obter_configuracao,
        )
        self.client.post(reverse('recuperar-senha'), {'usuario': 'professor'})
        pedido = SolicitacaoSenha.objects.latest('pk')
        resposta = self.client.post(reverse('login'), {'username': 'professor', 'password': SENHA})
        self.assertEqual(resposta.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.PENDENTE)
        config = obter_configuracao(self.professor.usuario.conta, criar=True)
        segredo = decifrar_segredo(config.segredo_criptografado)
        codigo = codigo_totp(segredo, int(timezone.now().timestamp()) // 30)
        resposta_falha = self.client.post(reverse('2fa-configurar'), {'codigo': '000000'})
        self.assertEqual(resposta_falha.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.PENDENTE)
        resposta = self.client.post(reverse('2fa-configurar'), {'codigo': codigo})
        self.assertEqual(resposta.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.CANCELADA)
