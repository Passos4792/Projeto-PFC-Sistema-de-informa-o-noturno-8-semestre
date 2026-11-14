import aplicacao.servicos.arquivos
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0013_solicitacao_senha'),
    ]

    operations = [
        migrations.AddField(
            model_name='atividade',
            name='material_apoio',
            field=models.FileField(blank=True, upload_to=aplicacao.servicos.arquivos.caminho_material, validators=[aplicacao.servicos.arquivos.validar_anexo_pedagogico]),
        ),
        migrations.AddField(
            model_name='atividade',
            name='material_nome',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='atividade',
            name='tipo_entrega',
            field=models.CharField(choices=[('ENVIO', 'Resposta ou anexo do aluno'), ('REGISTRO', 'Registro presencial (sem envio)')], default='REGISTRO', max_length=12),
        ),
        migrations.AddField(
            model_name='solicitacaoconclusao',
            name='anexo',
            field=models.FileField(blank=True, upload_to=aplicacao.servicos.arquivos.caminho_entrega, validators=[aplicacao.servicos.arquivos.validar_anexo_pedagogico]),
        ),
        migrations.AddField(
            model_name='solicitacaoconclusao',
            name='anexo_nome',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='solicitacaoconclusao',
            name='resposta_aluno',
            field=models.TextField(blank=True, verbose_name='Resposta do aluno'),
        ),
    ]
