from django.test import SimpleTestCase
from django.urls import reverse

from .models import Aluno, Professor, Responsavel, Vinculo


class TestesDaEstruturaDoProjeto(SimpleTestCase):
    def test_models_funcionalidade_2(self):
        self.assertEqual(Professor._meta.db_table, "professor")
        self.assertEqual(Responsavel._meta.db_table, "responsavel")
        self.assertEqual(Aluno._meta.db_table, "aluno")
        self.assertEqual(Vinculo._meta.db_table, "vinculo")
        self.assertTrue(Aluno._meta.get_field("usuario").unique)

    def test_rotas_funcionalidade_2(self):
        self.assertEqual(reverse("professor-listar"), "/professores/")
        self.assertEqual(reverse("responsavel-listar"), "/responsaveis/")
        self.assertEqual(reverse("aluno-listar"), "/alunos/")
        self.assertEqual(reverse("vinculo-listar"), "/vinculos/")
