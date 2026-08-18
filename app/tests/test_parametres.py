import entrepot
import parametres
import config


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_definir_puis_lire(tmp_path):
    db = _db(tmp_path)
    parametres.definir("secretaire.veille_freq", "1x/jour", db)
    assert parametres.lire("secretaire.veille_freq", db) == "1x/jour"


def test_cfg_get_prend_le_parametre(tmp_path, monkeypatch):
    db = _db(tmp_path)
    # _param_shadow lit chemin_ecriture() en mode=ro (write-DB du mode courant) : patcher
    # ce seul point suffit — plus de config.SHADOW en dur (correctif du lead de revue).
    monkeypatch.setattr(config, "chemin_ecriture", lambda: db)
    monkeypatch.delenv("SECRETAIRE_VEILLE_FREQ", raising=False)
    parametres.definir("secretaire.veille_freq", "3x/jour", db)
    assert config.cfg_get("secretaire", "veille_freq", "2x/jour") == "3x/jour"


def test_mode_ne_recurse_pas(
    monkeypatch,
):  # revue B1 : garde anti-récursion, NON patché
    monkeypatch.delenv("SECRETAIRE_MODE", raising=False)
    assert config.mode() in ("test", "prod")  # ne doit pas lever RecursionError


def test_cfg_get_ne_recurse_pas_chemin_complet(monkeypatch):
    # revue : la trace cfg_get -> _param_shadow -> chemin_ecriture -> mode -> cfg_get(systeme.mode)
    # doit se fermer sur la garde systeme.mode, sans aucun patch (pire cas : env mode absente).
    monkeypatch.delenv("SECRETAIRE_MODE", raising=False)
    monkeypatch.delenv("SECRETAIRE_VEILLE_FREQ", raising=False)
    config.cfg_get("secretaire", "veille_freq", "x")  # ne doit pas lever RecursionError
