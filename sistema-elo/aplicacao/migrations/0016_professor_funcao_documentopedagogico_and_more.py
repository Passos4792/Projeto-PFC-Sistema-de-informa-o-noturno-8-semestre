import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0015_atividade_tipo_entrega_padrao'),
    ]

    operations = [
        migrations.AddField(
            model_name='professor',
            name='funcao',
            field=models.CharField(choices=[('AEE', 'Professor do AEE'), ('REGENTE', 'Professor regente'), ('ACOMPANHANTE', 'Professor acompanhante')], default='AEE', max_length=15),
        ),
        migrations.CreateModel(
            name='DocumentoPedagogico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('PEI', 'Plano Educacional Individualizado (PEI)'), ('ESTUDO', 'Estudo de Caso'), ('PAEE', 'Plano de Atendimento Educacional Especializado (PAEE)')], max_length=10)),
                ('ano_letivo', models.PositiveSmallIntegerField()),
                ('bimestre', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(4)])),
                ('campos', models.JSONField(default=dict)),
                ('situacao', models.CharField(choices=[('RASCUNHO', 'Rascunho'), ('FINALIZADO', 'Finalizado (interno)'), ('PUBLICADO', 'Disponível à família')], default='RASCUNHO', max_length=12)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='documentos_pedagogicos', to='elo.aluno')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='documentos_pedagogicos', to='elo.professor')),
            ],
            options={
                'db_table': 'documento_pedagogico',
                'ordering': ['-ano_letivo', 'tipo', '-pk'],
            },
        ),
        migrations.CreateModel(
            name='RelatorioPedagogico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=180)),
                ('data_referencia', models.DateField(default=django.utils.timezone.localdate)),
                ('periodo', models.CharField(blank=True, max_length=80)),
                ('relato', models.TextField(help_text='Registro descritivo feito após o atendimento ou período acompanhado.')),
                ('situacao', models.CharField(choices=[('RASCUNHO', 'Rascunho'), ('FINALIZADO', 'Finalizado (interno)'), ('PUBLICADO', 'Disponível à família')], default='RASCUNHO', max_length=12)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='relatorios_pedagogicos', to='elo.aluno')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='relatorios_pedagogicos', to='elo.professor')),
            ],
            options={
                'db_table': 'relatorio_pedagogico',
                'ordering': ['-data_referencia', '-pk'],
            },
        ),
        migrations.CreateModel(
            name='VinculoFamiliar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vinculos_familiares', to='elo.aluno')),
                ('responsavel', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vinculos_familiares', to='elo.responsavel')),
            ],
            options={
                'db_table': 'vinculo_familiar',
                'constraints': [models.UniqueConstraint(fields=('aluno', 'responsavel'), name='elo_vinculo_familiar_unico')],
            },
        ),
        migrations.CreateModel(
            name='VinculoProfissional',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('funcao', models.CharField(choices=[('AEE', 'Professor do AEE'), ('REGENTE', 'Professor regente'), ('ACOMPANHANTE', 'Professor acompanhante')], max_length=15)),
                ('data_inicio', models.DateField(default=django.utils.timezone.localdate)),
                ('data_fim', models.DateField(blank=True, null=True)),
                ('ativo', models.BooleanField(default=True)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vinculos_profissionais', to='elo.aluno')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='atribuicoes', to='elo.professor')),
            ],
            options={
                'db_table': 'vinculo_profissional',
                'ordering': ['aluno__nome', 'professor__nome'],
                'constraints': [models.UniqueConstraint(fields=('aluno', 'professor', 'funcao'), name='elo_vinculo_profissional_unico')],
            },
        ),
    ]
