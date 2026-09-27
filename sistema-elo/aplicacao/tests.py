from django.test import SimpleTestCase
from django.urls import reverse

from .models import Aluno, Atividade, Meta, Professor, Usuario, Vinculo


class TestesDaEstruturaDoProjeto(SimpleTestCase):
    def test_models_usam_os_nomes_planejados(self):
        self.assertEqual(Professor._meta.db_table, "professor")
        self.assertEqual(Usuario._meta.db_table, "usuario")
        self.assertTrue(Usuario._meta.get_field("usuario").unique)
        self.assertEqual(Aluno._meta.db_table, "aluno")
        self.assertEqual(Vinculo._meta.db_table, "vinculo")
        self.assertEqual(Meta._meta.db_table, "meta")
        self.assertEqual(Atividade._meta.db_table, "atividade")

    def test_rotas_principais_existem(self):
        self.assertEqual(reverse("professor-listar"), "/professores/")
        self.assertEqual(reverse("aluno-listar"), "/alunos/")
        self.assertEqual(reverse("meta-listar"), "/metas/")
        self.assertEqual(reverse("atividade-listar"), "/atividades/")
