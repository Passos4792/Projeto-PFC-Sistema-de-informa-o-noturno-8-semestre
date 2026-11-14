from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from aplicacao.servicos.auditoria import registrar
from aplicacao.models import CodigoRecuperacao2FA, Configuracao2FA, DispositivoConfiavel2FA


class Command(BaseCommand):
    help = 'Redefine o Authenticator de uma conta após validação presencial da identidade.'

    def add_arguments(self, parser):
        parser.add_argument('usuario', help='Nome exato da conta que terá o Authenticator resetado')
        parser.add_argument('--identidade-conferida', action='store_true',
                            help='Confirma que a identidade do titular foi verificada pela administração')

    @transaction.atomic
    def handle(self, *args, **opcoes):
        if not opcoes['identidade_conferida']:
            raise CommandError('Confira a identidade do titular e use --identidade-conferida.')
        usuario = get_user_model().objects.filter(username__iexact=opcoes['usuario'].strip()).first()
        if usuario is None:
            raise CommandError('Conta não encontrada.')
        Configuracao2FA.objects.filter(conta=usuario).delete()
        CodigoRecuperacao2FA.objects.filter(conta=usuario).delete()
        DispositivoConfiavel2FA.objects.filter(conta=usuario).delete()
        registrar('PERMISSAO', entidade='segundo fator', objeto_id=usuario.pk,
                  detalhes='Autenticação em duas etapas redefinida pela administração após conferência de identidade.')
        self.stdout.write(self.style.SUCCESS(
            'Segundo fator redefinido. Na próxima entrada, a conta deverá configurar um novo Authenticator.'))
