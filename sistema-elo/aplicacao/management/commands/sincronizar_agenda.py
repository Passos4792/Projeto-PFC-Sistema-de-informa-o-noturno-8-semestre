from django.core.management.base import BaseCommand
from aplicacao.models import ConexaoGoogle
from aplicacao.servicos.sincronizacao_automatica import sincronizar_usuario


class Command(BaseCommand):
    help = 'Reconcilia atividades futuras e eventos do Google Agenda (uso manual/agendado).'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', type=int, help='ID opcional do perfil ELO')

    def handle(self, *args, **options):
        conexoes = ConexaoGoogle.objects.select_related('usuario').all()
        if options['usuario']:
            conexoes = conexoes.filter(usuario_id=options['usuario'])
        sucesso = falhas = 0
        for conexao in conexoes.iterator():
            ok, erros = sincronizar_usuario(conexao.usuario)
            sucesso += ok
            falhas += erros
        self.stdout.write(f'Envios/atualizações: {sucesso}; falhas: {falhas}.')
