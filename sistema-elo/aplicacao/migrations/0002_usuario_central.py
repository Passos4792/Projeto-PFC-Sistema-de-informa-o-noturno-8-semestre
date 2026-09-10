import django.db.models.deletion
from django.db import migrations, models


PERFIS = (
    ("Professor", "PROFESSOR"),
    ("Aluno", "ALUNO"),
    ("Responsavel", "RESPONSAVEL"),
)


def validar_usuarios_existentes(apps, schema_editor):
    usuarios_encontrados = {}

    for nome_modelo, tipo_perfil in PERFIS:
        Modelo = apps.get_model("elo", nome_modelo)

        for identificador, nome_usuario in Modelo.objects.values_list("pk", "usuario"):
            chave = nome_usuario.casefold()

            if chave in usuarios_encontrados:
                perfil_anterior = usuarios_encontrados[chave]
                raise RuntimeError(
                    f'O usuário "{nome_usuario}" está repetido entre os perfis '
                    f'{perfil_anterior} e {tipo_perfil}. Corrija o nome antes de migrar.'
                )

            usuarios_encontrados[chave] = tipo_perfil


def criar_contas_centrais(apps, schema_editor):
    Usuario = apps.get_model("elo", "Usuario")

    for nome_modelo, tipo_perfil in PERFIS:
        Modelo = apps.get_model("elo", nome_modelo)

        for perfil in Modelo.objects.all():
            conta = Usuario.objects.create(
                usuario=perfil.usuario,
                tipo_perfil=tipo_perfil,
            )
            perfil.conta_id = conta.pk
            perfil.save(update_fields=["conta"])


class Migration(migrations.Migration):

    dependencies = [
        ("elo", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(validar_usuarios_existentes, migrations.RunPython.noop),
        migrations.CreateModel(
            name="Usuario",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("usuario", models.CharField(max_length=160, unique=True)),
                (
                    "tipo_perfil",
                    models.CharField(
                        choices=[
                            ("PROFESSOR", "Professor"),
                            ("ALUNO", "Aluno"),
                            ("RESPONSAVEL", "Responsável"),
                        ],
                        max_length=20,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "usuário",
                "verbose_name_plural": "usuários",
                "db_table": "usuario",
                "ordering": ["usuario"],
            },
        ),
        migrations.AddField(
            model_name="aluno",
            name="conta",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="aluno_perfil",
                to="elo.usuario",
            ),
        ),
        migrations.AddField(
            model_name="professor",
            name="conta",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="professor_perfil",
                to="elo.usuario",
            ),
        ),
        migrations.AddField(
            model_name="responsavel",
            name="conta",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="responsavel_perfil",
                to="elo.usuario",
            ),
        ),
        migrations.RunPython(criar_contas_centrais, migrations.RunPython.noop),
        migrations.RemoveField(model_name="aluno", name="usuario"),
        migrations.RemoveField(model_name="professor", name="usuario"),
        migrations.RemoveField(model_name="responsavel", name="usuario"),
        migrations.RenameField(model_name="aluno", old_name="conta", new_name="usuario"),
        migrations.RenameField(model_name="professor", old_name="conta", new_name="usuario"),
        migrations.RenameField(model_name="responsavel", old_name="conta", new_name="usuario"),
        migrations.AlterField(
            model_name="aluno",
            name="usuario",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="aluno_perfil",
                to="elo.usuario",
            ),
        ),
        migrations.AlterField(
            model_name="professor",
            name="usuario",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="professor_perfil",
                to="elo.usuario",
            ),
        ),
        migrations.AlterField(
            model_name="responsavel",
            name="usuario",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="responsavel_perfil",
                to="elo.usuario",
            ),
        ),
    ]
