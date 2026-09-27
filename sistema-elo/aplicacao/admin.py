#importacoes
from django.contrib import admin
from django.db import transaction
from .auditoria import registrar

from .models import Aluno, Atividade, Conteudo, Frequencia, Meta, Professor, Responsavel, Usuario, Vinculo


#-------------------------------------------------------------------------------------

#configuracoes iniciais
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser


#-------------------------------------------------------------------------------------

#cadastros com auditoria no painel administrativo
class CadastroAuditado(admin.ModelAdmin):

    #-------------------------------------------------------------------------------------

    #salvar no painel administrativo
    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        registrar('EDICAO' if change else 'CRIACAO', request=request, objeto=obj,
                  detalhes='Campos: ' + ', '.join(form.changed_data))
        if isinstance(obj, Usuario) and (not change or {'tipo_perfil', 'professor_principal'} & set(form.changed_data)):
            registrar('PERMISSAO', request=request, objeto=obj,
                      detalhes=f'Perfil: {obj.get_tipo_perfil_display()}; professor principal: {obj.professor_principal}.')

    #-------------------------------------------------------------------------------------

    #excluir no painel administrativo
    @transaction.atomic
    def delete_model(self, request, obj):
        registrar('EXCLUSAO', request=request, objeto=obj)
        super().delete_model(request, obj)

    #-------------------------------------------------------------------------------------

    #exclusao de varios registros
    @transaction.atomic
    def delete_queryset(self, request, queryset):
        for objeto in queryset:
            registrar('EXCLUSAO', request=request, objeto=objeto)
        super().delete_queryset(request, queryset)


#-------------------------------------------------------------------------------------

#registro dos modelos
for modelo in [Professor, Usuario, Responsavel, Aluno, Vinculo, Meta, Atividade, Conteudo, Frequencia]:
    admin.site.register(modelo, CadastroAuditado)
#-------------------------------------------------------------------------------------
