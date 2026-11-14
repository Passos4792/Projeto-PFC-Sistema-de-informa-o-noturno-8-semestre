from datetime import date
from django.urls import reverse
from aplicacao.models import (Professor, SolicitacaoSenha,
                              VinculoFamiliar, VinculoProfissional)
from testes.base import CenarioTestCase


class SolicitacoesPorPerfilTests(CenarioTestCase):
    SENHA_TEMPORARIA = 'Temporaria@90812'

    def solicitar(self, nome):
        retorno = self.client.post(reverse('recuperar-senha'), {'usuario': nome})
        self.assertContains(retorno, 'Solicitação recebida')
        return SolicitacaoSenha.objects.latest('pk')

    def lista(self, operador):
        return self.cliente(operador).get(reverse('solicitacao-senha-listar'))

    def atender(self, operador, pedido):
        return self.cliente(operador).post(
            reverse('solicitacao-senha-atender', args=[pedido.pk]),
            {'new_password1': self.SENHA_TEMPORARIA,
             'new_password2': self.SENHA_TEMPORARIA},
        )

    def test_aluno_visivel_para_gestor_e_aee_vinculado(self):
        pedido = self.solicitar('ana')
        self.assertEqual(pedido.usuario_alvo, self.aluno.usuario)
        self.assertContains(self.lista(self.professor), 'ana Teste')
        self.assertContains(self.lista(self.gestor), 'ana Teste')
        self.assertNotContains(self.lista(self.outro_professor), 'ana Teste')
        self.assertEqual(self.atender(self.gestor, pedido).status_code, 302)
        self.assertEqual(self.atender(self.professor, pedido).status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, 'ATENDIDA')

    def test_responsavel_visivel_para_gestor_e_aee_do_aluno(self):
        pedido = self.solicitar('responsavel')
        self.assertEqual(pedido.usuario_alvo, self.responsavel.usuario)
        self.assertContains(self.lista(self.professor), 'responsavel Teste')
        self.assertContains(self.lista(self.gestor), 'responsavel Teste')
        self.assertNotContains(self.lista(self.outro_professor), 'responsavel Teste')
        self.assertEqual(self.atender(self.professor, pedido).status_code, 302)
        self.responsavel.usuario.conta.refresh_from_db()
        self.assertTrue(self.responsavel.usuario.conta.check_password(self.SENHA_TEMPORARIA))

    def test_professor_somente_gestor_pode_atender(self):
        pedido = self.solicitar('professor')
        self.assertEqual(pedido.usuario_alvo, self.professor.usuario)
        self.assertIsNone(pedido.aluno)
        self.assertContains(self.lista(self.gestor), 'professor Teste')
        self.assertNotContains(self.lista(self.professor), 'Atender pedido')
        self.assertNotContains(self.lista(self.outro_professor), 'Atender pedido')
        self.assertEqual(self.cliente(self.professor).get(
            reverse('solicitacao-senha-atender', args=[pedido.pk])).status_code, 404)
        self.assertEqual(self.atender(self.gestor, pedido).status_code, 302)
        self.professor.usuario.conta.refresh_from_db()
        self.assertTrue(self.professor.usuario.conta.check_password(self.SENHA_TEMPORARIA))

    def test_gestor_nao_abre_pedido_que_ninguem_pode_atender(self):
        resposta = self.client.post(reverse('recuperar-senha'), {'usuario': 'gestor'})
        self.assertContains(resposta, 'Solicitação recebida')
        self.assertFalse(SolicitacaoSenha.objects.exists())

    def test_responsavel_por_vinculo_familiar_unificado(self):
        self.vinculo.ativo = False
        self.vinculo.save(update_fields=['ativo'])
        VinculoProfissional.objects.create(
            aluno=self.aluno, professor=self.professor,
            funcao=Professor.Funcao.AEE, data_inicio=date(2026, 10, 1), ativo=True)
        VinculoFamiliar.objects.create(
            aluno=self.aluno, responsavel=self.responsavel, ativo=True)
        pedido = self.solicitar('responsavel')
        self.assertContains(self.lista(self.professor), 'responsavel Teste')
        self.assertEqual(self.atender(self.professor, pedido).status_code, 302)

    def test_desativacao_do_vinculo_antes_do_atendimento_bloqueia_aee(self):
        pedido = self.solicitar('responsavel')
        self.vinculo.ativo = False
        self.vinculo.save(update_fields=['ativo'])
        self.assertNotContains(self.lista(self.professor), 'responsavel Teste')
        self.assertEqual(self.atender(self.professor, pedido).status_code, 404)
        self.assertEqual(self.atender(self.gestor, pedido).status_code, 302)

    def test_professor_regente_sem_aee_nao_acessa_pedidos(self):
        VinculoProfissional.objects.create(
            aluno=self.aluno, professor=self.outro_professor,
            funcao=Professor.Funcao.REGENTE,
            data_inicio=date(2026, 10, 1), ativo=True,
        )
        pedido = self.solicitar('ana')
        self.assertNotContains(self.lista(self.outro_professor), 'Atender pedido')
        self.assertEqual(self.cliente(self.outro_professor).get(
            reverse('solicitacao-senha-atender', args=[pedido.pk])).status_code, 404)

    def test_interface_foto_e_aviso_google_compacto(self):
        perfil = self.cliente(self.gestor).get(reverse('meus-dados'))
        self.assertContains(perfil, 'foto-selecionar')
        self.assertContains(perfil, 'Nenhum arquivo selecionado')
        atividades = self.cliente(self.gestor).get(reverse('atividade-listar'))
        self.assertContains(atividades, 'elo-google-aviso-compacto')
        self.assertNotContains(atividades, 'elo-google-painel')
