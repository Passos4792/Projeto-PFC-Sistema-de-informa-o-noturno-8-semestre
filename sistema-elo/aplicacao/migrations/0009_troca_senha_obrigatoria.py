from django.db import migrations, models


def preservar_acessos_existentes(apps, schema_editor):
    Usuario = apps.get_model('elo', 'Usuario')
    Usuario.objects.using(schema_editor.connection.alias).filter(
        conta__last_login__isnull=False,
    ).update(troca_senha_obrigatoria=False)


class Migration(migrations.Migration):
    dependencies = [('elo', '0008_aceite_documentos')]
    operations = [
        migrations.AddField(
            model_name='usuario', name='troca_senha_obrigatoria',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(preservar_acessos_existentes, migrations.RunPython.noop),
    ]
