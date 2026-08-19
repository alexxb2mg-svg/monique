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


def pipeline(nom: str | None = None) -> list[str]:
    """Renvoie la liste d'étapes du pipeline demandé (ou le défaut). Un nom inconnu retombe sur
    le défaut plutôt que d'exploser — Beecham peut nommer un pipeline pas encore défini."""
    return list(PIPELINES.get(nom or PIPELINE_DEFAUT, PIPELINES[PIPELINE_DEFAUT]))
