"""Bench de latence des vues principales de Monique.

Chronomètre un aller-retour GET par route via un TestClient FastAPI et rend un
tableau trié du plus lent au plus rapide — sert à repérer une régression avant
qu'une vue ne redevienne un blocage (cf. cache 60s de relances.etat(), qui a
justement corrigé /vue/relances : commit fb321cb).
"""

import time

ROUTES_A_MESURER = [
    "/",
    "/vue/jour",
    "/vue/boite",
    "/vue/faire",
    "/vue/relances",
    "/vue/monitoring",
    "/vue/reglages",
    "/vue/planif",
    "/vue/fournisseurs",
    "/vue/agents",
    "/vue/beecham",
    "/vue/usage",
    "/vue/recherche",
]


def mesurer_routes(client, routes=None) -> list[dict]:
    """Chronomètre un GET par route (routes ou ROUTES_A_MESURER), dans l'ordre."""
    out = []
    for route in routes or ROUTES_A_MESURER:
        debut = time.perf_counter()
        r = client.get(route)
        duree = time.perf_counter() - debut
        out.append({"route": route, "statut": r.status_code, "secondes": round(duree, 4)})
    return out


def formater_tableau(mesures) -> str:
    """Rendu texte lisible, une ligne par route, la plus lente en premier."""
    lignes = [f"{'route':<20}{'statut':<8}{'temps'}"]
    for m in sorted(mesures, key=lambda m: m["secondes"], reverse=True):
        lignes.append(f"{m['route']:<20}{m['statut']:<8}{m['secondes'] * 1000:.1f} ms")
    return "\n".join(lignes)
