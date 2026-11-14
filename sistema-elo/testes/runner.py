from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import override_settings
from django.test.runner import DiscoverRunner


class ExecutorIsolado(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self.arquivos_temporarios = TemporaryDirectory(prefix='elo-testes-')
        self.configuracao_arquivos = override_settings(MEDIA_ROOT=self.arquivos_temporarios.name)
        self.configuracao_arquivos.enable()
        self.google_externo = patch(
            'aplicacao.servicos.google_calendar.urlopen',
            side_effect=AssertionError('O teste deve simular a resposta do Google, sem acessar a rede.'))
        self.google_externo.start()

    def teardown_test_environment(self, **kwargs):
        self.google_externo.stop()
        self.configuracao_arquivos.disable()
        self.arquivos_temporarios.cleanup()
        super().teardown_test_environment(**kwargs)
