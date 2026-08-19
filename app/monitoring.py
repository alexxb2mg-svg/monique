"""Onglet Monitoring (read-only) : état du moteur de collecte + chantier de la brigade Beecham."""

import re

import decouverte
from store import STORE, connexion_ro


def etat_moteur(chemin: str | None = None) -> dict:
    """État du moteur de collecte du secrétariat. FAIL-SOFT : si le store n'existe pas encore
    (collecte jamais lancée) ou si une table manque, on renvoie un état « inactif » propre au lieu
    de planter la page (le monitoring rendait un HTTP 500 quand ~/.monique/store.db était absent)."""
    etat_vide = {
        "collecte_active": False,
        "dernier_passage": None,
        "entrees_jour": 0,
        "a_traiter": 0,
        "tables_manquantes": [],
    }
    try:
        con = connexion_ro(chemin or STORE)
    except Exception:
        return etat_vide
    try:
        dernier = con.execute(
            "SELECT value FROM sys_constants WHERE key='collector_last_run'"
        ).fetchone()
        a_traiter = con.execute(
            "SELECT COUNT(*) FROM sys_incoming_events WHERE processed_at IS NULL"
        ).fetchone()[0]
        jour = con.execute(
            "SELECT COUNT(*) FROM sys_incoming_events WHERE date(timestamp)=date('now')"
        ).fetchone()[0]
        # Observabilité en plus, pas à la place : la robustesse (ne pas planter) est déjà acquise
        # par le fail-soft ci-dessus (cf. diagnostic_decouverte_orphelin.md §4). Un échec du
        # diagnostic lui-même ne doit pas dégrader l'état du moteur déjà lu avec succès.
        try:
            tables_manquantes = decouverte.diagnostic(chemin or STORE)["manques"]
        except Exception:
            tables_manquantes = []
        return {
            "collecte_active": dernier is not None,
            "dernier_passage": dernier[0] if dernier else None,
            "entrees_jour": jour,
            "a_traiter": a_traiter,
            "tables_manquantes": tables_manquantes,
        }
    except Exception:
        return etat_vide
    finally:
        con.close()


# --- Chantier de la brigade Beecham ------------------------------------------------------------

# Statuts « ouverts » (travail non terminé) vs « fusionnés » (livrés dans le code).
_EN_COURS = {"en_cours"}
_FUSION = {"valide"}
_RATE = {"rejete", "echec", "bloque"}


def _sujet(consigne: str) -> str:
    """Extrait un libellé LISIBLE d'une consigne de mission (souvent préfixée « Fichiers touches :
    … — »). On coupe le préfixe technique et on garde l'intention, tronquée court."""
    c = (consigne or "").strip()
    if c.startswith("Tu es Beecham"):
        return "Beecham — état des lieux et décision"
    if c.startswith("Tu es le chercheur") or c.startswith("Tu es l'auditeur") or c.startswith(
        "Tu es le stratège"
    ):
        return c.split(".")[0][:80]
    # « Fichiers touches : a.py, b.py — <intention> » -> on garde <intention> si présente
    m = re.match(r"^\s*Fichiers?\s+touch[ée]s?\s*:.*?[—-]\s*(.+)$", c, re.IGNORECASE | re.DOTALL)
    if m and m.group(1).strip():
        c = m.group(1).strip()
    # le boilerplate « verifie disjoint des N autres missions … (…). » précède le VRAI sujet :
    # on le saute pour ne garder que l'intention métier qui suit la parenthèse.
    m2 = re.match(r"^v[ée]rifie\s+disjoint.*?\)\.\s*(.+)$", c, re.IGNORECASE | re.DOTALL)
    if m2 and m2.group(1).strip():
        c = m2.group(1).strip()
    return " ".join(c.split())[:90]


def chantier_brigade(limit: int = 60) -> dict:
    """Ce que la brigade construit, lu depuis secw_beecham_missions : sujets EN COURS, derniers
    sujets FUSIONNÉS, et compteurs. Import paresseux de beecham pour éviter tout cycle au boot."""
    vide = {"disponible": False, "en_cours": [], "fusionnes": [], "compte": {}}
    try:
        import beecham
    except Exception:
        return vide
    try:
        missions = beecham.lister_missions(limit=limit)
    except Exception:
        return vide

    def vue(m):
        return {
            "sujet": _sujet(m.get("consigne", "")),
            "statut": m.get("statut", "?"),
            "heure": (m.get("maj_le") or m.get("cree_le") or "")[11:16],
        }

    # on masque les missions de pilotage (planif Beecham) du panneau « en cours » : ce qui parle à
    # Alex, ce sont les SUJETS (dev/recherche), pas la mécanique de planification.
    en_cours = [
        vue(m)
        for m in missions
        if m.get("statut") in _EN_COURS and not (m.get("consigne", "").startswith("Tu es Beecham"))
    ]
    fusionnes = [vue(m) for m in missions if m.get("statut") in _FUSION][:8]
    compte = {
        "en_cours": sum(1 for m in missions if m.get("statut") in _EN_COURS),
        "fusionnes": sum(1 for m in missions if m.get("statut") in _FUSION),
        "rates": sum(1 for m in missions if m.get("statut") in _RATE),
    }
    return {
        "disponible": True,
        "en_cours": en_cours[:8],
        "fusionnes": fusionnes,
        "compte": compte,
    }
