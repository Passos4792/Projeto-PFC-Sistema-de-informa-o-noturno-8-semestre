from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0026_renomear_professor_principal_gestor'),
    ]

    operations = [
        migrations.AddField(
            model_name='registroauditoria',
            name='ip',
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name='IP'),
        ),
    ]
