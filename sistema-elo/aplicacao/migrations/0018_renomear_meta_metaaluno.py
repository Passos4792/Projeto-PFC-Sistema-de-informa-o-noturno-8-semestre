from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0017_mesclar_perfis_vinculos'),
    ]

    operations = [
        migrations.RenameModel(old_name='Meta', new_name='MetaAluno'),
        migrations.AlterModelOptions(
            name='metaaluno',
            options={'ordering': ['data_prazo', 'titulo'], 'verbose_name': 'meta', 'verbose_name_plural': 'metas'},
        ),
    ]
