from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.urls import reverse

from aplicacao.models import Aluno, RegistroAuditoria, Usuario
from testes.base import SENHA, CenarioTestCase

CARGAS_SQL = [
    "' OR '1'='1", "' OR 1=1 -- ", '" OR ""="', "1; DROP TABLE aluno; --", "1' UNION SELECT username, password FROM auth_user --",
    "%' OR '%'='", "ana'--", "1 OR 1=1", "') OR ('1'='1", "\\'; SELECT SLEEP(5); --", "0x27", "%", "_",
]


class SqlInjectionTests(CenarioTestCase):
    def rotas_busca(self):
        return [('aluno-listar', 'busca'), ('professor-listar', 'busca'), ('responsavel-listar', 'busca'),
                ('vinculo-listar', 'busca'), ('atividade-listar', 'busca'), ('atividade-listar', 'aluno'),
                ('atividade-listar', 'situacao'), ('atividade-historico', 'ano'), ('documentos-lista', 'aluno'),
                ('documentos-lista', 'busca'), ('solicitacao-senha-listar', 'busca'), ('auditoria', 'autor'),
                ('auditoria', 'acao'), ('pagina-inicial', 'aluno'), ('meta-listar', 'busca'),
                ('aluno-listar', 'pagina')]

    def test_buscas_e_filtros_nao_quebram_nem_vazam(self):
        cliente = self.cliente(self.gestor)
        for rota, campo in self.rotas_busca():
            for carga in CARGAS_SQL:
                with self.subTest(rota=rota, campo=campo, carga=carga):
                    resposta = cliente.get(reverse(rota), {campo: carga})
                    self.assertIn(resposta.status_code, (200, 400, 403, 404))
                    self.assertNotContains(resposta, 'pbkdf2_sha256', status_code=resposta.status_code)
        self.assertEqual(Aluno.objects.count(), 2)

    def test_busca_maliciosa_nao_retorna_todos_os_alunos(self):
        resposta = self.cliente(self.gestor).get(reverse('aluno-listar'), {'busca': "' OR '1'='1"})
        self.assertNotContains(resposta, 'ana Teste')
        self.assertNotContains(resposta, 'bruno Teste')

    def test_login_e_recuperacao_com_carga_sql_sao_recusados(self):
        for carga in CARGAS_SQL:
            with self.subTest(carga=carga):
                resposta = Client().post(reverse('login'), {'username': carga, 'password': carga})
                self.assertEqual(resposta.status_code, 200)
                self.assertNotIn('_auth_user_id', Client().session)
                self.assertEqual(Client().post(reverse('recuperar-senha'), {'usuario': carga}).status_code, 200)
                self.assertIn(Client().post(reverse('admin-recuperar-senha'), {
                    'usuario': carga, 'codigo': '123456', 'codigo_recuperacao': carga,
                    'new_password1': 'SenhaNova@879', 'new_password2': 'SenhaNova@879'}).status_code, (200,))
        self.assertTrue(get_user_model().objects.filter(username='gestor').exists())

    def test_ids_maliciosos_na_url_e_no_post(self):
        cliente = self.cliente(self.gestor)
        for carga in CARGAS_SQL:
            with self.subTest(carga=carga):
                self.assertIn(cliente.get(reverse('vinculo-criar'), {'aluno': carga}).status_code, (200, 404))
                self.assertIn(cliente.post(reverse('vinculo-criar'), {'acao': 'mesclar', 'vinculo_id': carga}).status_code,
                              (200, 302, 400, 404))

    def test_api_com_carga_sql(self):
        cliente = self.cliente(self.gestor)
        for carga in CARGAS_SQL:
            with self.subTest(carga=carga):
                self.assertIn(cliente.get(reverse('api-painel'), {'secao': carga, 'aluno': carga}).status_code, (200, 400))


class MaiusculasMinusculasTests(CenarioTestCase):
    def test_login_digitado_em_maiusculas_entra(self):
        cliente = Client()
        resposta = cliente.post(reverse('login'), {'username': '  ANA ', 'password': SENHA})
        self.assertEqual(resposta.status_code, 302)

    def test_senha_continua_diferenciando_maiusculas(self):
        resposta = Client().post(reverse('login'), {'username': 'ana', 'password': SENHA.upper()})
        self.assertEqual(resposta.status_code, 200)

    def test_cadastro_recusa_login_que_so_muda_maiusculas(self):
        from aplicacao.forms import CadastroUsuario
        formulario = CadastroUsuario({'tipo_perfil': 'RESPONSAVEL', 'username': 'ANA', 'first_name': 'X',
                                      'last_name': 'Y', 'data_nascimento': '1980-01-01',
                                      'password1': 'SenhaNova@879', 'password2': 'SenhaNova@879'},
                                     operador=self.gestor.usuario)
        self.assertFalse(formulario.is_valid())
        self.assertIn('username', formulario.errors)

    def test_perfil_sempre_gravado_em_minusculas(self):
        perfil = Usuario.objects.create(usuario='  Novo.Usuario ', tipo_perfil='RESPONSAVEL')
        self.assertEqual(perfil.usuario, 'novo.usuario')

    def test_conta_criada_pelo_admin_django_fica_em_minusculas(self):
        conta = get_user_model()(username='Tecnico.Novo')
        conta.set_password('Senha@Tecnica123')
        requisicao = RequestFactory().post('/admin/')
        requisicao.user = get_user_model().objects.create_superuser('tecnico', password='Senha@Tecnica123')
        site._registry[get_user_model()].save_model(requisicao, conta, form=None, change=False)
        conta.refresh_from_db()
        self.assertEqual(conta.username, 'tecnico.novo')

    def test_solicitacao_de_senha_encontra_usuario_em_maiusculas(self):
        Client().post(reverse('recuperar-senha'), {'usuario': 'ANA'})
        from aplicacao.models import SolicitacaoSenha
        self.assertTrue(SolicitacaoSenha.objects.filter(usuario_alvo=self.aluno.usuario).exists())
