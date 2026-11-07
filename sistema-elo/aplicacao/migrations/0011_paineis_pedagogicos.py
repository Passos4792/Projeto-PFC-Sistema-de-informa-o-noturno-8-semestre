

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elo', '0010_google_calendario'),
    ]

    operations = [
        migrations.CreateModel(
            name='Disciplina',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True, verbose_name='Conteúdo')),
                ('descricao', models.TextField(blank=True, verbose_name='Descrição')),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'conteúdo curricular',
                'verbose_name_plural': 'conteúdos curriculares',
                'db_table': 'disciplina',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='SolicitacaoConclusao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mensagem', models.CharField(blank=True, max_length=500, verbose_name='Mensagem')),
                ('situacao', models.CharField(choices=[('PENDENTE', 'Aguardando aprovação'), ('APROVADA', 'Aprovada'), ('RECUSADA', 'Recusada')], db_index=True, default='PENDENTE', max_length=10)),
                ('resposta', models.CharField(blank=True, max_length=500)),
                ('solicitado_em', models.DateTimeField(auto_now_add=True)),
                ('respondido_em', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'solicitacao_conclusao',
                'ordering': ['-solicitado_em', '-pk'],
            },
        ),
        migrations.AddField(
            model_name='aluno',
            name='frequencia_minima',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='Frequência mínima (%)'),
        ),
        migrations.AddField(
            model_name='atividade',
            name='concluida_em',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='meta',
            name='periodo',
            field=models.CharField(choices=[('SEMANAL', 'Semanal'), ('MENSAL', 'Mensal'), ('TRIMESTRAL', 'Trimestral'), ('SEMESTRAL', 'Semestral'), ('PERSONALIZADO', 'Registro anterior')], default='PERSONALIZADO', max_length=20, verbose_name='Período'),
        ),
        migrations.AddField(
            model_name='meta',
            name='quantidade_alvo',
            field=models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Atividades a realizar'),
        ),
        migrations.AddConstraint(
            model_name='aluno',
            constraint=models.CheckConstraint(condition=models.Q(('frequencia_minima__isnull', True), models.Q(('frequencia_minima__gte', 0), ('frequencia_minima__lte', 100)), _connector='OR'), name='aluno_frequencia_entre_0_100'),
        ),
        migrations.AddField(
            model_name='atividade',
            name='disciplina',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='atividades', to='elo.disciplina', verbose_name='Conteúdo'),
        ),
        migrations.AddField(
            model_name='meta',
            name='disciplina',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='metas', to='elo.disciplina', verbose_name='Conteúdo'),
        ),
        migrations.AddConstraint(
            model_name='meta',
            constraint=models.CheckConstraint(condition=models.Q(('quantidade_alvo__gte', 1)), name='meta_alvo_positivo'),
        ),
        migrations.AddField(
            model_name='solicitacaoconclusao',
            name='aluno',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='solicitacoes', to='elo.aluno'),
        ),
        migrations.AddField(
            model_name='solicitacaoconclusao',
            name='atividade',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solicitacoes', to='elo.atividade'),
        ),
        migrations.AddField(
            model_name='solicitacaoconclusao',
            name='professor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='elo.professor'),
        ),
        migrations.AddField(
            model_name='solicitacaoconclusao',
            name='solicitante',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitacoes', to='elo.usuario'),
        ),
    ]
