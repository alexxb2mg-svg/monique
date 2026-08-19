# Prix par million de tokens (USD), source : atelier/connaissances/catalogue_prix_modeles.md,
# ligne Claude Sonnet 5, consulté 2026-08-19.
# "sonnet" == model="sonnet" du profil REGISTRE["claude"] (app/fournisseurs.py) — jamais
# d'autre clé : les profils openai_compat n'ont pas de model renseigné aujourd'hui, inventer
# un prix pour un modèle non branché serait un prix fantôme (règle absolue : jamais inventer
# un prix).
PRIX_PAR_MTOK_USD = {
    "sonnet": {"entree": 2.0, "sortie": 10.0},
}


def estimer_cout_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    prix = PRIX_PAR_MTOK_USD.get(model)
    if prix is None:
        return None
    return input_tokens / 1_000_000 * prix["entree"] + output_tokens / 1_000_000 * prix["sortie"]
