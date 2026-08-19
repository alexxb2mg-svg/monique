"""Le moteur de pipeline : exécution linéaire, sauts (reprise), stop, garde anti-boucle,
configuration invalide. Briques factices — aucune dépendance à beecham/git/claude."""

from harnais.moteur import continuer, executer_pipeline, sauter, stop


def test_pipeline_lineaire_va_au_bout():
    """Trois briques qui continuent : le pipeline traverse tout et finit 'fini'."""
    vus = []

    def brique(nom):
        def b(ctx):
            vus.append(nom)
            return continuer()

        return b

    briques = {"a": brique("a"), "b": brique("b"), "c": brique("c")}
    ctx = executer_pipeline(["a", "b", "c"], {}, briques)
    assert vus == ["a", "b", "c"]
    assert ctx["statut"] == "fini"
    assert [t[0] for t in ctx["trace"]] == ["a", "b", "c"]


def test_stop_interrompt_le_pipeline():
    """Une brique qui stop termine immédiatement (les suivantes ne tournent pas)."""
    vus = []

    def a(ctx):
        vus.append("a")
        return continuer()

    def b(ctx):
        vus.append("b")
        return stop("rejete", "mauvais")

    def c(ctx):
        vus.append("c")
        return continuer()

    ctx = executer_pipeline(["a", "b", "c"], {}, {"a": a, "b": b, "c": c})
    assert vus == ["a", "b"]  # c jamais atteint
    assert ctx["statut"] == "rejete"
    assert ctx["resume"] == "mauvais"


def test_saut_permet_la_reprise():
    """La brique 'revue' saute une fois vers 'code' (reprise), puis accepte -> fusion.
    Vérifie qu'un embranchement arrière fonctionne (cœur du verdict 'corriger')."""
    ctx = {"tours": 0}

    def code(ctx):
        ctx["tours"] += 1
        return continuer()

    def revue(ctx):
        # 1er passage : demande une reprise ; 2e passage : accepte
        if ctx["tours"] == 1:
            return sauter("code")
        return continuer()

    def fusion(ctx):
        return stop("valide", "fusionné")

    ctx = executer_pipeline(["code", "revue", "fusion"], ctx, {"code": code, "revue": revue, "fusion": fusion})
    assert ctx["tours"] == 2  # code exécuté deux fois (reprise)
    assert ctx["statut"] == "valide"


def test_garde_anti_boucle():
    """Deux briques qui se renvoient l'une vers l'autre -> le garde-fou coupe en 'echec'."""

    def a(ctx):
        return sauter("b")

    def b(ctx):
        return sauter("a")

    ctx = executer_pipeline(["a", "b"], {}, {"a": a, "b": b})
    assert ctx["statut"] == "echec"
    assert "garde" in ctx["resume"]


def test_etape_inconnue_est_une_erreur():
    """Un pipeline qui nomme une étape absente des briques -> 'erreur' (jamais silencieux)."""
    ctx = executer_pipeline(["a", "fantome"], {}, {"a": lambda c: continuer()})
    assert ctx["statut"] == "erreur"
    assert "fantome" in ctx["resume"]


def test_saut_vers_etape_inconnue_est_une_erreur():
    ctx = executer_pipeline(["a"], {}, {"a": lambda c: sauter("nulle_part")})
    assert ctx["statut"] == "erreur"
    assert "nulle_part" in ctx["resume"]
