"""Contrats de données de Monique (D-15 Phase 0/1) : validation pure Python, ZÉRO appel LLM,
déterministe — pré/post-conditions qui codent en dur les règles déjà actées ("jamais auto-envoyer
sans validation") plutôt que de compter sur la discipline d'un prompt. Voir
atelier/connaissances/proposition_d15_consolidee.md, addendum 5.

Construit via le pipeline pont (Gemini implémente, DeepSeek relit les tests) le 21/08/2026,
promu depuis atelier/sandbox_contrat_donnees/."""

TYPES_ENVOI_EXTERNE = {"email", "sms", "whatsapp", "telegram", "envoi_externe"}


def valider(action: dict) -> tuple[bool, str]:
    """Valide qu'une action respecte les contrats de sécurité de Monique.

    Contrôles effectués :
    1. Verrou d'envoi : pour les actions d'envoi externe (email, sms, whatsapp, telegram,
       envoi_externe), au moins un verrou de sécurité doit être actif : `is_draft=True` ou
       `requires_human_validation=True`.
    2. Cohérence financière : si les clés `total_ht`, `taux_tva` et `total_ttc` sont toutes
       présentes et numériques, vérifie que `total_ht + (total_ht * taux_tva)` est égal à
       `total_ttc` à 0.01 près.

    Args:
        action: Dictionnaire décrivant l'action à exécuter.

    Returns:
        tuple[bool, str]: Un tuple (succès, raison). Succès est True si l'action
        est autorisée, sinon False accompagné d'un message explicatif.
    """
    if not isinstance(action, dict):
        return False, "L'action doit être un dictionnaire."

    # 1. Verrou d'envoi
    type_action = action.get("type")
    if type_action in TYPES_ENVOI_EXTERNE:
        is_draft = action.get("is_draft")
        requires_human_validation = action.get("requires_human_validation")

        valid_draft = is_draft is True
        valid_human = requires_human_validation is True

        if not (valid_draft or valid_human):
            return (
                False,
                "Action d'envoi externe refusée : 'is_draft' ou 'requires_human_validation' doit être un booléen True.",
            )

    # 2. Cohérence financière
    total_ht = action.get("total_ht")
    taux_tva = action.get("taux_tva")
    total_ttc = action.get("total_ttc")

    # Vérifie que les trois clés sont présentes et numériques (int/float, pas bool)
    numerique_ok = (
        isinstance(total_ht, (int, float)) and not isinstance(total_ht, bool)
        and isinstance(taux_tva, (int, float)) and not isinstance(taux_tva, bool)
        and isinstance(total_ttc, (int, float)) and not isinstance(total_ttc, bool)
    )

    if numerique_ok:
        total_calcule = total_ht + (total_ht * taux_tva)
        ecart = abs(total_calcule - total_ttc)
        if ecart > 0.01:
            return (
                False,
                f"Incohérence financière : écart de {ecart:.4f} entre total_ht + total_ht * taux_tva et total_ttc.",
            )

    return True, ""
