from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
from aplicacao.servicos.auditoria import registrar
from aplicacao.models import Atividade, LimiteLogin, RegistroAuditoria, SolicitacaoConclusao


class Command(BaseCommand):
    help = 'Remove controles de login vencidos e, quando solicitado, auditoria antiga e anexos sem registro.'

    def add_arguments(self, parser):
        parser.add_argument('--auditoria-dias', type=int,
                            help='Exclui registros de auditoria mais antigos que este número de dias.')
        parser.add_argument('--arquivos-orfaos', action='store_true',
                            help='Exclui arquivos enviados que não pertencem a nenhuma atividade ou entrega.')
        parser.add_argument('--simular', action='store_true',
                            help='Mostra o que seria removido, sem remover.')

    def handle(self, *args, **options):
        simular = options['simular']
        agora = timezone.now()
        limite_login = agora - timedelta(seconds=settings.LOGIN_JANELA_SEGUNDOS)
        vencidos = LimiteLogin.objects.filter(inicio__lt=limite_login).filter(
            Q(bloqueado_ate__isnull=True) | Q(bloqueado_ate__lt=agora))
        self._remover('controles de login vencidos', vencidos, simular)

        dias = options['auditoria_dias']
        if dias is not None:
            if dias < 30:
                raise CommandError('Mantenha ao menos 30 dias de auditoria.')
            antigos = RegistroAuditoria.objects.filter(criado_em__lt=agora - timedelta(days=dias))
            quantidade = self._remover(f'registros de auditoria com mais de {dias} dias', antigos, simular)
            if not simular and quantidade:
                registrar('EXCLUSAO', entidade='Auditoria', detalhes=(
                    f'{quantidade} registro(s) anteriores a {dias} dias removidos pelo comando local.'))

        if options['arquivos_orfaos']:
            self._arquivos_orfaos(simular)

    def _remover(self, descricao, consulta, simular):
        quantidade = consulta.count()
        if not simular:
            consulta.delete()
        self.stdout.write(f'{"Seriam removidos" if simular else "Removidos"}: {quantidade} {descricao}.')
        return quantidade

    def _arquivos_orfaos(self, simular):
        raiz = Path(settings.MEDIA_ROOT)
        em_uso = set(Atividade.objects.exclude(material_apoio='').values_list('material_apoio', flat=True))
        em_uso |= set(SolicitacaoConclusao.objects.exclude(anexo='').values_list('anexo', flat=True))
        orfaos = []
        for pasta in ('atividades/materiais', 'atividades/entregas'):
            diretorio = raiz / pasta
            if diretorio.is_dir():
                orfaos += [arquivo for arquivo in diretorio.iterdir()
                           if arquivo.is_file() and arquivo.relative_to(raiz).as_posix() not in em_uso]
        if not simular:
            for arquivo in orfaos:
                arquivo.unlink(missing_ok=True)
        self.stdout.write(f'{"Seriam removidos" if simular else "Removidos"}: {len(orfaos)} arquivos sem registro.')
