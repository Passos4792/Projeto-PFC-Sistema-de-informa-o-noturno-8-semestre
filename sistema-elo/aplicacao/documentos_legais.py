"""Versões vigentes dos documentos legais apresentados no ELO."""

#-------------------------------------------------------------------------------------

#versoes e data de vigencia dos documentos
VERSAO_TERMOS = "1.1"
VERSAO_PRIVACIDADE = "1.1"
DATA_VIGENCIA = "24/09/2026"


#-------------------------------------------------------------------------------------

#verificacao do aceite das versoes vigentes
def documentos_aceitos(perfil):
    """Confirma se o usuário registrou aceite das versões atualmente vigentes."""
    return bool(
        perfil.documentos_aceitos_em
        and perfil.versao_termos_aceita == VERSAO_TERMOS
        and perfil.versao_privacidade_ciente == VERSAO_PRIVACIDADE
    )
