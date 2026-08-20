"""Journal des appels aux ponts (JSONL) — MESURE RÉELLE de l'économie de tokens, pour remplacer les
reconstructions approximatives a posteriori (cf. mémoire reference_ponts_format_parsable, éval du
20/08/2026 faite « à la louche »). Un appel = une ligne : horodatage, pont, rôle, succès, caractères
prompt/réponse, tokens estimés (car/4, grossier mais STABLE et reproductible — pas une vraie valeur
API, juste une unité de mesure cohérente d'un appel à l'autre).

Branché automatiquement dans ponts.lancer() : chaque appel réel à DeepSeek/Gemini s'enregistre seul,
fail-soft (la mesure ne doit jamais faire planter un appel de pont)."""

import json
import os
import time

_ATELIER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "atelier"
)
CHEMIN_JOURNAL = os.path.join(_ATELIER, "journal_ponts.jsonl")

CAR_PAR_TOKEN = 4  # approximation grossière mais stable (mélange français/code)


def enregistrer_appel(pont, role, ok, car_prompt, car_reponse, chemin=None) -> None:
    """Ajoute une ligne JSONL. Fail-soft : la mesure est secondaire au fonctionnement du pont —
    une erreur d'écriture ici ne doit JAMAIS remonter à l'appelant."""
    chemin = chemin or CHEMIN_JOURNAL
    entree = {
        "horodatage": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pont": pont,
        "role": role,
        "ok": bool(ok),
        "car_prompt": car_prompt,
        "car_reponse": car_reponse,
        "tokens_entree_estimes": round(car_prompt / CAR_PAR_TOKEN),
        "tokens_sortie_estimes": round(car_reponse / CAR_PAR_TOKEN),
    }
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    except OSError:
        pass


def resume(chemin=None) -> dict:
    """{par_pont: {nom: {appels, ok, ko, tokens_entree, tokens_sortie}}, total_tokens_entree,
    total_tokens_sortie}. Fail-soft : fichier absent ou ligne corrompue -> ignorée, jamais d'exception."""
    chemin = chemin or CHEMIN_JOURNAL
    stats: dict = {}
    try:
        with open(chemin, encoding="utf-8") as f:
            lignes = f.readlines()
    except OSError:
        lignes = []
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            e = json.loads(ligne)
        except (TypeError, ValueError):
            continue
        p = e.get("pont", "?")
        s = stats.setdefault(
            p, {"appels": 0, "ok": 0, "ko": 0, "tokens_entree": 0, "tokens_sortie": 0}
        )
        s["appels"] += 1
        s["ok" if e.get("ok") else "ko"] += 1
        s["tokens_entree"] += e.get("tokens_entree_estimes", 0)
        s["tokens_sortie"] += e.get("tokens_sortie_estimes", 0)
    return {
        "par_pont": stats,
        "total_tokens_entree": sum(s["tokens_entree"] for s in stats.values()),
        "total_tokens_sortie": sum(s["tokens_sortie"] for s in stats.values()),
    }
