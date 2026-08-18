"""Garde-fou : aucune identité RÉELLE (client, fournisseur, personne, chantier) dans le dépôt public.

POURQUOI. `gitleaks` cherche des secrets par SIGNATURE (clés, jetons, IBAN). Un nom propre
n'a aucune signature — il passe sans bruit. Il faut donc un contrôle dédié aux identités.
Sur un projet frère, trois noms réels sont partis dans un miroir public faute de ce contrôle.

PRINCIPE. La LISTE des noms interdits ne peut pas vivre dans le dépôt (elle serait
elle-même la fuite). Elle est lue HORS dépôt, dans le coffre local
`~/.monique_secrets/noms_interdits.txt` (un nom par ligne, `#` = commentaire), ou au chemin
donné par MONIQUE_NOMS_INTERDITS. Ce script, lui, est public et inoffensif : aucun nom dedans.

DEUX PASSAGES LIBRES, voulus :
- **dépôt de travail** : il a le droit de nommer les clients — c'est le MIROIR public qui ne
  l'a pas. Le contrôle ne mord que si `origin` est le dépôt public (motif MONIQUE_REMOTE_PUBLIC),
  ou si MONIQUE_ANONYMAT_FORCE=1.
- **liste absente** : un contributeur extérieur n'a pas le coffre — avertissement, code 0.

En plus des noms du coffre, des MOTIFS STRUCTURELS toujours actifs (chemins de poste,
emails hors noreply) : eux n'ont pas besoin du coffre. Le mode --historique regarde ce que
l'arbre courant ne montre pas : vieux commits, tags, et l'identité de chaque auteur/committer.

Usage :
    python scripts/verifier_anonymat.py               # fichiers suivis par git
    python scripts/verifier_anonymat.py f1 f2         # fichiers précis (hook pre-commit)
    python scripts/verifier_anonymat.py --historique  # TOUT l'historique + tags + auteurs
    MONIQUE_ANONYMAT_FORCE=1 python scripts/…         # contrôler quel que soit le remote
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

DEFAUT_LISTE = Path.home() / ".monique_secrets" / "noms_interdits.txt"
EXTENSIONS_IGNOREES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".gguf",
    ".zip",
    ".gz",
    ".pyc",
    ".ico",
    ".woff",
    ".woff2",
}
DOSSIERS_IGNORES = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
FICHIERS_IGNORES = {
    "scripts/verifier_anonymat.py"
}  # ce script parle DES motifs : il ne se dénonce pas

# Identités noreply acceptées pour un commit : celles de l'utilisateur ET celles générées
# par GitHub (web-flow, Actions, Dependabot). Le but est de bloquer une identité RÉELLE
# (nom + email perso), jamais les noreply GitHub qui ne révèlent rien.
_NOREPLY_OK = ("users.noreply.github.com>", "noreply@github.com>")

# Motifs STRUCTURELS — pas besoin du coffre : un chemin de poste ou un email personnel
# est une fuite quelle que soit la liste. Le chemin tolère 1 à 2 antislashs (dans un JSON
# il est stocké échappé) et n'importe quel nom de compte (pas seulement le nôtre).
MOTIFS_STRUCTURELS: list[tuple[str, re.Pattern[str]]] = [
    (
        "chemin de poste",
        re.compile(r"[A-Za-z]:[/\\]{1,2}Users[/\\]{1,2}[A-Za-z0-9._-]+", re.IGNORECASE),
    ),
    (
        "email hors noreply",
        re.compile(
            r"[\w.+-]+@(?!users\.noreply\.github\.com)[\w-]+\.\w{2,}", re.IGNORECASE
        ),
    ),
]


def charger_liste() -> list[str]:
    chemin = Path(os.environ.get("MONIQUE_NOMS_INTERDITS", DEFAUT_LISTE))
    if not chemin.exists():
        print(
            f"[anonymat] liste absente ({chemin}) — contrôle des NOMS sauté "
            "(normal hors du poste propriétaire). Les motifs structurels restent actifs.",
            file=sys.stderr,
        )
        return []
    return [
        li.strip()
        for li in chemin.read_text(encoding="utf-8").splitlines()
        if li.strip() and not li.startswith("#")
    ]


def fichiers_a_verifier(args: list[str]) -> list[Path]:
    if args:
        return [Path(a) for a in args]
    sortie = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout
    return [Path(li) for li in sortie.splitlines() if li.strip()]


def compiler_noms(noms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    # Bornes par LETTRES (pas \b) : dans ACME_2026 ou POMME_devis, chiffres/underscore sont
    # des caractères de mot et \b raterait. Convention de casse : une entrée TOUT EN MAJUSCULES
    # est cherchée en respectant la casse (évite d'interdire un mot courant) ; sinon insensible.
    return [
        (
            n,
            re.compile(
                rf"(?<![A-Za-zÀ-ÿ]){re.escape(n)}(?![A-Za-zÀ-ÿ])",
                0 if n.isupper() else re.IGNORECASE,
            ),
        )
        for n in noms
    ]


def _texte_de(p: Path) -> str | None:
    if p.suffix.lower() in EXTENSIONS_IGNOREES or any(
        d in p.parts for d in DOSSIERS_IGNORES
    ):
        return None
    if str(p).replace("\\", "/") in FICHIERS_IGNORES:
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def verifier_arbre(motifs, fichiers) -> int:
    problemes: list[str] = []
    for p in fichiers:
        texte = _texte_de(p)
        if texte is None:
            continue
        for nom, rx in motifs + MOTIFS_STRUCTURELS:
            if rx.search(texte):
                problemes.append(f"« {nom} » dans {p}")
    if problemes:
        print(f"[anonymat] REFUSÉ — {len(problemes)} problème(s) :", file=sys.stderr)
        for pb in problemes[:30]:
            print(f"  ! {pb}", file=sys.stderr)
        return 1
    print(
        f"[anonymat] OK — {len(fichiers)} fichier(s) contrôlé(s), aucune identité réelle."
    )
    return 0


def verifier_historique(motifs) -> int:
    problemes: list[str] = []
    identites = subprocess.run(
        ["git", "log", "--all", "--format=%an <%ae>%n%cn <%ce>"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    for ident in sorted({i for i in identites if i.strip()}):
        if not ident.endswith(_NOREPLY_OK):
            problemes.append(f"identité non-noreply (email réel ?) : {ident}")
    revs = subprocess.run(
        ["git", "rev-list", "--all"], capture_output=True, text=True, check=True
    ).stdout.split()
    a_chercher = [
        (nom, ("(?i)" if m.flags & re.IGNORECASE else "") + m.pattern)
        for nom, m in motifs + MOTIFS_STRUCTURELS
    ]
    for nom, pattern in a_chercher:
        grep = subprocess.run(
            ["git", "grep", "-l", "-I", "-P", pattern, *revs],
            capture_output=True,
            text=True,
        )
        if grep.returncode > 1:
            problemes.append(
                f"échec git grep sur « {nom} » : {grep.stderr.strip()[:120]}"
            )
            continue
        for ligne in grep.stdout.splitlines():
            if any(f in ligne for f in FICHIERS_IGNORES):
                continue
            problemes.append(f"« {nom} » dans {ligne}")
    if problemes:
        print(
            f"[anonymat] HISTORIQUE REFUSÉ — {len(problemes)} problème(s) :",
            file=sys.stderr,
        )
        for pb in problemes[:30]:
            print(f"  ! {pb}", file=sys.stderr)
        return 1
    print(
        f"[anonymat] historique OK — {len(revs)} commit(s) contrôlé(s) (branches + tags)."
    )
    return 0


def main(argv: list[str]) -> int:
    # Monique est un dépôt PUBLIC par nature : le contrôle tourne toujours (aucun dépôt de
    # travail séparé qui aurait le droit de nommer des clients). Escape hatch : git … --no-verify.
    motifs = compiler_noms(charger_liste())
    if "--historique" in argv:
        return verifier_historique(motifs)
    return verifier_arbre(
        motifs, fichiers_a_verifier([a for a in argv if not a.startswith("--")])
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
