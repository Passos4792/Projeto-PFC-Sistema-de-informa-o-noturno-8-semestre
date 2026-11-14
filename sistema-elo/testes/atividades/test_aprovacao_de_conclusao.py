from unittest.mock import patch
from django.test import Client
from django.urls import reverse
from aplicacao.models import RegistroAuditoria, SolicitacaoConclusao
from testes.base import CenarioTestCase


class SolicitacoesTests(CenarioTestCase):
    def setUp(self):
        self.tarefa = self.atividade()
        self.url = reverse('api-solicitar-conclusao', args=[self.tarefa.pk])

    def solicitar(self, pessoa=None, **dados):
        return self.cliente(pessoa or self.aluno).post(self.url, dados, content_type='application/json')

    def decidir(self, solicitacao, pessoa=None, **dados):
        return self.cliente(pessoa or self.professor).patch(
            reverse('api-decidir-conclusao', args=[solicitacao.pk]),
            dados or {'decisao': 'APROVADA'}, content_type='application/json')

    def pedido(self):
        self.assertEqual(self.solicitar(mensagem='Terminei em casa').status_code, 201)
        return SolicitacaoConclusao.objects.get(atividade=self.tarefa)

    def test_aluno_solicita_sem_concluir_atividade_automaticamente(self):
        pedido = self.pedido()
        self.tarefa.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')
        self.assertEqual(pedido.aluno_id, self.aluno.pk)
        self.assertEqual(pedido.solicitante_id, self.aluno.usuario_id)
        self.assertEqual(self.tarefa.situacao, 'PENDENTE')
        self.assertIsNone(self.tarefa.concluida_em)

    def test_responsavel_vinculado_pode_solicitar(self):
        self.assertEqual(self.solicitar(self.responsavel).status_code, 201)
        self.assertEqual(SolicitacaoConclusao.objects.get().solicitante_id, self.responsavel.usuario_id)

    def test_vinculo_inativo_nao_autoriza_responsavel(self):
        self.vinculo.ativo = False
        self.vinculo.save()
        self.assertEqual(self.solicitar(self.responsavel).status_code, 404)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_outro_aluno_nao_pode_solicitar(self):
        self.assertEqual(self.solicitar(self.outro_aluno).status_code, 404)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_professor_nao_pode_solicitar(self):
        self.assertEqual(self.solicitar(self.professor).status_code, 403)

    def test_anonimo_recebe_erro_json(self):
        resposta = Client().post(self.url, {}, content_type='application/json')
        self.assertEqual(resposta.status_code, 403)
        self.assertIn('detail', resposta.json())

    def test_duplicata_do_aluno_ou_responsavel_e_bloqueada(self):
        self.pedido()
        for pessoa in (self.aluno, self.responsavel):
            with self.subTest(perfil=pessoa.usuario.tipo_perfil):
                self.assertEqual(self.solicitar(pessoa).status_code, 409)
        self.assertEqual(SolicitacaoConclusao.objects.count(), 1)

    def test_cancelada_ou_concluida_nao_aceita_solicitacao(self):
        for situacao in ('CANCELADA', 'CONCLUIDA'):
            with self.subTest(situacao=situacao):
                self.tarefa.situacao = situacao
                self.tarefa.save()
                self.assertEqual(self.solicitar().status_code, 409)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_mensagem_acima_do_limite_e_rejeitada(self):
        self.assertEqual(self.solicitar(mensagem='x' * 501).status_code, 400)
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_aprovacao_conclui_atividade_e_registra_professor_data_e_auditoria(self):
        pedido = self.pedido()
        self.assertEqual(self.decidir(pedido).status_code, 200)
        pedido.refresh_from_db()
        self.tarefa.refresh_from_db()
        self.assertEqual(pedido.situacao, 'APROVADA')
        self.assertEqual(pedido.professor_id, self.professor.pk)
        self.assertIsNotNone(pedido.respondido_em)
        self.assertEqual(self.tarefa.situacao, 'CONCLUIDA')
        self.assertIsNotNone(self.tarefa.concluida_em)
        self.assertTrue(RegistroAuditoria.objects.filter(acao='APROVACAO', objeto_id=str(pedido.pk)).exists())
        self.assertTrue(RegistroAuditoria.objects.filter(acao='EDICAO', entidade='Atividade').exists())

    def test_recusa_exige_justificativa(self):
        pedido = self.pedido()
        for justificativa in ('', '   '):
            with self.subTest(justificativa=justificativa):
                self.assertEqual(self.decidir(pedido, decisao='RECUSADA', resposta=justificativa).status_code, 400)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')
        self.assertIsNone(pedido.respondido_em)

    def test_recusa_preserva_atividade_pendente_e_permite_reenvio(self):
        pedido = self.pedido()
        self.assertEqual(self.decidir(pedido, decisao='RECUSADA', resposta='Revisar exercício 2').status_code, 200)
        pedido.refresh_from_db()
        self.tarefa.refresh_from_db()
        self.assertEqual(pedido.resposta, 'Revisar exercício 2')
        self.assertEqual(pedido.situacao, 'RECUSADA')
        self.assertEqual(self.tarefa.situacao, 'PENDENTE')
        self.assertIsNone(self.tarefa.concluida_em)
        self.assertEqual(self.solicitar().status_code, 201)
        self.assertEqual(SolicitacaoConclusao.objects.filter(situacao='PENDENTE').count(), 1)
        self.assertTrue(RegistroAuditoria.objects.filter(acao='RECUSA').exists())

    def test_decisao_nao_pode_ser_aplicada_duas_vezes(self):
        pedido = self.pedido()
        self.assertEqual(self.decidir(pedido).status_code, 200)
        self.assertEqual(self.decidir(pedido, self.gestor).status_code, 409)
        self.assertEqual(RegistroAuditoria.objects.filter(acao='APROVACAO').count(), 1)

    def test_outro_professor_nao_decide(self):
        pedido = self.pedido()
        self.assertEqual(self.decidir(pedido, self.outro_professor).status_code, 404)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')

    def test_gestor_pode_decidir_atividade_de_outro_professor(self):
        pedido = self.pedido()
        self.assertEqual(self.decidir(pedido, self.gestor).status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.professor_id, self.gestor.pk)

    def test_aluno_e_responsavel_nao_podem_aprovar(self):
        pedido = self.pedido()
        for pessoa in (self.aluno, self.responsavel):
            with self.subTest(perfil=pessoa.usuario.tipo_perfil):
                self.assertEqual(self.decidir(pedido, pessoa).status_code, 403)

    def test_decisao_invalida_nao_altera_pedido(self):
        pedido = self.pedido()
        self.assertEqual(self.decidir(pedido, decisao='CONCLUIDA').status_code, 400)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')

    def test_atividade_alterada_invalida_decisao_antiga(self):
        pedido = self.pedido()
        self.tarefa.aluno = self.outro_aluno
        self.tarefa.save()
        self.assertEqual(self.decidir(pedido, self.gestor).status_code, 409)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')

    def test_falha_de_auditoria_reverte_solicitacao(self):
        cliente = self.cliente(self.aluno)
        with patch('aplicacao.views.api.registrar', side_effect=RuntimeError('falha simulada')):
            with self.assertRaises(RuntimeError):
                cliente.post(self.url, {}, content_type='application/json')
        self.assertFalse(SolicitacaoConclusao.objects.exists())

    def test_falha_de_auditoria_reverte_aprovacao_e_conclusao(self):
        pedido = self.pedido()
        cliente = self.cliente(self.professor)
        with patch('aplicacao.views.api.registrar', side_effect=RuntimeError('falha simulada')):
            with self.assertRaises(RuntimeError):
                cliente.patch(reverse('api-decidir-conclusao', args=[pedido.pk]),
                              {'decisao': 'APROVADA'}, content_type='application/json')
        pedido.refresh_from_db()
        self.tarefa.refresh_from_db()
        self.assertEqual(pedido.situacao, 'PENDENTE')
        self.assertEqual(self.tarefa.situacao, 'PENDENTE')
        self.assertIsNone(self.tarefa.concluida_em)

    def test_api_exige_csrf_mesmo_com_sessao_autenticada(self):
        cliente = self.cliente(self.aluno, csrf=True)
        self.assertEqual(cliente.post(self.url, {}, content_type='application/json').status_code, 403)
        cliente.get(reverse('minhas-atividades'))
        token = cliente.cookies['csrftoken'].value
        self.assertEqual(cliente.post(self.url, {}, content_type='application/json',
                                     HTTP_X_CSRFTOKEN=token).status_code, 201)

    def test_get_nao_cria_solicitacao(self):
        self.assertEqual(self.cliente(self.aluno).get(self.url).status_code, 405)
        self.assertFalse(SolicitacaoConclusao.objects.exists())
