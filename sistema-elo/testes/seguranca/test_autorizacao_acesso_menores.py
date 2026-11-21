"""Regressão: acesso de crianças somente com autorização específica do adulto."""
from datetime import date
from django.urls import reverse
from django.utils import timezone
from aplicacao.models import AutorizacaoAcessoMenor, VinculoFamiliar
from aplicacao.servicos.autorizacao_menores import menor_de_12
from aplicacao.servicos.documentos_legais import VERSAO_TERMOS
from testes.base import CenarioTestCase


class AutorizacaoAcessoMenoresTests(CenarioTestCase):
    def setUp(self):
        # Janeiro garante menos de 12 anos em qualquer mês do ano de execução.
        self.aluno.data_nascimento = date(timezone.localdate().year - 11, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        self.rota = reverse('autorizar-acesso-menor')

    def autorizar(self, aluno=None, responsavel=None):
        aluno = aluno or self.aluno
        responsavel = responsavel or self.responsavel
        return self.cliente(responsavel).post(self.rota, {
            'aluno_id': str(aluno.pk), 'autorizo': 'on',
        })

    def test_menor_bloqueado_em_telas_e_api_mesmo_que_ja_tenha_aceitado_termos(self):
        cliente = self.cliente(self.aluno)
        resposta = cliente.get(reverse('pagina-inicial'))
        self.assertRedirects(resposta, reverse('aguardando-autorizacao'), fetch_redirect_response=False)
        self.assertContains(cliente.get(reverse('aguardando-autorizacao')), 'Aguardando autorização')
        self.assertEqual(cliente.get(reverse('api-painel')).status_code, 403)
        self.assertRedirects(cliente.get(reverse('aceitar-termos')),
                             reverse('aguardando-autorizacao'), fetch_redirect_response=False)
        self.assertRedirects(cliente.post(reverse('aceitar-termos'), {'aceite': 'on'}),
                             reverse('aguardando-autorizacao'), fetch_redirect_response=False)
        self.assertEqual(cliente.get(reverse('atividade-listar')).status_code, 302)

    def test_responsavel_mantem_acesso_a_dados_antes_da_autorizacao_do_menor(self):
        """O bloqueio do login da criança não deve ocultar cadastros da família."""
        from aplicacao.servicos.acesso import alunos_area_estudante, alunos_permitidos

        perfil_adulto = self.responsavel.usuario
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(aluno=self.aluno).exists())
        self.assertTrue(alunos_permitidos(perfil_adulto).filter(pk=self.aluno.pk).exists())
        self.assertTrue(alunos_area_estudante(perfil_adulto).filter(pk=self.aluno.pk).exists())
        self.assertRedirects(
            self.cliente(self.aluno).get(reverse('pagina-inicial')),
            reverse('aguardando-autorizacao'), fetch_redirect_response=False,
        )

    def test_termos_do_responsavel_sozinhos_nao_liberam_menor(self):
        self.assertTrue(self.responsavel.usuario.documentos_aceitos_em)
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(aluno=self.aluno).exists())
        self.assertRedirects(self.cliente(self.aluno).get(reverse('pagina-inicial')),
                             reverse('aguardando-autorizacao'), fetch_redirect_response=False)
        resposta = self.cliente(self.responsavel).get(reverse('pagina-inicial'))
        self.assertContains(resposta, 'Autorizar acesso de menores')

    def test_responsavel_vinculado_autoriza_e_liberacao_e_imediata(self):
        cliente_aluno = self.cliente(self.aluno)
        resposta = self.autorizar()
        self.assertRedirects(resposta, self.rota, fetch_redirect_response=False)
        autorizacao = AutorizacaoAcessoMenor.objects.get(aluno=self.aluno, responsavel=self.responsavel)
        self.assertEqual(autorizacao.versao_termos, VERSAO_TERMOS)
        self.assertEqual(cliente_aluno.get(reverse('pagina-inicial')).status_code, 200)
        self.assertEqual(cliente_aluno.get(reverse('minhas-atividades')).status_code, 200)
        self.assertNotEqual(cliente_aluno.get(reverse('api-painel')).status_code, 403)
        # Nenhum aceite em nome da criança foi forjado.
        self.aluno.usuario.refresh_from_db()
        self.assertIsNotNone(self.aluno.usuario.documentos_aceitos_em)
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(responsavel__usuario=self.aluno.usuario).exists())

    def test_revogacao_pelo_responsavel_bloqueia_sem_encerrar_sessao(self):
        cliente = self.cliente(self.aluno)
        self.autorizar()
        self.assertEqual(cliente.get(reverse('pagina-inicial')).status_code, 200)
        self.cliente(self.responsavel).post(self.rota, {
            'aluno_id': str(self.aluno.pk), 'acao': 'revogar',
        })
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(aluno=self.aluno).exists())
        self.assertRedirects(cliente.get(reverse('pagina-inicial')),
                             reverse('aguardando-autorizacao'), fetch_redirect_response=False)

    def test_aluno_nao_pode_autorizar_outro_aluno(self):
        resposta = self.cliente(self.aluno).post(self.rota, {
            'aluno_id': str(self.aluno.pk), 'autorizo': 'on',
        })
        self.assertRedirects(resposta, reverse('aguardando-autorizacao'),
                             fetch_redirect_response=False)
        self.assertFalse(AutorizacaoAcessoMenor.objects.exists())

    def test_responsavel_sem_termos_vigentes_nao_autoriza(self):
        self.responsavel.usuario.documentos_aceitos_em = None
        self.responsavel.usuario.save(update_fields=['documentos_aceitos_em'])
        resposta = self.cliente(self.responsavel).post(self.rota, {
            'aluno_id': str(self.aluno.pk), 'autorizo': 'on',
        })
        self.assertIn(reverse('aceitar-termos'), resposta.url)
        self.assertFalse(AutorizacaoAcessoMenor.objects.exists())

    def test_crianca_sem_aceite_proprio_usa_o_sistema_apos_autorizacao(self):
        perfil = self.aluno.usuario
        perfil.documentos_aceitos_em = None
        perfil.versao_termos_aceita = ''
        perfil.versao_privacidade_ciente = ''
        perfil.save()
        self.autorizar()
        self.assertEqual(self.cliente(self.aluno).get(reverse('pagina-inicial')).status_code, 200)
        perfil.refresh_from_db()
        self.assertIsNone(perfil.documentos_aceitos_em)

    def test_desativar_vinculo_bloqueia_imediatamente_sessao_existente(self):
        cliente = self.cliente(self.aluno)
        self.autorizar()
        self.assertEqual(cliente.get(reverse('pagina-inicial')).status_code, 200)
        self.vinculo.ativo = False
        self.vinculo.save(update_fields=['ativo'])
        self.assertRedirects(cliente.get(reverse('pagina-inicial')),
                             reverse('aguardando-autorizacao'), fetch_redirect_response=False)
        self.assertEqual(cliente.get(reverse('api-painel')).status_code, 403)

    def test_sem_aceite_atual_do_responsavel_bloqueia_e_exige_nova_autorizacao(self):
        cliente = self.cliente(self.aluno)
        self.autorizar()
        self.responsavel.usuario.versao_termos_aceita = 'antiga'
        self.responsavel.usuario.save(update_fields=['versao_termos_aceita'])
        self.assertRedirects(cliente.get(reverse('pagina-inicial')),
                             reverse('aguardando-autorizacao'), fetch_redirect_response=False)
        adulto = self.cliente(self.responsavel)
        self.assertRedirects(adulto.get(self.rota), reverse('aceitar-termos') + '?next=%2Fautorizar-acesso-menor%2F',
                             fetch_redirect_response=False)
        resposta = adulto.post(reverse('aceitar-termos'), {'aceite': 'on'})
        self.assertRedirects(resposta, self.rota, fetch_redirect_response=False)
        self.assertRedirects(cliente.get(reverse('pagina-inicial')),
                             reverse('aguardando-autorizacao'), fetch_redirect_response=False)
        self.autorizar()
        self.assertEqual(cliente.get(reverse('pagina-inicial')).status_code, 200)

    def test_id_de_aluno_sem_vinculo_nao_gera_autorizacao(self):
        resposta = self.autorizar(aluno=self.outro_aluno)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(aluno=self.outro_aluno).exists())
        resposta = self.cliente(self.responsavel).post(self.rota, {'aluno_id': self.aluno.pk})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(AutorizacaoAcessoMenor.objects.filter(aluno=self.aluno).exists())

    def test_vinculo_familiar_alternativo_autoriza(self):
        self.vinculo.ativo = False
        self.vinculo.save(update_fields=['ativo'])
        VinculoFamiliar.objects.create(aluno=self.aluno, responsavel=self.responsavel, ativo=True)
        self.autorizar()
        self.assertEqual(self.cliente(self.aluno).get(reverse('pagina-inicial')).status_code, 200)

    def test_maiores_de_12_continuam_aceitando_seus_proprios_termos(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 13, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        perfil = self.aluno.usuario
        perfil.documentos_aceitos_em = None
        perfil.save(update_fields=['documentos_aceitos_em'])
        cliente = self.cliente(self.aluno)
        self.assertEqual(cliente.get(reverse('aguardando-autorizacao')).status_code, 302)
        self.assertIn(reverse('aceitar-termos'), cliente.get(reverse('pagina-inicial')).url)
        self.assertRedirects(cliente.post(reverse('aceitar-termos'), {'aceite': 'on'}),
                             reverse('inicio'), fetch_redirect_response=False)
        self.assertEqual(cliente.get(reverse('pagina-inicial')).status_code, 200)

    def test_nao_autoriza_crianca_que_ja_completou_12_anos(self):
        self.aluno.data_nascimento = date(timezone.localdate().year - 12, 1, 1)
        self.aluno.save(update_fields=['data_nascimento'])
        self.assertFalse(menor_de_12(self.aluno.data_nascimento))
        self.assertEqual(self.cliente(self.responsavel).get(self.rota).status_code, 200)
        self.assertFalse(AutorizacaoAcessoMenor.objects.exists())
