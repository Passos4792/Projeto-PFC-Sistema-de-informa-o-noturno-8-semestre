from django.contrib import admin
from django.db import transaction
from aplicacao.servicos.auditoria import registrar
from aplicacao.models import (Aluno, Atividade, Conteudo, DocumentoPedagogico, MetaAluno, Professor,
                     RelatorioPedagogico, Responsavel, Usuario, Vinculo, VinculoFamiliar, VinculoProfissional)


admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser


class CadastroAuditado(admin.ModelAdmin):
    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        registrar('EDICAO' if change else 'CRIACAO', request=request, objeto=obj,
                  detalhes='Campos: ' + ', '.join(form.changed_data))
        if isinstance(obj, Usuario) and (not change or {'tipo_perfil', 'gestor'} & set(form.changed_data)):
            registrar('PERMISSAO', request=request, objeto=obj,
                      detalhes=f'Perfil: {obj.get_tipo_perfil_display()}; gestor: {obj.gestor}.')

    @transaction.atomic
    def delete_model(self, request, obj):
        registrar('EXCLUSAO', request=request, objeto=obj)
        self._excluir(obj)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        for objeto in queryset:
            registrar('EXCLUSAO', request=request, objeto=objeto)
            self._excluir(objeto)

    @staticmethod
    def _excluir(objeto):
        if isinstance(objeto, Usuario):
            login = objeto.conta
            objeto.delete()
            if login is not None:
                login.delete()
        else:
            objeto.delete()


for modelo in [Professor, Usuario, Responsavel, Vinculo, MetaAluno, Atividade, Conteudo, VinculoFamiliar, VinculoProfissional, RelatorioPedagogico, DocumentoPedagogico]:
    admin.site.register(modelo, CadastroAuditado)


@admin.register(Aluno)
class CadastroAluno(CadastroAuditado):
    pass


from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin


class ContaAuditada(UserAdmin):
    def save_model(self, request, obj, form, change):
        obj.username = (obj.username or '').strip().lower()
        super().save_model(request, obj, form, change)

    def log_addition(self, request, obj, message):
        registrar('CRIACAO', request=request, entidade='conta de login', objeto_id=obj.pk,
                  detalhes=f'Conta {obj.get_username()} criada pelo admin.')
        return super().log_addition(request, obj, message)

    def log_change(self, request, obj, message):
        texto = str(message).lower()
        senha = 'senha' in texto or 'password' in texto
        registrar('SENHA' if senha else 'PERMISSAO', request=request, entidade='conta de login', objeto_id=obj.pk,
                  detalhes=(f'Conta {obj.get_username()} alterada pelo admin; superusuário: {obj.is_superuser}; '
                            f'equipe: {obj.is_staff}; ativa: {obj.is_active}.'))
        return super().log_change(request, obj, message)

    def log_deletions(self, request, queryset):
        for obj in queryset:
            registrar('EXCLUSAO', request=request, entidade='conta de login', objeto_id=obj.pk,
                      detalhes=f'Conta {obj.get_username()} excluída pelo admin.')
        return super().log_deletions(request, queryset)


_Conta = get_user_model()
if admin.site.is_registered(_Conta):
    admin.site.unregister(_Conta)
admin.site.register(_Conta, ContaAuditada)
