from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0023_autenticacao_2fa'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='metaaluno',
            name='disciplina',
        ),
    ]
