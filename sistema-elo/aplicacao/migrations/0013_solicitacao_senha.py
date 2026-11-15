from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('elo', '0012_auditoria_acompanhamento')]

    operations = [
        migrations.CreateModel(
            name='SolicitacaoSenha',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('situacao', models.CharField(choices=[('PENDENTE', 'Pendente'), ('ATENDIDA', 'Atendida')], db_index=True, default='PENDENTE', max_length=12)),
                ('criada_em', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('atendida_em', models.DateTimeField(blank=True, null=True)),
                ('origem_hash', models.CharField(blank=True, db_index=True, max_length=64)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='solicitacoes_senha', to='elo.aluno')),
                ('professor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='solicitacoes_senha', to='elo.professor')),
            ],
            options={
                'db_table': 'solicitacao_senha',
                'ordering': ['-criada_em', '-pk'],
                'verbose_name': 'solicitação de senha',
                'verbose_name_plural': 'solicitações de senha',
            },
        ),
    ]
