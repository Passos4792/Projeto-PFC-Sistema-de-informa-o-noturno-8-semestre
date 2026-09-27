#importacoes
from django.contrib import admin
from django.urls import include, path

#-------------------------------------------------------------------------------------

#rotas
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('aplicacao.urls')),
]
#-------------------------------------------------------------------------------------
