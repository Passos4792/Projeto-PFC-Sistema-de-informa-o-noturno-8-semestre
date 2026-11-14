from django.contrib import admin
from django.urls import include, path
from aplicacao.views.seguranca import trocar_senha_admin


#rotas do projeto
urlpatterns = [
    path('admin/password_change/', trocar_senha_admin, name='admin-trocar-senha-nativo'),
    path('admin/', admin.site.urls),
    path('', include('aplicacao.urls')),
]
