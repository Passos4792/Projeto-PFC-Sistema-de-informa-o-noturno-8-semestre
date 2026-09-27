#importacoes
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


#-------------------------------------------------------------------------------------

#migracao do banco de dados
class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL),
                    ('elo', '0003_renomear_campos_situacao')]
    operations = [
        migrations.AddField(model_name='usuario', name='conta',
                            field=models.OneToOneField(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL,
                                                       related_name='perfil_elo', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='usuario', name='professor_principal',
                            field=models.BooleanField(default=False)),
    ]
#-------------------------------------------------------------------------------------
