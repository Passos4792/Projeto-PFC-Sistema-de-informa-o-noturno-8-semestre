from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0021_solicitacao_senha_perfis'),
    ]

    operations = [
        migrations.AddField(
            model_name='professor',
            name='data_nascimento',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='responsavel',
            name='data_nascimento',
            field=models.DateField(blank=True, null=True),
        ),
    ]
