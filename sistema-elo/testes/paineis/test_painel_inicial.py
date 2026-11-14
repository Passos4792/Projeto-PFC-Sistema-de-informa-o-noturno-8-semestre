from datetime import date
from django.urls import reverse
from aplicacao.models import Atividade, VinculoFamiliar, VinculoProfissional
from testes.base import CenarioTestCase


class PainelInicialProgressoTests(CenarioTestCase):
    def test_calcula_somente_concluidas_e_exclui_canceladas(self):
        self.atividade(situacao='CONCLUIDA', titulo='Concluída')
        self.atividade(situacao='PENDENTE', titulo='Pendente')
        self.atividade(situacao='CANCELADA', titulo='Cancelada')
        resposta = self.cliente(self.aluno).get(reverse('pagina-inicial'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['progresso'], {
            'total': 2, 'realizadas': 1, 'pendentes': 1, 'percentual': 50,
        })
        self.assertContains(resposta, 'Progresso das atividades')
        self.assertNotContains(resposta, 'Frequência mínima')

    def test_apenas_solicitar_conclusao_nao_aumenta_progresso(self):
        from aplicacao.models import SolicitacaoConclusao
        tarefa = self.atividade(situacao='PENDENTE')
        SolicitacaoConclusao.objects.create(
            atividade=tarefa, aluno=self.aluno,
            solicitante=self.aluno.usuario, situacao='PENDENTE',
        )
        resposta = self.cliente(self.aluno).get(reverse('pagina-inicial'))
        self.assertEqual(resposta.context['progresso']['percentual'], 0)

    def test_sem_atividades_exibe_estado_vazio(self):
        resposta = self.cliente(self.aluno).get(reverse('pagina-inicial'))
        self.assertEqual(resposta.context['progresso']['total'], 0)
        self.assertContains(resposta, 'Ainda não há atividades cadastradas')

    def test_professor_pode_trocar_somente_entre_alunos_aee(self):
        self.atividade(situacao='CONCLUIDA')
        resposta = self.cliente(self.professor).get(reverse('pagina-inicial'))
        self.assertEqual(resposta.context['aluno_selecionado'], self.aluno)
        self.assertEqual(resposta.context['progresso']['percentual'], 100)
        self.assertEqual(self.cliente(self.professor).get(
            reverse('pagina-inicial'), {'aluno': self.outro_aluno.pk}).status_code, 403)

    def test_professor_aee_com_dois_alunos_pode_alternar_o_filtro(self):
        VinculoProfissional.objects.create(
            aluno=self.outro_aluno, professor=self.professor,
            funcao='AEE', data_inicio=date(2026, 1, 1),
        )
        self.atividade(situacao='CONCLUIDA')
        self.atividade(aluno=self.outro_aluno, situacao='PENDENTE')
        cliente = self.cliente(self.professor)
        resposta = cliente.get(reverse('pagina-inicial'), {'aluno': self.outro_aluno.pk})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['progresso']['percentual'], 0)
        self.assertEqual(len(resposta.context['alunos_disponiveis']), 2)
        self.assertTrue(resposta.context['mostrar_filtro_aluno'])
        resposta = cliente.get(reverse('pagina-inicial'), {'aluno': self.aluno.pk})
        self.assertEqual(resposta.context['progresso']['percentual'], 100)

    def test_gestor_pode_filtrar_varios_alunos(self):
        self.atividade(situacao='CONCLUIDA')
        self.atividade(aluno=self.outro_aluno, situacao='PENDENTE')
        cliente = self.cliente(self.gestor)
        resposta = cliente.get(reverse('pagina-inicial'), {'aluno': self.outro_aluno.pk})
        self.assertEqual(resposta.context['aluno_selecionado'], self.outro_aluno)
        self.assertEqual(resposta.context['progresso']['percentual'], 0)
        self.assertTrue(resposta.context['mostrar_filtro_aluno'])
        self.assertContains(resposta, 'selecionar-aluno')
        self.assertContains(resposta, 'Total de professores')

    def test_responsavel_ve_somente_os_filhos_vinculados(self):
        self.atividade(situacao='CONCLUIDA')
        self.atividade(aluno=self.outro_aluno, situacao='PENDENTE')
        cliente = self.cliente(self.responsavel)
        self.assertEqual(cliente.get(reverse('pagina-inicial'),
                                    {'aluno': self.outro_aluno.pk}).status_code, 403)
        VinculoFamiliar.objects.create(aluno=self.outro_aluno, responsavel=self.responsavel)
        resposta = cliente.get(reverse('pagina-inicial'), {'aluno': self.outro_aluno.pk})
        self.assertEqual(resposta.context['progresso']['percentual'], 0)
        self.assertTrue(resposta.context['mostrar_filtro_aluno'])
