"""Contrats de données de Monique (D-15 Phase 0/1) : validation pure Python, ZÉRO appel LLM,
déterministe — pré/post-conditions qui codent en dur les règles déjà actées ("jamais auto-envoyer
sans validation") plutôt que de compter sur la discipline d'un prompt. Voir
atelier/connaissances/proposition_d15_consolidee.md, addendum 5.

Construit via le pipeline pont (Gemini implémente, DeepSeek relit les tests) le 21/08/2026,
promu depuis atelier/sandbox_contrat_donnees/."""

TYPES_ENVOI_EXTERNE = {"email", "sms", "whatsapp", "telegram", "envoi_externe"}


def valider(action: dict) -> tuple[bool, str]:
    """Valide qu'une action respecte les contrats de sécurité de Monique.

    Pour les actions d'envoi externe (email, sms, whatsapp, telegram, envoi_externe),
    au moins un verrou de sécurité doit être actif : `is_draft=True` ou
    `requires_human_validation=True`.

    Args:
        action: Dictionnaire décrivant l'action à exécuter.

    Returns:
        tuple[bool, str]: Un tuple (succès, raison). Succès est True si l'action
        est autorisée, sinon False accompagné d'un message explicatif.
    """
    if not isinstance(action, dict):
        return False, "L'action doit être un dictionnaire."

    type_action = action.get("type")

    if type_action not in TYPES_ENVOI_EXTERNE:
        return True, ""

    is_draft = action.get("is_draft")
    requires_human_validation = action.get("requires_human_validation")

    valid_draft = is_draft is True
    valid_human = requires_human_validation is True

    if not (valid_draft or valid_human):
        return (
            False,
            "Action d'envoi externe refusée : 'is_draft' ou 'requires_human_validation' doit être un booléen True.",
        )

    return True, ""
