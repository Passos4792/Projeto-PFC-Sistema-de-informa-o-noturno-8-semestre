from datetime import date
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from aplicacao.servicos.documentos_legais import VERSAO_PRIVACIDADE, VERSAO_TERMOS
from aplicacao.models import Aluno, Atividade, Disciplina, MetaAluno, Professor, Responsavel, Usuario, Vinculo


SENHA = 'Teste-exclusivo@4829'
HOJE = date(2026, 11, 6)


def pessoa(login, tipo='ALUNO', gestor=False):
    conta = get_user_model().objects.create_user(username=login, password=SENHA)
    perfil = Usuario.objects.create(
        usuario=login, conta=conta, tipo_perfil=tipo, gestor=gestor,
        troca_senha_obrigatoria=False, documentos_aceitos_em=timezone.now(),
        versao_termos_aceita=VERSAO_TERMOS, versao_privacidade_ciente=VERSAO_PRIVACIDADE)
    modelo = {'ALUNO': Aluno, 'PROFESSOR': Professor, 'RESPONSAVEL': Responsavel}[tipo]
    return modelo.objects.create(usuario=perfil, nome=login, sobrenome='Teste')


class CenarioTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.professor = pessoa('professor', 'PROFESSOR')
        cls.outro_professor = pessoa('outro.professor', 'PROFESSOR')
        cls.gestor = pessoa('gestor', 'PROFESSOR', gestor=True)
        cls.aluno = pessoa('ana')
        cls.outro_aluno = pessoa('bruno')
        cls.responsavel = pessoa('responsavel', 'RESPONSAVEL')
        cls.vinculo = Vinculo.objects.create(
            aluno=cls.aluno, professor=cls.professor,
            responsavel=cls.responsavel, data_vinculo=HOJE, mesclar_perfis=True)
        cls.disciplina = Disciplina.objects.create(nome='Matemática')

    def cliente(self, pessoa_alvo, csrf=False):
        cliente = Client(enforce_csrf_checks=csrf)
        cliente.force_login(pessoa_alvo.usuario.conta)
        return cliente

    def atividade(self, **campos):
        dados = dict(aluno=self.aluno, professor=self.professor,
                     disciplina=self.disciplina, titulo='Operações', data_entrega=HOJE, tipo_entrega='REGISTRO')
        dados.update(campos)
        return Atividade.objects.create(**dados)

    def meta(self, **campos):
        dados = dict(aluno=self.aluno, professor=self.professor, titulo='Meta mensal',
                     periodo='MENSAL', quantidade_alvo=2,
                     data_inicio=date(2026, 11, 1), data_prazo=date(2026, 11, 30))
        dados.update(campos)
        return MetaAluno.objects.create(**dados)
