"""Pipelines-types (les « grandes orientations » d'Alex) + paramètres du harnais.

Un pipeline est une simple liste de noms d'étapes (voir briques.BRIQUES). C'est la donnée que
Beecham choisit/adapte par mission. Externalisé ici, hors du code du moteur : ajouter un
pipeline ou changer la concurrence ne touche plus la mécanique.

Ordre des étapes du 'standard' = comportement historique du harnais (code -> test -> revue ->
fusion), la revue gérant un tour de reprise sur « corriger » via un saut interne.
"""

PIPELINES = {
    # correction / feature simple : le chemin par défaut.
    "standard": ["code", "test", "revue", "fusion"],
}

PIPELINE_DEFAUT = "standard"

# Paramètres d'orchestration (étaient en dur dans la boucle du scratchpad).
CONCURRENCE = 4  # sessions claude simultanées max (protéger la machine)
MAX_VAGUES = 25  # backstop anti-emballement (arrêt réel = backlog sec ou STOP)

# --- D-15 Phase 1 : bornes dures sur les paramètres d'orchestration -----------------------------
# Ce fichier est un fichier ORDINAIRE de la zone d'écriture développeur : une mission peut le
# modifier, un contrôleur LLM peut fusionner la modification, et le changement prend effet au
# prochain lancement de boucle — silencieusement. C'était le second trou de sécurité du dossier
# D-15 (proposition du chercheur).
#
# On ne peut pas empêcher l'écriture du fichier (ce serait geler tout le harnais). Ce qu'on peut
# faire, c'est refuser d'OBÉIR à une valeur aberrante : les lecteurs passent par les accesseurs
# ci-dessous, qui bornent. Une valeur hors bornes retombe sur le défaut sûr — la machine ne se
# fait pas noyer par un CONCURRENCE=500 arrivé par un diff mal relu.
BORNES = {"concurrence": (1, 8), "max_vagues": (1, 100)}
_DEFAUTS_SURS = {"concurrence": 4, "max_vagues": 25}


def _borner(nom: str, valeur) -> int:
    mini, maxi = BORNES[nom]
    if not isinstance(valeur, int) or isinstance(valeur, bool) or not (mini <= valeur <= maxi):
        return _DEFAUTS_SURS[nom]
    return valeur


def concurrence() -> int:
    """Sessions simultanées max, bornée. Passer par ici, jamais lire CONCURRENCE directement."""
    return _borner("concurrence", CONCURRENCE)


def max_vagues() -> int:
    """Backstop anti-emballement, borné. Passer par ici, jamais lire MAX_VAGUES directement."""
    return _borner("max_vagues", MAX_VAGUES)


def filtrer_vague(missions: list[dict], concurrence: int) -> tuple[list[dict], list[dict]]:
    """RÈGLE DES 3 CRITÈRES : une mission n'est parallélisable que si (1) ses fichiers sont
    disjoints de ceux déjà pris, (2) elle ne déclare aucune dépendance, (3) elle ne touche pas
    d'état partagé. UN SEUL critère qui manque -> elle s'exécute SEULE.

    Le harnais ne vérifiait auparavant que le critère 1, et c'est insuffisant : le contre-exemple
    classique est « une mission crée le schéma de base, une autre écrit la page qui le consomme »
    — leurs FICHIERS sont disjoints, le file-lock les laisse donc passer ensemble, et la seconde
    est cassée parce que la première n'est pas encore fusionnée.

    Anti-famine : une mission séquentielle reportée garde sa place dans l'ordre et passera en tête
    de la vague suivante. Renvoie (retenues, reportées).
    """

    def fichiers_disjoints(a: dict, b: dict) -> bool:
        fa, fb = a.get("fichiers"), b.get("fichiers")
        if fa is None or fb is None:  # périmètre non déclaré = touche potentiellement tout
            return False
        if "*" in fa or "*" in fb:
            return False
        return set(fa).isdisjoint(fb)

    retenues, reportees, vague_close = [], [], False
    for mission in missions:
        if vague_close:
            reportees.append(mission)
            continue

        if mission.get("depend_de") or mission.get("etat_partage"):
            if not retenues:
                retenues.append(mission)  # elle passe, mais SEULE
                vague_close = True
            else:
                reportees.append(mission)
        elif len(retenues) >= concurrence:
            reportees.append(mission)
        elif all(fichiers_disjoints(mission, r) for r in retenues):
            retenues.append(mission)
        else:
            reportees.append(mission)

    return retenues, reportees


def pipeline(nom: str | None = None) -> list[str]:
    """Renvoie la liste d'étapes du pipeline demandé (ou le défaut). Un nom inconnu retombe sur
    le défaut plutôt que d'exploser — Beecham peut nommer un pipeline pas encore défini."""
    return list(PIPELINES.get(nom or PIPELINE_DEFAUT, PIPELINES[PIPELINE_DEFAUT]))
