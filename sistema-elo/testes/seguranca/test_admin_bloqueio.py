"""Regressoes para os dois formularios de autenticacao."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(LOGIN_MAX_FALHAS=3, LOGIN_MAX_FALHAS_USUARIO=30,
                   LOGIN_MAX_FALHAS_IP=100, LOGIN_BLOQUEIO_SEGUNDOS=60)
class LoginAdminBloqueioTests(TestCase):
    SENHA = 'TesteAdministrador@2026!'

    def setUp(self):
        self.administrador = get_user_model().objects.create_superuser(
            username='admin_teste_elo', password=self.SENHA)

    def _enviar(self, rota, senha):
        return self.client.post(reverse(rota), {
            'username': self.administrador.username, 'password': senha,
        }, REMOTE_ADDR='192.0.2.40')

    def test_falhas_no_admin_bloqueiam_login_comum(self):
        for _ in range(3):
            self._enviar('admin:login', 'senha-incorreta')
        resposta = self._enviar('login', self.SENHA)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Muitas tentativas')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_falhas_no_login_comum_bloqueiam_admin(self):
        for _ in range(3):
            self._enviar('login', 'senha-incorreta')
        resposta = self._enviar('admin:login', self.SENHA)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Muitas tentativas')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_usuario_comum_logado_nao_ve_nome_no_admin(self):
        aluno = get_user_model().objects.create_user(
            username='teste123', password='SenhaAluno@2026!')
        self.client.force_login(aluno)
        resposta = self.client.get(reverse('admin:login'))
        self.assertEqual(resposta.status_code, 404)
        self.assertNotContains(resposta, 'teste123', status_code=404)

    def test_aluno_anonimo_falha_no_admin_e_fica_bloqueado_no_login_normal(self):
        aluno = get_user_model().objects.create_user(
            username='estudante_teste', password='SenhaAluno@2026!')
        admin_url = reverse('admin:login')
        for _ in range(3):
            self.client.post(admin_url, {
                'username': aluno.username, 'password': 'incorreta',
            }, REMOTE_ADDR='192.0.2.40')
        resposta = self.client.post(reverse('login'), {
            'username': aluno.username, 'password': 'SenhaAluno@2026!',
        }, REMOTE_ADDR='192.0.2.40')
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Muitas tentativas')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_aluno_logado_nao_visualiza_indice_do_admin(self):
        aluno = get_user_model().objects.create_user(
            username='aluno_sem_admin', password='SenhaAluno@2026!')
        self.client.force_login(aluno)
        resposta = self.client.get(reverse('admin:index'))
        self.assertEqual(resposta.status_code, 404)
        self.assertNotContains(resposta, 'aluno_sem_admin', status_code=404)

    @override_settings(ELO_ADMIN_PATH='')
    def test_superusuario_tecnico_sem_admin_retoma_a_seguranca(self):
        from django.test import RequestFactory
        from aplicacao.views.seguranca import _destino_seguro
        request = RequestFactory().get('/seguranca/verificar/?next=%2F')
        request.user = self.administrador
        self.assertEqual(_destino_seguro(request), reverse('2fa-seguranca'))

    @override_settings(LOGIN_MAX_FALHAS=5, LOGIN_BLOQUEIO_SEGUNDOS=300)
    def test_rn03_cinco_falhas_ativam_bloqueio_de_cinco_minutos(self):
        # Usa os limites da RN03, em vez do limite reduzido dos demais testes.
        for _ in range(4):
            self._enviar('admin:login', 'senha-incorreta')
        quinta_falha = self._enviar('admin:login', 'senha-incorreta')
        self.assertEqual(quinta_falha.status_code, 200)
        self.assertContains(quinta_falha, 'Muitas tentativas')
        resposta = self._enviar('login', self.SENHA)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Muitas tentativas')
        self.assertNotIn('_auth_user_id', self.client.session)


    @override_settings(ELO_ADMIN_PATH='')
    def test_admin_esta_desligado_quando_nao_configurado(self):
        """A configuração de rotas deve omitir o painel em produção."""
        from pathlib import Path
        from runpy import run_path
        from configuracao import urls

        rotas = run_path(str(Path(urls.__file__)))['urlpatterns']
        self.assertFalse(any(getattr(rota, 'namespace', None) == 'admin' for rota in rotas))
        self.assertFalse(any(str(rota.pattern) == 'admin/' for rota in rotas))

    @override_settings(ELO_ADMIN_PATH='acesso-tecnico-privado')
    def test_rota_alternativa_nao_ressuscita_admin_padrao(self):
        """Habilitar uma rota técnica não reabre /admin/."""
        from pathlib import Path
        from runpy import run_path
        from configuracao import urls

        rotas = run_path(str(Path(urls.__file__)))['urlpatterns']
        self.assertTrue(any(
            getattr(rota, 'namespace', None) == 'admin' and
            str(rota.pattern) == 'acesso-tecnico-privado/'
            for rota in rotas
        ))
        self.assertFalse(any(str(rota.pattern) == 'admin/' for rota in rotas))
