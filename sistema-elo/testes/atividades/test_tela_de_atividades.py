from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from aplicacao.models import SolicitacaoConclusao
from testes.base import CenarioTestCase


class AtividadesUnificadasTests(CenarioTestCase):
    def test_todas_as_abas_usam_uma_unica_tela(self):
        cliente = self.cliente(self.professor)
        for filtro in ('todas', 'pendentes', 'aprovacoes', 'concluidas', 'canceladas', 'historico'):
            with self.subTest(filtro=filtro):
                resposta = cliente.get(reverse('atividade-listar'), {'filtro': filtro})
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.templates[0].name, 'aplicacao/atividades/atividades.html')
                self.assertEqual(resposta.context['pagina_ativa'], 'atividades')
                self.assertContains(resposta, 'Histórico')
                self.assertContains(resposta, 'Aguardando avaliação')

    def test_rotas_antigas_levam_a_tela_unica(self):
        cliente = self.cliente(self.professor)
        for rota, visao in [('atividade-historico', 'historico'), ('aprovacoes', 'aprovacoes')]:
            with self.subTest(rota=rota):
                resposta = cliente.get(reverse(rota))
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.context['visao'], visao)
                self.assertTemplateUsed(resposta, 'aplicacao/atividades/atividades.html')

    def test_pendentes_nao_repetem_entregas_em_avaliacao(self):
        aguardando = self.atividade(titulo='Em avaliação')
        livre = self.atividade(titulo='Por fazer')
        SolicitacaoConclusao.objects.create(
            atividade=aguardando, aluno=self.aluno, solicitante=self.aluno.usuario, situacao='PENDENTE')
        cliente = self.cliente(self.professor)
        resposta = cliente.get(reverse('atividade-listar'), {'filtro': 'pendentes'})
        self.assertContains(resposta, livre.titulo)
        self.assertNotContains(resposta, aguardando.titulo)
        resposta = cliente.get(reverse('atividade-listar'), {'filtro': 'aprovacoes'})
        self.assertContains(resposta, aguardando.titulo)
        self.assertContains(resposta, 'Aprovar realização')
        resposta = cliente.get(reverse('atividade-listar'))
        self.assertContains(resposta, 'Aguardando avaliação')

    def test_historico_reune_atrasadas_concluidas_e_canceladas(self):
        atrasada = self.atividade(titulo='Vencida', data_entrega=timezone.localdate() - timedelta(days=10))
        concluida = self.atividade(titulo='Concluída', situacao='CONCLUIDA', data_entrega=timezone.localdate() + timedelta(days=10))
        cancelada = self.atividade(titulo='Cancelada', situacao='CANCELADA')
        futura = self.atividade(titulo='Futura', data_entrega=timezone.localdate() + timedelta(days=10))
        cliente = self.cliente(self.professor)
        resposta = cliente.get(reverse('atividade-listar'), {'filtro': 'historico'})
        for tarefa in (atrasada, concluida, cancelada):
            self.assertContains(resposta, tarefa.titulo)
        self.assertNotContains(resposta, futura.titulo)
        resposta = cliente.get(reverse('atividade-listar'), {'filtro': 'historico', 'situacao': 'CONCLUIDA'})
        self.assertContains(resposta, concluida.titulo)
        self.assertNotContains(resposta, atrasada.titulo)

    def test_filtros_nao_ampliam_permissoes_profissionais(self):
        propria = self.atividade(titulo='Aluno autorizado')
        privada = self.atividade(aluno=self.outro_aluno, titulo='Outro aluno', professor=self.outro_professor)
        cliente = self.cliente(self.professor)
        for filtro in ('todas', 'pendentes', 'aprovacoes', 'concluidas', 'historico'):
            with self.subTest(filtro=filtro):
                resposta = cliente.get(reverse('atividade-listar'), {'filtro': filtro,
                                                                     'aluno': self.outro_aluno.pk})
                self.assertEqual(resposta.status_code, 200)
                self.assertNotContains(resposta, privada.titulo)
        self.assertEqual(self.cliente(self.aluno).get(reverse('atividade-listar')).status_code, 403)
        self.assertEqual(self.cliente(self.responsavel).get(reverse('aprovacoes')).status_code, 403)

    def test_conteudos_selecionados_continuam_associados_ao_progresso(self):
        tarefa = self.atividade(situacao='CONCLUIDA')
        self.assertEqual(tarefa.disciplina, self.disciplina)
        resposta = self.cliente(self.aluno).get(reverse('pagina-inicial'))
        self.assertEqual(resposta.context['progresso']['percentual'], 100)
