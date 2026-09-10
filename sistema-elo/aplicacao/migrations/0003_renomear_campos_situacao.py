from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("elo", "0002_usuario_central"),
    ]

    operations = [
        migrations.RenameField(
            model_name="meta",
            old_name="status_meta",
            new_name="situacao",
        ),
        migrations.RenameField(
            model_name="atividade",
            old_name="status_atividade",
            new_name="situacao",
        ),
    ]
