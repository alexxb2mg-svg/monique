"""Boucle d'auto-correction GRATUITE, pilotée par Python, sur 2 ponts LLM web (DeepSeek + Gemini) :
aucune intervention manuelle entre les étapes. DeepSeek DIAGNOSTIQUE (planifie, puis analyse les
échecs), Gemini IMPLÉMENTE (produit le FICHIER COMPLET, jamais un diff — plus simple et robuste à
extraire/écrire). Python EXTRAIT le code natif du dernier message et l'ÉCRIT directement au chemin
cible, lance les tests, et boucle sur l'échec jusqu'à succès ou plafond d'essais.

C'est le pendant gratuit et lent de harnais/briques.py (code→test→revue→corriger) : DeepSeek joue le
rôle du contrôleur/diagnostic, Gemini celui du développeur, Python celui du harnais déterministe.

RÉSILIENCE (jamais laisser le fichier cible dans un état pire qu'avant l'appel) : le contenu
existant est sauvegardé en mémoire avant toute écriture ; si tous les essais échouent, il est
RESTAURÉ (fichier existant) ou SUPPRIMÉ (fichier neuf jamais validé) — zéro résidu cassé.
"""

import os
import re
import subprocess
import sys

import ponts

_TIMEOUT_TEST_S = 60
_TRONQUER_SORTIE_TEST = 2000  # caractères de sortie de test envoyés au diagnostic
_RE_BRIQUE = re.compile(r"(?mi)^[^\w`]*BRIQUE\s*\d+\s*[:\-]\s*\**\s*(.+?)\**\s*$")

# Discipline Ponytail (cf. ROLES["developpeur"] de beecham.py) — formulée par Gemini, insérée ici :
# cohérence entre le développeur payant (claude -p) et les ponts gratuits.
_DISCIPLINE_PONYTAIL = (
    "\n\nViser la solution la plus simple, courte et minimale qui fonctionne réellement, sans "
    "abstraction spéculative ni sur-ingénierie. Privilégier systématiquement la bibliothèque "
    "standard Python et n'ajouter une dépendance externe que si c'est strictement indispensable. "
    "Produire un code direct, lisible et sobre, sans anticiper de besoins futurs incertains."
)


def _prompt_implementation(consigne) -> str:
    return (
        f"Écris le contenu COMPLET du fichier Python suivant : {consigne}\n\n"
        "Donne le fichier ENTIER dans un seul bloc de code Python, prêt à être écrit tel quel "
        "sur disque (pas d'extrait, pas de '...', pas de commentaire hors code)."
        + _DISCIPLINE_PONYTAIL
    )


def _prompt_correction(code, diagnostic) -> str:
    return (
        "Voici le code actuel du fichier :\n```python\n" + code + "\n```\n\n"
        f"Il échoue aux tests. Diagnostic reçu :\n{diagnostic}\n\n"
        "Corrige le fichier en conséquence. Donne le fichier Python COMPLET corrigé dans un "
        "seul bloc de code, prêt à être écrit tel quel sur disque."
        + _DISCIPLINE_PONYTAIL
    )


def _prompt_diagnostic(code, sortie_test) -> str:
    return (
        "Ce code Python échoue à ses tests :\n```python\n" + code + "\n```\n\n"
        "Sortie du test (erreur réelle) :\n```\n" + sortie_test[-_TRONQUER_SORTIE_TEST:] + "\n```\n\n"
        "Diagnostique PRÉCISÉMENT la cause (ligne/fonction concernée) et donne la correction "
        "à apporter. Sois concis et actionnable — pas besoin de réécrire tout le code."
    )


def implementer_et_corriger(chemin_cible, consigne, cmd_test, max_essais=3) -> dict:
    """Boucle complète : implémente `consigne` dans `chemin_cible` via Gemini, teste via `cmd_test`
    (liste d'argv, ex. [sys.executable, "-m", "pytest", "test_x.py", "-q"]), et sur échec fait
    diagnostiquer par DeepSeek puis corriger par Gemini, jusqu'à succès ou `max_essais`.
    Renvoie {ok, essais, journal: [str], dernier_code, dernier_test}."""
    journal = []
    contenu_original = None
    if os.path.exists(chemin_cible):
        with open(chemin_cible, encoding="utf-8") as f:
            contenu_original = f.read()  # sauvegarde en mémoire : restaurable si tout échoue

    code = None  # None = jamais obtenu de code valide (distinct de "code obtenu mais tests cassés")
    diagnostic = ""
    sortie_test = ""

    for essai in range(1, max_essais + 1):
        prompt = _prompt_implementation(consigne) if code is None else _prompt_correction(code, diagnostic)
        r = ponts.lancer("developpeur", prompt, nom="gemini")
        journal.append(f"essai {essai} · Gemini implémente (ok={r['ok']})")
        if not r["ok"]:
            journal.append(f"  échec envoi Gemini : {r['journal']}")
            continue

        nouveau_code = ponts.extraire_code("gemini")
        if not nouveau_code.strip():
            journal.append("  ÉCHEC : aucun code natif extrait (on retentera l'implémentation)")
            continue  # `code` reste ce qu'il était (None au 1er coup) -> prochain tour ré-implémente

        code = nouveau_code
        with open(chemin_cible, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        journal.append(f"  écrit -> {chemin_cible} ({len(code)} car.)")

        test = subprocess.run(
            cmd_test, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=_TIMEOUT_TEST_S
        )
        sortie_test = ((test.stdout or "") + (test.stderr or "")).strip()
        journal.append(f"  test rc={test.returncode}")

        if test.returncode == 0:
            return {"ok": True, "essais": essai, "journal": journal, "dernier_code": code, "dernier_test": sortie_test}

        if essai < max_essais:
            d = ponts.lancer("controleur", _prompt_diagnostic(code, sortie_test), nom="deepseek")
            diagnostic = d["texte"] if d["ok"] else "(diagnostic indisponible)"
            journal.append(f"  DeepSeek diagnostique (ok={d['ok']}) : {diagnostic[:150]}")

    # Échec définitif : ne JAMAIS laisser le fichier cible dans un état pire qu'avant l'appel.
    if contenu_original is not None:
        with open(chemin_cible, "w", encoding="utf-8") as f:
            f.write(contenu_original)
        journal.append("échec définitif -> fichier restauré à son état d'origine")
    elif code is not None and os.path.exists(chemin_cible):
        os.remove(chemin_cible)
        journal.append("échec définitif -> fichier neuf jamais validé, supprimé (zéro résidu)")

    return {"ok": False, "essais": max_essais, "journal": journal, "dernier_code": code, "dernier_test": sortie_test}


def planifier(consigne_globale) -> list[str]:
    """DeepSeek (rôle PLANIFICATEUR — persona distincte du diagnostic) découpe `consigne_globale`
    en briques minimales indépendantes. Format ancré `BRIQUE N:`, parsing tolérant (cf. mémoire
    reference_ponts_format_parsable). Renvoie une liste de descriptions (peut être vide si échec)."""
    prompt = (
        f"Je veux construire ceci : {consigne_globale}\n\n"
        "Planifie ce module en briques minimales et indépendantes. IMPORTANT : chaque brique est un "
        "AJOUT DE CODE dans le MÊME et UNIQUE fichier — jamais une brique qui créerait un fichier "
        "séparé (les tests existent déjà à part, ne les inclus PAS dans ce plan). Réponds une brique "
        "par ligne, chaque ligne commençant EXACTEMENT par `BRIQUE N:` (N = numéro), suivie d'une "
        "description courte. Aucun autre texte avant."
    )
    r = ponts.lancer("planificateur", prompt, nom="deepseek")
    if not r["ok"]:
        return []
    return _RE_BRIQUE.findall(r["texte"])


def orchestrer(consigne_globale, chemin_cible, cmd_test, max_essais_par_brique=2) -> dict:
    """Orchestrateur à personas distinctes : DeepSeek PLANIFIE (`planifier`), puis chaque brique est
    IMPLÉMENTÉE + TESTÉE + CORRIGÉE (`implementer_et_corriger` : Gemini développe, DeepSeek
    diagnostique) en ENCHAÎNANT sur le code déjà écrit par les briques précédentes (pas de repartir
    de zéro à chaque brique). S'arrête à la première brique qui échoue définitivement (le fichier
    reste dans le dernier état VALIDÉ, jamais cassé — géré par implementer_et_corriger).
    Renvoie {plan_ok, briques, resultats: [{brique, ok, essais, journal, ...}], toutes_ok}."""
    briques = planifier(consigne_globale)
    resultats = []
    for brique in briques:
        contexte_existant = ""
        if os.path.exists(chemin_cible):
            with open(chemin_cible, encoding="utf-8") as f:
                contexte_existant = f.read()
        consigne_brique = (
            f"Contexte global du module : {consigne_globale}\n\n"
            + (
                "Code déjà écrit dans ce fichier — à CONSERVER et ÉTENDRE, ne supprime rien sauf "
                f"pour corriger un bug avéré :\n```python\n{contexte_existant}\n```\n\n"
                if contexte_existant
                else ""
            )
            + f"Ajoute maintenant cette brique précise : {brique}"
        )
        r = implementer_et_corriger(chemin_cible, consigne_brique, cmd_test, max_essais=max_essais_par_brique)
        resultats.append({"brique": brique, **r})
        if not r["ok"]:
            break  # fichier déjà restauré/nettoyé par implementer_et_corriger -> on arrête la chaîne

    toutes_ok = bool(briques) and len(resultats) == len(briques) and all(r["ok"] for r in resultats)
    return {"plan_ok": bool(briques), "briques": briques, "resultats": resultats, "toutes_ok": toutes_ok}


if __name__ == "__main__":
    print("Module de boucle d'auto-correction — voir implementer_et_corriger(). Pas d'exécution directe.")
    sys.exit(0)
