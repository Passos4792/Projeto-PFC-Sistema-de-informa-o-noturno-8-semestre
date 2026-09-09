from django.contrib import admin

from .models import Aluno, Professor, Responsavel, Vinculo


admin.site.register(Professor)
admin.site.register(Responsavel)
admin.site.register(Aluno)
admin.site.register(Vinculo)
