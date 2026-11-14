from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from aplicacao.servicos.acesso import alunos_area_estudante, alunos_permitidos
from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.models import (Aluno, Atividade, Disciplina, DocumentoPedagogico, Professor, Responsavel, Usuario, Vinculo,
                              VinculoFamiliar, VinculoProfissional)


class TestesFichaUnificada(TestCase):
    def pessoa(self, usuario, tipo, modelo, **kwargs):
        conta = get_user_model().objects.create_user(username=usuario, password='SenhaTesteComplexa!2026')
        perfil = Usuario.objects.create(usuario=usuario, tipo_perfil=tipo, conta=conta,
            gestor=kwargs.pop('gestor', False), troca_senha_obrigatoria=False,
            documentos_aceitos_em=timezone.now(), versao_termos_aceita=VERSAO_TERMOS,
            versao_privacidade_ciente=VERSAO_PRIVACIDADE)
        return modelo.objects.create(usuario=perfil, nome='Teste', sobrenome=usuario, **kwargs)

    def setUp(self):
        self.admin = self.pessoa('coordenador', 'PROFESSOR', Professor, gestor=True)
        self.aee = self.pessoa('aee', 'PROFESSOR', Professor, funcao='AEE')
        self.regente = self.pessoa('regente', 'PROFESSOR', Professor, funcao='REGENTE')
        self.acomp = self.pessoa('acompanhante', 'PROFESSOR', Professor, funcao='ACOMPANHANTE')
        self.pai = self.pessoa('pai', 'RESPONSAVEL', Responsavel)
        self.mae = self.pessoa('mae', 'RESPONSAVEL', Responsavel)
        self.crianca = self.pessoa('crianca', 'ALUNO', Aluno)
        self.disciplina = Disciplina.objects.create(nome='Prática')
        self.atividade = Atividade.objects.create(aluno=self.crianca, professor=self.aee,
            titulo='Aprender o alfabeto', descricao='Texto', disciplina=self.disciplina,
            data_entrega=date(2026, 12, 15))
        self.dados = {
            'acao': 'salvar_ficha', 'aluno': self.crianca.pk, 'responsavel': self.pai.pk,
            'professor_aee': self.aee.pk, 'professor_regente': self.regente.pk,
            'professor_acompanhante': self.acomp.pk, 'data_vinculo': '2026-11-01',
            'ativo': 'on', 'mesclar_perfis': 'on'}

    def entrar(self, pessoa):
        self.client.force_login(pessoa.usuario.conta)

    def test_ficha_reune_roles_e_grava_sem_duplicar(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse('vinculo-listar')).status_code, 200)
        r = self.client.post(reverse('vinculo-listar'), self.dados)
        self.assertEqual(r.status_code, 302, r.content)
        principal = Vinculo.objects.get(aluno=self.crianca)
        self.assertEqual(principal.professor, self.aee)
        self.assertEqual(principal.responsavel, self.pai)
        self.assertTrue(principal.mesclar_perfis)
        self.assertEqual(VinculoProfissional.objects.filter(aluno=self.crianca, ativo=True).count(), 2)
        self.assertEqual(self.client.post(reverse('vinculo-listar'), self.dados).status_code, 302)
        self.assertEqual(Vinculo.objects.filter(aluno=self.crianca).count(), 1)
        self.assertEqual(VinculoProfissional.objects.filter(aluno=self.crianca).count(), 2)
        self.assertContains(self.client.get(reverse('vinculo-listar') + '?aluno=' + str(self.crianca.pk)), self.regente.nome_completo)

    def test_interruptor_controla_atividades_nao_documentos(self):
        self.entrar(self.admin)
        self.client.post(reverse('vinculo-listar'), self.dados)
        self.entrar(self.pai)
        self.assertEqual(self.client.get(reverse('minhas-atividades')).status_code, 200)
        self.assertContains(self.client.get(reverse('familia-estudantes')), 'Ver atividades')
        self.entrar(self.admin)
        desligado = {**self.dados}
        desligado.pop('mesclar_perfis')
        self.assertEqual(self.client.post(reverse('vinculo-listar'), desligado).status_code, 302)
        self.entrar(self.pai)
        self.assertFalse(alunos_area_estudante(self.pai.usuario).exists())
        self.assertTrue(alunos_permitidos(self.pai.usuario).filter(pk=self.crianca.pk).exists())
        self.assertContains(self.client.get(reverse('familia-estudantes')), 'Ver atividades')
        detalhe = self.client.get(reverse('atividade-detalhe', args=[self.atividade.pk]))
        self.assertEqual(detalhe.status_code, 200)
        self.assertNotContains(detalhe, 'Enviar atividade para avaliação')
        self.assertEqual(self.client.post(reverse('api-solicitar-conclusao', args=[self.atividade.pk]), {
            'resposta_aluno': 'Tentativa'}).status_code, 404)
        doc = DocumentoPedagogico.objects.create(aluno=self.crianca, professor=self.aee,
            tipo='PAEE', ano_letivo=2026, campos={'habilidades': 'Texto'}, situacao='PUBLICADO')
        self.assertEqual(self.client.get(reverse('documento-detalhe', args=[doc.pk])).status_code, 200)

    def test_professor_regente_nao_pode_administrar_vinculos(self):
        self.entrar(self.regente)
        self.assertEqual(self.client.get(reverse('vinculo-listar')).status_code, 403)
        self.assertEqual(self.client.post(reverse('vinculo-listar'), self.dados).status_code, 403)
        self.assertEqual(self.client.get(reverse('vinculo-criar')).status_code, 403)
        self.assertFalse(Vinculo.objects.exists())

    def test_mesmo_profissional_pode_ser_regente_e_aee(self):
        self.entrar(self.admin)
        dados = {**self.dados, 'professor_regente': self.aee.pk}
        r = self.client.post(reverse('vinculo-listar'), dados)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(VinculoProfissional.objects.filter(
            aluno=self.crianca, professor=self.aee, funcao='REGENTE', ativo=True).exists())

    def test_troca_de_regente_preserva_historico_inativando_anterior(self):
        self.entrar(self.admin)
        self.client.post(reverse('vinculo-listar'), self.dados)
        outro = self.pessoa('regente2', 'PROFESSOR', Professor, funcao='REGENTE')
        dados = {**self.dados, 'professor_regente': outro.pk}
        self.client.post(reverse('vinculo-listar'), dados)
        self.assertTrue(VinculoProfissional.objects.get(aluno=self.crianca, professor=outro).ativo)
        self.assertFalse(VinculoProfissional.objects.get(aluno=self.crianca, professor=self.regente).ativo)

    def test_responsavel_adicional_tambem_tem_interruptor_independente(self):
        self.entrar(self.admin)
        self.client.post(reverse('vinculo-listar'), self.dados)
        self.assertEqual(self.client.post(reverse('vinculo-listar'), {
            'acao': 'adicionar_familiar', 'aluno': self.crianca.pk,
            'responsavel': self.mae.pk, 'ativo': 'on'}).status_code, 302)
        extra = VinculoFamiliar.objects.get(aluno=self.crianca, responsavel=self.mae)
        self.assertFalse(extra.mesclar_perfis)
        self.assertTrue(alunos_permitidos(self.mae.usuario).filter(pk=self.crianca.pk).exists())
        self.assertFalse(alunos_area_estudante(self.mae.usuario).exists())
        self.client.post(reverse('vinculo-listar'), {
            'acao': 'alternar_familiar', 'vinculo_id': extra.pk, 'mesclar_perfis': 'on'})
        self.assertTrue(alunos_area_estudante(self.mae.usuario).filter(pk=self.crianca.pk).exists())
        self.assertFalse(Vinculo.objects.get(aluno=self.crianca).responsavel_id == self.mae.pk)
