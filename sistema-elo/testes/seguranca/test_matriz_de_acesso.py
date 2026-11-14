from django.contrib.auth import get_user_model
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from aplicacao.models import (Atividade, DocumentoPedagogico, MetaAluno, RelatorioPedagogico, Responsavel,
                              SolicitacaoConclusao, SolicitacaoSenha, Usuario, Vinculo)
from testes.base import HOJE, CenarioTestCase, pessoa

PUBLICAS = {'login', 'recuperar-senha', 'admin-recuperar-senha', 'sobre', 'politica-privacidade', 'termos-uso',
            'privacidade-aluno', 'logout'}


def rotas():
    def percorrer(padroes):
        for p in padroes:
            if isinstance(p, URLResolver):
                if p.app_name == 'admin':
                    continue
                yield from percorrer(p.url_patterns)
            elif isinstance(p, URLPattern) and p.name:
                yield p
    return list(percorrer(get_resolver().url_patterns))


def fotografia():
    from django.apps import apps
    ignorar = {'registroauditoria', 'limitelogin'}
    estado = {}
    for modelo in apps.get_app_config('elo').get_models():
        if modelo._meta.model_name not in ignorar:
            estado[modelo._meta.model_name] = list(modelo.objects.order_by('pk').values())
    estado['contas'] = list(get_user_model().objects.order_by('pk').values('pk', 'password', 'is_active',
                                                                            'is_superuser'))
    return estado


class MatrizAcessoBase(CenarioTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.resp_bruno = pessoa('resp.bruno', 'RESPONSAVEL')
        cls.vinculo_bruno = Vinculo.objects.create(aluno=cls.outro_aluno, professor=cls.gestor,
                                                   responsavel=cls.resp_bruno, data_vinculo=HOJE)
        cls.meta_bruno = MetaAluno.objects.create(aluno=cls.outro_aluno, professor=cls.gestor, titulo='Meta B',
                                                  data_inicio=HOJE, periodo='MENSAL')
        cls.ativ_bruno = Atividade.objects.create(aluno=cls.outro_aluno, professor=cls.gestor, titulo='Ativ B',
                                                  data_entrega=HOJE, tipo_entrega='ENVIO')
        cls.entrega_bruno = SolicitacaoConclusao.objects.create(atividade=cls.ativ_bruno, aluno=cls.outro_aluno,
                                                                resposta_aluno='resposta secreta')
        cls.doc_bruno = DocumentoPedagogico.objects.create(aluno=cls.outro_aluno, professor=cls.gestor, tipo='PEI',
                                                           ano_letivo=2026, situacao='PUBLICADO',
                                                           campos={'conteudos': 'conteudo secreto'})
        cls.rel_bruno = RelatorioPedagogico.objects.create(aluno=cls.outro_aluno, professor=cls.gestor,
                                                           titulo='Rel B', relato='relato secreto',
                                                           situacao='PUBLICADO')
        cls.pedido_bruno = SolicitacaoSenha.objects.create(usuario_alvo=cls.outro_aluno.usuario,
                                                           aluno=cls.outro_aluno)
        cls.sem_login = Usuario.objects.create(usuario='sem.login', tipo_perfil='RESPONSAVEL')
        Responsavel.objects.create(usuario=cls.sem_login, nome='Sem', sobrenome='Login')

    def argumentos(self, rota):
        alvo = {
            'professor-editar': self.outro_professor.pk, 'professor-excluir': self.outro_professor.pk,
            'aluno-editar': self.outro_aluno.pk, 'aluno-excluir': self.outro_aluno.pk,
            'aluno-documentos-pdf': self.outro_aluno.pk, 'aluno-inicio': self.outro_aluno.pk,
            'responsavel-editar': self.resp_bruno.pk, 'responsavel-excluir': self.resp_bruno.pk,
            'usuario-redefinir-senha': self.outro_aluno.usuario_id,
            'usuario-redefinir-2fa': self.resp_bruno.usuario_id,
            'usuario-ativar-acesso': self.sem_login.pk, 'solicitacao-senha-atender': self.pedido_bruno.pk,
            'vinculo-editar': self.vinculo_bruno.pk, 'vinculo-excluir': self.vinculo_bruno.pk,
            'meta-editar': self.meta_bruno.pk, 'meta-excluir': self.meta_bruno.pk,
            'atividade-editar': self.ativ_bruno.pk, 'atividade-excluir': self.ativ_bruno.pk,
            'atividade-detalhe': self.ativ_bruno.pk, 'atividade-enviar': self.ativ_bruno.pk,
            'atividade-material': self.ativ_bruno.pk, 'google-sincronizar': self.ativ_bruno.pk,
            'entrega-anexo': self.entrega_bruno.pk,
            'documento-detalhe': self.doc_bruno.pk, 'documento-pdf': self.doc_bruno.pk,
            'documento-editar': self.doc_bruno.pk, 'documento-publicar': self.doc_bruno.pk,
            'relatorio-detalhe': self.rel_bruno.pk, 'relatorio-pdf': self.rel_bruno.pk,
            'relatorio-editar': self.rel_bruno.pk, 'relatorio-publicar': self.rel_bruno.pk,
            'api-solicitar-conclusao': self.ativ_bruno.pk, 'api-decidir-conclusao': self.entrega_bruno.pk,
        }
        if rota.name == 'api-metas-aluno':
            return {'aluno_id': self.outro_aluno.pk}
        if rota.name == 'documento-criar':
            return {'tipo': 'PEI'}
        if rota.pattern.converters:
            return {'pk': alvo[rota.name]}
        return {}

    def url(self, rota):
        return reverse(rota.name, kwargs=self.argumentos(rota))


SEGREDOS = ('resposta secreta', 'conteudo secreto', 'relato secreto', 'Ativ B', 'Meta B')
METODOS = ('get', 'post', 'put', 'patch', 'delete')


class MatrizAcessoTests(MatrizAcessoBase):
    def dados(self):
        return {'acao': 'PUBLICADO', 'decisao': 'APROVADA', 'situacao': 'APROVADA', 'resposta_aluno': 'x',
                'aluno': self.outro_aluno.pk, 'professor': self.professor.pk, 'responsavel': self.resp_bruno.pk,
                'titulo': 'invasao', 'relato': 'invasao', 'tipo_perfil': 'PROFESSOR', 'gestor': 'on',
                'new_password1': 'SenhaNova@879', 'new_password2': 'SenhaNova@879', 'vinculo_id': self.vinculo_bruno.pk}

    def chamar(self, cliente, metodo, url):
        if metodo in ('get', 'post'):
            return getattr(cliente, metodo)(url, self.dados())
        return getattr(cliente, metodo)(url)

    def test_ninguem_sem_vinculo_le_ou_altera_dados_de_outro_aluno(self):
        atores = (self.professor, self.outro_professor, self.aluno, self.responsavel)
        for rota in rotas():
            for ator in atores:
                cliente = self.cliente(ator)
                for metodo in METODOS:
                    with self.subTest(rota=rota.name, ator=ator.usuario.usuario, metodo=metodo):
                        antes = fotografia()
                        resposta = self.chamar(cliente, metodo, self.url(rota))
                        self.assertEqual(fotografia(), antes, 'dados alterados sem permissão')
                        self.assertNotEqual(resposta.status_code, 500)
                        conteudo = resposta.content.decode('utf-8', 'ignore') if not resposta.streaming else ''
                        for segredo in SEGREDOS:
                            self.assertNotIn(segredo, conteudo)
                        if rota.pattern.converters and rota.name not in ('documento-criar',):
                            self.assertNotEqual(resposta.status_code, 200)

    def test_anonimo_nao_acessa_nenhuma_rota_interna(self):
        cliente = self.client
        for rota in rotas():
            if rota.name in PUBLICAS:
                continue
            for metodo in METODOS:
                with self.subTest(rota=rota.name, metodo=metodo):
                    antes = fotografia()
                    resposta = self.chamar(cliente, metodo, self.url(rota))
                    self.assertEqual(fotografia(), antes)
                    self.assertNotIn(resposta.status_code, (200, 500))
                    if resposta.status_code == 302:
                        self.assertIn('/login/', resposta.url)

    def test_2fa_pendente_bloqueia_todas_as_rotas_internas(self):
        from django.test import override_settings
        livres = PUBLICAS | {'2fa-configurar', '2fa-verificar', 'trocar-senha'}
        with override_settings(ELO_2FA_ATIVO=True):
            for ator in (self.gestor, self.professor, self.responsavel):
                cliente = self.cliente(ator)
                for rota in rotas():
                    if rota.name in livres:
                        continue
                    with self.subTest(rota=rota.name, ator=ator.usuario.usuario):
                        antes = fotografia()
                        resposta = cliente.get(self.url(rota))
                        self.assertNotIn(resposta.status_code, (200, 500))
                        resposta = cliente.post(self.url(rota), self.dados())
                        self.assertNotIn(resposta.status_code, (200, 500))
                        self.assertEqual(fotografia(), antes)
