#!/usr/bin/env python3
"""Refuse un push qui emporte ce qui décrit la MACHINE, pas le projet.

Ce que ce garde-fou refuse dans ce qui partirait :
1. Un chemin de profil utilisateur absolu (C:\\Users\\<compte>) ajouté dans du code source.
   Le code doit tourner depuis n'importe quel clone, jamais porter l'arborescence d'un poste.
2. Un fichier de log/journal : c'est de l'activité machine (chemins, horaires, volumes réels).
3. Un fichier de données volumineux (> SEUIL_MO) ajouté sans intention explicite.

Doctrine : ce sont les contrôles MÉCANIQUES qui arrêtent les erreurs, pas la vigilance.
Une consigne orale s'exécute une fois ; un hook s'exécute à chaque push.

Échappatoire assumée : `git push --no-verify` passe outre — le garde-fou protège de
l'inattention, pas d'une décision prise sciemment.

Installation : appelé par .git/hooks/pre-push (ou via .pre-commit-config.yaml, stage pre-push).
"""

import re
import subprocess
import sys

SEUIL_MO = 5
CHEMIN_MACHINE = re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}[A-Za-z0-9._-]+", re.I)
JOURNAUX = re.compile(r"(_audit|journal_|\.log|debug|stderr|stdout)", re.I)
# Fichiers où un chemin absolu est légitime : docs, exemples, tests (un test de contrôle
# d'accès DOIT contenir un chemin réel pour vérifier qu'un dossier frère est refusé), et
# ce garde-fou lui-même.
EXEMPTS = re.compile(
    r"(^|/)(.*\.md$|.*\.example$|.*exemple.*|_?tests?/|scripts/pre_push_garde_fou\.py$)",
    re.I,
)
CODE = (".py", ".js", ".ts", ".ps1", ".sh", ".bat", ".vbs")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def _plage() -> str | None:
    amont = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
    if not amont or "fatal" in amont.lower():
        return None  # pas d'amont : premier push, on laisse passer (le CI gitleaks prend le relais)
    return f"{amont}..HEAD"


def main() -> int:
    plage = _plage()
    if not plage:
        return 0
    fichiers = [f for f in _git("diff", "--name-only", plage).splitlines() if f.strip()]
    if not fichiers:
        return 0
    refus: list[str] = []

    for f in fichiers:
        if f.endswith(".log") or (
            JOURNAUX.search(f) and f.endswith((".jsonl", ".txt"))
        ):
            if _git("ls-tree", "HEAD", "--", f).strip():
                refus.append(f"  {f}\n      journal : décrit la machine, pas le projet")

    for f in fichiers:
        if EXEMPTS.search(f) or not f.endswith(CODE):
            continue
        for ligne in _git("diff", plage, "--", f).splitlines():
            if not ligne.startswith("+") or ligne.startswith("+++"):
                continue
            trouve = CHEMIN_MACHINE.search(ligne)
            if trouve:
                refus.append(
                    f"  {f}\n      chemin du poste en dur : {trouve.group(0)}\n"
                    f"      -> Path(__file__)... ou une variable d'environnement"
                )
                break

    for ligne in _git("diff", "--numstat", plage).splitlines():
        col = ligne.split("\t")
        if len(col) != 3 or col[0] == "-":
            continue
        taille = _git("cat-file", "-s", f"HEAD:{col[2]}").strip()
        if taille.isdigit() and int(taille) > SEUIL_MO * 1024 * 1024:
            refus.append(
                f"  {col[2]}\n      {int(taille) / 1024 / 1024:.1f} Mo — au-delà de {SEUIL_MO} Mo"
            )

    if refus:
        print(
            "\nPUSH REFUSÉ — ce qui partirait décrit la machine, pas le projet :\n",
            file=sys.stderr,
        )
        print("\n".join(refus), file=sys.stderr)
        print(
            "\nCorrigez, ou passez outre sciemment avec : git push --no-verify\n",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
