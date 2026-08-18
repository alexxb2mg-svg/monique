import entrepot
import usage


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_upsert_accumule(tmp_path):
    db = _db(tmp_path)
    usage.compter(
        "secretaire",
        "sonnet",
        "claude_cli",
        "brouillon",
        100,
        50,
        cost_status="included",
        chemin=db,
    )
    usage.compter(
        "secretaire",
        "sonnet",
        "claude_cli",
        "brouillon",
        10,
        5,
        cost_status="included",
        chemin=db,
    )
    t = usage.total("secretaire", db)
    assert t["input_tokens"] == 110 and t["output_tokens"] == 55 and t["calls"] == 2


def test_best_effort_ne_leve_pas(tmp_path):
    usage.compter(
        "a", "m", "p", "t", 1, 1, chemin="Z:/inexistant/x.db"
    )  # doit être avalé
