from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('elo', '0025_aluno_inativado_em')]
    operations = [
        migrations.RenameField(model_name='usuario', old_name='professor_principal', new_name='gestor'),
    ]
