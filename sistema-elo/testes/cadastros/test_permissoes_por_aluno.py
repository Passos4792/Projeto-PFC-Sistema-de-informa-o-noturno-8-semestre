from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from aplicacao.servicos.acesso import alunos_com_funcao, funcoes_no_aluno
from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.models import (Aluno, Atividade, Disciplina, DocumentoPedagogico, MetaAluno, Professor, RelatorioPedagogico,
                              Responsavel, SolicitacaoConclusao, Usuario, Vinculo, VinculoProfissional)


class PermissoesDiferentesPorAluno(TestCase):
    def pessoa(self, nome, tipo, modelo, **kwargs):
        user = get_user_model().objects.create_user(username=nome, password='SenhaTesteSegura!2026')
        perfil = Usuario.objects.create(
            usuario=nome, conta=user, tipo_perfil=tipo,
            gestor=kwargs.pop('gestor', False),
            troca_senha_obrigatoria=False, documentos_aceitos_em=timezone.now(),
            versao_termos_aceita=VERSAO_TERMOS,
            versao_privacidade_ciente=VERSAO_PRIVACIDADE)
        return modelo.objects.create(usuario=perfil, nome='Pessoa', sobrenome=nome, **kwargs)

    def setUp(self):
        self.admin = self.pessoa('adm-misto', 'PROFESSOR', Professor, gestor=True)
        self.misto = self.pessoa('prof-misto', 'PROFESSOR', Professor, funcao='REGENTE')
        self.aee_b = self.pessoa('aee-b', 'PROFESSOR', Professor, funcao='AEE')
        self.aluno_a = self.pessoa('estudante-a', 'ALUNO', Aluno)
        self.aluno_b = self.pessoa('estudante-b', 'ALUNO', Aluno)
        self.pai_a = self.pessoa('resp-a', 'RESPONSAVEL', Responsavel)
        self.pai_b = self.pessoa('resp-b', 'RESPONSAVEL', Responsavel)
        Vinculo.objects.create(aluno=self.aluno_a, professor=self.misto,
            responsavel=self.pai_a, data_vinculo=date(2026, 1, 1))
        Vinculo.objects.create(aluno=self.aluno_b, professor=self.aee_b,
            responsavel=self.pai_b, data_vinculo=date(2026, 1, 1))
        self.vinculo_b = VinculoProfissional.objects.create(aluno=self.aluno_b,
            professor=self.misto, funcao='ACOMPANHANTE', data_inicio=date(2026, 1, 1))
        self.disciplina = Disciplina.objects.create(nome='Língua Portuguesa')
        self.atividade_a = Atividade.objects.create(aluno=self.aluno_a, professor=self.misto,
            titulo='Atividade A', descricao='Leitura A', disciplina=self.disciplina,
            data_entrega=date(2026, 12, 1))
        self.atividade_b = Atividade.objects.create(aluno=self.aluno_b, professor=self.misto,
            titulo='Atividade B', descricao='Leitura B', disciplina=self.disciplina,
            data_entrega=date(2026, 12, 1))
        self.meta_b = MetaAluno.objects.create(aluno=self.aluno_b, professor=self.misto,
            titulo='Meta B', data_inicio=date(2026, 11, 1), periodo='SEMANAL')
        self.doc_b = DocumentoPedagogico.objects.create(aluno=self.aluno_b,
            professor=self.aee_b, tipo='PAEE', ano_letivo=2026, campos={'habilidades': 'Confidencial B'})
        self.rel_b = RelatorioPedagogico.objects.create(aluno=self.aluno_b,
            professor=self.misto, titulo='Relatório da acompanhante B', relato='Registro livre B')
        self.rel_aee_b = RelatorioPedagogico.objects.create(aluno=self.aluno_b,
            professor=self.aee_b, titulo='Relatório confidencial AEE B', relato='Não compartilhar com acompanhante')

    def entrar(self, pessoa):
        self.client.force_login(pessoa.usuario.conta)

    def test_funcao_por_estudante_independe_de_cadastro_geral(self):
        funcoes_a = funcoes_no_aluno(self.misto.usuario, self.aluno_a.pk)
        funcoes_b = funcoes_no_aluno(self.misto.usuario, self.aluno_b.pk)
        self.assertEqual(funcoes_a, {'AEE'})
        self.assertEqual(funcoes_b, {'ACOMPANHANTE'})
        self.assertEqual(list(alunos_com_funcao(self.misto.usuario, 'AEE')), [self.aluno_a])

    def test_menu_misto_oferece_documentacao_e_acompanhamento_aee(self):
        self.entrar(self.misto)
        r = self.client.get(reverse('profissional-estudantes'))
        self.assertContains(r, 'Professor do AEE')
        self.assertContains(r, 'Professor acompanhante')
        self.assertContains(r, 'Acompanhamento AEE')
        self.assertContains(r, 'Metas')

    def test_atividade_aee_pode_criar_para_a_mas_nao_para_b(self):
        self.entrar(self.misto)
        dados = {'aluno': self.aluno_a.pk, 'professor': self.misto.pk,
            'disciplina': self.disciplina.pk, 'titulo': 'Nova AEE A',
            'descricao': 'Atividade com instruções', 'tipo_entrega': 'ENVIO',
            'data_entrega': '2026-12-20', 'situacao': 'PENDENTE'}
        self.assertEqual(self.client.post(reverse('atividade-criar'), dados).status_code, 302)
        self.assertTrue(Atividade.objects.filter(titulo='Nova AEE A').exists())
        dados['aluno'] = self.aluno_b.pk
        self.assertEqual(self.client.post(reverse('atividade-criar'), dados).status_code, 403)
        self.assertFalse(Atividade.objects.filter(aluno=self.aluno_b, titulo='Nova AEE A').exists())
        self.assertEqual(self.client.get(reverse('atividade-editar', args=[self.atividade_b.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('atividade-excluir', args=[self.atividade_b.pk])).status_code, 403)

    def test_impede_falsificar_professor_e_visualizar_historico_de_b(self):
        self.entrar(self.misto)
        r = self.client.post(reverse('atividade-criar'), {
            'aluno': self.aluno_a.pk, 'professor': self.aee_b.pk,
            'disciplina': self.disciplina.pk, 'titulo': 'Falsa autoria',
            'descricao': 'Não', 'data_entrega': '2026-12-20', 'situacao': 'PENDENTE'})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Atividade.objects.filter(titulo='Falsa autoria').exists())
        self.assertNotContains(self.client.get(reverse('atividade-listar')), 'Atividade B')

    def test_meta_b_nao_editavel_ou_visivel_no_painel(self):
        self.entrar(self.misto)
        self.assertEqual(self.client.get(reverse('meta-editar', args=[self.meta_b.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('meta-listar')), 'Meta B')
        self.assertEqual(self.client.get(reverse('aluno-inicio', args=[self.aluno_b.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('api-metas-aluno', args=[self.aluno_b.pk])).status_code, 404)

    def test_inicio_filtra_somente_o_aluno_aee_e_nao_expoe_acompanhante(self):
        self.entrar(self.misto)
        resposta = self.client.get(reverse('pagina-inicial'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([aluno.pk for aluno in resposta.context['alunos_disponiveis']], [self.aluno_a.pk])
        self.assertEqual(self.client.get(reverse('pagina-inicial'),
                                         {'aluno': self.aluno_b.pk}).status_code, 403)

    def test_acompanhante_pode_relatar_b_mas_nao_pode_criar_paee_b(self):
        self.entrar(self.misto)
        self.assertEqual(self.client.get(reverse('relatorio-criar')).status_code, 200)
        r = self.client.post(reverse('relatorio-criar'), {
            'aluno': self.aluno_b.pk, 'titulo': 'Registro de acompanhamento B',
            'data_referencia': '2026-11-10', 'relato': 'Atendimento observado após aula'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(RelatorioPedagogico.objects.filter(aluno=self.aluno_b, titulo='Registro de acompanhamento B').exists())
        r = self.client.post(reverse('documento-criar', args=['PAEE']), {
            'aluno': self.aluno_b.pk, 'ano_letivo': 2026})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(DocumentoPedagogico.objects.filter(aluno=self.aluno_b, professor=self.misto).exists())
        self.assertEqual(self.client.get(reverse('documento-detalhe', args=[self.doc_b.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[self.rel_aee_b.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[self.rel_b.pk])).status_code, 200)
        self.assertNotContains(self.client.get(reverse('documentos-lista')), 'Relatório confidencial AEE B')
        self.assertNotContains(self.client.get(reverse('documentos-lista')), 'Confidencial B')

    def test_professor_nao_pode_gerir_senhas_de_aluno_acompanhado(self):
        self.entrar(self.misto)
        self.assertEqual(self.client.get(reverse('usuario-redefinir-senha', args=[self.aluno_b.usuario.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('solicitacao-senha-listar')).status_code, 200)

    def test_aprovacao_b_mesmo_que_professor_seja_autor_historico(self):
        sol = SolicitacaoConclusao.objects.create(atividade=self.atividade_b,
            aluno=self.aluno_b, solicitante=self.aluno_b.usuario)
        self.entrar(self.misto)
        self.assertNotContains(self.client.get(reverse('aprovacoes')), 'Atividade B')
        r = self.client.patch(reverse('api-decidir-conclusao', args=[sol.pk]),
            data='{"decisao":"APROVADA"}', content_type='application/json')
        self.assertEqual(r.status_code, 404)
        self.atividade_b.refresh_from_db()
        self.assertEqual(self.atividade_b.situacao, 'PENDENTE')

    def test_revogacao_aee_corta_acesso_sem_apagar_relatorio_b(self):
        self.entrar(self.misto)
        self.assertEqual(self.client.get(reverse('atividade-listar')).status_code, 200)
        Vinculo.objects.filter(aluno=self.aluno_a).update(ativo=False)
        self.assertEqual(self.client.get(reverse('atividade-listar')).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[self.rel_b.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('atividade-material', args=[self.atividade_b.pk])).status_code, 403)

    def test_gestor_mantem_administracao_dos_alunos(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse('atividade-listar')).status_code, 200)
        self.assertEqual(self.client.get(reverse('vinculo-listar')).status_code, 200)
        self.assertEqual(self.client.get(reverse('documento-detalhe', args=[self.doc_b.pk])).status_code, 200)

    def test_migracao_de_funcao_por_profissional_nao_necessaria(self):
        self.assertEqual(self.misto.funcao, 'REGENTE')
        self.assertTrue(VinculoProfissional.objects.filter(professor=self.misto, funcao='ACOMPANHANTE').exists())

    def test_somente_acompanhante_nao_abre_metas_e_atividades(self):
        somente_acomp = self.pessoa('apenas-acomp', 'PROFESSOR', Professor, funcao='AEE')
        VinculoProfissional.objects.create(aluno=self.aluno_b, professor=somente_acomp,
            funcao='ACOMPANHANTE', data_inicio=date(2026, 1, 1))
        self.entrar(somente_acomp)
        for rota in ('atividade-listar', 'meta-listar',
                     'atividade-criar', 'aprovacoes'):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(reverse(rota)).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-criar')).status_code, 200)
        self.assertNotContains(self.client.get(reverse('profissional-estudantes')), 'Acompanhamento AEE')
        self.assertEqual(self.client.get(reverse('api-painel')).status_code, 403)

    def test_regente_sem_aee_so_preenche_pei_e_relatorio(self):
        regente = self.pessoa('so-regente', 'PROFESSOR', Professor, funcao='AEE')
        VinculoProfissional.objects.create(aluno=self.aluno_b, professor=regente,
            funcao='REGENTE', data_inicio=date(2026, 1, 1))
        self.entrar(regente)
        self.assertEqual(self.client.get(reverse('documento-criar', args=['PEI'])).status_code, 200)
        self.assertEqual(self.client.get(reverse('documento-criar', args=['PAEE'])).status_code, 403)
        self.assertEqual(self.client.get(reverse('atividade-listar')).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-criar')).status_code, 200)

    def test_acompanhante_tem_acesso_revogado_ao_encerrar_vinculo(self):
        self.entrar(self.misto)
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[self.rel_b.pk])).status_code, 200)
        self.vinculo_b.data_fim = date(2026, 1, 31)
        self.vinculo_b.save()
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[self.rel_b.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('profissional-estudantes')), self.aluno_b.nome_completo)

    def test_acompanhante_nao_consulta_anexos_atividade_de_outro_professor(self):
        self.atividade_b.professor = self.aee_b
        self.atividade_b.save(update_fields=['professor'])
        self.entrar(self.misto)
        self.assertEqual(self.client.get(reverse('atividade-material', args=[self.atividade_b.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('api-metas-aluno', args=[self.aluno_b.pk])).status_code, 404)
