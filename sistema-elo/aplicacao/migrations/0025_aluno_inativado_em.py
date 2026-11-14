from django.db import migrations, models
from django.utils import timezone


def marcar_inativos_existentes(apps, schema_editor):
    Aluno = apps.get_model('elo', 'Aluno')
    Aluno.objects.using(schema_editor.connection.alias).filter(
        ativo=False, inativado_em__isnull=True).update(inativado_em=timezone.now())


class Migration(migrations.Migration):
    dependencies = [('elo', '0024_remove_metaaluno_disciplina')]
    operations = [
        migrations.AddField(
            model_name='aluno', name='inativado_em',
            field=models.DateTimeField(blank=True, null=True, editable=False, db_index=True),
        ),
        migrations.RunPython(marcar_inativos_existentes, migrations.RunPython.noop),
    ]
