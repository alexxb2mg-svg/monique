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

import os
import re

import boucle_ponts
import ponts

_ATELIER = os.path.join(
    # app/boucle_beecham.py -> app -> secretaire -> BSTEG_Logiciel, puis atelier/ (sibling de secretaire/)
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "atelier",
)
_RE_PROPOSITION = re.compile(r"(?mi)^[^\w`]*PROPOSITION\s*\d+\s*[:\-]\s*\**\s*(.+?)\**\s*$")
_RE_CHOIX = re.compile(r"(?mi)^[^\w`]*CHOIX\s*[:\-]\s*(\d+)")
_MAX_CONTEXTE_CAR = 15000  # borne raisonnable pour un seul message pont


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


def ecrire_tests_pour_brique(brique_desc, nom_module, chemin_test) -> bool:
    """Gemini, CONVERSATION FRAÎCHE : écrit les tests AVANT l'implémentation (juge indépendant, pas
    l'implémenteur qui s'auto-juge). Renvoie True si un fichier de test a bien été écrit."""
    ponts.nouvelle_conversation("gemini")
    prompt = (
        f"Tu vas écrire des tests pytest pour un module Python `{nom_module}.py` qui devra plus tard "
        f"implémenter ceci : {brique_desc}\n\n"
        f"Écris UNIQUEMENT les tests (pas l'implémentation), avec `from {nom_module} import ...` "
        "pour les imports nécessaires. 3 à 6 tests : le cas nominal + 1-2 cas limites. Donne le "
        "fichier de test COMPLET dans un seul bloc de code Python, prêt à écrire sur disque."
    )
    r = ponts.lancer("developpeur", prompt, nom="gemini")
    if not r["ok"]:
        return False
    code_test = ponts.extraire_code("gemini")
    if not code_test.strip():
        return False
    with open(chemin_test, "w", encoding="utf-8") as f:
        f.write(code_test + "\n")
    return True


def construire_brique_sandbox(brique_desc, dossier_sandbox, index) -> dict:
    """Construit UNE brique dans le sandbox : écrit ses tests (Gemini, juge indépendant), puis
    délègue à boucle_ponts.orchestrer (sous-planification + implémentation + correction)."""
    import sys

    nom_module = f"brique_{index}"
    chemin_module = os.path.join(dossier_sandbox, nom_module + ".py")
    chemin_test = os.path.join(dossier_sandbox, f"test_{nom_module}.py")

    tests_ok = ecrire_tests_pour_brique(brique_desc, nom_module, chemin_test)
    if not tests_ok:
        return {"ok": False, "brique": brique_desc, "erreur": "échec écriture des tests"}

    cmd_test = [sys.executable, "-m", "pytest", chemin_test, "-v"]
    res = boucle_ponts.orchestrer(brique_desc, chemin_module, cmd_test, max_essais_par_brique=2)
    return {"brique": brique_desc, "chemin_module": chemin_module, "chemin_test": chemin_test, **res}


def executer_cycle_beecham(dossier_sandbox, max_briques=None) -> dict:
    """La boucle complète : PROPOSER (une fois) -> CHOISIR -> CONSTRUIRE -> retirer -> reCHOISIR,
    jusqu'à épuisement du plan initial (ou `max_briques`, pour brider un premier essai)."""
    os.makedirs(dossier_sandbox, exist_ok=True)
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
