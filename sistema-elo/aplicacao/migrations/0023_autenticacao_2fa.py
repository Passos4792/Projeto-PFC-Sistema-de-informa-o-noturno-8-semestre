from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0022_nascimento_professor_responsavel'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Configuracao2FA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('segredo_criptografado', models.TextField()),
                ('confirmada_em', models.DateTimeField(blank=True, null=True)),
                ('ultimo_intervalo', models.BigIntegerField(default=-1)),
                ('falhas', models.PositiveSmallIntegerField(default=0)),
                ('bloqueado_ate', models.DateTimeField(blank=True, null=True)),
                ('versao', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('conta', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                    related_name='configuracao_2fa', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'elo_configuracao_2fa',
                     'verbose_name': 'configuração de autenticação em duas etapas'},
        ),
        migrations.CreateModel(
            name='DispositivoConfiavel2FA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(max_length=64, unique=True)),
                ('assinatura_senha', models.CharField(max_length=64)),
                ('descricao', models.CharField(blank=True, max_length=160)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('expira_em', models.DateTimeField()),
                ('conta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='dispositivos_confiaveis_2fa', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'elo_dispositivo_confiavel_2fa', 'ordering': ['-criado_em']},
        ),
        migrations.CreateModel(
            name='CodigoRecuperacao2FA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo_hash', models.CharField(max_length=64, unique=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('conta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='codigos_recuperacao_2fa', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'elo_codigo_recuperacao_2fa'},
        ),
    ]
