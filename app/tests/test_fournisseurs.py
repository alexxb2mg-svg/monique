import pytest

import entrepot
import usage
import fournisseurs as F


def test_coffre_roundtrip(tmp_path):
    coffre = tmp_path / ".monique_secrets"
    F.ecrire_cle("OPENAI_API_KEY", "sk-abc", coffre)
    assert F.lire_cle("OPENAI_API_KEY", coffre) == "sk-abc"


def test_coffre_refuse_injection_de_ligne(tmp_path):
    # revue C : une valeur contenant un saut de ligne ne doit PAS écrire une seconde clé
    coffre = tmp_path / ".monique_secrets"
    with pytest.raises(ValueError):
        F.ecrire_cle("AUTRE_CLE", "val\nOPENAI_API_KEY=sk-attaquant", coffre)
    # rien écrit : la clé cible n'existe pas, pas de contournement
    assert F.lire_cle("OPENAI_API_KEY", coffre) is None
    assert F.lire_cle("AUTRE_CLE", coffre) is None


def test_coffre_refuse_env_var_non_canonique(tmp_path):
    coffre = tmp_path / ".monique_secrets"
    with pytest.raises(ValueError):
        F.ecrire_cle("PATH; rm -rf", "poison", coffre)
    with pytest.raises(ValueError):
        F.ecrire_cle("bad=name", "x", coffre)


def test_cle_env_prioritaire(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    assert F.lire_cle("OPENAI_API_KEY", tmp_path / "vide") == "sk-env"


def test_usage_affiche(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    usage.compter(
        "secretaire",
        "sonnet",
        "claude_cli",
        "brouillon",
        100,
        40,
        cost_status="included",
        chemin=db,
    )
    u = F.usage_par_agent("secretaire", db)
    assert u["input_tokens"] == 100 and u["calls"] == 1
