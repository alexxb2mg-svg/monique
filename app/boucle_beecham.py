"""Cran au-dessus de boucle_ponts : relie les ponts gratuits au VRAI processus de construction de
Monique. Personas distincts, chacun en conversation FRAÎCHE (évite la dérive de contexte, mime un
humain qui change de sujet) :

  1. PROPOSER  (DeepSeek) — lit le vrai plan.md de Beecham, propose des candidats concrets.
  2. CHOISIR   (Gemini)   — reçoit les candidats, choisit le plus intéressant + justifie.
  3. TESTER    (Gemini, nouvelle conv.) — écrit les tests AVANT l'implémentation (juge indépendant
                de ce qui va suivre — esprit TDD, cf. discipline Ponytail).
  4. CONSTRUIRE (boucle_ponts.orchestrer) — sous-planifie en sous-briques et exécute jusqu'au bout.
  5. BOUCLE    — retire la brique traitée, reboucle sur CHOISIR (sur le reste du plan INITIAL,
                jamais régénéré), jusqu'à épuisement ou plafond.

SÉCURITÉ ASSUMÉE : construit dans un SANDBOX (dossier isolé), JAMAIS directement dans les fichiers
réels de Monique — cette boucle n'a ni l'isolation worktree, ni le contrôleur adversarial, ni la
validation d'Alex de la vraie brigade Beecham. Un humain relit et fusionne à la main s'il le souhaite.
"""

import ast
import os
import re

import boucle_ponts
import ponts
import proposer_ponts

_ATELIER = os.path.join(
    # app/boucle_beecham.py -> app -> secretaire -> BSTEG_Logiciel, puis atelier/ (sibling de secretaire/)
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "atelier",
)
_RE_PROPOSITION = re.compile(r"(?mi)^[^\w`]*PROPOSITION\s*\d+\s*[:\-]\s*\**\s*(.+?)\**\s*$")
_RE_CHOIX = re.compile(r"(?mi)^[^\w`]*CHOIX\s*[:\-]\s*(\d+)")
_MAX_CONTEXTE_CAR = 15000  # borne raisonnable pour un seul message pont
_REPO_GITHUB = "https://github.com/alexxb2mg-svg/monique"  # public — lisible par DeepSeek (accès web)
# Point de sortie visible : TOUT résultat (succès ET échec) y est déposé automatiquement — un
# échec sur un sujet sensible doit rester visible, pas seulement les succès (trouvé le 20/08/2026 :
# la tentative sur le garde-fou de sécurité avait échoué sans laisser aucune trace lisible).
DOSSIER_PROPOSITIONS = os.path.join(_ATELIER, "propositions_ponts")


def lire_contexte_beecham() -> str:
    """Le VRAI plan.md de Beecham (backlog priorisé), tronqué si trop long pour un message."""
    chemin = os.path.join(_ATELIER, "plan.md")
    with open(chemin, encoding="utf-8") as f:
        return f.read()[:_MAX_CONTEXTE_CAR]


def proposer_candidats(contexte) -> list[str]:
    """DeepSeek, CONVERSATION FRAÎCHE : propose des candidats concrets et bornés (pas de décision
    organisationnelle) à partir du vrai plan de Beecham."""
    ponts.nouvelle_conversation("deepseek")
    prompt = (
        "Voici le plan RÉEL (backlog priorisé) d'un projet agentique en construction, Monique :\n\n"
        f"{contexte}\n\n"
        f"Le code source RÉEL et À JOUR est public sur GitHub : {_REPO_GITHUB} — le dossier "
        f"applicatif est {_REPO_GITHUB}/tree/main/app. Consulte-le (tu as un accès web) pour ancrer "
        "tes propositions dans le VRAI code existant plutôt que dans le seul texte du plan — vérifie "
        "ce qui existe déjà avant de proposer, pour ne rien redemander de fait.\n\n"
        "Propose 3 à 5 candidats concrets pour « la prochaine brique de CODE à construire » — des "
        "tâches BORNÉES et autonomes (un petit module/fonction cohérent, testable seul), PAS des "
        "décisions organisationnelles ou humaines. Réponds une proposition par ligne, chaque ligne "
        "commençant EXACTEMENT par `PROPOSITION N:` suivie d'une description courte et actionnable. "
        "Aucun autre texte avant."
    )
    r = ponts.lancer("chercheur", prompt, nom="deepseek")
    if not r["ok"]:
        return []
    return _RE_PROPOSITION.findall(r["texte"])


def choisir_brique(candidats) -> tuple:
    """Gemini, CONVERSATION FRAÎCHE : choisit le candidat le plus intéressant parmi ceux restants.
    Renvoie (index dans `candidats`, justification) ou (None, texte brut) si le format n'a pas tenu."""
    ponts.nouvelle_conversation("gemini")
    liste = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(candidats))
    prompt = (
        "Voici des candidats pour la prochaine brique de code à construire dans un projet agentique "
        f"appelé Monique :\n\n{liste}\n\n"
        "Choisis LE plus intéressant à construire maintenant (impact réel, faisabilité, cohérence "
        "avec un projet existant). Réponds en 2 lignes : la première EXACTEMENT `CHOIX: N` (N = "
        "numéro), la seconde une justification courte."
    )
    r = ponts.lancer("developpeur", prompt, nom="gemini")
    if not r["ok"]:
        return None, ""
    m = _RE_CHOIX.search(r["texte"])
    if not m:
        return None, r["texte"]
    idx = int(m.group(1)) - 1
    if not (0 <= idx < len(candidats)):
        return None, r["texte"]
    return idx, r["texte"]


def _prompt_ecrire_tests(nom_module, brique_desc) -> str:
    return (
        f"Tu vas écrire des tests pytest pour un module Python `{nom_module}.py` qui devra plus tard "
        f"implémenter ceci : {brique_desc}\n\n"
        f"Écris UNIQUEMENT les tests (pas l'implémentation), avec `from {nom_module} import ...` "
        "pour les imports nécessaires. 3 à 6 tests : le cas nominal + 1-2 cas limites. Bibliothèque "
        "standard uniquement pour les mocks (unittest.mock). Donne le fichier de test COMPLET dans "
        "un seul bloc de code Python, prêt à écrire sur disque."
    )


def revoir_tests_deepseek(code_test, brique_desc) -> str:
    """DeepSeek relit les tests écrits par Gemini (renforce le juge : un test faible validerait
    silencieusement une mauvaise implémentation). Verdict INFORMATIF, non bloquant — visible dans
    le journal, laissé à l'appréciation humaine plutôt que d'ajouter une seconde boucle de retente
    à celle déjà existante pour la syntaxe (discipline Ponytail : pas de complexité pour un gain
    marginal). Renvoie "" en cas d'échec d'envoi."""
    prompt = (
        f"Voici des tests pytest écrits pour une brique : « {brique_desc} ».\n\n"
        f"```python\n{code_test}\n```\n\n"
        "Relis-les d'un œil critique : couvrent-ils vraiment le cas nominal et les cas limites "
        "utiles, ou sont-ils trop faibles/triviaux ? Réponds en 2 lignes : la première EXACTEMENT "
        "`VERDICT: OK` ou `VERDICT: FAIBLE`, la seconde une justification courte."
    )
    r = ponts.lancer("controleur", prompt, nom="deepseek")
    return r["texte"] if r["ok"] else ""


def ecrire_tests_pour_brique(brique_desc, nom_module, chemin_test) -> bool:
    """Gemini, CONVERSATION FRAÎCHE : écrit les tests AVANT l'implémentation (juge indépendant, pas
    l'implémenteur qui s'auto-juge). VALIDE LA SYNTAXE avant d'écrire (un test cassé bloquerait toute
    la boucle de correction en aval : elle ne peut réparer que l'IMPLÉMENTATION, jamais le test lui-
    même) — retente UNE fois avec l'erreur précise si invalide. Renvoie True si un test SYNTAXIQUEMENT
    VALIDE a été écrit."""
    ponts.nouvelle_conversation("gemini")
    r = ponts.lancer("developpeur", _prompt_ecrire_tests(nom_module, brique_desc), nom="gemini")
    if not r["ok"]:
        return False
    code_test = ponts.extraire_code("gemini")

    for derniere_tentative in (False, True):  # 1 essai + 1 retente sur erreur de syntaxe
        if not code_test.strip():
            return False
        try:
            ast.parse(code_test)
        except SyntaxError as e:
            if derniere_tentative:
                return False  # toujours invalide après la retente
            prompt_fix = (
                f"Ce code Python a une erreur de syntaxe :\n```python\n{code_test}\n```\n\n"
                f"Erreur : {e}\n\n"
                "Corrige UNIQUEMENT cette erreur (ex. si c'est un littéral bytes b'...' contenant un "
                "accent, retire l'accent ou passe en str). Donne le fichier COMPLET corrigé dans un "
                "seul bloc de code Python."
            )
            r2 = ponts.lancer("developpeur", prompt_fix, nom="gemini")
            code_test = ponts.extraire_code("gemini") if r2["ok"] else ""
            continue
        verdict = revoir_tests_deepseek(code_test, brique_desc)
        if verdict:
            print(f"[revue DeepSeek des tests] {verdict[:200]}")  # informatif, jamais bloquant
        with open(chemin_test, "w", encoding="utf-8") as f:
            f.write(code_test + "\n")
        return True
    return False


def construire_brique_sandbox(brique_desc, dossier_sandbox, index) -> dict:
    """Construit UNE brique dans le sandbox : écrit ses tests (Gemini, juge indépendant), puis
    délègue à boucle_ponts.orchestrer (sous-planification + implémentation + correction).
    Testé avec l'interpréteur Python 3.14 (`ponts._PY314`) — le sandbox est un bac à sable
    d'idées, pas contraint aux dépendances minimales du venv réel de l'app (ex. `requests`,
    absent de app/.venv car l'app n'en a jamais eu besoin jusqu'ici ; présent sur 3.14).
    Dépose TOUJOURS une proposition lisible dans DOSSIER_PROPOSITIONS (succès ET échec — un échec
    sur un sujet sensible doit rester visible, jamais silencieux)."""
    os.makedirs(dossier_sandbox, exist_ok=True)  # autonome : ne dépend pas de l'appelant
    nom_module = f"brique_{index}"
    chemin_module = os.path.join(dossier_sandbox, nom_module + ".py")
    chemin_test = os.path.join(dossier_sandbox, f"test_{nom_module}.py")

    tests_ok = ecrire_tests_pour_brique(brique_desc, nom_module, chemin_test)
    if not tests_ok:
        resultat = {"ok": False, "brique": brique_desc, "erreur": "échec écriture des tests"}
        try:
            resultat["proposition_ecrite"] = proposer_ponts.proposer_a_alex(resultat, DOSSIER_PROPOSITIONS)
        except Exception:
            # Une erreur de RAPPORT ne doit JAMAIS faire perdre un résultat de construction (bug réel
            # 20/08/2026 : un nom de fichier trop long a fait planter tout le pipeline).
            resultat["proposition_ecrite"] = None
        return resultat

    cmd_test = [ponts._PY314, "-m", "pytest", chemin_test, "-v"]
    res = boucle_ponts.orchestrer(brique_desc, chemin_module, cmd_test, max_essais_par_brique=2)
    resultat = {"brique": brique_desc, "chemin_module": chemin_module, "chemin_test": chemin_test, **res}
    try:
        resultat["proposition_ecrite"] = proposer_ponts.proposer_a_alex(resultat, DOSSIER_PROPOSITIONS)
    except Exception:
        resultat["proposition_ecrite"] = None
    return resultat


def executer_cycle_beecham(dossier_sandbox, max_briques=None) -> dict:
    """La boucle complète : PROPOSER (une fois) -> CHOISIR -> CONSTRUIRE -> retirer -> reCHOISIR,
    jusqu'à épuisement du plan initial (ou `max_briques`, pour brider un premier essai)."""
    contexte = lire_contexte_beecham()
    candidats = proposer_candidats(contexte)
    restants = list(candidats)
    resultats = []
    while restants and (max_briques is None or len(resultats) < max_briques):
        idx, justification = choisir_brique(restants)
        if idx is None:
            break
        brique = restants.pop(idx)
        res = construire_brique_sandbox(brique, dossier_sandbox, len(resultats) + 1)
        res["justification"] = justification
        resultats.append(res)
    return {"candidats_initiaux": candidats, "resultats": resultats}
