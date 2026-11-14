from django.urls import reverse
from aplicacao.models import Aluno, Usuario, Vinculo
from testes.base import CenarioTestCase, HOJE


class ListaVinculosTests(CenarioTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for indice in range(12):
            perfil = Usuario.objects.create(usuario=f'vinculo{indice}', tipo_perfil='ALUNO')
            aluno = Aluno.objects.create(usuario=perfil, nome=f'Lista {indice:02}', sobrenome='Teste')
            Vinculo.objects.create(aluno=aluno, professor=cls.professor,
                                   responsavel=cls.responsavel, data_vinculo=HOJE)

    def test_paginacao_nao_repete_alunos_e_busca_antes_do_limite(self):
        cliente = self.cliente(self.gestor)
        url = reverse('vinculo-listar')
        primeira = cliente.get(url)
        segunda = cliente.get(url, {'pagina': 2})
        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(len(primeira.context['fichas']), 10)
        self.assertEqual(len(segunda.context['fichas']), 3)
        self.assertTrue({f['aluno'].pk for f in primeira.context['fichas']}.isdisjoint(
            {f['aluno'].pk for f in segunda.context['fichas']}))
        busca = cliente.get(url, {'busca': 'Lista 11'})
        self.assertEqual(busca.context['pagina'].paginator.count, 1)
        self.assertEqual(busca.context['fichas'][0]['aluno'].nome, 'Lista 11')
        self.assertNotContains(primeira, 'name="professor_aee"')
        self.assertContains(primeira, reverse('vinculo-criar'))

    def test_formulario_separado_carrega_ficha_e_mantem_erros(self):
        cliente = self.cliente(self.gestor)
        url = reverse('vinculo-criar')
        resposta = cliente.get(url, {'aluno': self.aluno.pk})
        self.assertContains(resposta, 'name="professor_aee"')
        self.assertEqual(resposta.context['formulario'].initial['responsavel'], self.responsavel.pk)
        self.assertNotContains(resposta, 'elo-resumo-aluno')
        invalida = cliente.post(url, {'acao': 'salvar_ficha'})
        self.assertEqual(invalida.status_code, 200)
        self.assertTrue(invalida.context['formulario'].errors)
        self.assertEqual(Vinculo.objects.count(), 13)

    def test_sem_resultados_e_pagina_invalida_nao_quebram_tela(self):
        cliente = self.cliente(self.gestor)
        url = reverse('vinculo-listar')
        self.assertEqual(cliente.get(url, {'pagina': 'abc'}).context['pagina'].number, 1)
        self.assertEqual(cliente.get(url, {'pagina': 999}).context['pagina'].number, 2)
        vazia = cliente.get(url, {'busca': 'nao existe'})
        self.assertEqual(vazia.context['pagina'].paginator.count, 0)
        self.assertContains(vazia, 'Nenhum vínculo encontrado.')
