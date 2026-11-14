from datetime import timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from aplicacao.views.api import DecisaoSerializer, SolicitarSerializer
from aplicacao.forms import (
    CadastroUsuario, FichaVinculos, FiltroAuditoria, FiltroPainel,
    FormularioAluno, FormularioAtividade, FormularioMeta,
    FormularioProfessor, FormularioResponsavel, FormularioVinculoProfissional,
)
from aplicacao.forms.documentos import FormularioCabecalhoDocumento, FormularioRelatorio
from aplicacao.models import SolicitacaoSenha
from testes.base import CenarioTestCase, HOJE


class AuditoriaFormulariosTests(CenarioTestCase):
    def dados_pessoa(self, **alteracoes):
        dados = {'nome': 'Maria', 'sobrenome': 'Silva', 'nome_usuario': 'nova.conta', 'ativo': True}
        dados.update(alteracoes)
        return dados

    def dados_atividade(self, **alteracoes):
        dados = {'aluno': self.aluno.pk, 'professor': self.professor.pk,
                 'disciplina': self.disciplina.pk, 'titulo': 'Atividade de teste',
                 'descricao': 'Realize a atividade.', 'tipo_entrega': 'ENVIO',
                 'data_entrega': HOJE.isoformat(), 'situacao': 'PENDENTE'}
        dados.update(alteracoes)
        return dados

    def test_identificadores_invalidos_rejeitados_por_todos_os_cadastros_de_pessoas(self):
        for classe in (FormularioAluno, FormularioProfessor, FormularioResponsavel):
            for usuario in ('nome de pessoa', 'nome<>', 'nome/../../', 'nome😀'):
                with self.subTest(classe=classe.__name__, usuario=usuario):
                    form = classe(self.dados_pessoa(nome_usuario=usuario))
                    self.assertFalse(form.is_valid())
                    self.assertIn('nome_usuario', form.errors)

    def test_identificador_com_acentos_hifen_e_ponto_permitido(self):
        form = FormularioAluno(self.dados_pessoa(nome_usuario='ana-maria.é'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_nomes_com_html_numero_ou_emoji_sao_rejeitados(self):
        for classe in (FormularioAluno, FormularioProfessor, FormularioResponsavel):
            for texto in ('Maria123', '<script>alert(1)</script>', '😅'):
                for campo in ('nome', 'sobrenome'):
                    with self.subTest(classe=classe.__name__, campo=campo, texto=texto):
                        formulario = classe(self.dados_pessoa(**{campo: texto}))
                        self.assertFalse(formulario.is_valid())
                        self.assertIn(campo, formulario.errors)

    def test_nome_composto_hifen_e_apostrofo_sao_aceitos(self):
        formulario = FormularioAluno(self.dados_pessoa(nome=" Ana  Maria ", sobrenome="D'Ávila-Souza"))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.cleaned_data['nome'], 'Ana Maria')

    def test_data_nascimento_futura_e_rejeitada_no_cadastro_e_edicao(self):
        futuro = (timezone.localdate() + timedelta(days=1)).isoformat()
        form = FormularioAluno(self.dados_pessoa(data_nascimento=futuro))
        self.assertFalse(form.is_valid())
        self.assertIn('data_nascimento', form.errors)
        dados = {'nome':'Nova','sobrenome':'Pessoa','username':'nova.cadastro',
                 'tipo_perfil':'ALUNO','data_nascimento':futuro,
                 'password1':'Forte@senha2026', 'password2':'Forte@senha2026'}
        form = CadastroUsuario(dados, operador=self.gestor.usuario)
        self.assertFalse(form.is_valid())
        self.assertIn('data_nascimento', form.errors)

    def test_cadastro_nao_aceita_funcao_ou_perfil_privilegiado_injetado(self):
        dados = {'nome':'Nova', 'sobrenome':'Pessoa','username':'nao.permitida',
                 'tipo_perfil':'PROFESSOR','funcao_profissional':'AEE',
                 'password1':'SenhaMuitoForte@782', 'password2':'SenhaMuitoForte@782'}
        form = CadastroUsuario(dados, operador=self.professor.usuario)
        self.assertFalse(form.is_valid())
        self.assertIn('tipo_perfil', form.errors)

    def test_cadastro_nao_aceita_nome_com_codigo(self):
        dados = {'nome':'1234', 'sobrenome':'Teste','username':'outro.login',
                 'tipo_perfil':'ALUNO', 'password1':'SenhaMuitoForte@782',
                 'password2':'SenhaMuitoForte@782'}
        form = CadastroUsuario(dados, operador=self.gestor.usuario)
        self.assertFalse(form.is_valid())
        self.assertIn('nome', form.errors)

    def test_meta_exige_aluno_professor_valido_e_numero_positivo(self):
        for alteracao in ({'aluno':999999}, {'professor':999999}, {'quantidade_alvo': -3},
                          {'periodo':'INVALIDO'}, {'data_inicio':'2026-88-01'}):
            with self.subTest(alteracao=alteracao):
                dados = {'aluno':self.aluno.pk, 'professor':self.professor.pk,
                         'titulo':'Meta', 'periodo':'MENSAL','quantidade_alvo':3,
                         'data_inicio':HOJE.isoformat(),'situacao':'EM_ANDAMENTO'}
                dados.update(alteracao)
                self.assertFalse(FormularioMeta(dados).is_valid())

    def test_atividade_rejeita_enum_data_texto_e_foreign_key_invalidos(self):
        alteracoes = ({'aluno':999999},{'professor':999999}, {'data_entrega':'2026-13-99'},
                      {'tipo_entrega':'EXECUTAVEL'}, {'titulo':'x'*151},
                      {'descricao':'x'*5001},{'situacao':'CONCLUIDA'},
                      {'novo_conteudo':'c'*101,'disciplina':''})
        for alteracao in alteracoes:
            with self.subTest(alteracao=str(alteracao)[:60]):
                self.assertFalse(FormularioAtividade(self.dados_atividade(**alteracao)).is_valid())

    def test_ficha_vinculos_rejeita_ids_inexistentes_e_data_invalida(self):
        dados = {'aluno': self.aluno.pk,'responsavel':self.responsavel.pk,
                 'professor_aee':self.professor.pk,'data_vinculo':HOJE.isoformat(),'ativo':'on'}
        for alteracao in ({'aluno':999999},{'responsavel':999999},
                          {'professor_aee':999999},{'data_vinculo':'invalid'}):
            with self.subTest(alteracao=alteracao):
                self.assertFalse(FichaVinculos({**dados,**alteracao}).is_valid())

    def test_vinculo_profissional_rejeita_fim_anterior_inicio(self):
        form = FormularioVinculoProfissional({
            'aluno':self.aluno.pk,'professor':self.professor.pk,'funcao':'AEE',
            'data_inicio':'2026-11-10','data_fim':'2026-11-09','ativo':'on'})
        self.assertFalse(form.is_valid())
        self.assertIn('data_fim',form.errors)

    def test_relatorio_rejeita_aluno_alheio_data_futura_e_texto_gigante(self):
        dados = {'aluno':self.aluno.pk,'titulo':'Relato','data_referencia':HOJE.isoformat(),
                 'periodo':'1º bimestre','relato':'Trabalho realizado.'}
        permitidos = type(self.aluno).objects.filter(pk=self.aluno.pk)
        for alteracao in ({'aluno': self.outro_aluno.pk},
                          {'data_referencia':(timezone.localdate()+timedelta(days=1)).isoformat()},
                          {'relato':'x'*12001}):
            with self.subTest(caso=str(alteracao)[:50]):
                form = FormularioRelatorio({**dados,**alteracao}, alunos=permitidos)
                self.assertFalse(form.is_valid())

    def test_documento_rejeita_ano_bimestre_aluno_e_texto_excessivo(self):
        base={'aluno':self.aluno.pk,'ano_letivo':'2026','bimestre':'2'}
        permitidos = type(self.aluno).objects.filter(pk=self.aluno.pk)
        for alteracao in ({'ano_letivo':'1800'}, {'ano_letivo':'abc'},
                          {'bimestre':'6'}, {'aluno':self.outro_aluno.pk},
                          {'conteudos':'x'*4001}):
            with self.subTest(caso=str(alteracao)[:50]):
                form = FormularioCabecalhoDocumento({**base,**alteracao}, alunos=permitidos,tipo='PEI')
                self.assertFalse(form.is_valid())

    def test_filtros_rejeitam_datas_invertidas_e_aluno_alheio(self):
        form = FiltroPainel({'aluno':self.outro_aluno.pk}, perfil=self.professor.usuario)
        self.assertFalse(form.is_valid())
        self.assertIn('aluno',form.errors)
        self.assertFalse(FiltroAuditoria({'inicio':'2026-11-20','fim':'2026-11-10'}).is_valid())

    def test_api_rejeita_solicitacao_sem_resposta_ou_anexo(self):
        atividade=self.atividade(tipo_entrega='ENVIO')
        self.assertFalse(SolicitarSerializer(data={'mensagem':'ok'},context={'atividade':atividade}).is_valid())
        self.assertFalse(SolicitarSerializer(data={'resposta_aluno':'ok','mensagem':'z'*501},
                                            context={'atividade':atividade}).is_valid())
        self.assertFalse(DecisaoSerializer(data={'decisao':'RECUSADA', 'resposta':' '}).is_valid())
        self.assertFalse(DecisaoSerializer(data={'decisao':'OUTRA'}).is_valid())

    def test_upload_imagem_falsa_com_cabecalho_correto_e_rejeitado(self):
        atividade=self.atividade(tipo_entrega='ENVIO')
        invalida=SimpleUploadedFile('forjada.png', b'\x89PNG\r\n\x1a\n' + b'not a real PNG',
                                    content_type='image/png')
        serializer=SolicitarSerializer(data={'anexo':invalida},context={'atividade':atividade})
        self.assertFalse(serializer.is_valid())
        self.assertIn('anexo', serializer.errors)

    def test_upload_png_real_e_permitido(self):
        atividade=self.atividade(tipo_entrega='ENVIO')
        memoria=BytesIO()
        Image.new('RGB',(3,3),'white').save(memoria,format='PNG')
        arquivo=SimpleUploadedFile('valida.png',memoria.getvalue(),content_type='image/png')
        serializer=SolicitarSerializer(data={'anexo':arquivo},context={'atividade':atividade})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_pedido_inexistente_ou_inativo_nao_gera_registro(self):
        for nome in ('nao.existe.abc','gestor'):
            resposta=self.client.post(reverse('recuperar-senha'),{'usuario':nome})
            self.assertContains(resposta,'Solicitação recebida')
        self.assertFalse(SolicitacaoSenha.objects.exists())
        self.aluno.ativo=False
        self.aluno.save(update_fields=['ativo'])
        resposta=self.client.post(reverse('recuperar-senha'),{'usuario':'ana'})
        self.assertContains(resposta,'Solicitação recebida')
        self.assertFalse(SolicitacaoSenha.objects.exists())

    def test_pedido_legado_do_aluno_nao_bloqueia_responsavel(self):
        SolicitacaoSenha.objects.create(aluno=self.aluno,professor=self.professor,
                                        usuario_alvo=None,situacao='PENDENTE')
        resposta=self.client.post(reverse('recuperar-senha'),{'usuario':'responsavel'})
        self.assertContains(resposta,'Solicitação recebida')
        self.assertEqual(SolicitacaoSenha.objects.count(),2)
        self.assertTrue(SolicitacaoSenha.objects.filter(usuario_alvo=self.responsavel.usuario).exists())

    def test_pedido_de_mesmo_usuario_nao_cria_duplicata(self):
        for nome in (' ANA ','ana'):
            self.client.post(reverse('recuperar-senha'), {'usuario':nome})
        self.assertEqual(SolicitacaoSenha.objects.count(),1)

    def test_post_real_cadastro_nao_salva_nome_com_digitos(self):
        from aplicacao.models import Aluno
        cliente = self.cliente(self.gestor)
        antes=Aluno.objects.count()
        resposta=cliente.post(reverse('aluno-criar-sem-login'),
                             self.dados_pessoa(nome='Ana 123',nome_usuario='invalido-sem-login'))
        self.assertEqual(resposta.status_code,200)
        self.assertEqual(Aluno.objects.count(),antes)
        self.assertContains(resposta,'Use apenas letras')

    def test_post_real_cadastro_nao_salva_identificador_inesperado(self):
        from aplicacao.models import Responsavel
        cliente = self.cliente(self.gestor)
        antes=Responsavel.objects.count()
        resposta=cliente.post(reverse('responsavel-editar',args=[self.responsavel.pk]),
                              self.dados_pessoa(nome_usuario='nome com espaço'))
        self.assertEqual(resposta.status_code,200)
        self.assertEqual(Responsavel.objects.count(),antes)
        self.responsavel.usuario.refresh_from_db()
        self.assertEqual(self.responsavel.usuario.usuario,'responsavel')
        self.assertContains(resposta,'Use letras, números')

    def test_post_real_atividade_nao_salva_texto_gigante(self):
        from aplicacao.models import Atividade
        cliente=self.cliente(self.gestor)
        anterior=Atividade.objects.count()
        resposta=cliente.post(reverse('atividade-criar'),self.dados_atividade(descricao='m'*5001))
        self.assertEqual(resposta.status_code,200)
        self.assertEqual(Atividade.objects.count(),anterior)
        self.assertContains(resposta,'Certifique-se')

    def test_post_real_pedido_de_usuario_inexistente_nao_cria_registro(self):
        resposta=self.client.post(reverse('recuperar-senha'), {'usuario':'<script>alert(1)</script>'})
        self.assertContains(resposta,'Solicitação recebida')
        self.assertFalse(SolicitacaoSenha.objects.exists())
