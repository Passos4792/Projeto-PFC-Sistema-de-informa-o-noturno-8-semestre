from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('elo', '0029_usuario_conta_encerrada_em')]

    operations = [
        migrations.AlterField(
            model_name='solicitacaosenha', name='situacao',
            field=models.CharField(
                max_length=12, db_index=True, default='PENDENTE',
                choices=[('PENDENTE', 'Pendente'), ('ATENDIDA', 'Atendida'),
                         ('CANCELADA', 'Cancelada'),
                         ('NEGADA', 'Negada')],
            ),
        ),
    ]
