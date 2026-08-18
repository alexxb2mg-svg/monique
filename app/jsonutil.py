"""Extraction tolérante de JSON d'une réponse LLM (le modèle peut entourer le JSON de texte)."""

import json


def extraire(texte: str):
    if not texte:
        return None
    # revue M1 : profondeur d'accolades avec suivi des chaînes — prend le PREMIER objet {...}
    # ÉQUILIBRÉ. Robuste à un « { » qui apparaît dans du texte cité avant le vrai JSON, et aux
    # accolades à l'intérieur d'une valeur chaîne (elles ne faussent pas la profondeur).
    depth = 0
    debut = -1
    in_str = False
    esc = False
    for i, ch in enumerate(texte):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                debut = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and debut != -1:
                    try:
                        return json.loads(texte[debut : i + 1])
                    except Exception:
                        debut = (
                            -1
                        )  # objet invalide => chercher l'objet équilibré suivant
    return None
