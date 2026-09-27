#importacoes
from getpass import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from aplicacao.models import Usuario, Professor


#-------------------------------------------------------------------------------------

#comando de gerenciamento
class Command(BaseCommand):
    help = 'Ativa uma conta existente ou cria o primeiro professor principal, com senha solicitada no terminal.'

    #-------------------------------------------------------------------------------------

    #argumentos do comando
    def add_arguments(self, parser):
        parser.add_argument('usuario')
        parser.add_argument('--principal', action='store_true')

    #-------------------------------------------------------------------------------------

    #execucao do comando
    @transaction.atomic
    def handle(self, *args, **options):
        nome = options['usuario'].strip().lower()
        User = get_user_model()
        candidato = User(username=nome)
        try:
            candidato.full_clean(exclude=['password'])
        except ValidationError as exc:
            # Existing linked accounts are allowed for password resets.
            if not Usuario.objects.filter(usuario=nome, conta__username=nome).exists():
                raise CommandError(str(exc))
        perfil = Usuario.objects.filter(usuario__iexact=nome).first()
        if options['principal']:
            if perfil and perfil.tipo_perfil != 'PROFESSOR':
                raise CommandError('Esta conta não é de professor.')
            outros = Usuario.objects.filter(professor_principal=True)
            if perfil:
                outros = outros.exclude(pk=perfil.pk)
            if outros.exists():
                raise CommandError('Já existe um professor principal.')
        elif perfil is None:
            raise CommandError('Cadastre o usuário pelo sistema antes de ativá-lo.')
        conta = perfil.conta if perfil and perfil.conta_id else candidato
        if conta.pk is None and User.objects.filter(username__iexact=nome).exists():
            raise CommandError('Nome já ocupado por outra conta de autenticação.')
        senha = getpass('Nova senha: ')
        if senha != getpass('Confirme a senha: '):
            raise CommandError('As senhas não coincidem.')
        try:
            validate_password(senha, conta)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages))
        conta.set_password(senha)
        conta.save()
        if perfil is None:
            perfil = Usuario.objects.create(usuario=nome, tipo_perfil='PROFESSOR')
            Professor.objects.create(usuario=perfil, nome=input('Nome: ').strip() or nome,
                                     sobrenome=input('Sobrenome: ').strip())
        perfil.conta = conta
        perfil.troca_senha_obrigatoria = True
        if options['principal']:
            perfil.professor_principal = True
        perfil.save()
        from aplicacao.auditoria import registrar
        registrar('SENHA', objeto=perfil)
        if options['principal']:
            registrar('PERMISSAO', objeto=perfil,
                      detalhes='Professor principal definido pelo comando local.')
        self.stdout.write(self.style.SUCCESS(
            'Conta configurada. O estado ativo do cadastro foi preservado.'))
#-------------------------------------------------------------------------------------
