from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('elo', '0018_renomear_meta_metaaluno'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='aluno',
            name='aluno_frequencia_entre_0_100',
        ),
        migrations.RemoveField(
            model_name='aluno',
            name='frequencia_minima',
        ),
        migrations.DeleteModel(
            name='Frequencia',
        ),
        migrations.AlterField(
            model_name='registroauditoria',
            name='acao',
            field=models.CharField(
                max_length=25,
                db_index=True,
                choices=[
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
                    ('CONSULTA', 'Consulta de dados'),
                    ('SOLICITACAO', 'Conclusão solicitada'),
                    ('APROVACAO', 'Conclusão aprovada'),
                    ('RECUSA', 'Conclusão recusada'),
                ],
            ),
        ),
    ]
