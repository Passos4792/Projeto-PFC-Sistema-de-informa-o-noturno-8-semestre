from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('elo', '0014_atividade_material_apoio_atividade_material_nome_and_more')]

    operations = [
        migrations.AlterField(
            model_name='atividade',
            name='tipo_entrega',
            field=models.CharField(
                choices=[('ENVIO', 'Resposta ou anexo do aluno'), ('REGISTRO', 'Registro presencial (sem envio)')],
                default='ENVIO', max_length=12,
            ),
        ),
    ]
