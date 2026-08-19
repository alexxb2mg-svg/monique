import catalogue_prix
import entrepot
import usage
import vue_usage


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_agregation_plusieurs_agents_et_plusieurs_modeles(tmp_path):
    db = _db(tmp_path)
    usage.compter(
        "secretaire", "sonnet", "claude_cli", "brouillon", 100, 50,
        cost_status="included", estimated_cost_usd=0.0, chemin=db,
    )
    usage.compter(
        "secretaire", "haiku", "claude_cli", "resume", 20, 10,
        cost_status="included", estimated_cost_usd=0.0, chemin=db,
    )
    usage.compter(
        "beecham", "sonnet", "claude_cli", "mission", 200, 80,
        cost_status="estimated", estimated_cost_usd=1.5, chemin=db,
    )

    ctx = vue_usage.contexte_usage(db)

    assert [c["agent"] for c in ctx] == ["beecham", "secretaire"]

    secretaire = next(c for c in ctx if c["agent"] == "secretaire")
    assert secretaire["input_tokens"] == 120
    assert secretaire["output_tokens"] == 60
    assert secretaire["calls"] == 2
    assert secretaire["cost_status"] == "included"  # tous identiques

    beecham_ctx = next(c for c in ctx if c["agent"] == "beecham")
    assert beecham_ctx["input_tokens"] == 200
    assert beecham_ctx["calls"] == 1
    assert beecham_ctx["estimated_cost_usd"] == 1.5
    assert beecham_ctx["cost_status"] == "estimated"


def test_cost_status_degrade_a_unknown_si_un_seul_enregistrement_unknown(tmp_path):
    db = _db(tmp_path)
    usage.compter(
        "secretaire", "sonnet", "claude_cli", "brouillon", 100, 50,
        cost_status="included", chemin=db,
    )
    usage.compter(
        "secretaire", "modele_x", "openai_compat", "resume", 20, 10,
        cost_status="unknown", chemin=db,
    )

    ctx = vue_usage.contexte_usage(db)

    assert len(ctx) == 1
    assert ctx[0]["cost_status"] == "unknown"
    # les totaux restent calculés (utiles), seule la fiabilité du statut est dégradée
    assert ctx[0]["input_tokens"] == 120
    assert ctx[0]["calls"] == 2


def test_cost_status_degrade_a_unknown_si_melange_non_homogene(tmp_path):
    db = _db(tmp_path)
    usage.compter(
        "secretaire", "sonnet", "claude_cli", "brouillon", 100, 50,
        cost_status="included", chemin=db,
    )
    usage.compter(
        "secretaire", "haiku", "claude_cli", "resume", 20, 10,
        cost_status="estimated", chemin=db,
    )

    ctx = vue_usage.contexte_usage(db)

    assert len(ctx) == 1
    assert ctx[0]["cost_status"] == "unknown"


def test_fichier_absent_fail_soft(tmp_path):
    db = str(tmp_path / "n_existe_pas.db")

    ctx = vue_usage.contexte_usage(db)

    assert ctx == []


def test_previsionnel_multi_fournisseurs_calcule_sur_le_total_global(tmp_path):
    db = _db(tmp_path)
    usage.compter(
        "secretaire", "sonnet", "claude_cli", "brouillon", 100, 50,
        cost_status="included", estimated_cost_usd=0.0, chemin=db,
    )
    usage.compter(
        "beecham", "sonnet", "claude_cli", "mission", 200, 80,
        cost_status="estimated", estimated_cost_usd=1.5, chemin=db,
    )

    previsionnel = vue_usage.previsionnel_multi_fournisseurs(db)

    attendu = catalogue_prix.comparer_fournisseurs(300, 130)
    assert previsionnel == attendu
    assert previsionnel  # non vide
    assert [c["cout_usd"] for c in previsionnel] == sorted(c["cout_usd"] for c in previsionnel)


def test_previsionnel_vide_si_aucun_usage(tmp_path):
    db = _db(tmp_path)

    assert vue_usage.previsionnel_multi_fournisseurs(db) == []

    db_absent = str(tmp_path / "n_existe_pas.db")
    assert vue_usage.previsionnel_multi_fournisseurs(db_absent) == []
