from django.db import migrations, models


def preservar_acessos_existentes(apps, schema_editor):
    apps.get_model('elo', 'Vinculo').objects.all().update(mesclar_perfis=True)
    apps.get_model('elo', 'VinculoFamiliar').objects.all().update(mesclar_perfis=True)


class Migration(migrations.Migration):
    dependencies = [('elo', '0016_professor_funcao_documentopedagogico_and_more')]
    operations = [
        migrations.AddField(
            model_name='vinculo', name='mesclar_perfis',
            field=models.BooleanField(default=False, verbose_name='Mesclar acesso com o responsável')),
        migrations.AddField(
            model_name='vinculofamiliar', name='mesclar_perfis',
            field=models.BooleanField(default=False, verbose_name='Mesclar acesso com o responsável')),
        migrations.RunPython(preservar_acessos_existentes, migrations.RunPython.noop),
    ]
