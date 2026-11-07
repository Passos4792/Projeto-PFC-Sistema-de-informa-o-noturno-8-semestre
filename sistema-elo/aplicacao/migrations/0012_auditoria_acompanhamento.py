

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elo', '0011_paineis_pedagogicos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='registroauditoria',
            name='acao',
            field=models.CharField(choices=[('LOGIN', 'Entrada no sistema'), ('SAIDA', 'Saída do sistema'), ('FALHA_LOGIN', 'Falha no login'), ('BLOQUEIO_LOGIN', 'Login bloqueado'), ('ACESSO_NEGADO', 'Acesso negado'), ('CRIACAO', 'Cadastro criado'), ('EDICAO', 'Cadastro alterado'), ('EXCLUSAO', 'Cadastro excluído'), ('PERMISSAO', 'Permissão definida ou alterada'), ('SENHA', 'Senha definida ou redefinida'), ('DOCUMENTOS', 'Aceite de termos e privacidade'), ('CONSULTA', 'Consulta de dados'), ('SOLICITACAO', 'Conclusão solicitada'), ('APROVACAO', 'Conclusão aprovada'), ('RECUSA', 'Conclusão recusada'), ('FREQUENCIA', 'Frequência mínima alterada')], db_index=True, max_length=25),
        ),
    ]
