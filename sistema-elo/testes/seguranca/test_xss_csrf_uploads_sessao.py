import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from aplicacao.servicos.arquivos import validar_anexo_pedagogico
from aplicacao.models import DocumentoPedagogico, RelatorioPedagogico
from testes.base import SENHA, CenarioTestCase
from testes.seguranca.test_matriz_de_acesso import PUBLICAS, MatrizAcessoBase, fotografia, rotas

XSS = '<script>alert(1)</script><img src=x onerror=alert(2)>'


class XssTests(CenarioTestCase):
    def test_conteudo_armazenado_e_escapado_em_todas_as_telas(self):
        self.aluno.nome = XSS
        self.aluno.save()
        self.atividade(titulo=XSS, descricao=XSS)
        self.meta(titulo=XSS, descricao=XSS)
        doc = DocumentoPedagogico.objects.create(aluno=self.aluno, professor=self.professor, tipo='PEI',
                                                 ano_letivo=2026, campos={'conteudos': XSS})
        rel = RelatorioPedagogico.objects.create(aluno=self.aluno, professor=self.professor, titulo=XSS, relato=XSS)
        cliente = self.cliente(self.gestor)
        for url in [reverse(n) for n in ('pagina-inicial', 'aluno-listar', 'atividade-listar', 'meta-listar',
                                         'documentos-lista', 'vinculo-listar', 'auditoria', 'aprovacoes')] + [
                reverse('documento-detalhe', args=[doc.pk]), reverse('relatorio-detalhe', args=[rel.pk]),
                reverse('aluno-editar', args=[self.aluno.pk])]:
            with self.subTest(url=url):
                conteudo = cliente.get(url).content.decode()
                self.assertNotIn('<script>alert(1)</script>', conteudo)
                self.assertNotIn('<img src=x onerror', conteudo)

    def test_busca_refletida_e_escapada(self):
        cliente = self.cliente(self.gestor)
        for rota in ('aluno-listar', 'professor-listar', 'atividade-listar', 'documentos-lista', 'vinculo-listar'):
            with self.subTest(rota=rota):
                conteudo = cliente.get(reverse(rota), {'busca': XSS}).content.decode()
                self.assertNotIn('<script>alert(1)</script>', conteudo)

    def test_pdf_nao_interpreta_marcacao_digitada(self):
        carga = '<img src="manage.py"/><link href="javascript:alert(1)">x</link><font size=900>'
        doc = DocumentoPedagogico.objects.create(aluno=self.aluno, professor=self.professor, tipo='PEI',
                                                 ano_letivo=2026, campos={'conteudos': carga})
        resposta = self.cliente(self.gestor).get(reverse('documento-pdf', args=[doc.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.content.startswith(b'%PDF'))
        self.assertNotIn(b'javascript:', resposta.content)


class CsrfTests(MatrizAcessoBase):
    def test_nenhuma_rota_aceita_post_sem_token_csrf(self):
        cliente = self.cliente(self.gestor, csrf=True)
        for rota in rotas():
            if rota.name in ('logout',):
                continue
            with self.subTest(rota=rota.name):
                antes = fotografia()
                resposta = cliente.post(self.url(rota), {'aluno': self.aluno.pk, 'titulo': 'x', 'acao': 'RETIRAR'})
                self.assertEqual(fotografia(), antes)
                self.assertIn(resposta.status_code, (403, 405))


class RedirecionamentoAbertoTests(CenarioTestCase):
    EXTERNOS = ['https://site-malicioso.com', '//site-malicioso.com', '/\\site-malicioso.com',
                'javascript:alert(1)', 'https:site-malicioso.com']

    def test_login_nao_redireciona_para_fora(self):
        for destino in self.EXTERNOS:
            with self.subTest(destino=destino):
                resposta = Client().post(reverse('login') + '?next=' + destino,
                                         {'username': 'ana', 'password': SENHA, 'next': destino})
                self.assertEqual(resposta.status_code, 302)
                self.assertNotIn('site-malicioso', resposta.url)
                self.assertFalse(resposta.url.startswith('javascript'))

    def test_aceite_dos_termos_nao_redireciona_para_fora(self):
        self.aluno.usuario.documentos_aceitos_em = None
        self.aluno.usuario.save()
        cliente = self.cliente(self.aluno)
        for destino in self.EXTERNOS:
            with self.subTest(destino=destino):
                self.aluno.usuario.documentos_aceitos_em = None
                self.aluno.usuario.save()
                resposta = cliente.post(reverse('aceitar-termos'), {
                    'aceito_termos': 'on', 'aceito_privacidade': 'on', 'ciente_privacidade': 'on',
                    'next': destino})
                if resposta.status_code == 302:
                    self.assertNotIn('site-malicioso', resposta.url)
                    self.assertFalse(resposta.url.startswith('javascript'))


class UploadTests(CenarioTestCase):
    def arquivo(self, nome, conteudo):
        return SimpleUploadedFile(nome, conteudo, content_type='image/png')

    def test_arquivos_disfarcados_sao_recusados(self):
        casos = [
            ('pagina.html', b'<html><script>alert(1)</script></html>'),
            ('imagem.svg', b'<svg onload="alert(1)"></svg>'),
            ('falso.png', b'<html><script>alert(1)</script></html>'),
            ('falso.pdf', b'MZ\x90\x00executavel'),
            ('script.php.png', b'<?php system($_GET[1]); ?>'),
            ('falso.jpg', b'\xff\xd8\xff' + b'<script>alert(1)</script>' * 10),
            ('vazio.pdf', b''),
        ]
        for nome, conteudo in casos:
            with self.subTest(nome=nome):
                with self.assertRaises(ValidationError):
                    validar_anexo_pedagogico(self.arquivo(nome, conteudo))

    def test_nome_do_arquivo_nao_permite_sair_da_pasta(self):
        from aplicacao.servicos.arquivos import caminho_entrega, caminho_material
        for funcao in (caminho_material, caminho_entrega):
            caminho = funcao(None, '../../../configuracao/settings.py.pdf')
            with self.subTest(funcao=funcao.__name__):
                self.assertNotIn('..', caminho)
                self.assertNotIn('settings', caminho)
                self.assertTrue(caminho.startswith('atividades/'))

    def test_arquivos_privados_nao_sao_servidos_por_url(self):
        cliente = self.cliente(self.gestor)
        for url in ('/arquivos_privados/', '/media/', '/arquivos_privados/fotos_perfil/x.png',
                    '/static/../configuracao/settings.py', '/.env', '/../.env'):
            with self.subTest(url=url):
                self.assertIn(cliente.get(url).status_code, (301, 400, 404))


class SessaoTests(CenarioTestCase):
    def test_sessao_e_trocada_no_login(self):
        cliente = Client()
        cliente.get(reverse('login'))
        cliente.session['marca'] = 'antes'
        cliente.session.save()
        antes = cliente.session.session_key
        cliente.post(reverse('login'), {'username': 'ana', 'password': SENHA})
        self.assertNotEqual(cliente.session.session_key, antes)

    def test_logout_so_por_post(self):
        cliente = self.cliente(self.aluno)
        self.assertEqual(cliente.get(reverse('logout')).status_code, 405)
        self.assertIn('_auth_user_id', cliente.session)

    def test_paginas_autenticadas_nao_ficam_em_cache(self):
        cliente = self.cliente(self.gestor)
        for rota in ('pagina-inicial', 'aluno-listar', 'professor-listar', 'responsavel-listar', 'auditoria',
                     'documentos-lista', 'vinculo-listar', 'solicitacao-senha-listar'):
            with self.subTest(rota=rota):
                self.assertIn('no-store', cliente.get(reverse(rota)).headers.get('Cache-Control', ''))

    def test_cabecalhos_de_protecao(self):
        resposta = self.cliente(self.gestor).get(reverse('pagina-inicial'))
        self.assertEqual(resposta.headers.get('X-Frame-Options'), 'DENY')
        self.assertIn("frame-ancestors 'none'", resposta.headers.get('Content-Security-Policy', ''))
        self.assertEqual(resposta.headers.get('X-Content-Type-Options'), 'nosniff')


class DadosNaUrlTests(CenarioTestCase):
    def test_formularios_com_senha_ou_codigo_nunca_usam_get(self):
        pasta = Path(settings.BASE_DIR) / 'templates'
        sensiveis = re.compile(r'type="password"|name="(codigo|codigo_recuperacao|new_password\d|password\d?|old_password)"'
                               r'|formulario\b|form\.')
        for arquivo in pasta.rglob('*.html'):
            texto = arquivo.read_text(encoding='utf-8')
            for bloco in re.findall(r'<form[^>]*>.*?</form>', texto, flags=re.S | re.I):
                abertura = re.match(r'<form[^>]*>', bloco, flags=re.I).group(0)
                if 'method="post"' in abertura.lower():
                    continue
                with self.subTest(template=arquivo.name, form=abertura[:80]):
                    self.assertIsNone(re.search(r'type="password"|name="(codigo|codigo_recuperacao|'
                                                r'new_password\d|password\d?|old_password)"', bloco))

    def test_operacoes_que_alteram_dados_nao_aceitam_get(self):
        cliente = self.cliente(self.gestor)
        for rota, args in (('aluno-excluir', [self.outro_aluno.pk]), ('professor-excluir', [self.outro_professor.pk]),
                           ('foto-perfil-remover', []), ('2fa-revogar', []), ('logout', [])):
            with self.subTest(rota=rota):
                antes = fotografia()
                cliente.get(reverse(rota, args=args))
                self.assertEqual(fotografia(), antes)
