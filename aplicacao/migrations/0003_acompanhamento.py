import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("aplicacao", "0002_aluno_vinculo"),
    ]

    operations = [
        migrations.CreateModel(
            name="Meta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=150)),
                ("descricao", models.TextField(blank=True)),
                ("data_inicio", models.DateField()),
                ("data_prazo", models.DateField(blank=True, null=True)),
                ("situacao", models.CharField(choices=[("EM_ANDAMENTO", "Em andamento"), ("CONCLUIDA", "Concluída"), ("CANCELADA", "Cancelada")], default="EM_ANDAMENTO", max_length=20)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("aluno", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="metas", to="aplicacao.aluno")),
                ("professor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="metas", to="aplicacao.professor")),
            ],
            options={
                "db_table": "meta",
                "ordering": ["data_prazo", "titulo"],
            },
        ),
        migrations.CreateModel(
            name="Atividade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=150)),
                ("descricao", models.TextField(blank=True)),
                ("data_entrega", models.DateField(blank=True, null=True)),
                ("situacao", models.CharField(choices=[("PENDENTE", "Pendente"), ("CONCLUIDA", "Concluída"), ("CANCELADA", "Cancelada")], default="PENDENTE", max_length=20)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("aluno", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="atividades", to="aplicacao.aluno")),
                ("meta", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="atividades", to="aplicacao.meta")),
                ("professor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="atividades", to="aplicacao.professor")),
            ],
            options={
                "db_table": "atividade",
                "ordering": ["data_entrega", "titulo"],
            },
        ),
        migrations.CreateModel(
            name="Frequencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data_acompanhamento", models.DateField()),
                ("compareceu", models.BooleanField(default=True)),
                ("observacao", models.CharField(blank=True, max_length=255)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("aluno", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="frequencias", to="aplicacao.aluno")),
                ("professor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="frequencias", to="aplicacao.professor")),
            ],
            options={
                "verbose_name": "frequência",
                "verbose_name_plural": "frequências",
                "db_table": "frequencia",
                "ordering": ["-data_acompanhamento"],
            },
        ),
        migrations.CreateModel(
            name="Conteudo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=150)),
                ("descricao", models.TextField(blank=True)),
                ("tipo_conteudo", models.CharField(blank=True, max_length=40)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("aluno", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="conteudos", to="aplicacao.aluno")),
                ("atividade", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="conteudos", to="aplicacao.atividade")),
                ("professor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="conteudos", to="aplicacao.professor")),
            ],
            options={
                "db_table": "conteudo",
                "ordering": ["titulo"],
            },
        ),
        migrations.AddConstraint(
            model_name="meta",
            constraint=models.CheckConstraint(
                condition=models.Q(("data_prazo__isnull", True), ("data_prazo__gte", models.F("data_inicio")), _connector="OR"),
                name="chk_meta_datas",
            ),
        ),
    ]
