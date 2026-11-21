from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0027_auditoria_ip'),
    ]

    operations = [
        migrations.CreateModel(
            name='AutorizacaoAcessoMenor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('versao_termos', models.CharField(max_length=20)),
                ('versao_privacidade', models.CharField(max_length=20)),
                ('autorizado_em', models.DateTimeField(default=django.utils.timezone.now)),
                ('aluno', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='autorizacoes_acesso', to='elo.aluno')),
                ('responsavel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='autorizacoes_acesso', to='elo.responsavel')),
            ],
            options={
                'db_table': 'autorizacao_acesso_menor',
                'verbose_name': 'autorização de acesso de menor',
                'verbose_name_plural': 'autorizações de acesso de menores',
            },
        ),
        migrations.AddConstraint(
            model_name='autorizacaoacessomenor',
            constraint=models.UniqueConstraint(fields=('aluno', 'responsavel'), name='elo_autorizacao_menor_unica'),
        ),
    ]
