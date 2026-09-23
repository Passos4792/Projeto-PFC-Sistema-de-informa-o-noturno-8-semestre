#importacoes
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db import transaction
from django.shortcuts import render, redirect
from .models import Usuario, Professor, Aluno, Responsavel
from .acesso import alunos_permitidos


#-------------------------------------------------------------------------------------

#formulario de login
class LoginElo(AuthenticationForm):

    #-------------------------------------------------------------------------------------

    #mensagem de erro no login
    def get_invalid_login_error(self):
        espera = getattr(self.request, 'login_espera', 0)
        if espera:
            from math import ceil
            return forms.ValidationError(
                'Muitas tentativas de acesso. Tente novamente em %(minutos)s minuto(s).',
                code='login_bloqueado', params={'minutos': ceil(espera / 60)})
        return super().get_invalid_login_error()

    #-------------------------------------------------------------------------------------

    #validacao do nome de usuario
    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()


#-------------------------------------------------------------------------------------

#formulario de cadastro de usuario
class CadastroUsuario(UserCreationForm):
    nome = forms.CharField(max_length=80)
    sobrenome = forms.CharField(max_length=120)
    tipo_perfil = forms.ChoiceField(label='Nível de acesso')
    data_nascimento = forms.DateField(required=False, label='Data de nascimento (aluno)',
                                      widget=forms.DateInput(attrs={'type': 'date'}))

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = get_user_model()
        fields = ['nome', 'sobrenome', 'username', 'tipo_perfil',
                  'data_nascimento', 'password1', 'password2']

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, *args, operador, **kwargs):
        super().__init__(*args, **kwargs)
        escolhas = [('ALUNO', 'Aluno'), ('RESPONSAVEL', 'Responsável')]
        if operador.professor_principal:
            escolhas.append(('PROFESSOR', 'Professor'))
        self.fields['tipo_perfil'].choices = escolhas
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'campo-formulario'

    #-------------------------------------------------------------------------------------

    #validacao do nome de usuario
    def clean_username(self):
        nome = self.cleaned_data['username'].strip().lower()
        if Usuario.objects.filter(usuario__iexact=nome).exists() or get_user_model().objects.filter(username__iexact=nome).exists():
            raise forms.ValidationError('Este usuário já está sendo utilizado.')
        return nome

    #-------------------------------------------------------------------------------------

    #salvar registro
    @transaction.atomic
    def save(self, commit=True):
        conta = super().save(commit=False)
        conta.first_name = self.cleaned_data['nome']
        conta.last_name = self.cleaned_data['sobrenome']
        conta.save()
        tipo = self.cleaned_data['tipo_perfil']
        perfil = Usuario.objects.create(usuario=conta.username, tipo_perfil=tipo, conta=conta)
        campos = dict(nome=conta.first_name, sobrenome=conta.last_name, usuario=perfil)
        if tipo == 'ALUNO':
            campos['data_nascimento'] = self.cleaned_data['data_nascimento']
        {'PROFESSOR': Professor, 'ALUNO': Aluno, 'RESPONSAVEL': Responsavel}[
            tipo].objects.create(**campos)
        return conta


#-------------------------------------------------------------------------------------

#cadastrar
def cadastrar(request):
    form = CadastroUsuario(request.POST or None, operador=request.perfil_elo)
    if request.method == 'POST' and form.is_valid():
        from .auditoria import registrar
        with transaction.atomic():
            conta = form.save()
            registrar('CRIACAO', request=request, objeto=conta.perfil_elo)
            registrar('PERMISSAO', request=request, objeto=conta.perfil_elo,
                      detalhes='Perfil definido: ' + conta.perfil_elo.get_tipo_perfil_display())
        from django.contrib import messages
        messages.success(request, 'Usuário criado com o nível de acesso selecionado.')
        return redirect('usuario-criar')
    return render(request, 'aplicacao/formulario-padrao.html', {
        'formulario': form, 'titulo': 'Cadastrar usuário', 'pagina_ativa': 'usuarios', 'url_voltar': '/'})


#-------------------------------------------------------------------------------------

#inicio
def inicio(request):
    perfil = request.perfil_elo
    if perfil.tipo_perfil == 'PROFESSOR':
        return redirect('professor-listar')
    if perfil.tipo_perfil == 'ALUNO':
        return redirect('aluno-inicio', pk=perfil.aluno_perfil.pk)
    return render(request, 'aplicacao/portal.html', {'alunos': alunos_permitidos(perfil)})
#-------------------------------------------------------------------------------------
