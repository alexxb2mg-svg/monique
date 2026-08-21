"""Contrats de données de Monique (D-15 Phase 0/1) : validation pure Python, ZÉRO appel LLM,
déterministe — pré/post-conditions qui codent en dur les règles déjà actées ("jamais auto-envoyer
sans validation") plutôt que de compter sur la discipline d'un prompt. Voir
atelier/connaissances/proposition_d15_consolidee.md, addendum 5.

Construit via le pipeline pont (Gemini implémente, DeepSeek relit les tests) le 21/08/2026,
promu depuis atelier/sandbox_contrat_donnees/."""

import re
import unicodedata

TYPES_ENVOI_EXTERNE = {"email", "sms", "whatsapp", "telegram", "envoi_externe"}

# Caractères invisibles servant à cacher du texte dans un message (le nom est cité dans la raison
# de refus, jamais le caractère lui-même — il est invisible, ça ne servirait à rien).
# Écrits en échappements \uXXXX volontairement : littéraux, ces caractères seraient invisibles
# dans le code source lui-même — donc illisibles et inéditables pour un relecteur humain.
INVISIBLES = {
    "\u200b": "zero-width space",
    "\u200c": "zero-width non-joiner",
    "\u200d": "zero-width joiner",
    "\ufeff": "zero-width no-break space / BOM",
    "\u200e": "left-to-right mark",
    "\u200f": "right-to-left mark",
    "\u202a": "left-to-right embedding",
    "\u202b": "right-to-left embedding",
    "\u202c": "pop directional formatting",
    "\u202d": "left-to-right override",
    "\u202e": "right-to-left override",
}

# Formulations canoniques d'injection de prompt (comparées sur texte normalisé : minuscules, sans
# accents, espaces réduits — un message peut arriver sans accents).
INJECTIONS = [
    "ignore les instructions precedentes",
    "ignore previous instructions",
    "ignore all previous",
    "oublie tout ce qui precede",
    "disregard previous",
    "forget your instructions",
    "nouvelles instructions systeme",
    "system prompt",
    "tu es maintenant",
    "you are now a",
    "override your instructions",
]

# Motif IBAN : 2 lettres pays + 2 chiffres + 11 à 30 caractères alphanumériques, espaces UNIQUES
# tolérés ENTRE les caractères (pas de suppression globale des espaces du texte -- ça fusionnerait
# les mots alentour et casserait la frontière \b sur le cas le plus courant : un IBAN entouré de
# prose normale avec espaces. Bug réel trouvé et corrigé le 22/08/2026, cf. test dédié).
_MOTIF_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b", re.IGNORECASE)


def valider(action: dict) -> tuple[bool, str]:
    """Valide qu'une action respecte les contrats de sécurité de Monique.

    Contrôles effectués, dans l'ordre (refuse au premier problème trouvé) :
    0. Interdiction d'IBAN en clair : si une clé `texte` (str) est présente et contient
       un motif IBAN (format international, espaces internes tolérés), refuse SANS EXCEPTION
       et sans jamais citer l'IBAN trouvé dans le message (pour ne pas le faire fuiter).
       S'applique quel que soit le type de l'action.
    1. Verrou d'envoi : pour les actions d'envoi externe (email, sms, whatsapp, telegram,
       envoi_externe), au moins un verrou de sécurité doit être actif : `is_draft=True` ou
       `requires_human_validation=True`.
    2. Cohérence financière : si les clés `total_ht`, `taux_tva` et `total_ttc` sont toutes
       présentes et numériques, vérifie que `total_ht + (total_ht * taux_tva)` est égal à
       `total_ttc` à 0.01 près.
    3. Vouvoiement strict : pour les envois externes, si une clé `texte` (str) est présente,
       refuse tout tutoiement isolé (tu, ton, ta, tes, toi, te, t').

    Args:
        action: Dictionnaire décrivant l'action à exécuter.

    Returns:
        tuple[bool, str]: Un tuple (succès, raison). Succès est True si l'action
        est autorisée, sinon False accompagné d'un message explicatif.
    """
    if not isinstance(action, dict):
        return False, "L'action doit être un dictionnaire."

    # 0. Interdiction d'IBAN en clair (quel que soit le type d'action)
    texte_brut = action.get("texte")
    if isinstance(texte_brut, str) and _MOTIF_IBAN.search(texte_brut):
        return False, "IBAN détecté dans le texte."

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

    # 3. Vouvoiement strict
    if type_action in TYPES_ENVOI_EXTERNE and isinstance(action.get("texte"), str):
        texte = action["texte"]
        # "t" isolé n'est jamais un vrai pronom en français (l'élision donne "t'", jamais un "t"
        # nu) -- l'exclure de l'alternance \b...\b évite un faux positif rare (taille "T",
        # initiale). Le cas "t'" reste couvert séparément.
        motif_tutoiement = re.compile(r"\b(tu|ton|ta|tes|toi|te)\b|\bt'", re.IGNORECASE)
        match = motif_tutoiement.search(texte)
        if match:
            mot_trouve = match.group(0).lower()
            return (
                False,
                f"Tutoiement détecté dans le texte : '{mot_trouve}'.",
            )

    return True, ""


# Rubriques imposées au rapport de fin de mission. Format repris d'Hermes Agent (leur contrat de
# sortie de sous-agent : "tasks performed, results found, files modified, issues encountered"),
# plutôt qu'inventé ici — c'est un format éprouvé en production ailleurs.
RUBRIQUES_RAPPORT = ("FAIT", "RESULTAT", "FICHIERS", "PROBLEMES")

# Parsing TOLÉRANT (leçon reference_ponts_format_parsable, apprise sur un bug réel) : le texte
# d'un LLM arrive avec des décorations imprévisibles — puces, gras markdown, accents, deux-points
# ou tiret. On absorbe les décorations AVANT et APRÈS le mot-clé (`**FAIT**`), mais jamais un saut
# de ligne : `[ \t]*` et non `\s*` après le séparateur, sinon une rubrique laissée vide aspirerait
# la ligne suivante et passerait pour remplie (bug réel, attrapé au test avant livraison).
_MOTIF_RUBRIQUE = "(?mi)^[^\\w\\n]*{}[^\\w\\n]*[:\\-][ \\t]*(.+)$"


def valider_rapport_mission(texte: str) -> tuple[bool, str]:
    """PORTE DE SORTIE : un rapport de fin de mission doit porter les 4 rubriques, non vides.

    Cette porte ne peut pas *forcer* un agent à produire le bon format — aucun code ne le peut.
    Ce qu'elle fait, c'est ne pas le laisser passer : l'appelant relance l'agent avec le motif
    exact. La consigne de format vit dans le prompt (on ne peut pas la deviner), mais la garantie
    vit ici, dans le code — pas dans l'espoir que le prompt ait été suivi.

    Renvoie (True, "") si conforme, (False, raison citant les rubriques manquantes) sinon.
    """
    if not isinstance(texte, str) or not texte.strip():
        return False, "Rapport vide."

    manquantes = []
    for rubrique in RUBRIQUES_RAPPORT:
        # accents optionnels : PROBLEMES doit matcher PROBLÈMES, RESULTAT doit matcher RÉSULTAT
        souple = rubrique.replace("E", "[EÉÈÊ]").replace("A", "[AÀÂ]")
        trouve = re.search(_MOTIF_RUBRIQUE.format(souple), texte)
        if not trouve or not trouve.group(1).strip():
            manquantes.append(rubrique)

    if manquantes:
        return False, "Rubrique(s) manquante(s) ou vide(s) : " + ", ".join(manquantes)
    return True, ""


def _normaliser_texte(texte: str) -> str:
    """Minuscules, sans accents, espaces réduits — pour comparer un message à des formulations
    canoniques quelle que soit sa graphie d'arrivée."""
    nfkd = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sans_accents.lower()).strip()


def scanner_message(texte: str) -> tuple[bool, str]:
    """Scanne le CONTENU d'un message inter-agents avant acceptation dans une boîte.

    Surface distincte de `valider()` : celle-ci contrôle une action que Monique s'apprête à
    exécuter, celle-là un message entrant qui sera injecté dans le contexte d'un autre agent —
    deux menaces différentes, deux points de contrôle.

    Refuse (1) tout caractère invisible servant à cacher du texte, (2) toute formulation
    canonique d'injection de prompt. Renvoie (True, "") si le message est propre.
    """
    if not isinstance(texte, str):
        return False, "Le texte doit être une chaîne de caractères."

    for caractere in texte:
        if caractere in INVISIBLES:
            return False, f"Caractère invisible détecté : {INVISIBLES[caractere]}"

    texte_normalise = _normaliser_texte(texte)
    for motif in INJECTIONS:
        if motif in texte_normalise:
            return False, f"Injection de prompt détectée : '{motif}'"

    return True, ""
