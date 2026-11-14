import base64
from datetime import timedelta
import hashlib
import io
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from django.test import override_settings, RequestFactory, SimpleTestCase
from django.urls import reverse
from aplicacao.servicos import google_calendar as google
from aplicacao.models import ConexaoGoogle, SincronizacaoGoogle
from testes.base import CenarioTestCase, HOJE


class ProtocoloGoogleTests(SimpleTestCase):
    def test_configuracao_completa_e_necessaria(self):
        self.assertTrue(google.configurado())
        for chave in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI', 'GOOGLE_TOKEN_ENCRYPTION_KEY'):
            with self.subTest(chave=chave), override_settings(**{chave: ''}):
                self.assertFalse(google.configurado())
        with override_settings(GOOGLE_TOKEN_ENCRYPTION_KEY='invalida'):
            self.assertFalse(google.configurado())

    def test_tokens_sao_cifrados_e_podem_ser_recuperados(self):
        dados = {'access_token': 'acesso-ficticio', 'refresh_token': 'renovacao-ficticia'}
        cifrado = google.cifrar(dados)
        self.assertNotIn('acesso-ficticio', cifrado)
        self.assertNotIn('renovacao-ficticia', cifrado)
        self.assertEqual(google.decifrar(SimpleNamespace(credenciais=cifrado)), dados)

    def test_credencial_adulterada_exige_reconexao(self):
        with self.assertRaises(google.ReconectarGoogle):
            google.decifrar(SimpleNamespace(credenciais='conteudo-adulterado'))

    def test_oauth_gera_estado_e_pkce_e_solicita_escopo_do_calendario(self):
        request = RequestFactory().get('/')
        request.session = {}
        request.user = SimpleNamespace(pk=9)
        url = google.iniciar_oauth(request)
        parametros = parse_qs(urlparse(url).query)
        fluxo = request.session['google_oauth']
        esperado = base64.urlsafe_b64encode(hashlib.sha256(fluxo['verifier'].encode()).digest()).decode().rstrip('=')
        self.assertEqual(parametros['state'], [fluxo['state']])
        self.assertEqual(parametros['code_challenge'], [esperado])
        self.assertEqual(parametros['code_challenge_method'], ['S256'])
        self.assertIn(google.SCOPES[1], parametros['scope'][0].split())
        self.assertEqual(fluxo['usuario'], 9)
        self.assertNotIn('code_verifier', parametros)

    def test_oauth_complementar_mantem_conta_selecionada(self):
        request = SimpleNamespace(session={}, user=SimpleNamespace(pk=9))
        parametros = parse_qs(urlparse(google.iniciar_oauth(request, 'conta-opaca')).query)
        self.assertEqual(parametros['login_hint'], ['conta-opaca'])
        self.assertEqual(parametros['prompt'], ['consent'])

    def test_requisicao_envia_json_e_token_no_cabecalho(self):
        resposta = MagicMock()
        resposta.__enter__.return_value.read.return_value = b'{"id": "evento"}'
        with patch.object(google, 'urlopen', return_value=resposta) as abrir:
            self.assertEqual(google.requisicao('https://example.invalid', metodo='POST',
                token='ficticio', dados={'summary': 'Tarefa'}), {'id': 'evento'})
        request = abrir.call_args.args[0]
        self.assertEqual(request.get_header('Authorization'), 'Bearer ficticio')
        self.assertEqual(json.loads(request.data), {'summary': 'Tarefa'})
        self.assertEqual(abrir.call_args.kwargs['timeout'], 15)

    def test_requisicao_envia_formulario_e_aceita_resposta_vazia(self):
        resposta = MagicMock()
        resposta.__enter__.return_value.read.return_value = b''
        with patch.object(google, 'urlopen', return_value=resposta) as abrir:
            self.assertEqual(google.requisicao('https://example.invalid', metodo='POST',
                                             formulario={'token': 'ficticio'}), {})
        self.assertEqual(parse_qs(abrir.call_args.args[0].data.decode()), {'token': ['ficticio']})

    def test_erro_http_preserva_codigo_sem_expor_segredo(self):
        erro = HTTPError('https://example.invalid', 400, 'erro', {}, io.BytesIO(b'{"error":"invalid_grant"}'))
        with patch.object(google, 'urlopen', side_effect=erro):
            with self.assertRaises(google.RespostaGoogle) as captura:
                google.requisicao('https://example.invalid', token='segredo')
        self.assertEqual(captura.exception.codigo, 'invalid_grant')
        self.assertEqual(captura.exception.status, 400)
        self.assertNotIn('segredo', str(captura.exception))

    def test_falha_de_rede_gera_mensagem_controlada(self):
        with patch.object(google, 'urlopen', side_effect=URLError('falha simulada')):
            with self.assertRaisesMessage(google.GoogleErro, 'Não foi possível comunicar'):
                google.requisicao('https://example.invalid')

    def test_resposta_json_invalida_e_tratada(self):
        resposta = MagicMock()
        resposta.__enter__.return_value.read.return_value = b'nao-json'
        with patch.object(google, 'urlopen', return_value=resposta):
            with self.assertRaises(google.GoogleErro):
                google.requisicao('https://example.invalid')

    def test_troca_codigo_exige_permissao_de_calendario(self):
        with patch.object(google, 'requisicao', side_effect=[
            {'access_token': 'a', 'scope': 'openid', 'refresh_token': 'r'}, {'sub': 'conta1'}]):
            with self.assertRaises(google.PermissaoCalendarioPendente) as captura:
                google.trocar_codigo('codigo', 'verificador')
        self.assertEqual(captura.exception.identidade, 'conta1')

    def test_troca_codigo_valida_identidade_e_cifra_tokens(self):
        with patch.object(google, 'requisicao', side_effect=[
            {'access_token': 'a', 'scope': ' '.join(google.SCOPES), 'refresh_token': 'r'}, {'sub': 'conta1'}]):
            identidade, cifrado = google.trocar_codigo('codigo', 'verificador')
        self.assertNotEqual(identidade, 'conta1')
        self.assertEqual(len(identidade), 64)
        self.assertEqual(google.decifrar(SimpleNamespace(credenciais=cifrado))['refresh_token'], 'r')

    def test_conta_diferente_no_fluxo_complementar_e_rejeitada(self):
        with patch.object(google, 'requisicao', side_effect=[
            {'access_token': 'a', 'scope': ' '.join(google.SCOPES)}, {'sub': 'conta2'}]):
            with self.assertRaisesMessage(google.GoogleErro, 'conta Google foi alterada'):
                google.trocar_codigo('codigo', 'verificador', conta_esperada='conta1')

    def test_respostas_sem_token_identidade_ou_refresh_sao_rejeitadas(self):
        casos = [[{}], [{'access_token': 'a'}, {}],
                 [{'access_token': 'a', 'scope': ' '.join(google.SCOPES)}, {'sub': 'conta1'}]]
        for respostas in casos:
            with self.subTest(respostas=respostas), patch.object(google, 'requisicao', side_effect=respostas):
                with self.assertRaises(google.GoogleErro):
                    google.trocar_codigo('codigo', 'verificador')


class SincronizacaoGoogleTests(CenarioTestCase):
    def setUp(self):
        self.tarefa = self.atividade(descricao='Orientações')
        self.conexao = ConexaoGoogle.objects.create(usuario=self.aluno.usuario, identidade='identidade-ficticia',
            credenciais=google.cifrar({'access_token': 'a', 'refresh_token': 'r', 'expira': time.time() + 3600}))

    def evento_confirmado(self, identificador='evento1', **campos):
        dados = {'id': identificador, 'status': 'confirmed', 'summary': 'ELO · Operações',
            'description': 'Atividade do ELO. Consulte as orientações e os materiais no próprio sistema.',
            'start': {'date': HOJE.isoformat()}, 'end': {'date': (HOJE + timedelta(days=1)).isoformat()}}
        dados.update(campos)
        return dados

    def test_token_valido_e_reutilizado_sem_renovar(self):
        with patch.object(google, 'requisicao') as requisicao:
            self.assertEqual(google.token_acesso(self.conexao), 'a')
        requisicao.assert_not_called()

    def test_token_expirado_e_renovado_e_salvo_cifrado(self):
        with patch.object(google, 'requisicao', return_value={'access_token': 'novo', 'refresh_token': 'novo-refresh'}):
            self.assertEqual(google.token_acesso(self.conexao, renovar=True), 'novo')
        self.conexao.refresh_from_db()
        self.assertNotIn('novo-refresh', self.conexao.credenciais)
        self.assertEqual(google.decifrar(self.conexao)['refresh_token'], 'novo-refresh')

    def test_token_revogado_exige_reconectar(self):
        with patch.object(google, 'requisicao', side_effect=google.RespostaGoogle(400, 'invalid_grant')):
            with self.assertRaises(google.ReconectarGoogle):
                google.token_acesso(self.conexao, renovar=True)

    def test_erro_401_renova_token_uma_vez(self):
        with patch.object(google, 'token_acesso', side_effect=['antigo', 'novo']) as token:
            with patch.object(google, 'requisicao', side_effect=[google.RespostaGoogle(401), {'id': 'evento1'}]):
                self.assertEqual(google.chamar_calendar(self.conexao, 'url', 'GET'), {'id': 'evento1'})
        self.assertEqual(token.call_count, 2)
        self.assertTrue(token.call_args.kwargs['renovar'])

    def test_erro_apos_renovacao_exige_reconectar(self):
        with patch.object(google, 'token_acesso', return_value='token'):
            with patch.object(google, 'requisicao', side_effect=[google.RespostaGoogle(401), google.RespostaGoogle(403)]):
                with self.assertRaises(google.ReconectarGoogle):
                    google.chamar_calendar(self.conexao, 'url', 'GET')

    def test_id_do_evento_e_estavel_e_separa_contas_e_atividades(self):
        original = google.evento_id(self.aluno.usuario, 'conta1', self.tarefa)
        self.assertEqual(original, google.evento_id(self.aluno.usuario, 'conta1', self.tarefa))
        self.assertNotEqual(original, google.evento_id(self.aluno.usuario, 'conta2', self.tarefa))
        self.assertNotEqual(original, google.evento_id(self.responsavel.usuario, 'conta1', self.tarefa))
        self.assertNotEqual(original, google.evento_id(self.aluno.usuario, 'conta1', self.atividade()))

    def test_evento_existente_e_atualizado_e_confirmado_sem_insert(self):
        with patch.object(google, 'chamar_calendar', side_effect=[{}, self.evento_confirmado()]) as chamar:
            self.assertEqual(google.enviar_atividade(self.conexao, self.tarefa, 'evento1'), 'evento1')
        self.assertEqual([c.args[2] for c in chamar.call_args_list], ['PATCH', 'GET'])
        dados = chamar.call_args_list[0].args[3]
        self.assertEqual(dados['visibility'], 'private')
        self.assertEqual(dados['end']['date'], (HOJE + timedelta(days=1)).isoformat())

    def test_evento_inexistente_e_criado_com_id_estavel(self):
        with patch.object(google, 'chamar_calendar', side_effect=[
            google.RespostaGoogle(404), {}, self.evento_confirmado()]) as chamar:
            self.assertEqual(google.enviar_atividade(self.conexao, self.tarefa, 'evento1'), 'evento1')
        self.assertEqual([c.args[2] for c in chamar.call_args_list], ['PATCH', 'POST', 'GET'])
        self.assertEqual(chamar.call_args_list[1].args[3]['id'], 'evento1')

    def test_evento_apagado_com_id_reservado_recebe_sucessor_deterministico(self):
        sucessor = 'elo' + hashlib.sha256(b'evento1:recriado').hexdigest()
        respostas = [google.RespostaGoogle(410), google.RespostaGoogle(409), google.RespostaGoogle(410),
                     google.RespostaGoogle(404), {}, self.evento_confirmado(sucessor)]
        with patch.object(google, 'chamar_calendar', side_effect=respostas):
            self.assertEqual(google.enviar_atividade(self.conexao, self.tarefa, 'evento1'), sucessor)

    def test_google_que_nao_atualizou_data_nao_e_reportado_como_sucesso(self):
        evento_antigo = self.evento_confirmado(start={'date': '2026-11-05'})
        with patch.object(google, 'chamar_calendar', side_effect=[{}, evento_antigo]):
            with self.assertRaisesMessage(google.GoogleErro, 'não confirmou'):
                google.enviar_atividade(self.conexao, self.tarefa, 'evento1')

    def test_atividade_sem_data_nao_e_enviada(self):
        self.tarefa.data_entrega = None
        with patch.object(google, 'chamar_calendar') as chamar:
            with self.assertRaises(google.GoogleErro):
                google.enviar_atividade(self.conexao, self.tarefa, 'evento1')
        chamar.assert_not_called()

    def test_repetir_sincronizacao_pela_tela_nao_duplica_registro(self):
        cliente = self.cliente(self.aluno)
        url = reverse('google-sincronizar', args=[self.tarefa.pk])
        with patch.object(google, 'enviar_atividade', return_value='evento1') as enviar:
            self.assertEqual(cliente.post(url).status_code, 302)
            self.tarefa.data_entrega = HOJE + timedelta(days=3)
            self.tarefa.save()
            self.assertEqual(cliente.post(url).status_code, 302)
        self.assertEqual(SincronizacaoGoogle.objects.count(), 1)
        self.assertIsNotNone(SincronizacaoGoogle.objects.get().sincronizado_em)
        self.assertEqual(enviar.call_args.args[1].data_entrega, HOJE + timedelta(days=3))
        self.assertEqual(enviar.call_args.args[2], 'evento1')

    def test_falha_no_google_nao_grava_sincronizacao_bem_sucedida(self):
        with patch.object(google, 'enviar_atividade', side_effect=google.GoogleErro('Falha simulada')):
            resposta = self.cliente(self.aluno).post(reverse('google-sincronizar', args=[self.tarefa.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(SincronizacaoGoogle.objects.exists())

    def test_revogacao_remove_conexao_e_nao_registra_sucesso(self):
        with patch.object(google, 'enviar_atividade', side_effect=google.ReconectarGoogle('Reconecte')):
            self.cliente(self.aluno).post(reverse('google-sincronizar', args=[self.tarefa.pk]))
        self.assertFalse(ConexaoGoogle.objects.exists())
        self.assertFalse(SincronizacaoGoogle.objects.exists())

    def test_outro_aluno_nao_pode_sincronizar_atividade(self):
        with patch.object(google, 'enviar_atividade') as enviar:
            resposta = self.cliente(self.outro_aluno).post(reverse('google-sincronizar', args=[self.tarefa.pk]))
        self.assertEqual(resposta.status_code, 404)
        enviar.assert_not_called()

    def test_atividade_cancelada_nao_e_sincronizada(self):
        self.tarefa.situacao = 'CANCELADA'
        self.tarefa.save()
        with patch.object(google, 'enviar_atividade') as enviar:
            self.cliente(self.aluno).post(reverse('google-sincronizar', args=[self.tarefa.pk]))
        enviar.assert_not_called()


class FluxoOAuthTests(CenarioTestCase):
    def setUp(self):
        self.cliente_aluno = self.cliente(self.aluno)

    def iniciar(self):
        resposta = self.cliente_aluno.post(reverse('google-conectar'))
        self.assertEqual(resposta.status_code, 302)
        return self.cliente_aluno.session['google_oauth']

    def test_tela_mostra_conectar_quando_configurado(self):
        resposta = self.cliente_aluno.get(reverse('minhas-atividades'))
        self.assertTrue(resposta.context['google_configurado'])
        self.assertNotContains(resposta, 'Integração ainda não configurada pelo administrador.')

    def test_tela_mostra_em_configuracao_quando_falta_chave(self):
        with override_settings(GOOGLE_CLIENT_SECRET=''):
            resposta = self.cliente_aluno.get(reverse('minhas-atividades'))
            self.assertContains(resposta, 'Integração ainda não configurada pelo administrador.')
            self.assertRedirects(self.cliente_aluno.post(reverse('google-conectar')),
                                 reverse('minhas-atividades'), fetch_redirect_response=False)

    def test_retorno_valido_grava_conexao(self):
        fluxo = self.iniciar()
        with patch.object(google, 'trocar_codigo', return_value=('id-ficticio', google.cifrar({'token': 'ficticio'}))):
            resposta = self.cliente_aluno.get(reverse('google-retorno'), {'state': fluxo['state'], 'code': 'codigo'})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(ConexaoGoogle.objects.get().usuario_id, self.aluno.usuario_id)
        self.assertNotIn('google_oauth', self.cliente_aluno.session)

    def test_state_incorreto_nao_troca_codigo(self):
        self.iniciar()
        with patch.object(google, 'trocar_codigo') as trocar:
            self.cliente_aluno.get(reverse('google-retorno'), {'state': 'incorreto', 'code': 'codigo'})
        trocar.assert_not_called()
        self.assertFalse(ConexaoGoogle.objects.exists())

    def test_fluxo_expirado_nao_troca_codigo(self):
        fluxo = self.iniciar()
        sessao = self.cliente_aluno.session
        sessao['google_oauth'] = dict(fluxo, criado=time.time() - 601)
        sessao.save()
        with patch.object(google, 'trocar_codigo') as trocar:
            self.cliente_aluno.get(reverse('google-retorno'), {'state': fluxo['state'], 'code': 'codigo'})
        trocar.assert_not_called()

    def test_autorizacao_parcial_continua_uma_vez_sem_voltar_ao_painel(self):
        fluxo = self.iniciar()
        with patch.object(google, 'trocar_codigo', side_effect=google.PermissaoCalendarioPendente('conta1')):
            resposta = self.cliente_aluno.get(reverse('google-retorno'), {'state': fluxo['state'], 'code': 'codigo'})
            self.assertTrue(resposta.url.startswith('https://accounts.google.com/'))
            complementar = self.cliente_aluno.session['google_oauth']
            self.assertEqual(complementar['conta_google'], 'conta1')
            self.assertNotEqual(complementar['state'], fluxo['state'])
            resposta = self.cliente_aluno.get(reverse('google-retorno'),
                {'state': complementar['state'], 'code': 'segundo-codigo'})
        self.assertRedirects(resposta, reverse('minhas-atividades'), fetch_redirect_response=False)
        self.assertFalse(ConexaoGoogle.objects.exists())

    def test_usuario_cancela_autorizacao_sem_criar_conexao(self):
        fluxo = self.iniciar()
        with patch.object(google, 'trocar_codigo') as trocar:
            self.cliente_aluno.get(reverse('google-retorno'), {'state': fluxo['state'], 'error': 'access_denied'})
        trocar.assert_not_called()
        self.assertFalse(ConexaoGoogle.objects.exists())

    def test_desconexao_remove_credenciais_mesmo_se_revogacao_remota_falhar(self):
        ConexaoGoogle.objects.create(usuario=self.aluno.usuario, identidade='id', credenciais=google.cifrar({}))
        with patch.object(google, 'revogar', side_effect=google.GoogleErro('Indisponível')):
            resposta = self.cliente_aluno.post(reverse('google-desconectar'))
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(ConexaoGoogle.objects.exists())

    def test_professor_nao_pode_conectar_conta_pelo_portal_dos_alunos(self):
        self.assertEqual(self.cliente(self.professor).post(reverse('google-conectar')).status_code, 403)
