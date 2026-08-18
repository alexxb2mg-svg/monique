import config


def test_mode_defaut_test(monkeypatch):
    monkeypatch.delenv("SECRETAIRE_MODE", raising=False)
    assert config.mode() == "test"


def test_ecriture_shadow_en_test(monkeypatch):
    monkeypatch.delenv("SECRETAIRE_MODE", raising=False)
    assert config.chemin_ecriture().endswith("monique_shadow.db")
    assert config.chemin_ecriture() != config.chemin_lecture()


def test_ecriture_reel_en_prod(monkeypatch):
    monkeypatch.setenv("SECRETAIRE_MODE", "prod")
    assert config.chemin_ecriture() == config.chemin_lecture()


def test_cfg_get_defaut_code(monkeypatch):
    monkeypatch.delenv("SECRETAIRE_MODE", raising=False)
    assert config.cfg_get("systeme", "mode", "test") in ("test", "prod")
