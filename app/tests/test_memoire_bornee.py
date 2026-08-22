"""La mémoire partagée des agents doit rester BORNÉE.

Incident réel du 22/08 : `plan.md` (22 k) et `memoire/chef.md` (12 k) sont injectés dans le
prompt du chef — au-delà de 32 767 caractères le lancement échoue. Le passage par stdin a
déplacé la limite, pas le problème : sans borne, la croissance recommence. Ce test est la
borne (revue 22/08 §2.3).

Fichier absent = test qui passe : le CI tourne sans atelier, il n'a rien à borner.
"""

import beecham

BORNE_PLAN = 8000
BORNE_MEMOIRE = 6000
CONSEIL = "condenser avant d'ajouter (revue 22/08 §2.3)"


def _taille(fichier):
    return len(fichier.read_text(encoding="utf-8", errors="replace"))


def test_plan_sous_sa_borne():
    # ATELIER relu ici, pas une constante figée au chargement : le test suit un atelier déplacé.
    plan = beecham.ATELIER / "plan.md"
    if not plan.exists():
        return
    n = _taille(plan)
    assert n <= BORNE_PLAN, f"plan.md : {n} caractères > {BORNE_PLAN} — {CONSEIL}"


def test_memoires_sous_leur_borne():
    memoire = beecham.ATELIER / "memoire"
    if not memoire.is_dir():
        return
    trop = [
        f"{f.name} : {_taille(f)} caractères"
        for f in sorted(memoire.glob("*.md"))
        if _taille(f) > BORNE_MEMOIRE
    ]
    assert not trop, f"mémoire > {BORNE_MEMOIRE} caractères — {', '.join(trop)} — {CONSEIL}"
