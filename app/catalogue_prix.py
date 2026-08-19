"""Prix par million de tokens (USD), transcrit depuis atelier/connaissances/catalogue_prix_modeles.md
(lecture seule, source de vérité, édition 2026-08-19). Couvre les modèles à tarif simple (une
seule valeur entree/sortie) ET les modèles xAI/Grok, dont le tarif dépend d'un unique critère
déterministe déjà disponible dans la signature de estimer_cout_usd() : le volume d'input_tokens
(structure 'paliers', cf. prix()/_tarif_effectif() ci-dessous). DeepSeek reste EXCLU : son tarif
dépend d'une heure UTC et d'un ratio cache hit/miss, deux critères non déterminables ici (hors
scope, question de modélisation ouverte). Jamais inventer un prix (règle absolue du dépôt) : un
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
    "xai": {
        # Palier appliqué à l'INTÉGRALITÉ de la requête (entrée ET sortie) dès que
        # input_tokens atteint le seuil — pas seulement au dépassement.
        "grok-4.6": {"paliers": [
            {"jusqu_a": 200_000, "entree": 2.0, "sortie": 6.0},
            {"jusqu_a": None, "entree": 4.0, "sortie": 12.0},
        ]},
        "grok-4.5": {"paliers": [
            {"jusqu_a": 200_000, "entree": 2.0, "sortie": 6.0},
            {"jusqu_a": None, "entree": 4.0, "sortie": 12.0},
        ]},
        "grok-4.3": {"paliers": [
            {"jusqu_a": 200_000, "entree": 1.25, "sortie": 2.50},
            {"jusqu_a": None, "entree": 2.50, "sortie": 5.00},
        ]},
        "grok-4.20-0309-reasoning": {"paliers": [
            {"jusqu_a": 200_000, "entree": 1.25, "sortie": 2.50},
            {"jusqu_a": None, "entree": 2.50, "sortie": 5.00},
        ]},
        "grok-4.20-0309-non-reasoning": {"paliers": [
            {"jusqu_a": 200_000, "entree": 1.25, "sortie": 2.50},
            {"jusqu_a": None, "entree": 2.50, "sortie": 5.00},
        ]},
        "grok-4.20-multi-agent-0309": {"paliers": [
            {"jusqu_a": 200_000, "entree": 1.25, "sortie": 2.50},
            {"jusqu_a": None, "entree": 2.50, "sortie": 5.00},
        ]},
        "grok-build-0.1": {"paliers": [
            {"jusqu_a": 200_000, "entree": 1.0, "sortie": 2.0},
            {"jusqu_a": None, "entree": 2.0, "sortie": 4.0},
        ]},
    },
}


def prix(fournisseur: str, modele: str) -> dict | None:
    """Renvoie le tarif brut du catalogue pour ce modèle, ou None si fournisseur/modèle absent
    (jamais inventer un prix — règle absolue du dépôt). Deux formats possibles : le format
    simple {'entree': ..., 'sortie': ...} en USD/MTok, ou {'paliers': [...]} pour les modèles
    dont le tarif dépend du volume d'entrée (cf. _tarif_effectif())."""
    return CATALOGUE_PRIX_USD.get(fournisseur, {}).get(modele)


def _tarif_effectif(p: dict, input_tokens: int) -> dict:
    """Résout un tarif brut (format simple ou à paliers) en {'entree': ..., 'sortie': ...}
    applicable pour ce volume d'input_tokens. Le format simple est renvoyé tel quel — aucun
    changement de comportement pour les fournisseurs qui n'ont pas de paliers."""
    if "paliers" not in p:
        return p
    for palier in p["paliers"]:
        if palier["jusqu_a"] is None or input_tokens < palier["jusqu_a"]:
            return {"entree": palier["entree"], "sortie": palier["sortie"]}
    # Inatteignable tant que le dernier palier a jusqu_a=None (garde-fou de cohérence).
    dernier = p["paliers"][-1]
    return {"entree": dernier["entree"], "sortie": dernier["sortie"]}


def estimer_cout_usd(fournisseur: str, modele: str, input_tokens: int, output_tokens: int) -> float | None:
    p = prix(fournisseur, modele)
    if p is None:
        return None
    tarif = _tarif_effectif(p, input_tokens)
    return input_tokens / 1_000_000 * tarif["entree"] + output_tokens / 1_000_000 * tarif["sortie"]


def comparer_fournisseurs(input_tokens: int, output_tokens: int) -> list[dict]:
    """Pour un volume de tokens donné, le coût de CHAQUE modèle de CHAQUE fournisseur du
    catalogue, trié du moins cher au plus cher. Réutilise estimer_cout_usd() — ne duplique
    pas la formule de coût."""
    resultats = []
    for fournisseur, modeles in CATALOGUE_PRIX_USD.items():
        for modele in modeles:
            cout = estimer_cout_usd(fournisseur, modele, input_tokens, output_tokens)
            assert cout is not None  # fournisseur/modele viennent du catalogue, toujours connus
            resultats.append({"fournisseur": fournisseur, "modele": modele, "cout_usd": cout})
    resultats.sort(key=lambda r: r["cout_usd"])
    return resultats
