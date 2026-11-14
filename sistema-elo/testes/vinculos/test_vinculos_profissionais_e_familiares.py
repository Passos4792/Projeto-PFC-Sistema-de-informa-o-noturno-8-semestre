from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from aplicacao.servicos.acesso import alunos_permitidos
from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.models import (Aluno, DocumentoPedagogico, Professor, RelatorioPedagogico, Responsavel, Usuario, Vinculo,
                              VinculoFamiliar, VinculoProfissional)


class TestesDocumentosEVinculos(TestCase):
    def pessoa(self, nome, tipo, modelo, **kwargs):
        conta = get_user_model().objects.create_user(username=nome, password='SenhaSeguraTestes123!')
        usuario = Usuario.objects.create(usuario=nome, conta=conta, tipo_perfil=tipo,
                                         troca_senha_obrigatoria=False,
                                         documentos_aceitos_em=timezone.now(),
                                         versao_termos_aceita=VERSAO_TERMOS,
                                         versao_privacidade_ciente=VERSAO_PRIVACIDADE,
                                         gestor=kwargs.pop('gestor', False))
        return modelo.objects.create(usuario=usuario, nome='Nome', sobrenome=nome, **kwargs)

    def setUp(self):
        self.diretor = self.pessoa('diretor-aee', 'PROFESSOR', Professor, gestor=True)
        self.aee = self.pessoa('doc-aee', 'PROFESSOR', Professor)
        self.regente = self.pessoa('doc-regente', 'PROFESSOR', Professor, funcao='REGENTE')
        self.acompanhante = self.pessoa('doc-acomp', 'PROFESSOR', Professor, funcao='ACOMPANHANTE')
        self.familiar = self.pessoa('doc-familiar', 'RESPONSAVEL', Responsavel)
        self.outro_familiar = self.pessoa('doc-outrofamiliar', 'RESPONSAVEL', Responsavel)
        self.aluno = self.pessoa('doc-aluno', 'ALUNO', Aluno)
        self.outro = self.pessoa('doc-outro', 'ALUNO', Aluno)
        Vinculo.objects.create(aluno=self.aluno, professor=self.aee, responsavel=self.familiar,
                               data_vinculo=date(2026, 11, 10))
        Vinculo.objects.create(aluno=self.outro, professor=self.aee, responsavel=self.outro_familiar,
                               data_vinculo=date(2026, 11, 10))
        self.vinculo_regente = VinculoProfissional.objects.create(
            aluno=self.aluno, professor=self.regente, funcao='REGENTE', data_inicio=date(2026, 1, 1))
        VinculoProfissional.objects.create(
            aluno=self.aluno, professor=self.acompanhante, funcao='ACOMPANHANTE', data_inicio=date(2026, 1, 1))

    def entrar(self, pessoa):
        self.client.force_login(pessoa.usuario.conta)

    def test_responsavel_com_login_unico_ve_aluno_sem_login_proprio(self):
        self.aluno.usuario.conta = None
        self.aluno.usuario.save(update_fields=['conta'])
        self.entrar(self.familiar)
        resp = self.client.get(reverse('familia-estudantes'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.aluno.nome_completo)
        self.assertNotContains(resp, self.outro.usuario.usuario)

    def test_segundo_responsavel_pode_ver_so_aluno_adicional(self):
        VinculoFamiliar.objects.create(aluno=self.aluno, responsavel=self.outro_familiar)
        self.assertEqual(alunos_permitidos(self.outro_familiar.usuario).count(), 2)
        self.entrar(self.outro_familiar)
        self.assertEqual(self.client.get(reverse('familia-estudantes')).status_code, 200)

    def test_regente_ve_apenas_alunos_vinculados(self):
        self.entrar(self.regente)
        self.assertEqual(self.client.get(reverse('profissional-estudantes')).status_code, 200)
        self.assertEqual(list(alunos_permitidos(self.regente.usuario)), [self.aluno])
        self.assertEqual(self.client.get(reverse('aluno-inicio', args=[self.outro.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('usuario-criar')).status_code, 403)

    def test_profissional_sem_vinculo_nao_pode_gerar_relatorio_do_outro(self):
        self.entrar(self.regente)
        resp = self.client.post(reverse('relatorio-criar'), {
            'aluno': self.outro.pk, 'titulo': 'Texto proibido', 'data_referencia': '2026-11-10',
            'relato': 'Não deve gravar'} )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(RelatorioPedagogico.objects.exists())

    def test_acompanhante_pode_escrever_relatorio_livre_em_rascunho(self):
        self.entrar(self.acompanhante)
        resp = self.client.post(reverse('relatorio-criar'), {
            'aluno': self.aluno.pk, 'titulo': 'Observações de novembro',
            'data_referencia': '2026-11-10', 'periodo': 'Novembro',
            'relato': 'Participou da rotina com apoio visual.'})
        self.assertEqual(resp.status_code, 302, resp.content)
        rel = RelatorioPedagogico.objects.get()
        self.assertEqual(rel.situacao, 'RASCUNHO')
        self.assertEqual(rel.professor, self.acompanhante)
        self.entrar(self.familiar)
        self.assertNotContains(self.client.get(reverse('documentos-lista')), rel.titulo)
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[rel.pk])).status_code, 403)

    def test_publicacao_explicita_libera_apenas_familia_do_aluno(self):
        rel = RelatorioPedagogico.objects.create(aluno=self.aluno, professor=self.regente,
                titulo='Registro de evolução', relato='Evolução no período.')
        self.entrar(self.regente)
        self.assertEqual(self.client.post(reverse('relatorio-publicar', args=[rel.pk]),
                                          {'acao': 'PUBLICADO'}).status_code, 302)
        self.entrar(self.familiar)
        self.assertContains(self.client.get(reverse('documentos-lista')), rel.titulo)
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[rel.pk])).status_code, 200)
        self.entrar(self.outro_familiar)
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[rel.pk])).status_code, 403)

    def test_aluno_nao_ve_documentos_ou_relatorios_publicados(self):
        doc = DocumentoPedagogico.objects.create(
            aluno=self.aluno, professor=self.aee, tipo='PEI', ano_letivo=2026,
            situacao='PUBLICADO', campos={'conteudos': 'Dado reservado aos responsáveis'})
        rel = RelatorioPedagogico.objects.create(
            aluno=self.aluno, professor=self.aee, titulo='Relatório reservado',
            relato='Observações reservadas', situacao='PUBLICADO')
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(reverse('documentos-lista')).status_code, 403)
        self.assertEqual(self.client.get(reverse('documento-detalhe', args=[doc.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-detalhe', args=[rel.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('documento-editar', args=[doc.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-editar', args=[rel.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('documento-criar', args=['PEI'])).status_code, 403)
        self.assertEqual(self.client.get(reverse('relatorio-criar')).status_code, 403)
        self.assertEqual(self.client.post(reverse('documento-publicar', args=[doc.pk]),
                                          {'acao': 'FINALIZADO'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('relatorio-publicar', args=[rel.pk]),
                                          {'acao': 'FINALIZADO'}).status_code, 403)

    def test_menu_aluno_oculta_documentos_e_responsavel_mantem_acesso(self):
        self.entrar(self.aluno)
        resposta_aluno = self.client.get(reverse('minhas-atividades'))
        self.assertEqual(resposta_aluno.status_code, 200)
        self.assertNotContains(resposta_aluno, 'Documentos disponíveis')
        self.entrar(self.familiar)
        resposta_familiar = self.client.get(reverse('documentos-lista'))
        self.assertEqual(resposta_familiar.status_code, 200)
        self.assertContains(resposta_familiar, 'Documentos disponíveis')

    def test_estudo_e_paee_reservados_ao_aee(self):
        self.entrar(self.regente)
        self.assertEqual(self.client.get(reverse('documento-criar', args=['PAEE'])).status_code, 403)
        self.assertEqual(self.client.get(reverse('documento-criar', args=['PEI'])).status_code, 200)
        self.entrar(self.aee)
        self.assertEqual(self.client.get(reverse('documento-criar', args=['PAEE'])).status_code, 200)

    def test_pei_preenchimento_e_publicacao(self):
        self.entrar(self.regente)
        resp = self.client.post(reverse('documento-criar', args=['PEI']), {
            'aluno': self.aluno.pk, 'ano_letivo': 2026, 'bimestre': '3',
            'conteudos': 'Habilidades de leitura', 'estrategias': 'Material visual',
            'avaliacao': 'Registros descritivos', 'materiais': 'Livros ilustrados'})
        self.assertEqual(resp.status_code, 302, resp.content)
        doc = DocumentoPedagogico.objects.get()
        self.assertEqual(doc.campos['estrategias'], 'Material visual')
        self.entrar(self.familiar)
        self.assertEqual(self.client.get(reverse('documento-detalhe', args=[doc.pk])).status_code, 403)
        self.entrar(self.regente)
        self.assertEqual(self.client.post(reverse('documento-publicar', args=[doc.pk]),
                                          {'acao': 'PUBLICADO'}).status_code, 302)
        self.entrar(self.familiar)
        self.assertContains(self.client.get(reverse('documento-detalhe', args=[doc.pk])), 'Material visual')

    def test_vinculo_profissional_somente_gestor(self):
        self.entrar(self.regente)
        self.assertEqual(self.client.get(reverse('vinculos-profissionais')).status_code, 403)
        self.entrar(self.diretor)
        self.assertEqual(self.client.get(reverse('vinculos-profissionais')).status_code, 200)
        novo = self.pessoa('novo-regente', 'PROFESSOR', Professor, funcao='REGENTE')
        resp = self.client.post(reverse('vinculos-profissionais'), {
            'aluno': self.outro.pk, 'professor': novo.pk,
            'data_inicio': '2026-10-01', 'ativo': 'on'})
        self.assertEqual(resp.status_code, 302, resp.content)
        self.assertTrue(VinculoProfissional.objects.filter(aluno=self.outro, professor=novo, funcao='REGENTE').exists())

    def test_vinculo_profissional_inativo_nao_permite_acesso(self):
        self.vinculo_regente.ativo = False
        self.vinculo_regente.save()
        self.entrar(self.regente)
        self.assertEqual(self.client.get(reverse('profissional-estudantes')).status_code, 200)
        self.assertNotContains(self.client.get(reverse('profissional-estudantes')), self.aluno.nome_completo)
        self.assertEqual(self.client.get(reverse('documento-criar', args=['PEI'])).status_code, 403)
        self.assertFalse(alunos_permitidos(self.regente.usuario).exists())

    def test_cadastro_aluno_sem_login_pelo_gestor(self):
        self.entrar(self.diretor)
        resp = self.client.post(reverse('aluno-criar-sem-login'), {
            'nome': 'Joana', 'sobrenome': 'Teste', 'nome_usuario': 'joana-sem-email',
            'ativo': 'on', 'data_nascimento': '2017-04-01'})
        self.assertEqual(resp.status_code, 302, resp.content)
        novo = Aluno.objects.get(usuario__usuario='joana-sem-email')
        self.assertIsNone(novo.usuario.conta_id)
        self.entrar(self.regente)
        self.assertEqual(self.client.get(reverse('aluno-criar-sem-login')).status_code, 403)

    def test_cadastro_professor_com_funcao_regente(self):
        self.entrar(self.diretor)
        resp = self.client.post(reverse('usuario-criar'), {
            'nome': 'Nova', 'sobrenome': 'Regente', 'username': 'nova-regente',
            'tipo_perfil': 'PROFESSOR', 'funcao_profissional': 'REGENTE',
            'password1': 'SenhaMuitoSegura#2026', 'password2': 'SenhaMuitoSegura#2026',
        })
        self.assertEqual(resp.status_code, 302, resp.content)
        novo = Professor.objects.get(usuario__usuario='nova-regente')
        self.assertEqual(novo.funcao, 'REGENTE')
        self.assertEqual(novo.usuario.tipo_perfil, 'PROFESSOR')

    def test_publicacao_apenas_por_post(self):
        doc = DocumentoPedagogico.objects.create(aluno=self.aluno, professor=self.aee, tipo='PAEE',
             ano_letivo=2026, campos={'habilidades': 'Integração'})
        self.entrar(self.aee)
        self.assertEqual(self.client.get(reverse('documento-publicar', args=[doc.pk])).status_code, 405)
        doc.refresh_from_db()
        self.assertEqual(doc.situacao, 'RASCUNHO')
