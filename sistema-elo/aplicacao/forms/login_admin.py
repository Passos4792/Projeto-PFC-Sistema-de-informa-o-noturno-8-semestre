"""Mensagem de bloqueio no login administrativo com o limite do ELO."""
from math import ceil
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm


class LoginAdministrativoElo(AdminAuthenticationForm):
    def get_invalid_login_error(self):
        espera = getattr(self.request, 'login_espera', 0)
        if espera:
            return forms.ValidationError(
                'Muitas tentativas de acesso. Tente novamente em %(minutos)s minuto(s).',
                code='login_bloqueado', params={'minutos': ceil(espera / 60)},
            )
        return super().get_invalid_login_error()
