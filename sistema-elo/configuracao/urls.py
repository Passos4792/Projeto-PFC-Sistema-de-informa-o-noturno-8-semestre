from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from aplicacao.forms.login_admin import LoginAdministrativoElo
from aplicacao.views.seguranca import trocar_senha_admin


# O login administrativo usa o mesmo backend/contador do login comum.
admin.site.login_form = LoginAdministrativoElo

urlpatterns = [path('', include('aplicacao.urls'))]

# Em producao nao existe /admin/ aberto: sem ELO_ADMIN_PATH, Admin fica ausente.
# Quando habilitado, a rota de alteracao de senha preserva o 2FA obrigatorio.
if settings.ELO_ADMIN_PATH:
    prefixo = settings.ELO_ADMIN_PATH + '/'
    urlpatterns = [
        path(prefixo + 'password_change/', trocar_senha_admin,
             name='admin-trocar-senha-nativo'),
        path(prefixo, admin.site.urls),
    ] + urlpatterns
