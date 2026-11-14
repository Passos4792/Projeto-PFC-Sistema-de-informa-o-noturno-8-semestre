from datetime import date
from django.urls import reverse
from aplicacao.forms import CadastroUsuario
from aplicacao.models import DocumentoPedagogico, RelatorioPedagogico, SolicitacaoConclusao, SolicitacaoSenha
from testes.base import CenarioTestCase


class CadastroPorNivelTests(CenarioTestCase):
    SENHA_NOVA = 'Senha-nova@39582'

    def dados(self, **campos):
        dados = dict(nome='Nova', sobrenome='Pessoa', username='nova.pessoa',
                     password1=self.SENHA_NOVA, password2=self.SENHA_NOVA)
        dados.update(campos)
        return dados

    def test_nivel_de_acesso_e_o_primeiro_campo_e_comeca_sem_selecao(self):
        formulario = CadastroUsuario(operador=self.gestor.usuario)
        self.assertEqual(list(formulario.fields)[0], 'tipo_perfil')
        self.assertEqual(formulario.fields['tipo_perfil'].choices[0][0], '')
        resposta = self.cliente(self.gestor).get(reverse('usuario-criar'))
        self.assertContains(resposta, 'grupo-destaque')
        self.assertContains(resposta, 'data-nivel-acesso')
        self.assertContains(resposta, 'data-somente-nivel="PROFESSOR"')
        self.assertContains(resposta, 'data-obrigatorio-nivel="ALUNO"')
        self.assertContains(resposta, 'cadastro-usuario.js')

    def test_nivel_de_acesso_e_obrigatorio(self):
        formulario = CadastroUsuario(self.dados(tipo_perfil=''), operador=self.gestor.usuario)
        self.assertFalse(formulario.is_valid())
        self.assertIn('tipo_perfil', formulario.errors)

    def test_aluno_exige_data_de_nascimento(self):
        formulario = CadastroUsuario(self.dados(tipo_perfil='ALUNO'), operador=self.gestor.usuario)
        self.assertFalse(formulario.is_valid())
        self.assertEqual(formulario.errors['data_nascimento'], ['Informe a data de nascimento do aluno.'])
        formulario = CadastroUsuario(self.dados(tipo_perfil='ALUNO', data_nascimento='2015-03-10'),
                                     operador=self.gestor.usuario)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        conta = formulario.save()
        self.assertEqual(conta.perfil_elo.aluno_perfil.data_nascimento, date(2015, 3, 10))

    def test_responsavel_e_professor_tem_data_opcional_e_gravam_quando_informada(self):
        sem_data = CadastroUsuario(self.dados(tipo_perfil='RESPONSAVEL'), operador=self.gestor.usuario)
        self.assertTrue(sem_data.is_valid(), sem_data.errors)
        self.assertIsNone(sem_data.save().perfil_elo.responsavel_perfil.data_nascimento)
        com_data = CadastroUsuario(
            self.dados(username='novo.professor', tipo_perfil='PROFESSOR', funcao_profissional='REGENTE',
                       data_nascimento='1985-07-20'), operador=self.gestor.usuario)
        self.assertTrue(com_data.is_valid(), com_data.errors)
        professor = com_data.save().perfil_elo.professor_perfil
        self.assertEqual(professor.data_nascimento, date(1985, 7, 20))
        self.assertEqual(professor.funcao, 'REGENTE')

    def test_funcao_do_professor_nao_aparece_para_professor_comum(self):
        formulario = CadastroUsuario(operador=self.professor.usuario)
        self.assertNotIn('funcao_profissional', formulario.fields)


class RequisitosSenhaTests(CenarioTestCase):
    def test_telas_de_senha_mostram_a_lista_dinamica_no_lugar_do_texto_fixo(self):
        telas = [
            (self.aluno, reverse('trocar-senha')),
            (self.gestor, reverse('usuario-redefinir-senha', args=[self.aluno.usuario_id])),
            (self.gestor, reverse('usuario-criar')),
        ]
        for pessoa, url in telas:
            with self.subTest(url=url):
                resposta = self.cliente(pessoa).get(url)
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, 'data-regras-senha')
                self.assertContains(resposta, 'regras-senha.js')
                for regra in ('tamanho', 'numerica', 'pessoal', 'comum', 'confirmacao'):
                    self.assertContains(resposta, f'data-regra="{regra}"')
                self.assertNotContains(resposta, 'Sua senha não pode ser muito parecida')
                self.assertNotContains(resposta, 'Orientações para a senha')

    def test_lista_usa_os_dados_da_conta_que_tera_a_senha_alterada(self):
        resposta = self.cliente(self.gestor).get(
            reverse('usuario-redefinir-senha', args=[self.aluno.usuario_id]))
        self.assertContains(resposta, 'data-pessoal-usuario="ana"')


class BuscaPadronizadaTests(CenarioTestCase):
    def test_atividades_do_professor_tem_pesquisa_automatica_e_abas_com_os_filtros(self):
        self.atividade(titulo='Leitura guiada')
        self.atividade(titulo='Frações')
        resposta = self.cliente(self.professor).get(
            reverse('atividade-listar'), {'busca': 'leitura', 'aluno': self.aluno.pk})
        self.assertContains(resposta, 'data-busca-automatica')
        self.assertContains(resposta, 'Leitura guiada')
        self.assertNotContains(resposta, 'Frações')
        self.assertContains(resposta, f'filtro=pendentes&amp;aluno={self.aluno.pk}&amp;busca=leitura')

    def test_atividades_do_aluno_filtram_por_aba(self):
        pendente = self.atividade(titulo='Tarefa pendente')
        avaliando = self.atividade(titulo='Tarefa enviada')
        SolicitacaoConclusao.objects.create(atividade=avaliando, aluno=self.aluno,
                                            solicitante=self.aluno.usuario, situacao='PENDENTE')
        self.atividade(titulo='Tarefa finalizada', situacao='CONCLUIDA')
        self.atividade(titulo='Tarefa cancelada', situacao='CANCELADA')
        esperado = {'todas': 4, 'pendentes': 1, 'avaliacao': 1, 'concluidas': 1, 'canceladas': 1, 'invalida': 4}
        cliente = self.cliente(self.aluno)
        for filtro, total in esperado.items():
            with self.subTest(filtro=filtro):
                resposta = cliente.get(reverse('minhas-atividades'), {'filtro': filtro})
                self.assertEqual(resposta.context['pagina'].paginator.count, total)
        resposta = cliente.get(reverse('minhas-atividades'), {'filtro': 'pendentes'})
        self.assertEqual([a.pk for a in resposta.context['atividades']], [pendente.pk])
        self.assertContains(resposta, 'abas-atividades')

    def test_metas_tem_pesquisa_e_abas_para_professor_e_aluno(self):
        self.meta(titulo='Leitura diária')
        self.meta(titulo='Cálculo mental', situacao='CANCELADA')
        for pessoa in (self.professor, self.aluno):
            with self.subTest(pessoa=pessoa):
                cliente = self.cliente(pessoa)
                resposta = cliente.get(reverse('meta-listar'))
                self.assertEqual(resposta.context['total_metas'], 2)
                self.assertContains(resposta, 'abas-atividades')
                self.assertContains(resposta, 'name="busca"')
                resposta = cliente.get(reverse('meta-listar'), {'busca': 'leitura'})
                self.assertEqual([m['titulo'] for m in resposta.context['metas_lista']], ['Leitura diária'])
                resposta = cliente.get(reverse('meta-listar'), {'estado': 'CANCELADA'})
                self.assertEqual([m['titulo'] for m in resposta.context['metas_lista']], ['Cálculo mental'])
                self.assertEqual(len(resposta.context['dados']['metas']), 2)

    def test_documentos_filtram_por_pesquisa_e_situacao(self):
        DocumentoPedagogico.objects.create(aluno=self.aluno, professor=self.gestor, tipo='PEI',
                                           ano_letivo=2026, campos={}, situacao='PUBLICADO')
        DocumentoPedagogico.objects.create(aluno=self.outro_aluno, professor=self.gestor, tipo='PAEE',
                                           ano_letivo=2026, campos={})
        RelatorioPedagogico.objects.create(aluno=self.aluno, professor=self.gestor, titulo='Evolução na leitura',
                                           periodo='1 bimestre', relato='Texto', data_referencia=date(2026, 11, 1))
        cliente = self.cliente(self.gestor)
        resposta = cliente.get(reverse('documentos-lista'), {'busca': 'ana'})
        self.assertEqual(resposta.context['pagina_documentos'].paginator.count, 1)
        self.assertEqual(resposta.context['pagina_relatorios'].paginator.count, 1)
        self.assertContains(resposta, 'data-busca-automatica')
        resposta = cliente.get(reverse('documentos-lista'), {'busca': 'paee'})
        self.assertEqual([d.tipo for d in resposta.context['documentos']], ['PAEE'])
        resposta = cliente.get(reverse('documentos-lista'), {'filtro': 'publicados'})
        self.assertEqual([d.tipo for d in resposta.context['documentos']], ['PEI'])
        self.assertEqual(resposta.context['pagina_relatorios'].paginator.count, 0)
        resposta = self.cliente(self.responsavel).get(reverse('documentos-lista'), {'filtro': 'rascunhos'})
        self.assertEqual([d.situacao for d in resposta.context['documentos']], ['PUBLICADO'])
        self.assertNotContains(resposta, 'filtro=rascunhos')

    def test_pedidos_de_senha_tem_pesquisa_e_abas(self):
        SolicitacaoSenha.objects.create(usuario_alvo=self.aluno.usuario, aluno=self.aluno)
        SolicitacaoSenha.objects.create(usuario_alvo=self.responsavel.usuario, aluno=self.aluno, situacao='ATENDIDA')
        cliente = self.cliente(self.gestor)
        url = reverse('solicitacao-senha-listar')
        self.assertEqual(cliente.get(url).context['pagina'].paginator.count, 2)
        resposta = cliente.get(url, {'busca': 'ana'})
        self.assertEqual([p.usuario_alvo_id for p in resposta.context['pedidos']], [self.aluno.usuario_id])
        self.assertContains(resposta, 'data-busca-automatica')
        resposta = cliente.get(url, {'filtro': 'atendidas'})
        self.assertEqual([p.usuario_alvo_id for p in resposta.context['pedidos']], [self.responsavel.usuario_id])
        self.assertEqual(cliente.get(url, {'busca': 'ninguem'}).context['pagina'].paginator.count, 0)
