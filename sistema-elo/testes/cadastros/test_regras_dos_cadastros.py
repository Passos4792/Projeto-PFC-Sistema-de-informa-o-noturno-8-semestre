from datetime import date
from unittest import skipUnless
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from aplicacao.forms import (FormularioAluno, FormularioAtividade, FormularioDisciplina,
                             FormularioMeta, FormularioVinculo)
from aplicacao.models import Disciplina, SolicitacaoConclusao, Vinculo
from testes.base import CenarioTestCase, HOJE


class ModelosFormulariosTests(CenarioTestCase):
    def dados_atividade(self, **campos):
        dados = dict(aluno=self.aluno.pk, professor=self.professor.pk, disciplina=self.disciplina.pk,
                     titulo='Tarefa', descricao='Resolva os exercicios.', tipo_entrega='REGISTRO', data_entrega=HOJE.isoformat(), situacao='PENDENTE')
        dados.update(campos)
        return dados

    def dados_meta(self, **campos):
        dados = dict(aluno=self.aluno.pk, professor=self.professor.pk, titulo='Meta',
            periodo='MENSAL', quantidade_alvo=2, data_inicio=HOJE.isoformat(), situacao='EM_ANDAMENTO')
        dados.update(campos)
        return dados

    def test_conteudo_normaliza_espacos(self):
        form = FormularioDisciplina({'nome': '  Língua   Portuguesa  ', 'ativo': True})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().nome, 'Língua Portuguesa')

    def test_conteudo_repetido_ignora_caixa_e_espacos(self):
        Disciplina.objects.create(nome='Geografia')
        form = FormularioDisciplina({'nome': '  GEOGRAFIA ', 'ativo': True})
        self.assertFalse(form.is_valid())
        self.assertIn('nome', form.errors)

    @skipUnless(connection.vendor == 'mysql', 'A comparação Unicode depende da collation do MySQL; execute com --mysql.')
    def test_mysql_rejeita_conteudo_acentuado_repetido_em_maiusculas(self):
        form = FormularioDisciplina({'nome': '  MATEMÁTICA ', 'ativo': True})
        self.assertFalse(form.is_valid())
        self.assertIn('nome', form.errors)

    def test_conteudo_vazio_e_rejeitado(self):
        with self.assertRaises(ValidationError):
            Disciplina(nome='   ').clean()

    def test_atividade_exige_conteudo_e_data(self):
        form = FormularioAtividade(self.dados_atividade(disciplina='', data_entrega=''))
        self.assertFalse(form.is_valid())
        self.assertIn('disciplina', form.errors)
        self.assertIn('data_entrega', form.errors)

    def test_novo_conteudo_pode_ser_informado_sem_cadastro_previo(self):
        form = FormularioAtividade(self.dados_atividade(disciplina='', novo_conteudo='  Leitura   adaptada  '))
        self.assertTrue(form.is_valid(), form.errors)
        atividade = form.save()
        self.assertEqual(atividade.disciplina.nome, 'Leitura adaptada')

    def test_novo_conteudo_ja_existente_reaproveita_catalogo(self):
        form = FormularioAtividade(self.dados_atividade(disciplina='', novo_conteudo='  MATEMÁTICA  '))
        self.assertTrue(form.is_valid(), form.errors)
        atividade = form.save()
        self.assertEqual(atividade.disciplina.pk, self.disciplina.pk)
        self.assertEqual(Disciplina.objects.count(), 1)

    def test_escolher_e_criar_conteudo_ao_mesmo_tempo_e_erro(self):
        form = FormularioAtividade(self.dados_atividade(novo_conteudo='Artes'))
        self.assertFalse(form.is_valid())
        self.assertIn('novo_conteudo', form.errors)
        self.assertFalse(Disciplina.objects.filter(nome='Artes').exists())

    def test_atividade_nao_pode_ser_criada_ja_concluida_pelo_formulario(self):
        form = FormularioAtividade(self.dados_atividade(situacao='CONCLUIDA'))
        self.assertFalse(form.is_valid())
        self.assertIn('situacao', form.errors)

    def test_meta_da_atividade_deve_ser_do_mesmo_aluno(self):
        meta = self.meta(aluno=self.outro_aluno)
        tarefa = self.atividade(meta=meta)
        with self.assertRaises(ValidationError):
            tarefa.clean()
        form = FormularioAtividade(self.dados_atividade(meta=meta.pk))
        self.assertFalse(form.is_valid())
        self.assertIn('meta', form.errors)

    def test_atividade_aceita_qualquer_conteudo_com_meta_do_mesmo_aluno(self):
        meta = self.meta()
        outro = Disciplina.objects.create(nome='História')
        form = FormularioAtividade(self.dados_atividade(meta=meta.pk, disciplina=outro.pk))
        self.assertTrue(form.is_valid(), form.errors)
        atividade = form.save()
        self.assertEqual(atividade.meta, meta)
        self.assertEqual(atividade.disciplina, outro)

    def test_atividade_aceita_novo_conteudo_com_meta(self):
        meta = self.meta()
        form = FormularioAtividade(self.dados_atividade(
            meta=meta.pk, disciplina='', novo_conteudo='Expressão corporal'))
        self.assertTrue(form.is_valid(), form.errors)
        atividade = form.save()
        self.assertEqual(atividade.meta, meta)
        self.assertEqual(atividade.disciplina.nome, 'Expressão corporal')


    def test_nova_atividade_nao_pode_usar_conteudo_inativo(self):
        self.disciplina.ativo = False
        self.disciplina.save()
        form = FormularioAtividade(self.dados_atividade())
        self.assertFalse(form.is_valid())
        self.assertIn('disciplina', form.errors)

    def test_atividade_antiga_pode_manter_conteudo_inativo(self):
        atividade = self.atividade()
        self.disciplina.ativo = False
        self.disciplina.save()
        form = FormularioAtividade(self.dados_atividade(titulo='Título revisado'), instance=atividade)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().titulo, 'Título revisado')

    def test_solicitacao_pendente_impede_mudar_aluno_ou_situacao(self):
        atividade = self.atividade()
        SolicitacaoConclusao.objects.create(atividade=atividade, aluno=self.aluno, solicitante=self.aluno.usuario)
        atividade.situacao = 'CANCELADA'
        with self.assertRaises(ValidationError):
            atividade.clean()
        atividade.situacao = 'PENDENTE'
        atividade.aluno = self.outro_aluno
        with self.assertRaises(ValidationError):
            atividade.clean()

    def test_conclusao_nao_pode_ser_transferida_a_outro_aluno(self):
        atividade = self.atividade(situacao='CONCLUIDA')
        atividade.aluno = self.outro_aluno
        with self.assertRaises(ValidationError):
            atividade.clean()

    def test_data_de_conclusao_e_preservada_e_limpa_ao_reabrir(self):
        atividade = self.atividade(situacao='CONCLUIDA')
        instante = atividade.concluida_em
        atividade.titulo = 'Revisado'
        atividade.save(update_fields=['titulo'])
        atividade.refresh_from_db()
        self.assertEqual(atividade.concluida_em, instante)
        atividade.situacao = 'PENDENTE'
        atividade.save(update_fields=['situacao'])
        atividade.refresh_from_db()
        self.assertIsNone(atividade.concluida_em)

    def test_meta_normaliza_data_de_referencia_para_mes(self):
        form = FormularioMeta(self.dados_meta())
        self.assertTrue(form.is_valid(), form.errors)
        meta = form.save()
        self.assertEqual((meta.data_inicio, meta.data_prazo), (date(2026, 11, 1), date(2026, 11, 30)))

    def test_alvo_de_meta_precisa_ser_positivo(self):
        form = FormularioMeta(self.dados_meta(quantidade_alvo=0))
        self.assertFalse(form.is_valid())
        self.assertIn('quantidade_alvo', form.errors)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.meta(quantidade_alvo=0)

    def test_meta_antiga_rejeita_prazo_anterior_ao_inicio(self):
        meta = self.meta(periodo='PERSONALIZADO')
        meta.data_prazo = date(2026, 10, 1)
        with self.assertRaises(ValidationError):
            meta.clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            meta.save()

    def test_nova_meta_nao_admite_periodo_legado_ou_conclusao_manual(self):
        for campos in ({'periodo': 'PERSONALIZADO'}, {'situacao': 'CONCLUIDA'}):
            with self.subTest(campos=campos):
                form = FormularioMeta(self.dados_meta(**campos))
                self.assertFalse(form.is_valid())

    def test_um_aluno_nao_pode_ter_dois_vinculos(self):
        dados = dict(aluno=self.aluno.pk, professor=self.outro_professor.pk,
                     responsavel=self.responsavel.pk, data_vinculo=HOJE, ativo=True)
        self.assertFalse(FormularioVinculo(dados).is_valid())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vinculo.objects.create(aluno=self.aluno, professor=self.outro_professor,
                                   responsavel=self.responsavel, data_vinculo=HOJE)

    def test_edicao_de_aluno_atualiza_login_nome_e_status_da_conta(self):
        form = FormularioAluno({'nome': 'Ana Nova', 'sobrenome': 'Silva',
            'nome_usuario': 'ANA.NOVA', 'ativo': False}, instance=self.aluno)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.aluno.usuario.conta.refresh_from_db()
        self.assertEqual(self.aluno.usuario.conta.username, 'ana.nova')
        self.assertEqual(self.aluno.usuario.conta.first_name, 'Ana Nova')
        self.assertFalse(self.aluno.usuario.conta.is_active)

    def test_edicao_nao_pode_usar_login_de_outro_perfil(self):
        form = FormularioAluno({'nome': 'Ana', 'sobrenome': 'Silva',
            'nome_usuario': 'PROFESSOR', 'ativo': True}, instance=self.aluno)
        self.assertFalse(form.is_valid())
        self.assertIn('nome_usuario', form.errors)
