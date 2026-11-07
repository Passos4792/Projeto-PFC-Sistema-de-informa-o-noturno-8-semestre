from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from .models import Aluno, Professor, Responsavel, SolicitacaoSenha, Usuario, Vinculo


class TestesRecuperacaoDeSenha(TestCase):
    def setUp(self):
        User = get_user_model()
        self.login_prof = User.objects.create_user(username='professor1', password='SenhaAtualProf999!')
        self.perfil_prof = Usuario.objects.create(
            conta=self.login_prof, usuario='professor1', tipo_perfil='PROFESSOR',
            troca_senha_obrigatoria=False, documentos_aceitos_em=timezone.now(), versao_termos_aceita=VERSAO_TERMOS,
            versao_privacidade_ciente=VERSAO_PRIVACIDADE,
        )
        self.professor = Professor.objects.create(usuario=self.perfil_prof, nome='Prof', sobrenome='Um')
        self.login_outro = User.objects.create_user(username='professor2', password='SenhaAtualProf999!')
        self.perfil_outro = Usuario.objects.create(
            conta=self.login_outro, usuario='professor2', tipo_perfil='PROFESSOR',
            troca_senha_obrigatoria=False, documentos_aceitos_em=timezone.now(), versao_termos_aceita=VERSAO_TERMOS,
            versao_privacidade_ciente=VERSAO_PRIVACIDADE,
        )
        self.outro = Professor.objects.create(usuario=self.perfil_outro, nome='Prof', sobrenome='Dois')
        self.perfil_aluno = Usuario.objects.create(usuario='aluno1', tipo_perfil='ALUNO')
        self.aluno = Aluno.objects.create(usuario=self.perfil_aluno, nome='Aluno', sobrenome='Exemplo')
        self.perfil_resp = Usuario.objects.create(usuario='responsavel1', tipo_perfil='RESPONSAVEL')
        self.responsavel = Responsavel.objects.create(usuario=self.perfil_resp, nome='Responsável', sobrenome='Exemplo')
        self.vinculo = Vinculo.objects.create(
            aluno=self.aluno, professor=self.professor, responsavel=self.responsavel,
            data_vinculo=date(2026, 11, 1), ativo=True,
        )

    def _solicitar(self, usuario='aluno1'):
        return self.client.post(reverse('recuperar-senha'), {'usuario': usuario})

    def _ativar_com_formulario(self, url, senha='NovaSenhaAbc998!'):
        return self.client.post(url, {
            'new_password1': senha, 'new_password2': senha,
        })

    def test_solicitacao_publica_cria_um_pedido_e_impede_duplicidade(self):
        self.assertEqual(self._solicitar().status_code, 200)
        self.assertContains(self._solicitar(), 'Solicitação recebida')
        self.assertEqual(SolicitacaoSenha.objects.count(), 1)
        self.assertEqual(SolicitacaoSenha.objects.get().professor, self.professor)

    def test_usuario_inexistente_tem_resposta_igual_e_nao_cria_pedido(self):
        resposta = self._solicitar('usuario-inexistente')
        self.assertContains(resposta, 'Solicitação recebida')
        self.assertEqual(SolicitacaoSenha.objects.count(), 0)

    def test_solicitacao_exige_vinculo_ativo(self):
        self.vinculo.ativo = False
        self.vinculo.save()
        self.assertContains(self._solicitar(), 'Solicitação recebida')
        self.assertFalse(SolicitacaoSenha.objects.exists())

    def test_professor_vinculado_atende_e_ativa_conta_antiga(self):
        self._solicitar()
        pedido = SolicitacaoSenha.objects.get()
        self.client.force_login(self.login_prof)
        self.assertContains(self.client.get(reverse('solicitacao-senha-listar')), 'Aluno Exemplo')
        self.assertEqual(self._ativar_com_formulario(
            reverse('solicitacao-senha-atender', args=[pedido.pk])).status_code, 302)
        self.perfil_aluno.refresh_from_db()
        pedido.refresh_from_db()
        self.assertIsNotNone(self.perfil_aluno.conta_id)
        self.assertTrue(self.perfil_aluno.conta.check_password('NovaSenhaAbc998!'))
        self.assertTrue(self.perfil_aluno.troca_senha_obrigatoria)
        self.assertEqual(pedido.situacao, SolicitacaoSenha.Situacao.ATENDIDA)

    def test_professor_sem_vinculo_nao_visualiza_nem_atende(self):
        self._solicitar()
        pedido = SolicitacaoSenha.objects.get()
        self.client.force_login(self.login_outro)
        self.assertNotContains(self.client.get(reverse('solicitacao-senha-listar')), 'Aluno Exemplo')
        self.assertEqual(self.client.get(reverse('solicitacao-senha-atender', args=[pedido.pk])).status_code, 404)

    def test_ativacao_manual_de_conta_antiga_pelo_painel(self):
        self.client.force_login(self.login_prof)
        url = reverse('usuario-ativar-acesso', args=[self.perfil_aluno.pk])
        self.assertContains(self.client.get(reverse('aluno-listar')), 'Ativar acesso')
        self.assertEqual(self._ativar_com_formulario(url).status_code, 302)
        self.perfil_aluno.refresh_from_db()
        self.assertIsNotNone(self.perfil_aluno.conta_id)
        self.assertTrue(self.perfil_aluno.conta.check_password('NovaSenhaAbc998!'))
        self.assertContains(self.client.get(reverse('aluno-listar')), 'Redefinir senha')

    def test_perfil_com_senha_definitiva_continua_redefinivel(self):
        User = get_user_model()
        login = User.objects.create_user(username='aluno1', password='DefinitivaAbc123!')
        self.perfil_aluno.conta = login
        self.perfil_aluno.troca_senha_obrigatoria = False
        self.perfil_aluno.save()
        self.client.force_login(self.login_prof)
        url = reverse('usuario-redefinir-senha', args=[self.perfil_aluno.pk])
        self.assertEqual(self._ativar_com_formulario(url).status_code, 302)
        self.perfil_aluno.refresh_from_db()
        self.assertTrue(self.perfil_aluno.conta.check_password('NovaSenhaAbc998!'))
        self.assertTrue(self.perfil_aluno.troca_senha_obrigatoria)

    def test_solicitacao_redefine_senha_definitiva(self):
        login = get_user_model().objects.create_user(username='aluno1', password='DefinitivaAbc123!')
        self.perfil_aluno.conta = login
        self.perfil_aluno.troca_senha_obrigatoria = False
        self.perfil_aluno.save()
        self._solicitar()
        pedido = SolicitacaoSenha.objects.get()
        self.client.force_login(self.login_prof)
        self.assertEqual(self._ativar_com_formulario(
            reverse('solicitacao-senha-atender', args=[pedido.pk])).status_code, 302)
        login.refresh_from_db()
        self.perfil_aluno.refresh_from_db()
        self.assertTrue(login.check_password('NovaSenhaAbc998!'))
        self.assertTrue(self.perfil_aluno.troca_senha_obrigatoria)

    def test_redefinir_senha_solicitada_nao_pode_ser_atendida_duas_vezes(self):
        self._solicitar()
        pedido = SolicitacaoSenha.objects.get()
        self.client.force_login(self.login_prof)
        url = reverse('solicitacao-senha-atender', args=[pedido.pk])
        self._ativar_com_formulario(url)
        resposta = self._ativar_com_formulario(url, senha='OutraSenha123XYZ!')
        self.assertEqual(resposta.status_code, 302)
        self.perfil_aluno.refresh_from_db()
        self.assertFalse(self.perfil_aluno.conta.check_password('OutraSenha123XYZ!'))

    def test_usuario_aluno_nao_tem_permissao_no_painel_de_senhas(self):
        User = get_user_model()
        login = User.objects.create_user(username='aluno1', password='DefinitivaAbc123!')
        self.perfil_aluno.conta = login
        self.perfil_aluno.troca_senha_obrigatoria = False
        self.perfil_aluno.documentos_aceitos_em = timezone.now()
        self.perfil_aluno.versao_termos_aceita = VERSAO_TERMOS
        self.perfil_aluno.versao_privacidade_ciente = VERSAO_PRIVACIDADE
        self.perfil_aluno.save()
        self.client.force_login(login)
        self.assertEqual(self.client.get(reverse('solicitacao-senha-listar')).status_code, 403)
