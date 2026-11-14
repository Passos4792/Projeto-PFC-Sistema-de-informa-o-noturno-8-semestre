from django.urls import reverse
from aplicacao.models import (Aluno, Disciplina, DocumentoPedagogico, RelatorioPedagogico,
                              SolicitacaoConclusao, SolicitacaoSenha, Usuario, Vinculo)
from testes.base import CenarioTestCase, HOJE


class PaginacaoMenuFixoTests(CenarioTestCase):
    def test_atividades_do_aluno_sao_paginadas_antes_de_carregar_detalhes(self):
        for numero in range(23):
            self.atividade(titulo=f'Lista atividade {numero:02}')
        cliente = self.cliente(self.aluno)
        url = reverse('minhas-atividades')
        primeira = cliente.get(url, {'busca': 'Lista atividade', 'aluno': self.aluno.pk})
        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(primeira.context['pagina'].paginator.count, 23)
        self.assertEqual(len(primeira.context['atividades']), 10)
        self.assertContains(primeira, 'pagina=2')
        self.assertContains(primeira, f'aluno={self.aluno.pk}')
        segunda = cliente.get(url, {'busca': 'Lista atividade', 'pagina': 2})
        self.assertEqual(len(segunda.context['atividades']), 10)
        self.assertTrue({a.pk for a in primeira.context['atividades']}.isdisjoint(
            {a.pk for a in segunda.context['atividades']}))
        filtrada = cliente.get(url, {'busca': 'Lista atividade 22'})
        self.assertEqual(filtrada.context['pagina'].paginator.count, 1)
        self.assertEqual(len(filtrada.context['atividades']), 1)
        self.assertEqual(cliente.get(url, {'pagina': 'erro'}).context['pagina'].number, 1)

    def test_documentos_e_relatorios_tem_paginas_independentes_e_permissoes(self):
        for numero in range(17):
            DocumentoPedagogico.objects.create(
                aluno=self.aluno, professor=self.professor, tipo='PEI', ano_letivo=2026,
                campos={'numero': numero}, situacao='PUBLICADO')
            RelatorioPedagogico.objects.create(
                aluno=self.aluno, professor=self.professor, titulo=f'Relatorio {numero:02}',
                relato='Acompanhamento', situacao='PUBLICADO')
        outro = RelatorioPedagogico.objects.create(
            aluno=self.outro_aluno, professor=self.professor, titulo='Privado de outro aluno',
            relato='Privado', situacao='PUBLICADO')
        cliente = self.cliente(self.responsavel)
        url = reverse('documentos-lista')
        primeira = cliente.get(url, {'aluno': self.aluno.pk, 'pagina_relatorios': 2})
        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(len(primeira.context['documentos']), 8)
        self.assertEqual(len(primeira.context['relatorios']), 8)
        self.assertEqual(primeira.context['pagina_relatorios'].number, 2)
        self.assertContains(primeira, 'pagina_documentos=2')
        self.assertContains(primeira, 'pagina_relatorios=2')
        self.assertContains(primeira, f'aluno={self.aluno.pk}')
        self.assertNotContains(primeira, outro.titulo)
        terceira = cliente.get(url, {'aluno': self.aluno.pk, 'pagina_documentos': 3,
                                     'pagina_relatorios': 3})
        self.assertEqual(len(terceira.context['documentos']), 1)
        self.assertEqual(len(terceira.context['relatorios']), 1)

    def test_pedidos_de_senha_nao_sao_cortados_apos_150(self):
        for numero in range(157):
            SolicitacaoSenha.objects.create(usuario_alvo=self.professor.usuario)
        cliente = self.cliente(self.gestor)
        url = reverse('solicitacao-senha-listar')
        primeira = cliente.get(url)
        ultima = cliente.get(url, {'pagina': 11})
        self.assertEqual(primeira.context['pagina'].paginator.count, 157)
        self.assertEqual(len(primeira.context['pedidos']), 15)
        self.assertEqual(ultima.context['pagina'].number, 11)
        self.assertEqual(len(ultima.context['pedidos']), 7)
        self.assertContains(primeira, 'pagina=2')

    def test_cartoes_de_alunos_paginar_sem_mostrar_outros_alunos(self):
        for numero in range(19):
            perfil = Usuario.objects.create(usuario=f'pagina_aluno_{numero}', tipo_perfil='ALUNO')
            aluno = Aluno.objects.create(usuario=perfil, nome=f'Estudante {numero:02}', sobrenome='Teste')
            Vinculo.objects.create(aluno=aluno, professor=self.professor, responsavel=self.responsavel,
                                   data_vinculo=HOJE, mesclar_perfis=True)
        for pessoa, rota in [(self.responsavel, 'familia-estudantes'),
                             (self.professor, 'profissional-estudantes')]:
            with self.subTest(rota=rota):
                cliente = self.cliente(pessoa)
                pagina1 = cliente.get(reverse(rota))
                pagina2 = cliente.get(reverse(rota), {'pagina': 2})
                self.assertEqual(pagina1.status_code, 200)
                self.assertEqual(len(pagina1.context['alunos']), 9)
                self.assertEqual(len(pagina2.context['alunos']), 9)
                self.assertTrue({a.pk for a in pagina1.context['alunos']}.isdisjoint(
                    {a.pk for a in pagina2.context['alunos']}))
                self.assertContains(pagina1, 'pagina=2')

    def test_entregas_da_atividade_sao_paginadas(self):
        atividade = self.atividade()
        for _ in range(21):
            SolicitacaoConclusao.objects.create(atividade=atividade, aluno=self.aluno,
                                               solicitante=self.aluno.usuario)
        cliente = self.cliente(self.gestor)
        url = reverse('atividade-detalhe', args=[atividade.pk])
        primeira = cliente.get(url)
        ultima = cliente.get(url, {'pagina': 3})
        self.assertEqual(len(primeira.context['entregas']), 10)
        self.assertEqual(ultima.context['pagina_entregas'].number, 3)
        self.assertEqual(len(ultima.context['entregas']), 1)
        self.assertContains(primeira, 'pagina=2')

    def test_metas_e_conteudos_paginados_no_acompanhamento(self):
        for numero in range(14):
            self.meta(titulo=f'Meta pagina {numero:02}')
            disciplina = Disciplina.objects.create(nome=f'Conteudo pagina {numero:02}')
            self.atividade(titulo=f'Tarefa conteudo {numero:02}', disciplina=disciplina)
        cliente = self.cliente(self.gestor)
        resposta = cliente.get(reverse('aluno-inicio', args=[self.aluno.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.context['metas_lista']), 10)
        self.assertEqual(len(resposta.context['conteudos_lista']), 10)
        self.assertContains(resposta, 'pagina_conteudos=2')
        segunda = cliente.get(reverse('aluno-inicio', args=[self.aluno.pk]),
                              {'pagina': 2, 'pagina_conteudos': 2})
        self.assertEqual(len(segunda.context['metas_lista']), 4)
        self.assertEqual(len(segunda.context['conteudos_lista']), 5)
