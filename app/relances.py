"""Onglet Relances : devis sans réponse + factures impayées (Dolibarr).

Wrapper fail-soft : ne lève jamais. Si Dolibarr est absent/injoignable,
`disponible=False` et listes vides — la page affiche un encart dégradé.
"""

import time

import dolibarr as doli

# Cache court : l'accueil (brief) et l'onglet Relances appellent ceci à CHAQUE chargement, et
# chaque appel fait 2 requêtes HTTP Dolibarr (~2,8 s si Dolibarr est lent/absent) — c'était TOUTE
# la latence de la page. Les relances ne changent pas à la seconde : un cache mémoire de 60 s rend
# l'accueil instantané (appel réel au plus une fois par minute). Fail-soft inchangé.
_CACHE: dict = {"t": 0.0, "v": None}
_TTL = 60.0


def etat() -> dict:
    now = time.monotonic()
    if _CACHE["v"] is not None and (now - _CACHE["t"]) < _TTL:
        return _CACHE["v"]
    v = _etat_frais()
    _CACHE["t"], _CACHE["v"] = now, v
    return v


def _etat_frais() -> dict:
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
