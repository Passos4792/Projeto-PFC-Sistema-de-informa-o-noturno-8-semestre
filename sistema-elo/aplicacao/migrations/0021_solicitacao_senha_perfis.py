from django.db import migrations, models
import django.db.models.deletion


def preencher_usuarios_antigos(apps, schema_editor):
    Pedido = apps.get_model('elo', 'SolicitacaoSenha')
    for pedido in Pedido.objects.filter(usuario_alvo__isnull=True).select_related('aluno'):
        if pedido.aluno_id:
            pedido.usuario_alvo_id = pedido.aluno.usuario_id
            pedido.save(update_fields=['usuario_alvo'])


class Migration(migrations.Migration):
    dependencies = [('elo', '0020_usuario_foto_perfil')]

    operations = [
        migrations.AlterField(
            model_name='solicitacaosenha', name='aluno',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='solicitacoes_senha', to='elo.aluno'),
        ),
        migrations.AlterField(
            model_name='solicitacaosenha', name='professor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='solicitacoes_senha', to='elo.professor'),
        ),
        migrations.AddField(
            model_name='solicitacaosenha', name='usuario_alvo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='solicitacoes_recuperacao', to='elo.usuario'),
        ),
        migrations.RunPython(preencher_usuarios_antigos, migrations.RunPython.noop),
    ]
