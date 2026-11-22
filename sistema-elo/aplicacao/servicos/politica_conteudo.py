from django.conf import settings


POLITICA = '; '.join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "form-action 'self' https://accounts.google.com",
])


class PoliticaConteudo:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        caminho_admin = (getattr(settings, 'ELO_ADMIN_PATH', '') or '').strip('/')
        admin_ativo = bool(caminho_admin) and request.path.startswith('/' + caminho_admin + '/')
        if not admin_ativo:
            resposta.headers.setdefault('Content-Security-Policy', POLITICA)
        return resposta
