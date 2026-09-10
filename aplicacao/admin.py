from django.contrib import admin

from .models import Aluno, Atividade, Conteudo, Frequencia, Meta, Professor, Responsavel, Vinculo


admin.site.register(Professor)
admin.site.register(Responsavel)
admin.site.register(Aluno)
admin.site.register(Vinculo)
admin.site.register(Meta)
admin.site.register(Atividade)
admin.site.register(Conteudo)
admin.site.register(Frequencia)
