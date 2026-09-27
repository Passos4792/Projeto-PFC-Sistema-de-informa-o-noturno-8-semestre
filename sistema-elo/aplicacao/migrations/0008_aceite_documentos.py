from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elo', '0007_registroauditoria'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='documentos_aceitos_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='versao_privacidade_ciente',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='usuario',
            name='versao_termos_aceita',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name='registroauditoria',
            name='acao',
            field=models.CharField(choices=[
                ('LOGIN', 'Entrada no sistema'),
                ('SAIDA', 'Saída do sistema'),
                ('FALHA_LOGIN', 'Falha no login'),
                ('BLOQUEIO_LOGIN', 'Login bloqueado'),
                ('ACESSO_NEGADO', 'Acesso negado'),
                ('CRIACAO', 'Cadastro criado'),
                ('EDICAO', 'Cadastro alterado'),
                ('EXCLUSAO', 'Cadastro excluído'),
                ('PERMISSAO', 'Permissão definida ou alterada'),
                ('SENHA', 'Senha definida ou redefinida'),
                ('DOCUMENTOS', 'Aceite de termos e privacidade'),
            ], db_index=True, max_length=25),
        ),
    ]
