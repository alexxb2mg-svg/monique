"""Les briques du harnais : chaque étape est une fonction `(ctx) -> Decision`.

Une brique lit/écrit dans le CONTEXTE partagé `ctx` et pilote le moteur via sa Decision.
Les outils réels (agent dev, harnais de test, contrôleur, fusion git) sont fournis dans
`ctx["outils"]` — injectés par la boucle en prod, remplacés par des factices en test. Les
briques ne connaissent donc ni git ni claude directement : elles restent pures et testables.

Contrat de `ctx["outils"]` :
  - agent(role, consigne, worktree, reprendre=None) -> {journal, texte, session_id, ...}
  - harnais(worktree) -> {diff, tests_ok, tests_resume}
  - controleur(consigne, diff, tests_resume, worktree) -> {verdict, raison}
  - fusion(branche, worktree, mid) -> bool
"""

from harnais.moteur import continuer, sauter, stop


def _journal(ctx, ligne):
    ctx.setdefault("journal", []).append(ligne)


def brique_code(ctx):
    """Le développeur code dans le worktree. En reprise, on le relance avec la correction du
    contrôleur et sa session (--resume) pour ne pas repartir de zéro."""
    outils = ctx["outils"]
    role = ctx["mission"].get("role", "developpeur")
    if ctx.get("_reprise"):
        r = outils["agent"](role, ctx.get("raison", ""), ctx["worktree"], reprendre=ctx.get("session_id"))
        _journal(ctx, "→ reprise après « corriger »")
    else:
        r = outils["agent"](role, ctx["mission"]["consigne"], ctx["worktree"])
    ctx["journal"] = ctx.get("journal", []) + (r.get("journal", []) if isinstance(r, dict) else [])
    if isinstance(r, dict) and r.get("session_id"):
        ctx["session_id"] = r["session_id"]
    return continuer()


def brique_test(ctx):
    """Harnais déterministe : diff réel + tests. Diff vide => rien à coder (livré) ; tests
    rouges => rejet immédiat (on ne fusionne jamais du code cassé)."""
    h = ctx["outils"]["harnais"](ctx["worktree"])
    ctx["diff"] = h.get("diff", "")
    ctx["tests_ok"] = h.get("tests_ok", False)
    ctx["tests_resume"] = h.get("tests_resume", "")
    _journal(ctx, f"harnais · tests: {ctx['tests_resume']}")
    if not ctx["diff"].strip():
        return stop("livre", "livré (rien à coder)")
    if not ctx["tests_ok"]:
        return stop("rejete", "tests rouges")
    return continuer()


def brique_revue(ctx):
    """Revue adversariale. « accepte » -> on avance vers la fusion ; « corriger » -> UN tour de
    reprise (saut vers 'code') pour récupérer le travail ; « rejeter » (ou corriger déjà tenté)
    -> abandon propre. Reproduit la logique reprise-sur-corriger."""
    v = ctx["outils"]["controleur"](
        ctx["mission"]["consigne"], ctx["diff"], ctx["tests_resume"], ctx["worktree"]
    )
    ctx["verdict"] = v.get("verdict", "rejeter")
    ctx["raison"] = v.get("raison", "")
    _journal(ctx, f"controleur · {ctx['verdict']}")
    if ctx["verdict"] == "accepte":
        return continuer()
    if ctx["verdict"] == "corriger" and not ctx.get("_reprise") and ctx.get("session_id"):
        ctx["_reprise"] = True  # une seule reprise, sinon boucle
        return sauter("code")
    return stop("rejete", f"{ctx['verdict']}: {ctx['raison'][:80]}")


def brique_fusion(ctx):
    """Fusion locale en série (le verrou de sérialisation git est porté par la boucle, pas ici)."""
    ok = ctx["outils"]["fusion"](ctx["branche"], ctx["worktree"], ctx["mission"]["mid"])
    if ok:
        return stop("valide", "accepté + fusionné (local)")
    return stop("echec", "conflit de fusion (à replanifier)")


# Registre des briques disponibles (nom d'étape -> fonction). Beecham compose ses pipelines
# à partir de ces noms ; en ajouter une (recherche, banc…) suffit à l'exposer à la composition.
BRIQUES = {
    "code": brique_code,
    "test": brique_test,
    "revue": brique_revue,
    "fusion": brique_fusion,
}
