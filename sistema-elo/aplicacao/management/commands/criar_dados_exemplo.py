from datetime import date

from django.core.management.base import BaseCommand, CommandError

from aplicacao.models import Aluno, Atividade, Conteudo, Frequencia, Meta, Professor, Responsavel, Usuario, Vinculo


class Command(BaseCommand):
    help = "Cria os dados de exemplo da primeira versão do ELO."

    def handle(self, *args, **options):
        def obter_conta(nome_usuario, tipo_perfil):
            conta, criada = Usuario.objects.get_or_create(
                usuario=nome_usuario,
                defaults={"tipo_perfil": tipo_perfil},
            )

            if not criada and conta.tipo_perfil != tipo_perfil:
                raise CommandError(
                    f'O usuário "{nome_usuario}" já pertence a outro tipo de perfil.'
                )

            return conta

        conta_ana = obter_conta("ana.martins", Usuario.TipoPerfil.PROFESSOR)
        ana, _ = Professor.objects.update_or_create(
            usuario=conta_ana,
            defaults={"nome": "Ana", "sobrenome": "Martins", "ativo": True},
        )
        conta_carlos = obter_conta("carlos.souza", Usuario.TipoPerfil.PROFESSOR)
        carlos, _ = Professor.objects.update_or_create(
            usuario=conta_carlos,
            defaults={"nome": "Carlos", "sobrenome": "Souza", "ativo": True},
        )
        conta_fernanda = obter_conta("fernanda.lima", Usuario.TipoPerfil.PROFESSOR)
        fernanda, _ = Professor.objects.update_or_create(
            usuario=conta_fernanda,
            defaults={"nome": "Fernanda", "sobrenome": "Lima", "ativo": True},
        )

        conta_paula = obter_conta("paula.oliveira", Usuario.TipoPerfil.RESPONSAVEL)
        paula, _ = Responsavel.objects.update_or_create(
            usuario=conta_paula,
            defaults={"nome": "Paula", "sobrenome": "Oliveira", "ativo": True},
        )
        conta_roberto = obter_conta("roberto.costa", Usuario.TipoPerfil.RESPONSAVEL)
        roberto, _ = Responsavel.objects.update_or_create(
            usuario=conta_roberto,
            defaults={"nome": "Roberto", "sobrenome": "Costa", "ativo": True},
        )
        conta_juliana = obter_conta("juliana.santos", Usuario.TipoPerfil.RESPONSAVEL)
        juliana, _ = Responsavel.objects.update_or_create(
            usuario=conta_juliana,
            defaults={"nome": "Juliana", "sobrenome": "Santos", "ativo": True},
        )

        conta_maria = obter_conta("maria.oliveira", Usuario.TipoPerfil.ALUNO)
        maria, _ = Aluno.objects.update_or_create(
            usuario=conta_maria,
            defaults={"nome": "Maria", "sobrenome": "Oliveira", "data_nascimento": date(2012, 5, 14), "ativo": True},
        )
        conta_lucas = obter_conta("lucas.costa", Usuario.TipoPerfil.ALUNO)
        lucas, _ = Aluno.objects.update_or_create(
            usuario=conta_lucas,
            defaults={"nome": "Lucas", "sobrenome": "Costa", "data_nascimento": date(2011, 9, 22), "ativo": True},
        )
        conta_beatriz = obter_conta("beatriz.santos", Usuario.TipoPerfil.ALUNO)
        beatriz, _ = Aluno.objects.update_or_create(
            usuario=conta_beatriz,
            defaults={"nome": "Beatriz", "sobrenome": "Santos", "data_nascimento": date(2013, 2, 10), "ativo": True},
        )

        Vinculo.objects.update_or_create(aluno=maria, defaults={"professor": ana, "responsavel": paula, "data_vinculo": date(2026, 8, 10), "ativo": True})
        Vinculo.objects.update_or_create(aluno=lucas, defaults={"professor": carlos, "responsavel": roberto, "data_vinculo": date(2026, 8, 11), "ativo": True})
        Vinculo.objects.update_or_create(aluno=beatriz, defaults={"professor": fernanda, "responsavel": juliana, "data_vinculo": date(2026, 8, 12), "ativo": True})

        meta_leitura, _ = Meta.objects.update_or_create(
            aluno=maria,
            titulo="Melhorar a leitura",
            defaults={"professor": ana, "descricao": "Ler durante vinte minutos por dia.", "data_inicio": date(2026, 8, 10), "data_prazo": date(2026, 9, 30), "situacao": Meta.Situacao.EM_ANDAMENTO},
        )
        meta_emocoes, _ = Meta.objects.update_or_create(
            aluno=maria,
            titulo="Expressar emoções",
            defaults={"professor": ana, "descricao": "Registrar como se sentiu durante a semana.", "data_inicio": date(2026, 8, 1), "data_prazo": date(2026, 8, 25), "situacao": Meta.Situacao.CONCLUIDA},
        )

        tarefa, _ = Atividade.objects.update_or_create(
            aluno=maria,
            titulo="Tarefa",
            defaults={"professor": ana, "meta": meta_leitura, "descricao": "Ler e escrever um resumo sobre o livro entregue na sexta.", "data_entrega": date(2026, 9, 11), "situacao": Atividade.Situacao.PENDENTE},
        )
        Atividade.objects.update_or_create(
            aluno=maria,
            titulo="Emoções",
            defaults={"professor": ana, "meta": meta_emocoes, "descricao": "Fazer um diário de emoções dos fins de semana.", "data_entrega": date(2026, 9, 14), "situacao": Atividade.Situacao.PENDENTE},
        )
        Atividade.objects.update_or_create(
            aluno=maria,
            titulo="Extra",
            defaults={"professor": ana, "descricao": "Realizar atividade musical ensinada em sala com os pais.", "data_entrega": date(2026, 9, 18), "situacao": Atividade.Situacao.PENDENTE},
        )

        Conteudo.objects.update_or_create(
            aluno=maria,
            titulo="Guia para o resumo",
            defaults={"professor": ana, "atividade": tarefa, "descricao": "Passos para organizar o resumo do livro.", "tipo_conteudo": "Texto"},
        )
        Frequencia.objects.update_or_create(
            aluno=maria,
            data_acompanhamento=date(2026, 8, 21),
            defaults={"professor": ana, "compareceu": True, "observacao": "Apresentou evolução na leitura."},
        )

        self.stdout.write(self.style.SUCCESS("Dados de exemplo criados com sucesso."))
