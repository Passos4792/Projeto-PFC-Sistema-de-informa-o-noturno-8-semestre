from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('elo', '0028_autorizacao_acesso_menor')]

    operations = [
        migrations.AddField(
            model_name='usuario', name='conta_encerrada_em',
            field=models.DateTimeField(blank=True, db_index=True, editable=False, null=True),
        ),
    ]
