from datetime import datetime
from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone
from aplicacao.models import (Aluno, Atividade, Disciplina, RegistroAuditoria, SolicitacaoConclusao, Usuario, Vinculo)
from testes.base import CenarioTestCase, HOJE


class CadastrosAuditoriaTests(CenarioTestCase):
    def setUp(self):
        self.operador = self.cliente(self.gestor)

    def dados_atividade_novo_conteudo(self, nome='Geografia'):
        return {
            'aluno': self.aluno.pk, 'professor': self.professor.pk,
            'disciplina': '', 'novo_conteudo': nome,
            'titulo': 'Atividade curricular', 'descricao': 'Ler e responder.',
            'tipo_entrega': 'ENVIO', 'data_entrega': HOJE.isoformat(), 'situacao': 'PENDENTE',
        }

    def test_conteudo_criado_ao_cadastrar_atividade_com_auditoria(self):
        resposta = self.operador.post(reverse('atividade-criar'), self.dados_atividade_novo_conteudo('  Geografia  '))
        self.assertEqual(resposta.status_code, 302)
        conteudo = Disciplina.objects.get(nome='Geografia')
        atividade = Atividade.objects.get(titulo='Atividade curricular')
        self.assertEqual(atividade.disciplina, conteudo)
        evento = RegistroAuditoria.objects.get(acao='CRIACAO', entidade='Atividade')
        self.assertEqual(evento.objeto_id, str(atividade.pk))
        evento_conteudo = RegistroAuditoria.objects.get(acao='CRIACAO', entidade='Conteúdo curricular')
        self.assertEqual(evento_conteudo.objeto_id, str(conteudo.pk))
        self.assertIn('Geografia', evento_conteudo.detalhes)

    def test_conteudo_em_uso_continua_protegido_no_banco(self):
        from django.db.models.deletion import ProtectedError
        self.atividade()
        with self.assertRaises(ProtectedError):
            self.disciplina.delete()


    def test_falha_de_auditoria_reverte_atividade_e_novo_conteudo(self):
        with patch('aplicacao.views.comum.registrar', side_effect=RuntimeError('falha simulada')):
            with self.assertRaises(RuntimeError):
                self.operador.post(reverse('atividade-criar'), self.dados_atividade_novo_conteudo('Não persistir'))
        self.assertFalse(Disciplina.objects.filter(nome='Não persistir').exists())
        self.assertFalse(Atividade.objects.filter(titulo='Atividade curricular').exists())

    def test_formulario_invalido_nao_cria_conteudo_nem_auditoria(self):
        resposta = self.operador.post(reverse('atividade-criar'), self.dados_atividade_novo_conteudo(''))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('disciplina', resposta.context['formulario'].errors)
        self.assertEqual(Disciplina.objects.count(), 1)
        self.assertFalse(RegistroAuditoria.objects.filter(acao='CRIACAO').exists())

    def test_criacao_edicao_e_exclusao_de_atividade(self):
        dados = dict(aluno=self.aluno.pk, professor=self.professor.pk, disciplina=self.disciplina.pk,
                     titulo='Atividade nova', descricao='Resolva os exercicios.', tipo_entrega='REGISTRO', data_entrega=HOJE, situacao='PENDENTE')
        self.assertEqual(self.operador.post(reverse('atividade-criar'), dados).status_code, 302)
        atividade = Atividade.objects.get(titulo='Atividade nova')
        dados['titulo'] = 'Atividade revisada'
        self.assertEqual(self.operador.post(reverse('atividade-editar', args=[atividade.pk]), dados).status_code, 302)
        atividade.refresh_from_db()
        self.assertEqual(atividade.titulo, 'Atividade revisada')
        self.assertEqual(self.operador.post(reverse('atividade-excluir', args=[atividade.pk])).status_code, 302)
        self.assertFalse(Atividade.objects.filter(pk=atividade.pk).exists())

    def test_gestor_nao_pode_ser_excluido(self):
        resposta = self.cliente(self.gestor).post(reverse('professor-excluir', args=[self.gestor.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Usuario.objects.filter(pk=self.gestor.usuario_id).exists())

    def test_consulta_registra_filtros_sem_gravar_texto_pesquisado(self):
        self.operador.get(reverse('aluno-listar'), {'busca': 'nome-confidencial', 'pagina': 2})
        evento = RegistroAuditoria.objects.get(acao='CONSULTA')
        self.assertEqual(evento.entidade, 'Alunos')
        self.assertIn('pesquisa', evento.detalhes)
        self.assertIn('Página: 2', evento.detalhes)
        self.assertNotIn('nome-confidencial', evento.detalhes)

    def test_consultar_auditoria_nao_gera_auditoria_recursiva(self):
        cliente = self.cliente(self.gestor)
        antes = RegistroAuditoria.objects.count()
        self.assertEqual(cliente.get(reverse('auditoria')).status_code, 200)
        self.assertEqual(RegistroAuditoria.objects.count(), antes)

    def test_filtro_auditoria_inclui_dia_final_inteiro_no_fuso_local(self):
        cliente = self.cliente(self.gestor)
        instantes = [
            datetime(2026, 11, 5, 23, 59, 59),
            datetime(2026, 11, 6, 0, 0),
            datetime(2026, 11, 6, 23, 59, 59),
            datetime(2026, 11, 7, 0, 0),
        ]
        ids = []
        for instante in instantes:
            evento = RegistroAuditoria.objects.create(autor='autor.data', acao='EDICAO')
            RegistroAuditoria.objects.filter(pk=evento.pk).update(criado_em=timezone.make_aware(instante))
            ids.append(evento.pk)
        resposta = cliente.get(reverse('auditoria'),
            {'inicio': '2026-11-06', 'fim': '2026-11-06', 'autor': 'autor.data', 'acao': 'EDICAO'})
        self.assertEqual({e.pk for e in resposta.context['pagina']}, set(ids[1:3]))

    def test_intervalo_invalido_da_auditoria_exibe_erro_sem_resultados(self):
        resposta = self.cliente(self.gestor).get(reverse('auditoria'),
            {'inicio': '2026-11-07', 'fim': '2026-11-06'})
        self.assertFalse(resposta.context['formulario'].is_valid())
        self.assertEqual(resposta.context['pagina'].paginator.count, 0)


class PaginacaoPaineisTests(CenarioTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for indice in range(12):
            perfil = Usuario.objects.create(usuario=f'lista{indice}', tipo_perfil='ALUNO')
            aluno = Aluno.objects.create(usuario=perfil, nome=f'Lista {indice:02}', sobrenome='Teste')
            Vinculo.objects.create(aluno=aluno, professor=cls.professor,
                                   responsavel=cls.responsavel, data_vinculo=HOJE)
            Atividade.objects.create(aluno=aluno, professor=cls.professor, disciplina=cls.disciplina,
                                     titulo=f'Tarefa {indice:02}', data_entrega=HOJE)
            for tipo, modelo in [('PROFESSOR', type(cls.professor)), ('RESPONSAVEL', type(cls.responsavel))]:
                perfil_extra = Usuario.objects.create(usuario=f'{tipo.lower()}{indice}', tipo_perfil=tipo)
                modelo.objects.create(usuario=perfil_extra, nome=f'Lista {indice:02}', sobrenome='Teste')

    def test_cadastros_e_atividades_limitam_dez_itens_por_pagina(self):
        cliente = self.cliente(self.gestor)
        for rota in ('aluno-listar', 'professor-listar', 'responsavel-listar', 'atividade-listar'):
            with self.subTest(rota=rota):
                primeira = cliente.get(reverse(rota)).context['pagina']
                segunda = cliente.get(reverse(rota), {'pagina': 2}).context['pagina']
                self.assertEqual(len(primeira), 10)
                self.assertTrue(primeira.has_next())
                self.assertTrue({obj.pk for obj in primeira}.isdisjoint({obj.pk for obj in segunda}))

    def test_busca_acontece_antes_da_paginacao(self):
        resposta = self.cliente(self.professor).get(reverse('aluno-listar'), {'busca': 'Lista 11'})
        self.assertEqual(resposta.context['pagina'].paginator.count, 1)
        self.assertEqual(resposta.context['pagina'][0].nome, 'Lista 11')

    def test_busca_atividades_por_data_e_situacao(self):
        cliente = self.cliente(self.professor)
        resposta = cliente.get(reverse('atividade-listar'), {'busca': '06/11/2026 pendente'})
        self.assertEqual(resposta.context['pagina'].paginator.count, 12)
        resposta = cliente.get(reverse('atividade-listar'), {'busca': 'concluída'})
        self.assertEqual(resposta.context['pagina'].paginator.count, 0)

    def test_pagina_invalida_nao_provoca_erro(self):
        cliente = self.cliente(self.professor)
        self.assertEqual(cliente.get(reverse('aluno-listar'), {'pagina': 'abc'}).context['pagina'].number, 1)
        resposta = cliente.get(reverse('aluno-listar'), {'pagina': 999})
        self.assertFalse(resposta.context['pagina'].has_next())

    def test_grafico_de_metas_aparece_sempre_para_professor_e_segue_a_pesquisa(self):
        self.meta(titulo='Meta da Ana')
        self.meta(titulo='Meta do Bruno', aluno=self.outro_aluno, professor=self.gestor)
        cliente = self.cliente(self.gestor)
        resposta = cliente.get(reverse('meta-listar'))
        self.assertTrue(resposta.context['mostrar_grafico_individual'])
        self.assertContains(resposta, 'data-grafico')
        self.assertContains(resposta, 'dados-painel-iniciais')
        self.assertNotContains(resposta, 'Selecione um aluno')
        mensal = next(p for p in resposta.context['dados']['periodos'] if p['codigo'] == 'MENSAL')
        self.assertEqual(mensal['total'], 2)
        resposta = cliente.get(reverse('meta-listar'), {'busca': 'bruno'})
        mensal = next(p for p in resposta.context['dados']['periodos'] if p['codigo'] == 'MENSAL')
        self.assertEqual(mensal['total'], 1)
        self.assertEqual([m['titulo'] for m in resposta.context['dados']['metas']], ['Meta do Bruno'])

    def test_grafico_de_metas_usa_selecao_de_aluno_para_a_familia(self):
        cliente = self.cliente(self.responsavel)
        resposta = cliente.get(reverse('meta-listar'))
        self.assertFalse(resposta.context['mostrar_grafico_individual'])
        self.assertContains(resposta, 'Selecione um aluno')
        resposta = cliente.get(reverse('meta-listar'), {'aluno': self.aluno.pk})
        self.assertTrue(resposta.context['mostrar_grafico_individual'])
        self.assertContains(resposta, 'dados-painel-iniciais')

    def test_metas_limitam_dez_registros(self):
        for indice in range(12):
            self.meta(titulo=f'Meta {indice:02}')
        cliente = self.cliente(self.professor)
        pagina = cliente.get(reverse('meta-listar')).context['pagina_metas']
        self.assertEqual(len(pagina), 10)
        self.assertTrue(pagina.has_next())


class FiltrosAprovacoesTests(CenarioTestCase):
    def setUp(self):
        self.pedidos = []
        for indice in range(8):
            pedido = SolicitacaoConclusao.objects.create(
                atividade=self.atividade(titulo=f'Tarefa {indice}'), aluno=self.aluno, solicitante=self.aluno.usuario)
            instante = timezone.make_aware(datetime(2026, 11, 6, indice, 0))
            SolicitacaoConclusao.objects.filter(pk=pedido.pk).update(solicitado_em=instante)
            self.pedidos.append(pedido)

    def test_fila_exibe_seis_e_preserva_ordem_nas_paginas(self):
        cliente = self.cliente(self.professor)
        pagina = cliente.get(reverse('aprovacoes')).context['pagina']
        self.assertEqual([s.pk for s in pagina], [s.pk for s in self.pedidos[::-1]][:6])
        segunda = cliente.get(reverse('aprovacoes'), {'pagina': 2}).context['pagina']
        self.assertEqual(len(segunda), 2)
        antiga = cliente.get(reverse('aprovacoes'), {'ordem': 'antigas'}).context['pagina']
        self.assertEqual(antiga[0].pk, self.pedidos[0].pk)

    def test_professor_so_ve_suas_solicitacoes_e_gestor_ve_todas(self):
        self.assertEqual(self.cliente(self.outro_professor).get(reverse('aprovacoes')).status_code, 403)
        self.assertEqual(self.cliente(self.professor).get(reverse('aprovacoes')).context['pendentes'], 8)
        self.assertEqual(self.cliente(self.gestor).get(reverse('aprovacoes')).context['pendentes'], 8)

    def test_busca_filtra_titulo(self):
        resposta = self.cliente(self.professor).get(reverse('aprovacoes'), {'busca': 'Tarefa 7'})
        self.assertEqual([s.pk for s in resposta.context['pagina']], [self.pedidos[7].pk])

    def test_filtro_de_data_inclui_ultimo_segundo_do_dia(self):
        SolicitacaoConclusao.objects.filter(pk=self.pedidos[-1].pk).update(
            solicitado_em=timezone.make_aware(datetime(2026, 11, 6, 23, 59, 59)))
        resposta = self.cliente(self.professor).get(reverse('aprovacoes'),
            {'inicio': '2026-11-06', 'fim': '2026-11-06'})
        self.assertEqual(resposta.context['pagina'].paginator.count, 8)
        self.assertEqual(resposta.context['pagina'][0].pk, self.pedidos[-1].pk)

    def test_data_invertida_rejeita_filtro(self):
        resposta = self.cliente(self.professor).get(reverse('aprovacoes'),
            {'inicio': '2026-11-07', 'fim': '2026-11-06'})
        self.assertTrue(resposta.context['formulario_filtros'].errors)
        self.assertEqual(resposta.context['pagina'].paginator.count, 0)
