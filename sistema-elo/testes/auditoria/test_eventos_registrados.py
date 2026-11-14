from datetime import timedelta
from io import StringIO

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from aplicacao.servicos.duplo_fator import cifrar_segredo, criar_codigos_recuperacao, novo_segredo
from aplicacao.models import Configuracao2FA, DocumentoPedagogico, RegistroAuditoria
from testes.base import CenarioTestCase


class CoberturaAuditoriaTests(CenarioTestCase):
    def test_registros_de_pessoas_trazem_nome_e_login(self):
        from aplicacao.servicos.auditoria import registrar
        for acao in ('CRIACAO', 'EDICAO', 'SENHA', 'PERMISSAO'):
            with self.subTest(acao=acao):
                registro = registrar(acao, objeto=self.outro_professor, detalhes='Campos: nome')
                self.assertIn('outro.professor Teste (usuário: outro.professor)', registro.detalhes)
                self.assertIn('Campos: nome', registro.detalhes)
                self.assertNotIn('Excluído', registro.detalhes)

    def test_consulta_de_documento_e_pdf(self):
        doc = DocumentoPedagogico.objects.create(aluno=self.aluno, professor=self.professor, tipo='PEI',
                                                 ano_letivo=2026, campos={'conteudos': 'Leitura'})
        cliente = self.cliente(self.gestor)
        self.assertEqual(cliente.get(reverse('documento-detalhe', args=[doc.pk])).status_code, 200)
        self.assertEqual(cliente.get(reverse('documento-pdf', args=[doc.pk])).status_code, 200)
        for entidade in ('Documento pedagógico', 'Documento pedagógico (PDF)'):
            with self.subTest(entidade=entidade):
                self.assertTrue(RegistroAuditoria.objects.filter(acao='CONSULTA', entidade=entidade,
                                                                 autor='gestor').exists())

    @override_settings(ELO_2FA_ATIVO=True)
    def test_codigo_2fa_recusado_fica_registrado_sem_o_codigo(self):
        conta = self.professor.usuario.conta
        Configuracao2FA.objects.create(conta=conta, segredo_criptografado=cifrar_segredo(novo_segredo()),
                                       confirmada_em=timezone.now())
        self.cliente(self.professor).post(reverse('2fa-verificar'), {'codigo': '000000'})
        registro = RegistroAuditoria.objects.get(acao='FALHA_LOGIN', entidade='segundo fator')
        self.assertEqual(registro.autor, 'professor')
        self.assertNotIn('000000', registro.detalhes)

    @override_settings(ELO_2FA_ATIVO=True)
    def test_falha_na_recuperacao_administrativa_fica_registrada(self):
        conta = self.gestor.usuario.conta
        Configuracao2FA.objects.create(conta=conta, segredo_criptografado=cifrar_segredo(novo_segredo()),
                                       confirmada_em=timezone.now())
        reserva = criar_codigos_recuperacao(conta)[0]
        Client().post(reverse('admin-recuperar-senha'), {
            'usuario': 'gestor', 'codigo': '000000', 'codigo_recuperacao': reserva,
            'new_password1': 'SenhaNova@879', 'new_password2': 'SenhaNova@879'})
        registro = RegistroAuditoria.objects.get(entidade='recuperação de senha administrativa')
        self.assertEqual(registro.acao, 'FALHA_LOGIN')
        self.assertNotIn('gestor', registro.objeto_id)

    def test_alteracoes_de_conta_pelo_admin_django(self):
        conta = self.professor.usuario.conta
        requisicao = RequestFactory().post('/admin/')
        requisicao.user = get_user_model().objects.create_superuser('tecnico', password='Senha@Tecnica123')
        modelo_admin = site._registry[get_user_model()]
        modelo_admin.log_change(requisicao, conta, [{'changed': {'fields': ['password']}}])
        modelo_admin.log_change(requisicao, conta, [{'changed': {'fields': ['is_superuser']}}])
        self.assertTrue(RegistroAuditoria.objects.filter(acao='SENHA', entidade='conta de login',
                                                         objeto_id=str(conta.pk), autor='tecnico').exists())
        self.assertTrue(RegistroAuditoria.objects.filter(acao='PERMISSAO', entidade='conta de login',
                                                         objeto_id=str(conta.pk)).exists())

    def test_limpeza_da_auditoria_deixa_registro(self):
        antigo = RegistroAuditoria.objects.create(autor='x', acao='LOGIN')
        RegistroAuditoria.objects.filter(pk=antigo.pk).update(criado_em=timezone.now() - timedelta(days=400))
        call_command('limpar_registros', '--auditoria-dias', '365', stdout=StringIO())
        self.assertFalse(RegistroAuditoria.objects.filter(pk=antigo.pk).exists())
        self.assertTrue(RegistroAuditoria.objects.filter(acao='EXCLUSAO', entidade='Auditoria',
                                                         detalhes__startswith='1 registro').exists())


class ExclusaoDeUsuariosTests(CenarioTestCase):
    def test_exclusao_pela_tela_identifica_a_pessoa_e_remove_o_login(self):
        from aplicacao.models import Professor
        conta_id = self.outro_professor.usuario.conta_id
        resposta = self.cliente(self.gestor).post(reverse('professor-excluir', args=[self.outro_professor.pk]))
        self.assertEqual(resposta.status_code, 302)
        registro = RegistroAuditoria.objects.get(acao='EXCLUSAO', entidade='professor')
        self.assertIn('outro.professor Teste', registro.detalhes)
        self.assertIn('usuário: outro.professor', registro.detalhes)
        self.assertFalse(get_user_model().objects.filter(pk=conta_id).exists())

    def test_exclusao_em_lote_no_admin_remove_o_login(self):
        from aplicacao.models import Professor, Usuario
        conta_id = self.outro_professor.usuario.conta_id
        perfil_id = self.outro_professor.usuario_id
        requisicao = RequestFactory().post('/admin/')
        requisicao.user = get_user_model().objects.create_superuser('tecnico', password='Senha@Tecnica123')
        site._registry[Professor].delete_queryset(requisicao, Professor.objects.filter(pk=self.outro_professor.pk))
        self.assertFalse(Usuario.objects.filter(pk=perfil_id).exists())
        self.assertFalse(get_user_model().objects.filter(pk=conta_id).exists())
        self.assertIn('usuário: outro.professor',
                      RegistroAuditoria.objects.get(acao='EXCLUSAO', entidade='professor').detalhes)

    def test_exclusao_do_perfil_no_admin_remove_o_login(self):
        from aplicacao.models import Usuario
        perfil = self.outro_professor.usuario
        conta_id = perfil.conta_id
        requisicao = RequestFactory().post('/admin/')
        requisicao.user = get_user_model().objects.create_superuser('tecnico', password='Senha@Tecnica123')
        site._registry[Usuario].delete_model(requisicao, perfil)
        self.assertFalse(get_user_model().objects.filter(pk=conta_id).exists())


class IpNaAuditoriaTests(CenarioTestCase):
    def test_login_registra_ip_do_cliente(self):
        Client(REMOTE_ADDR='203.0.113.7').post(reverse('login'), {'username': 'ana', 'password': 'errada'})
        self.assertEqual(RegistroAuditoria.objects.get(acao='FALHA_LOGIN').ip, '203.0.113.7')

    @override_settings(CONFIAR_PROXY=True)
    def test_atras_do_proxy_usa_o_ip_garantido_pelo_balanceador(self):
        Client(REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR='1.1.1.1, 198.51.100.20').post(
            reverse('login'), {'username': 'ana', 'password': 'errada'})
        self.assertEqual(RegistroAuditoria.objects.get(acao='FALHA_LOGIN').ip, '198.51.100.20')

    def test_comando_local_fica_sem_ip_e_tela_mostra_coluna(self):
        from aplicacao.servicos.auditoria import registrar
        self.assertIsNone(registrar('EDICAO', entidade='teste').ip)
        resposta = self.cliente(self.gestor).get(reverse('auditoria'))
        self.assertContains(resposta, '<th>IP</th>', html=False)
