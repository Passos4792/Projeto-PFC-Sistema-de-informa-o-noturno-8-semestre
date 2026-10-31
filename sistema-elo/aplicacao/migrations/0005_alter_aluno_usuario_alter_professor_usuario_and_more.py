

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elo', '0004_autenticacao'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aluno',
            name='usuario',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                       related_name='%(class)s_perfil', to='elo.usuario'),
        ),
        migrations.AlterField(
            model_name='professor',
            name='usuario',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                       related_name='%(class)s_perfil', to='elo.usuario'),
        ),
        migrations.AlterField(
            model_name='responsavel',
            name='usuario',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                       related_name='%(class)s_perfil', to='elo.usuario'),
        ),
    ]

