from datetime import date, timedelta
from unittest.mock import patch
from django.test import SimpleTestCase
from django.urls import reverse
from aplicacao.forms import FiltroPainel
from aplicacao.servicos.indicadores import dados_metas, dados_painel
from aplicacao.models import Disciplina, SolicitacaoConclusao
from aplicacao.servicos.periodos import limites_periodo
from testes.base import CenarioTestCase, HOJE


class PeriodosTests(SimpleTestCase):
    def test_semana_que_atravessa_o_ano(self):
        self.assertEqual(limites_periodo('SEMANAL', date(2026, 1, 1)),
                         (date(2025, 12, 29), date(2026, 1, 4)))

    def test_fevereiro_bissexto_e_comum(self):
        self.assertEqual(limites_periodo('MENSAL', date(2024, 2, 20)),
                         (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(limites_periodo('MENSAL', date(2026, 2, 20)),
                         (date(2026, 2, 1), date(2026, 2, 28)))

    def test_trimestre_e_semestre_seguem_calendario(self):
        casos = [
            ('TRIMESTRAL', date(2026, 4, 1), date(2026, 4, 1), date(2026, 6, 30)),
            ('TRIMESTRAL', date(2026, 12, 31), date(2026, 10, 1), date(2026, 12, 31)),
            ('SEMESTRAL', date(2026, 6, 30), date(2026, 1, 1), date(2026, 6, 30)),
            ('SEMESTRAL', date(2026, 7, 1), date(2026, 7, 1), date(2026, 12, 31)),
        ]
        for periodo, referencia, inicio, fim in casos:
            with self.subTest(periodo=periodo, referencia=referencia):
                self.assertEqual(limites_periodo(periodo, referencia), (inicio, fim))

    def test_periodo_invalido_e_rejeitado(self):
        with self.assertRaises(ValueError):
            limites_periodo('ANUAL', HOJE)


class ConteudosTests(CenarioTestCase):
    def setUp(self):
        relogio = patch('aplicacao.servicos.indicadores.timezone.localdate', return_value=HOJE)
        relogio.start()
        self.addCleanup(relogio.stop)

    def montar_atividades(self):
        self.atividade(situacao='CONCLUIDA')
        self.atividade(data_entrega=HOJE - timedelta(days=1))
        self.atividade(data_entrega=HOJE + timedelta(days=1))
        self.atividade(data_entrega=None)
        self.atividade(situacao='CANCELADA')
        self.atividade(aluno=self.outro_aluno, situacao='CONCLUIDA')

    def test_responsavel_so_recebe_indicadores_do_aluno_vinculado(self):
        self.montar_atividades()
        resultado = dados_painel(self.responsavel.usuario, {})
        self.assertEqual(resultado['resumo']['alunos'], 1)
        self.assertEqual(resultado['resumo']['realizadas'], 1)
        self.assertEqual({a['aluno_id'] for a in resultado['atividades']}, {self.aluno.pk})

    def test_gestor_pode_filtrar_um_aluno(self):
        self.montar_atividades()
        resultado = dados_painel(self.gestor.usuario, {'aluno': self.outro_aluno})
        self.assertEqual(resultado['resumo']['alunos'], 1)
        self.assertEqual(resultado['resumo']['realizadas'], 1)

    def test_conteudos_contam_realizadas_e_pendentes_sem_canceladas(self):
        self.montar_atividades()
        resultado = dados_painel(self.aluno.usuario, {})
        self.assertEqual(len(resultado['conteudos']), 1)
        conteudo = resultado['conteudos'][0]
        self.assertEqual(conteudo['nome'], 'Matemática')
        self.assertEqual((conteudo['total'], conteudo['realizadas'], conteudo['pendentes']), (4, 1, 3))

    def test_catalogo_vazio_para_aluno_e_completo_para_professor(self):
        Disciplina.objects.create(nome='Português')
        self.assertEqual(dados_painel(self.aluno.usuario, {})['conteudos'], [])
        self.assertEqual(len(dados_painel(self.professor.usuario, {})['conteudos']), 2)

    def test_atividades_antigas_sem_conteudo_continuam_contadas(self):
        self.atividade(disciplina=None, situacao='CONCLUIDA')
        resultado = dados_painel(self.aluno.usuario, {})['conteudos'][0]
        self.assertIsNone(resultado['id'])
        self.assertEqual(resultado['nome'], 'Sem conteúdo definido')
        self.assertEqual(resultado['realizadas'], 1)

    def test_busca_e_intervalo_no_acompanhamento_individual(self):
        self.atividade(titulo='Leitura', data_entrega=HOJE)
        self.atividade(titulo='Outra tarefa', data_entrega=HOJE + timedelta(days=1))
        resultado = dados_painel(self.aluno.usuario, {'inicio': HOJE, 'fim': HOJE, 'busca': 'leitura'})
        self.assertEqual([a['titulo'] for a in resultado['atividades']], ['Leitura'])

    def test_ultima_orientacao_do_professor_aparece_no_painel(self):
        atividade = self.atividade()
        SolicitacaoConclusao.objects.create(atividade=atividade, aluno=self.aluno,
            solicitante=self.aluno.usuario, situacao='RECUSADA', resposta='Revisar a soma')
        resultado = dados_painel(self.aluno.usuario, {})
        self.assertEqual(resultado['atividades'][0]['resposta'], 'Revisar a soma')


class ProgressoMetasTests(CenarioTestCase):
    def setUp(self):
        relogio = patch('aplicacao.servicos.indicadores.timezone.localdate', return_value=HOJE)
        relogio.start()
        self.addCleanup(relogio.stop)

    def test_metas_contam_todos_conteudos_no_periodo_e_excluem_outros_alunos(self):
        meta = self.meta()
        for dia in (date(2026, 11, 1), date(2026, 11, 30)):
            self.atividade(situacao='CONCLUIDA', data_entrega=dia)
        self.atividade(situacao='CONCLUIDA', data_entrega=date(2026, 10, 31))
        self.atividade(situacao='CONCLUIDA', data_entrega=date(2026, 12, 1))
        self.atividade(situacao='CONCLUIDA', data_entrega=None)
        self.atividade(situacao='CANCELADA')
        self.atividade(situacao='CONCLUIDA', aluno=self.outro_aluno)
        self.atividade(situacao='CONCLUIDA', disciplina=Disciplina.objects.create(nome='Artes'))
        self.atividade()
        resultado = dados_metas(self.aluno.usuario, {})['metas'][0]
        self.assertEqual(resultado['id'], meta.pk)
        self.assertEqual(resultado['realizadas'], 3)
        self.assertEqual(resultado['atribuidas'], 4)
        self.assertEqual(resultado['percentual'], 100)
        self.assertEqual(resultado['estado'], 'ALCANCADA')

    def test_meta_conta_todas_disciplinas_sem_vinculo_curricular(self):
        self.meta(quantidade_alvo=4)
        self.atividade(situacao='CONCLUIDA')
        self.atividade(situacao='CONCLUIDA', disciplina=None)
        resultado = dados_metas(self.aluno.usuario, {})['metas'][0]
        self.assertEqual(resultado['realizadas'], 2)
        self.assertNotIn('conteudo', resultado)
        self.assertEqual(resultado['percentual'], 50)
        self.assertEqual(resultado['estado'], 'EM_ANDAMENTO')

    def test_percentual_nao_ultrapassa_cem(self):
        self.meta(quantidade_alvo=1)
        self.atividade(situacao='CONCLUIDA')
        self.atividade(situacao='CONCLUIDA')
        self.assertEqual(dados_metas(self.aluno.usuario, {})['metas'][0]['percentual'], 100)

    def test_estados_futura_encerrada_e_cancelada(self):
        self.meta(titulo='Futura', data_inicio=date(2026, 12, 1), data_prazo=date(2026, 12, 31))
        self.meta(titulo='Encerrada', data_inicio=date(2026, 10, 1), data_prazo=date(2026, 10, 31))
        self.meta(titulo='Cancelada', situacao='CANCELADA')
        estados = {m['titulo']: m['estado'] for m in dados_metas(self.aluno.usuario, {})['metas']}
        self.assertEqual(estados, {'Futura': 'FUTURA', 'Encerrada': 'ENCERRADA', 'Cancelada': 'CANCELADA'})

    def test_filtro_de_periodo_e_resumo_ignoram_metas_canceladas(self):
        self.meta()
        self.meta(situacao='CANCELADA')
        self.meta(periodo='SEMANAL')
        resultado = dados_metas(self.aluno.usuario, {'periodo': 'MENSAL'})
        self.assertEqual(len(resultado['metas']), 2)
        mensal = next(p for p in resultado['periodos'] if p['codigo'] == 'MENSAL')
        self.assertEqual(mensal['total'], 1)
        self.assertEqual(mensal['alcancadas'], 0)

    def test_meta_antiga_conta_apenas_atividades_vinculadas(self):
        meta = self.meta(periodo='PERSONALIZADO', situacao='CONCLUIDA')
        self.atividade(meta=meta, situacao='CONCLUIDA', data_entrega=None)
        self.atividade(situacao='CONCLUIDA')
        resultado = dados_metas(self.aluno.usuario, {})['metas'][0]
        self.assertEqual(resultado['realizadas'], 1)
        self.assertEqual(resultado['estado'], 'ALCANCADA')

    def test_aluno_nao_recebe_meta_de_outro_aluno(self):
        self.meta(aluno=self.outro_aluno)
        self.assertEqual(dados_metas(self.aluno.usuario, {})['metas'], [])


class ApiIndicadoresTests(CenarioTestCase):
    def test_todos_os_paineis_retornam_json_sem_cache(self):
        self.atividade()
        self.meta()
        cliente = self.cliente(self.aluno)
        for secao, chave in [('', 'atividades'), ('metas', 'metas'),
                              ('acompanhamento', 'atividades')]:
            with self.subTest(secao=secao):
                resposta = cliente.get(reverse('api-painel'), {'secao': secao})
                self.assertEqual(resposta.status_code, 200)
                self.assertIn(chave, resposta.json())
                self.assertIn('no-store', resposta['Cache-Control'])

    def test_filtro_nao_permite_aluno_de_outra_familia(self):
        resposta = self.cliente(self.responsavel).get(reverse('api-painel'), {'aluno': self.outro_aluno.pk})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('aluno', resposta.json()['erros'])

    def test_intervalo_invertido_e_periodo_invalido(self):
        for campos in ({'inicio': '2026-11-07', 'fim': '2026-11-06'}, {'periodo': 'ANUAL'}):
            with self.subTest(campos=campos):
                form = FiltroPainel(campos, perfil=self.professor.usuario)
                self.assertFalse(form.is_valid())
                self.assertEqual(self.cliente(self.professor).get(reverse('api-painel'), campos).status_code, 400)

    def test_secoes_ignoram_filtros_que_foram_removidos_da_tela(self):
        for secao in ('metas',):
            with self.subTest(secao=secao):
                resposta = self.cliente(self.professor).get(reverse('api-painel'),
                    {'secao': secao, 'inicio': 'data-invalida', 'fim': 'data-invalida', 'busca': 'x' * 101})
                self.assertEqual(resposta.status_code, 200)

    def test_api_nao_expoe_catalogo_curricular_separado(self):
        resposta = self.cliente(self.professor).get(reverse('api-painel'), {'secao': 'conteudos'})
        self.assertEqual(resposta.status_code, 400)

    def test_opcoes_de_metas_excluem_canceladas_e_outros_alunos(self):
        meta = self.meta()
        self.meta(situacao='CANCELADA')
        self.meta(aluno=self.outro_aluno)
        cliente = self.cliente(self.aluno)
        resposta = cliente.get(reverse('api-metas-aluno', args=[self.aluno.pk]))
        self.assertEqual([m['id'] for m in resposta.json()], [meta.pk])
        self.assertEqual(list(resposta.json()[0]), ['id', 'titulo'])
        self.assertEqual(cliente.get(reverse('api-metas-aluno', args=[self.outro_aluno.pk])).status_code, 404)
