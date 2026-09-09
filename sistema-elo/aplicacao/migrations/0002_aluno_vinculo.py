import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("aplicacao", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Aluno",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=80)),
                ("sobrenome", models.CharField(max_length=120)),
                ("usuario", models.CharField(max_length=160, unique=True)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("data_nascimento", models.DateField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "aluno",
                "verbose_name_plural": "alunos",
                "db_table": "aluno",
                "ordering": ["nome", "sobrenome"],
            },
        ),
        migrations.CreateModel(
            name="Vinculo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data_vinculo", models.DateField()),
                ("ativo", models.BooleanField(default=True)),
                ("aluno", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="vinculo", to="aplicacao.aluno")),
                ("professor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="vinculos", to="aplicacao.professor")),
                ("responsavel", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="vinculos", to="aplicacao.responsavel")),
            ],
            options={
                "verbose_name": "vínculo",
                "verbose_name_plural": "vínculos",
                "db_table": "vinculo",
                "ordering": ["aluno__nome"],
            },
        ),
    ]
