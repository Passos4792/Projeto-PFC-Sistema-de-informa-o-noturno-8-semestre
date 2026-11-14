VERSAO_TERMOS = "1.2"
VERSAO_PRIVACIDADE = "1.3"
DATA_VIGENCIA = "13/11/2026"


def documentos_aceitos(perfil):
    return bool(
        perfil.documentos_aceitos_em
        and perfil.versao_termos_aceita == VERSAO_TERMOS
        and perfil.versao_privacidade_ciente == VERSAO_PRIVACIDADE
    )
