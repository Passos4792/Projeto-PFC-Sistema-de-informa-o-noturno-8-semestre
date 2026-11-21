import json
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from aplicacao.models import Atividade, SolicitacaoConclusao
from testes.base import CenarioTestCase


class ReenvioAposRevisao(CenarioTestCase):
    def setUp(self):
        self.tarefa = self.atividade(tipo_entrega='ENVIO', data_entrega=timezone.localdate() + timedelta(days=5))

    def _decidir(self, solicitacao, decisao, resposta=''):
        return self.cliente(self.professor).patch(
            reverse('api-decidir-conclusao', args=[solicitacao.pk]),
            data=json.dumps({'decisao': decisao, 'resposta': resposta}), content_type='application/json')

    def test_professor_recebe_reenvio_do_responsavel_apos_pedir_revisao(self):
        familia = self.cliente(self.responsavel)
        familia.post(reverse('atividade-enviar', args=[self.tarefa.pk]), {'resposta_aluno': 'Primeira versão.'})
        primeira = SolicitacaoConclusao.objects.get()
        self.assertEqual(self._decidir(primeira, 'RECUSADA', 'Complete a última questão.').status_code, 200)

        familia.post(reverse('atividade-enviar', args=[self.tarefa.pk]), {'resposta_aluno': 'Versão revisada.'})
        self.assertEqual(SolicitacaoConclusao.objects.filter(situacao='PENDENTE').count(), 1)

        professor = self.cliente(self.professor)
        tela = professor.get(reverse('aprovacoes'))
        self.assertContains(tela, 'Versão revisada.')
        menu = professor.get(reverse('atividade-listar'))
        self.assertEqual(menu.context['aprovacoes_pendentes'], 1)


class ReaberturaDeAtividadeConcluida(CenarioTestCase):
    def _dados(self, tarefa, situacao):
        return {'aluno': tarefa.aluno_id, 'professor': tarefa.professor_id, 'disciplina': tarefa.disciplina_id,
                'titulo': tarefa.titulo, 'descricao': 'Instruções.', 'tipo_entrega': tarefa.tipo_entrega,
                'data_entrega': tarefa.data_entrega.isoformat(), 'situacao': situacao}

    def test_professor_reabre_e_conclui_novamente(self):
        tarefa = self.atividade(situacao='CONCLUIDA', descricao='Instruções.')
        SolicitacaoConclusao.objects.create(atividade=tarefa, aluno=self.aluno, solicitante=self.aluno.usuario,
                                            situacao='APROVADA', professor=self.professor)
        professor = self.cliente(self.professor)
        url = reverse('atividade-editar', args=[tarefa.pk])

        self.assertEqual(professor.post(url, self._dados(tarefa, 'PENDENTE')).status_code, 302)
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.situacao, 'PENDENTE')

        formulario = professor.get(url).context['formulario']
        self.assertIn('CONCLUIDA', [valor for valor, _ in formulario.fields['situacao'].choices])
        self.assertEqual(professor.post(url, self._dados(tarefa, 'CONCLUIDA')).status_code, 302)
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.situacao, Atividade.Situacao.CONCLUIDA)

    def test_atividade_nunca_aprovada_continua_sem_opcao_concluida(self):
        tarefa = self.atividade(descricao='Instruções.')
        formulario = self.cliente(self.professor).get(
            reverse('atividade-editar', args=[tarefa.pk])).context['formulario']
        self.assertNotIn('CONCLUIDA', [valor for valor, _ in formulario.fields['situacao'].choices])
