"""Onglet Relances : devis sans réponse + factures impayées (Dolibarr).

Wrapper fail-soft : ne lève jamais. Si Dolibarr est absent/injoignable,
`disponible=False` et listes vides — la page affiche un encart dégradé.
"""

import dolibarr as doli


def etat() -> dict:
    try:
        if not doli.is_configured():
            p = doli.ping()
            return {
                "disponible": False,
                "devis": [],
                "factures": [],
                "message": p.get("message", "Dolibarr non configuré"),
            }
        return {
            "disponible": True,
            "devis": doli.list_devis_a_relancer(),
            "factures": doli.list_factures_impayees(),
            "message": "ok",
        }
    except Exception as e:  # fail-soft absolu
        return {
            "disponible": False,
            "devis": [],
            "factures": [],
            "message": f"indisponible ({e.__class__.__name__})",
        }
