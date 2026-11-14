from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("elo", "0019_remover_frequencia_escolar")]
    operations = [migrations.AddField(
        model_name="usuario", name="foto_perfil",
        field=models.FileField(blank=True, upload_to="fotos_perfil/"),
    )]
