from django.test import SimpleTestCase
from django.urls import reverse

from .models import Aluno, Atividade, Meta, Professor, Responsavel, Vinculo


class TestesDaEstruturaDoProjeto(SimpleTestCase):
    def test_models_principais(self):
        self.assertEqual(Professor._meta.db_table, "professor")
        self.assertEqual(Responsavel._meta.db_table, "responsavel")
        self.assertEqual(Aluno._meta.db_table, "aluno")
        self.assertEqual(Vinculo._meta.db_table, "vinculo")
        self.assertEqual(Meta._meta.db_table, "meta")
        self.assertEqual(Atividade._meta.db_table, "atividade")
        self.assertTrue(Aluno._meta.get_field("usuario").unique)

    def test_rotas_principais(self):
        self.assertEqual(reverse("professor-listar"), "/professores/")
        self.assertEqual(reverse("responsavel-listar"), "/responsaveis/")
        self.assertEqual(reverse("aluno-listar"), "/alunos/")
        self.assertEqual(reverse("vinculo-listar"), "/vinculos/")
        self.assertEqual(reverse("meta-listar"), "/metas/")
        self.assertEqual(reverse("atividade-listar"), "/atividades/")
