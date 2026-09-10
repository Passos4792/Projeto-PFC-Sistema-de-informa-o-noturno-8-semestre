import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Aluno',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=80)),
                ('sobrenome', models.CharField(max_length=120)),
                ('usuario', models.CharField(max_length=160, unique=True)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('data_nascimento', models.DateField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'aluno',
                'verbose_name_plural': 'alunos',
                'db_table': 'aluno',
                'ordering': ['nome', 'sobrenome'],
            },
        ),
        migrations.CreateModel(
            name='Professor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=80)),
                ('sobrenome', models.CharField(max_length=120)),
                ('usuario', models.CharField(max_length=160, unique=True)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'professor',
                'verbose_name_plural': 'professores',
                'db_table': 'professor',
                'ordering': ['nome', 'sobrenome'],
            },
        ),
        migrations.CreateModel(
            name='Responsavel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=80)),
                ('sobrenome', models.CharField(max_length=120)),
                ('usuario', models.CharField(max_length=160, unique=True)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'responsável',
                'verbose_name_plural': 'responsáveis',
                'db_table': 'responsavel',
                'ordering': ['nome', 'sobrenome'],
            },
        ),
        migrations.CreateModel(
            name='Meta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=150)),
                ('descricao', models.TextField(blank=True)),
                ('data_inicio', models.DateField()),
                ('data_prazo', models.DateField(blank=True, null=True)),
                ('status_meta', models.CharField(choices=[('EM_ANDAMENTO', 'Em andamento'), ('CONCLUIDA', 'Concluída'), ('CANCELADA', 'Cancelada')], default='EM_ANDAMENTO', max_length=20)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='metas', to='elo.aluno')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='metas', to='elo.professor')),
            ],
            options={
                'db_table': 'meta',
                'ordering': ['data_prazo', 'titulo'],
            },
        ),
        migrations.CreateModel(
            name='Atividade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=150)),
                ('descricao', models.TextField(blank=True)),
                ('data_entrega', models.DateField(blank=True, null=True)),
                ('status_atividade', models.CharField(choices=[('PENDENTE', 'Pendente'), ('CONCLUIDA', 'Concluída'), ('CANCELADA', 'Cancelada')], default='PENDENTE', max_length=20)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='atividades', to='elo.aluno')),
                ('meta', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='atividades', to='elo.meta')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='atividades', to='elo.professor')),
            ],
            options={
                'db_table': 'atividade',
                'ordering': ['data_entrega', 'titulo'],
            },
        ),
        migrations.CreateModel(
            name='Frequencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_acompanhamento', models.DateField()),
                ('compareceu', models.BooleanField(default=True)),
                ('observacao', models.CharField(blank=True, max_length=255)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='frequencias', to='elo.aluno')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='frequencias', to='elo.professor')),
            ],
            options={
                'verbose_name': 'frequência',
                'verbose_name_plural': 'frequências',
                'db_table': 'frequencia',
                'ordering': ['-data_acompanhamento'],
            },
        ),
        migrations.CreateModel(
            name='Conteudo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=150)),
                ('descricao', models.TextField(blank=True)),
                ('tipo_conteudo', models.CharField(blank=True, max_length=40)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='conteudos', to='elo.aluno')),
                ('atividade', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conteudos', to='elo.atividade')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='conteudos', to='elo.professor')),
            ],
            options={
                'db_table': 'conteudo',
                'ordering': ['titulo'],
            },
        ),
        migrations.CreateModel(
            name='Vinculo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_vinculo', models.DateField()),
                ('ativo', models.BooleanField(default=True)),
                ('aluno', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='vinculo', to='elo.aluno')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vinculos', to='elo.professor')),
                ('responsavel', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vinculos', to='elo.responsavel')),
            ],
            options={
                'verbose_name': 'vínculo',
                'verbose_name_plural': 'vínculos',
                'db_table': 'vinculo',
                'ordering': ['aluno__nome'],
            },
        ),
        migrations.AddConstraint(
            model_name='meta',
            constraint=models.CheckConstraint(condition=models.Q(('data_prazo__isnull', True), ('data_prazo__gte', models.F('data_inicio')), _connector='OR'), name='chk_meta_datas'),
        ),
    ]
