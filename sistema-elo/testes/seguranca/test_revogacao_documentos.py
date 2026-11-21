"""Regressões para a revogação de documentos e o bloqueio do responsável e criança."""
from datetime import date

from django.urls import reverse
from django.utils import timezone

from aplicacao.models import AutorizacaoAcessoMenor, VinculoFamiliar
from aplicacao.servicos.autorizacao_menores import acesso_menor_autorizado
from aplicacao.servicos.documentos_legais import (
    MARCADOR_REVOGACAO, VERSAO_PRIVACIDADE, VERSAO_TERMOS,
)
from testes.base import CenarioTestCase, SENHA, pessoa


class RevogacaoDocumentosTests(CenarioTestCase):
    def setUp(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 11, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        self.url = reverse('privacidade-revogar')
        self.confirmacao = {
            'senha': SENHA, 'confirmacao': 'REVOGAR', 'confirmo': 'on',
        }

    def autorizar(self, responsavel=None):
        responsavel = responsavel or self.responsavel
        return AutorizacaoAcessoMenor.objects.create(
            aluno=self.aluno, responsavel=responsavel,
            versao_termos=VERSAO_TERMOS, versao_privacidade=VERSAO_PRIVACIDADE,
            autorizado_em=timezone.now(),
        )

    def test_opcoes_privacidade_e_layout(self):
        cliente = self.cliente(self.responsavel)
        self.assertContains(cliente.get(reverse('meus-dados')), 'cartao-privacidade')
        pagina = cliente.get(reverse('privacidade-conta'))
        self.assertContains(pagina, 'Gerenciar meus dados e conta')
        self.assertContains(pagina, 'Revogar Termos de Uso e Política de Privacidade')
        self.assertContains(pagina, reverse('privacidade-gerenciar'))
        self.assertContains(pagina, self.url)
        self.assertContains(cliente.get(reverse('privacidade-gerenciar')),
                            reverse('privacidade-exportar-menor', args=[self.aluno.pk]))

    def test_confirmacoes_invalidas_nao_revogam(self):
        cliente = self.cliente(self.responsavel)
        for campos in (
            {'senha': 'senha errada', 'confirmacao': 'REVOGAR', 'confirmo': 'on'},
            {'senha': SENHA, 'confirmacao': 'NAO', 'confirmo': 'on'},
            {'senha': SENHA, 'confirmacao': 'REVOGAR'},
        ):
            self.assertEqual(cliente.post(self.url, campos).status_code, 200)
            self.responsavel.usuario.refresh_from_db()
            self.assertIsNotNone(self.responsavel.usuario.documentos_aceitos_em)

    def test_revogacao_bloqueia_pai_e_crianca_sem_excluir_dados(self):
        self.autorizar()
        self.meta()
        self.atividade()
        cliente_crianca = self.cliente(self.aluno)
        cliente_pai = self.cliente(self.responsavel)
        self.assertEqual(cliente_crianca.get(reverse('pagina-inicial')).status_code, 200)
        self.assertEqual(cliente_pai.post(self.url, self.confirmacao).status_code, 302)
        self.responsavel.usuario.refresh_from_db()
        self.aluno.refresh_from_db()
        self.assertIsNone(self.responsavel.usuario.documentos_aceitos_em)
        self.assertEqual(self.responsavel.usuario.versao_termos_aceita, MARCADOR_REVOGACAO)
        self.assertEqual(self.responsavel.usuario.versao_privacidade_ciente, MARCADOR_REVOGACAO)
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(responsavel=self.responsavel, aluno=self.aluno).exists())
        self.assertTrue(self.responsavel.ativo)
        self.assertTrue(self.aluno.ativo)
        self.assertTrue(self.vinculo.ativo)
        self.assertEqual(self.aluno.metas.count(), 1)
        self.assertEqual(self.aluno.atividades.count(), 1)
        # Sessão do menor já autenticada deixa de acessar páginas e APIs.
        self.assertRedirects(cliente_crianca.get(reverse('pagina-inicial')),
                             reverse('aguardando-autorizacao'), fetch_redirect_response=False)
        self.assertEqual(cliente_crianca.get(reverse('api-painel')).status_code, 403)
        # Responsável sai da conta. Mesmo se logar de novo, só acessa o aceite.
        self.assertRedirects(cliente_pai.get(reverse('meus-dados')),
                             reverse('login') + '?next=' + reverse('meus-dados'), fetch_redirect_response=False)
        cliente_pai_novamente = self.cliente(self.responsavel)
        self.assertIn(reverse('aceitar-termos'), cliente_pai_novamente.get(reverse('meus-dados')).url)
        self.assertEqual(cliente_pai_novamente.get(reverse('api-painel')).status_code, 403)

    def test_revogar_bloqueia_crianca_mesmo_com_autorizacao_de_outro_responsavel(self):
        outro_responsavel = pessoa('responsavel.adicional', 'RESPONSAVEL')
        VinculoFamiliar.objects.create(aluno=self.aluno, responsavel=outro_responsavel, ativo=True)
        self.autorizar(outro_responsavel)
        self.assertTrue(acesso_menor_autorizado(self.aluno))
        self.cliente(self.responsavel).post(self.url, self.confirmacao)
        self.assertTrue(AutorizacaoAcessoMenor.objects.filter(
            aluno=self.aluno, responsavel=outro_responsavel).exists())
        self.assertFalse(acesso_menor_autorizado(self.aluno))

    def test_reaceite_exige_nova_autorizacao_da_crianca(self):
        self.autorizar()
        self.cliente(self.responsavel).post(self.url, self.confirmacao)
        cliente = self.cliente(self.responsavel)
        resposta = cliente.post(reverse('aceitar-termos'), {'aceite': 'on'})
        self.assertRedirects(resposta, reverse('autorizar-acesso-menor'),
                             fetch_redirect_response=False)
        self.assertFalse(acesso_menor_autorizado(self.aluno))
        self.assertEqual(cliente.post(reverse('autorizar-acesso-menor'), {
            'aluno_id': str(self.aluno.pk), 'autorizo': 'on',
        }).status_code, 302)
        self.assertTrue(acesso_menor_autorizado(self.aluno))

    def test_maior_de_12_nao_depende_do_aceite_de_outro_perfil(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 12, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        self.cliente(self.responsavel).post(self.url, self.confirmacao)
        self.assertEqual(self.cliente(self.aluno).get(reverse('pagina-inicial')).status_code, 200)

    def test_menor_e_professor_nao_podem_revogar(self):
        self.autorizar()
        self.assertEqual(self.cliente(self.aluno).post(self.url, self.confirmacao).status_code, 403)
        self.assertEqual(self.cliente(self.professor).post(self.url, self.confirmacao).status_code, 403)

    def test_aluno_com_12_anos_pode_revogar_apenas_o_proprio_aceite(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 12, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        self.assertEqual(self.cliente(self.aluno).post(self.url, self.confirmacao).status_code, 302)
        self.aluno.usuario.refresh_from_db()
        self.responsavel.usuario.refresh_from_db()
        self.assertIsNone(self.aluno.usuario.documentos_aceitos_em)
        self.assertIsNotNone(self.responsavel.usuario.documentos_aceitos_em)
