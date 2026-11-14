from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.test import Client, override_settings, RequestFactory
from django.urls import reverse
from django.utils import timezone
from aplicacao.servicos.acesso import alunos_permitidos, perfil_ativo
from aplicacao.servicos.documentos_legais import documentos_aceitos
from aplicacao.servicos.limite_login import autenticar_com_limite
from aplicacao.models import LimiteLogin, RegistroAuditoria, Usuario
from testes.base import CenarioTestCase, SENHA


class AcessoTests(CenarioTestCase):
    def test_paginas_publicas_abrem_sem_login(self):
        for rota in ('login', 'recuperar-senha', 'sobre', 'termos-uso', 'politica-privacidade', 'privacidade-aluno'):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(reverse(rota)).status_code, 200)

    def test_pagina_privada_redireciona_anonimo_para_login(self):
        resposta = self.client.get(reverse('aluno-listar'))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn('/login/?next=', resposta.url)

    def test_aluno_e_responsavel_nao_acessam_cadastros_e_aprovacoes(self):
        for pessoa in (self.aluno, self.responsavel):
            cliente = self.cliente(pessoa)
            for rota in ('aluno-listar', 'usuario-criar', 'atividade-criar', 'aprovacoes', 'auditoria'):
                with self.subTest(perfil=pessoa.usuario.tipo_perfil, rota=rota):
                    self.assertEqual(cliente.get(reverse(rota)).status_code, 403)

    def test_somente_gestor_acessa_auditoria_e_cadastro_professor(self):
        for rota in ('auditoria', 'professor-criar'):
            with self.subTest(rota=rota):
                self.assertEqual(self.cliente(self.professor).get(reverse(rota)).status_code, 403)
                self.assertEqual(self.cliente(self.gestor).get(reverse(rota)).status_code, 200)

    def test_troca_obrigatoria_bloqueia_paginas_e_api(self):
        self.aluno.usuario.troca_senha_obrigatoria = True
        self.aluno.usuario.save()
        cliente = self.cliente(self.aluno)
        self.assertRedirects(cliente.get(reverse('meta-listar')), reverse('trocar-senha'), fetch_redirect_response=False)
        self.assertEqual(cliente.get(reverse('api-painel')).status_code, 403)
        self.assertEqual(cliente.get(reverse('trocar-senha')).status_code, 200)

    def test_termos_desatualizados_bloqueiam_paginas_e_api(self):
        self.aluno.usuario.versao_termos_aceita = 'antiga'
        self.aluno.usuario.save()
        cliente = self.cliente(self.aluno)
        resposta = cliente.get(reverse('meta-listar'))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('aceitar-termos'), resposta.url)
        self.assertEqual(cliente.get(reverse('api-painel')).status_code, 403)

    def test_perfil_inativo_perde_acesso_mesmo_com_sessao(self):
        cliente = self.cliente(self.aluno)
        self.aluno.ativo = False
        self.aluno.save()
        resposta = cliente.get(reverse('meta-listar'))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn('/login/', resposta.url)
        self.assertEqual(cliente.get(reverse('api-painel')).status_code, 403)
        self.assertIsNone(perfil_ativo(get_user_model().objects.get(pk=self.aluno.usuario.conta_id)))

    def test_conta_sem_perfil_nao_acessa_api(self):
        conta = get_user_model().objects.create_user(username='semperfil', password=SENHA)
        self.client.force_login(conta)
        self.assertEqual(self.client.get(reverse('api-painel')).status_code, 403)

    def test_regras_atuais_de_visibilidade_por_perfil(self):
        self.assertEqual(set(alunos_permitidos(self.professor.usuario).values_list('pk', flat=True)),
                         {self.aluno.pk})
        self.assertEqual(set(alunos_permitidos(self.gestor.usuario).values_list('pk', flat=True)),
                         {self.aluno.pk, self.outro_aluno.pk})
        self.assertEqual(list(alunos_permitidos(self.aluno.usuario)), [self.aluno])
        self.assertEqual(list(alunos_permitidos(self.responsavel.usuario)), [self.aluno])

    def test_acompanhamento_individual_nao_vaza_outro_aluno(self):
        cliente = self.cliente(self.aluno)
        self.assertEqual(cliente.get(reverse('aluno-inicio', args=[self.aluno.pk])).status_code, 200)
        self.assertEqual(cliente.get(reverse('aluno-inicio', args=[self.outro_aluno.pk])).status_code, 403)

    def test_destino_inicial_por_perfil(self):
        for pessoa in (self.professor, self.gestor, self.aluno, self.responsavel):
            with self.subTest(perfil=pessoa.usuario.tipo_perfil):
                cliente = self.cliente(pessoa)
                self.assertRedirects(cliente.get(reverse('inicio')),
                                     reverse('pagina-inicial'), fetch_redirect_response=False)
                self.assertEqual(cliente.get(reverse('pagina-inicial')).status_code, 200)

    def test_acompanhamento_sem_permissao_nao_oferece_envio(self):
        self.vinculo.mesclar_perfis = False
        self.vinculo.save()
        cliente = self.cliente(self.responsavel)
        resposta = cliente.get(reverse('aluno-inicio', args=[self.aluno.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['url_atividades'],
                         reverse('minhas-atividades') + f'?aluno={self.aluno.pk}')
        self.assertFalse(resposta.context['pode_enviar_atividades'])
        self.assertNotContains(resposta, 'Abrir atividades e solicitar conclusão')
        self.assertContains(resposta, 'Ver atividades')
        atividade = self.atividade()
        self.assertEqual(cliente.post(reverse('api-solicitar-conclusao', args=[atividade.pk]),
                                      {}, content_type='application/json').status_code, 404)

    def test_permissao_de_outro_filho_nao_libera_botao_deste_aluno(self):
        from aplicacao.models import VinculoFamiliar
        self.vinculo.mesclar_perfis = False
        self.vinculo.save()
        VinculoFamiliar.objects.create(aluno=self.outro_aluno, responsavel=self.responsavel,
                                      ativo=True, mesclar_perfis=True)
        cliente = self.cliente(self.responsavel)
        resposta = cliente.get(reverse('aluno-inicio', args=[self.aluno.pk]))
        self.assertEqual(resposta.context['url_atividades'],
                         reverse('minhas-atividades') + f'?aluno={self.aluno.pk}')
        self.assertFalse(resposta.context['pode_enviar_atividades'])
        liberada = cliente.get(reverse('aluno-inicio', args=[self.outro_aluno.pk]))
        destino = reverse('minhas-atividades') + f'?aluno={self.outro_aluno.pk}'
        self.assertEqual(liberada.context['url_atividades'], destino)
        self.assertTrue(liberada.context['pode_enviar_atividades'])
        self.assertContains(liberada, 'Abrir atividades e solicitar conclusão')
        self.assertEqual(cliente.get(destino).status_code, 200)

    def test_aluno_mantem_botao_para_as_proprias_atividades(self):
        resposta = self.cliente(self.aluno).get(reverse('aluno-inicio', args=[self.aluno.pk]))
        self.assertEqual(resposta.context['url_atividades'],
                         reverse('minhas-atividades') + f'?aluno={self.aluno.pk}')

    def test_logout_requer_post_e_remove_sessao(self):
        cliente = self.cliente(self.aluno)
        self.assertEqual(cliente.get(reverse('logout')).status_code, 405)
        self.assertEqual(cliente.post(reverse('logout')).status_code, 302)
        self.assertNotIn('_auth_user_id', cliente.session)
        self.assertTrue(RegistroAuditoria.objects.filter(acao='SAIDA', autor='ana').exists())


class SenhasCadastroTests(CenarioTestCase):
    NOVA = 'Senha-nova@39582'

    def test_login_normaliza_usuario_e_registra_entrada(self):
        resposta = self.client.post(reverse('login'), {'username': ' ANA ', 'password': SENHA})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.aluno.usuario.conta_id)
        self.assertTrue(RegistroAuditoria.objects.filter(acao='LOGIN', autor='ana').exists())

    def test_login_aceita_conta_gravada_com_maiusculas(self):
        conta = self.aluno.usuario.conta
        get_user_model().objects.filter(pk=conta.pk).update(username='Ana')
        resposta = self.client.post(reverse('login'), {'username': 'ana', 'password': SENHA})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), conta.pk)

    def test_perfil_salvo_pelo_admin_fica_em_minusculas(self):
        perfil = Usuario.objects.create(usuario='  Novo.Usuario ', tipo_perfil='ALUNO')
        self.assertEqual(perfil.usuario, 'novo.usuario')

    def test_senha_armazenada_e_hash_e_nao_texto(self):
        conta = self.aluno.usuario.conta
        self.assertNotEqual(conta.password, SENHA)
        self.assertEqual(identify_hasher(conta.password).algorithm, 'pbkdf2_sha256')
        self.assertTrue(conta.check_password(SENHA))
        self.assertFalse(conta.check_password('senha errada'))

    def test_professor_redefine_senha_e_usuario_deve_trocar_no_proximo_login(self):
        cliente_antigo = self.cliente(self.aluno)
        resposta = self.cliente(self.professor).post(
            reverse('usuario-redefinir-senha', args=[self.aluno.usuario_id]),
            {'new_password1': self.NOVA, 'new_password2': self.NOVA})
        self.assertEqual(resposta.status_code, 302)
        self.aluno.usuario.refresh_from_db()
        self.assertTrue(self.aluno.usuario.troca_senha_obrigatoria)
        self.assertTrue(self.aluno.usuario.conta.check_password(self.NOVA))
        self.assertFalse(self.aluno.usuario.conta.check_password(SENHA))
        self.assertIn('/login/', cliente_antigo.get(reverse('meta-listar')).url)
        cliente = Client()
        self.assertTrue(cliente.login(username='ana', password=self.NOVA))
        self.assertRedirects(cliente.get(reverse('meta-listar')), reverse('trocar-senha'), fetch_redirect_response=False)
        self.assertTrue(RegistroAuditoria.objects.filter(acao='SENHA', objeto_id=str(self.aluno.usuario_id)).exists())

    def test_gestor_redefine_senha_do_responsavel(self):
        resposta = self.cliente(self.gestor).post(
            reverse('usuario-redefinir-senha', args=[self.responsavel.usuario_id]),
            {'new_password1': self.NOVA, 'new_password2': self.NOVA})
        self.assertEqual(resposta.status_code, 302)
        self.responsavel.usuario.refresh_from_db()
        self.assertTrue(self.responsavel.usuario.troca_senha_obrigatoria)

    def test_gestor_redefine_professor_sem_alunos_e_invalida_sessao(self):
        from aplicacao.models import Vinculo, Aluno
        Vinculo.objects.all().delete()
        Aluno.objects.all().delete()
        cliente_antigo = self.cliente(self.professor)
        resposta = self.cliente(self.gestor).post(
            reverse('usuario-redefinir-senha', args=[self.professor.usuario_id]),
            {'new_password1': self.NOVA, 'new_password2': self.NOVA})
        self.assertRedirects(resposta, reverse('professor-listar'), fetch_redirect_response=False)
        self.professor.usuario.refresh_from_db()
        self.assertTrue(self.professor.usuario.conta.check_password(self.NOVA))
        self.assertTrue(self.professor.usuario.troca_senha_obrigatoria)
        self.assertIn('/login/', cliente_antigo.get(reverse('inicio')).url)
        cliente = Client()
        self.assertTrue(cliente.login(username='professor', password=self.NOVA))
        self.assertRedirects(cliente.get(reverse('inicio')), reverse('trocar-senha'), fetch_redirect_response=False)
        self.assertTrue(RegistroAuditoria.objects.filter(acao='SENHA', objeto_id=str(self.professor.usuario_id)).exists())

    def test_outros_perfis_nao_redefinem_professor_por_post(self):
        url = reverse('usuario-redefinir-senha', args=[self.outro_professor.usuario_id])
        for pessoa in (self.professor, self.aluno, self.responsavel):
            with self.subTest(perfil=pessoa.usuario.tipo_perfil):
                resposta = self.cliente(pessoa).post(url, {'new_password1': self.NOVA, 'new_password2': self.NOVA})
                self.assertIn(resposta.status_code, (403, 404))
        self.outro_professor.usuario.conta.refresh_from_db()
        self.assertTrue(self.outro_professor.usuario.conta.check_password(SENHA))
        self.assertFalse(RegistroAuditoria.objects.filter(acao='SENHA').exists())

    def test_conta_gestor_permanece_protegida(self):
        resposta = self.cliente(self.gestor).post(
            reverse('usuario-redefinir-senha', args=[self.gestor.usuario_id]),
            {'new_password1': self.NOVA, 'new_password2': self.NOVA})
        self.assertEqual(resposta.status_code, 404)
        self.gestor.usuario.conta.refresh_from_db()
        self.assertTrue(self.gestor.usuario.conta.check_password(SENHA))

    def test_professor_nao_redefine_senha_de_outro_professor(self):
        resposta = self.cliente(self.professor).get(
            reverse('usuario-redefinir-senha', args=[self.outro_professor.usuario_id]))
        self.assertEqual(resposta.status_code, 404)

    def test_aluno_nao_redefine_senha_pelo_painel_do_professor(self):
        resposta = self.cliente(self.aluno).post(reverse('usuario-redefinir-senha', args=[self.outro_aluno.usuario_id]),
            {'new_password1': self.NOVA, 'new_password2': self.NOVA})
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(self.outro_aluno.usuario.conta.check_password(SENHA))

    def test_redefinicao_rejeita_senha_igual_fraca_ou_confirmacao_diferente(self):
        cliente = self.cliente(self.professor)
        for senha, confirmacao in [(SENHA, SENHA), ('123', '123'), (self.NOVA, 'outra')]:
            with self.subTest(senha=senha):
                resposta = cliente.post(reverse('usuario-redefinir-senha', args=[self.aluno.usuario_id]),
                    {'new_password1': senha, 'new_password2': confirmacao})
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context['formulario'].errors)
        self.aluno.usuario.conta.refresh_from_db()
        self.assertTrue(self.aluno.usuario.conta.check_password(SENHA))

    def test_troca_inicial_valida_remove_obrigacao_e_preserva_sessao(self):
        self.aluno.usuario.troca_senha_obrigatoria = True
        self.aluno.usuario.save()
        cliente = self.cliente(self.aluno)
        resposta = cliente.post(reverse('trocar-senha'), {'old_password': SENHA,
            'new_password1': self.NOVA, 'new_password2': self.NOVA})
        self.assertEqual(resposta.status_code, 302)
        self.aluno.usuario.refresh_from_db()
        self.assertFalse(self.aluno.usuario.troca_senha_obrigatoria)
        self.assertEqual(cliente.get(reverse('meta-listar')).status_code, 200)

    def test_troca_inicial_rejeita_reutilizacao_da_senha(self):
        self.aluno.usuario.troca_senha_obrigatoria = True
        self.aluno.usuario.save()
        resposta = self.cliente(self.aluno).post(reverse('trocar-senha'),
            {'old_password': SENHA, 'new_password1': SENHA, 'new_password2': SENHA})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('new_password1', resposta.context['formulario'].errors)

    def test_cadastro_cria_conta_perfil_e_pessoa_com_troca_obrigatoria(self):
        dados = dict(nome='Nova', sobrenome='Pessoa', username='NOVA.PESSOA',
                     tipo_perfil='ALUNO', data_nascimento='2015-03-10',
                     password1=self.NOVA, password2=self.NOVA)
        resposta = self.cliente(self.gestor).post(reverse('usuario-criar'), dados)
        self.assertEqual(resposta.status_code, 302)
        perfil = Usuario.objects.get(usuario='nova.pessoa')
        self.assertEqual(perfil.aluno_perfil.nome, 'Nova')
        self.assertTrue(perfil.troca_senha_obrigatoria)
        self.assertFalse(documentos_aceitos(perfil))
        self.assertTrue(perfil.conta.check_password(self.NOVA))

    def test_professor_comum_nao_cria_professor_mesmo_manipulando_formulario(self):
        resposta = self.cliente(self.professor).post(reverse('usuario-criar'),
            dict(nome='Novo', sobrenome='Professor', username='novo.prof', tipo_perfil='PROFESSOR',
                 password1=self.NOVA, password2=self.NOVA))
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Usuario.objects.filter(usuario='novo.prof').exists())

    def test_cadastro_impede_usuario_duplicado_sem_diferenciar_caixa(self):
        resposta = self.cliente(self.gestor).post(reverse('usuario-criar'),
            dict(nome='Outra', sobrenome='Pessoa', username='ANA', tipo_perfil='ALUNO',
                 password1=self.NOVA, password2=self.NOVA))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('username', resposta.context['formulario'].errors)


class TermosTests(CenarioTestCase):
    def setUp(self):
        self.aluno.usuario.documentos_aceitos_em = None
        self.aluno.usuario.save()
        self.cliente_aluno = self.cliente(self.aluno)

    def test_checkbox_e_obrigatorio(self):
        self.cliente_aluno.post(reverse('aceitar-termos'), {'next': '/metas/'})
        self.aluno.usuario.refresh_from_db()
        self.assertFalse(documentos_aceitos(self.aluno.usuario))

    def test_aceite_grava_versoes_data_e_auditoria(self):
        resposta = self.cliente_aluno.post(reverse('aceitar-termos'), {'aceite': 'on', 'next': '/metas/'})
        self.assertRedirects(resposta, '/metas/', fetch_redirect_response=False)
        self.aluno.usuario.refresh_from_db()
        self.assertTrue(documentos_aceitos(self.aluno.usuario))
        self.assertTrue(RegistroAuditoria.objects.filter(acao='DOCUMENTOS', autor='ana').exists())

    def test_next_externo_nao_e_seguido(self):
        resposta = self.cliente_aluno.post(reverse('aceitar-termos'),
                                          {'aceite': 'on', 'next': 'https://externo.invalid/'})
        self.assertRedirects(resposta, reverse('inicio'), fetch_redirect_response=False)


@override_settings(LOGIN_MAX_FALHAS=3, LOGIN_MAX_FALHAS_IP=5, LOGIN_BLOQUEIO_SEGUNDOS=60)
class LimiteLoginTests(CenarioTestCase):
    def test_tres_falhas_bloqueiam_ate_mesmo_senha_correta(self):
        for _ in range(3):
            self.client.post(reverse('login'), {'username': 'ana', 'password': 'incorreta'})
        resposta = self.client.post(reverse('login'), {'username': 'ana', 'password': SENHA})
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(resposta, 'Muitas tentativas')
        self.assertTrue(RegistroAuditoria.objects.filter(acao='BLOQUEIO_LOGIN').exists())

    def test_expiracao_do_bloqueio_permite_login(self):
        instante = timezone.now()
        with patch('aplicacao.servicos.limite_login.timezone.now', return_value=instante):
            for _ in range(3):
                self.client.post(reverse('login'), {'username': 'ana', 'password': 'incorreta'})
        with patch('aplicacao.servicos.limite_login.timezone.now', return_value=instante + timedelta(seconds=61)):
            self.assertTrue(self.client.login(username='ana', password=SENHA))

    def test_sucesso_nao_zera_falhas_do_ip_contra_outras_contas(self):
        request = RequestFactory().get('/', REMOTE_ADDR='192.0.2.1')
        autenticar_com_limite(request, 'ana', lambda nome: None)
        autenticar_com_limite(request, 'bruno', lambda nome: None)
        autenticar_com_limite(request, 'ana', lambda nome: self.aluno.usuario.conta)
        self.assertEqual(sorted(LimiteLogin.objects.values_list('falhas', flat=True)), [0, 0, 1, 1, 2])

    def test_nome_ip_e_senha_nao_sao_guardados_nos_logs_de_falha(self):
        self.client.post(reverse('login'), {'username': 'inexistente', 'password': 'segredo-unico'},
                         REMOTE_ADDR='192.0.2.9')
        for chave in LimiteLogin.objects.values_list('chave', flat=True):
            self.assertNotIn('inexistente', chave)
            self.assertNotIn('192.0.2.9', chave)
        eventos = str(list(RegistroAuditoria.objects.values()))
        self.assertNotIn('segredo-unico', eventos)
        self.assertNotIn('inexistente', eventos)

    def test_cabecalho_forwarded_nao_contorna_limite_de_ip(self):
        for i in range(5):
            self.client.post(reverse('login'), {'username': f'inexistente{i}', 'password': 'erro'},
                             HTTP_X_FORWARDED_FOR=f'192.0.2.{i}')
        resposta = self.client.post(reverse('login'), {'username': 'ana', 'password': SENHA},
                                   HTTP_X_FORWARDED_FOR='198.51.100.1')
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
