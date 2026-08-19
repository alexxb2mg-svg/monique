"""Prix par million de tokens (USD), transcrit depuis atelier/connaissances/catalogue_prix_modeles.md
(lecture seule, source de vérité, édition 2026-08-19). Ne couvre QUE les modèles à tarif simple
(une seule valeur entree/sortie, sans palier de contexte ni condition horaire) : xAI/Grok est
EXCLU (tous ses modèles ont un palier ≥200k tokens dans la source) ; DeepSeek est EXCLU (tarif
dépendant des heures pleines/creuses). Jamais inventer un prix (règle absolue du dépôt) : un
modèle absent d'ici renvoie None, pas une estimation."""

CATALOGUE_PRIX_USD = {
    "anthropic": {
        "claude-sonnet-5": {"entree": 2.0, "sortie": 10.0},
        "claude-haiku-4.5": {"entree": 1.0, "sortie": 5.0},
        "claude-opus-5": {"entree": 5.0, "sortie": 25.0},
    },
    "openai": {
        "gpt-5": {"entree": 1.25, "sortie": 10.0},
        "gpt-4o": {"entree": 2.5, "sortie": 10.0},
    },
    "google": {
        "gemini-2.5-flash": {"entree": 0.30, "sortie": 2.50},
        "gemini-2.5-flash-lite": {"entree": 0.10, "sortie": 0.40},
    },
    "mistral": {
        "mistral-large-3": {"entree": 0.50, "sortie": 1.50},
        "mistral-small-4": {"entree": 0.15, "sortie": 0.60},
    },
}


def prix(fournisseur: str, modele: str) -> dict | None:
    """Renvoie {'entree': ..., 'sortie': ...} en USD/MTok, ou None si fournisseur/modèle
    absent du catalogue (jamais inventer un prix — règle absolue du dépôt)."""
    return CATALOGUE_PRIX_USD.get(fournisseur, {}).get(modele)


def estimer_cout_usd(fournisseur: str, modele: str, input_tokens: int, output_tokens: int) -> float | None:
    p = prix(fournisseur, modele)
    if p is None:
        return None
    return input_tokens / 1_000_000 * p["entree"] + output_tokens / 1_000_000 * p["sortie"]
