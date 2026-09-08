from django.test import SimpleTestCase
from django.urls import reverse

from .models import Professor, Responsavel


class TestesDaEstruturaDoProjeto(SimpleTestCase):
    def test_models_base(self):
        self.assertEqual(Professor._meta.db_table, "professor")
        self.assertEqual(Responsavel._meta.db_table, "responsavel")
        self.assertTrue(Professor._meta.get_field("usuario").unique)

    def test_rotas_base(self):
        self.assertEqual(reverse("professor-listar"), "/professores/")
        self.assertEqual(reverse("responsavel-listar"), "/responsaveis/")
