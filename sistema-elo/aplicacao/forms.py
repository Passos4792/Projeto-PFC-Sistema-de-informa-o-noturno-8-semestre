#importacoes
from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import RegistroAuditoria


#-------------------------------------------------------------------------------------

#filtros da auditoria
class FiltroAuditoria(forms.Form):
    acao = forms.ChoiceField(label='Ação', required=False,
                             choices=[('', 'Todas')] + list(RegistroAuditoria.Acao.choices))
    autor = forms.CharField(label='Usuário responsável', required=False, max_length=150)
    inicio = forms.DateField(label='De', required=False,
                             widget=forms.DateInput(attrs={'type': 'date'}))
    fim = forms.DateField(label='Até', required=False,
                          widget=forms.DateInput(attrs={'type': 'date'}))

    #-------------------------------------------------------------------------------------

    #validacao dos dados
    def clean(self):
        dados = super().clean()
        if dados.get('inicio') and dados.get('fim') and dados['inicio'] > dados['fim']:
            raise forms.ValidationError('A data inicial deve ser anterior ou igual à data final.')
        return dados


from .models import Aluno, Atividade, Conteudo, Frequencia, Meta, Professor, Responsavel, Usuario, Vinculo


#-------------------------------------------------------------------------------------

#formulario base
class FormularioBase(forms.ModelForm):

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "campo-formulario")


#-------------------------------------------------------------------------------------

#formulario pessoa base
class FormularioPessoaBase(FormularioBase):
    nome_usuario = forms.CharField(
        label="Usuário",
        max_length=160,
        help_text="Este nome deve ser único em todo o sistema.",
    )
    tipo_perfil = None

    #-------------------------------------------------------------------------------------

    #inicializacao
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.usuario_id:
            self.fields["nome_usuario"].initial = self.instance.usuario.usuario

    #-------------------------------------------------------------------------------------

    #validacao do nome de usuario
    def clean_nome_usuario(self):
        nome_usuario = self.cleaned_data["nome_usuario"].strip().lower()
        contas = Usuario.objects.filter(usuario__iexact=nome_usuario)

        if self.instance.pk and self.instance.usuario_id:
            contas = contas.exclude(pk=self.instance.usuario_id)

        autenticacoes = get_user_model().objects.filter(username__iexact=nome_usuario)
        if self.instance.pk and self.instance.usuario.conta_id:
            autenticacoes = autenticacoes.exclude(pk=self.instance.usuario.conta_id)
        if len(nome_usuario) > 150:
            raise forms.ValidationError('Use no máximo 150 caracteres.')
        if contas.exists() or autenticacoes.exists():
            raise forms.ValidationError("Este usuário já está sendo utilizado por outro perfil.")

        return nome_usuario

    #-------------------------------------------------------------------------------------

    #salvar registro
    def save(self, commit=True):
        perfil = super().save(commit=False)

        if not commit:
            return perfil

        with transaction.atomic():
            if perfil.pk and perfil.usuario_id:
                conta = perfil.usuario
                conta.usuario = self.cleaned_data["nome_usuario"]
                conta.save()
                if conta.conta_id:
                    login = conta.conta
                    login.username = conta.usuario
                    login.is_active = perfil.ativo
                    login.first_name = perfil.nome
                    login.last_name = perfil.sobrenome
                    login.save()
            else:
                conta = Usuario.objects.create(
                    usuario=self.cleaned_data["nome_usuario"],
                    tipo_perfil=self.tipo_perfil,
                )

            perfil.usuario = conta
            perfil.save()
            self.save_m2m()

        return perfil


#-------------------------------------------------------------------------------------

#formulario professor
class FormularioProfessor(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.PROFESSOR

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Professor
        fields = ["nome", "sobrenome", "nome_usuario", "ativo"]


#-------------------------------------------------------------------------------------

#formulario responsavel
class FormularioResponsavel(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.RESPONSAVEL

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Responsavel
        fields = ["nome", "sobrenome", "nome_usuario", "ativo"]


#-------------------------------------------------------------------------------------

#formulario aluno
class FormularioAluno(FormularioPessoaBase):
    tipo_perfil = Usuario.TipoPerfil.ALUNO

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Aluno
        fields = ["nome", "sobrenome", "nome_usuario", "data_nascimento", "ativo"]
        widgets = {"data_nascimento": forms.DateInput(attrs={"type": "date"})}


#-------------------------------------------------------------------------------------

#formulario vinculo
class FormularioVinculo(FormularioBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Vinculo
        fields = ["aluno", "professor", "responsavel", "data_vinculo", "ativo"]
        widgets = {"data_vinculo": forms.DateInput(attrs={"type": "date"})}


#-------------------------------------------------------------------------------------

#formulario meta
class FormularioMeta(FormularioBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Meta
        fields = ["aluno", "professor", "titulo", "descricao",
                  "data_inicio", "data_prazo", "situacao"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_prazo": forms.DateInput(attrs={"type": "date"}),
        }


#-------------------------------------------------------------------------------------

#formulario atividade
class FormularioAtividade(FormularioBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Atividade
        fields = ["aluno", "professor", "meta", "titulo", "descricao", "data_entrega", "situacao"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_entrega": forms.DateInput(attrs={"type": "date"}),
        }


#-------------------------------------------------------------------------------------

#formulario conteudo
class FormularioConteudo(FormularioBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Conteudo
        fields = ["aluno", "professor", "atividade", "titulo", "descricao", "tipo_conteudo"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4})}


#-------------------------------------------------------------------------------------

#formulario frequencia
class FormularioFrequencia(FormularioBase):

    #-------------------------------------------------------------------------------------

    #metadados do modelo
    class Meta:
        model = Frequencia
        fields = ["aluno", "professor", "data_acompanhamento", "compareceu", "observacao"]
        widgets = {"data_acompanhamento": forms.DateInput(attrs={"type": "date"})}
#-------------------------------------------------------------------------------------
