from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Professor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=80)),
                ("sobrenome", models.CharField(max_length=120)),
                ("usuario", models.CharField(max_length=160, unique=True)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "professor", "verbose_name_plural": "professores", "db_table": "professor", "ordering": ["nome", "sobrenome"]},
        ),
        migrations.CreateModel(
            name="Responsavel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=80)),
                ("sobrenome", models.CharField(max_length=120)),
                ("usuario", models.CharField(max_length=160, unique=True)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "responsável", "verbose_name_plural": "responsáveis", "db_table": "responsavel", "ordering": ["nome", "sobrenome"]},
        ),
    ]
