"""Vrais tests (écrits à la main, pas par le pont) de vue_ponts.contexte_ponts() — produit par
DeepSeek (mode expert) dans le cadre du test « pipeline complet sur une problématique réelle »."""

import ponts
import vue_ponts


def test_pont_actif_ouvert_et_suivi(monkeypatch):
    monkeypatch.setattr(
        ponts, "etat", lambda: [{"nom": "deepseek", "ouvert": True, "suivi": True, "pid": 1, "descendants": 3, "dernier_usage": None}]
    )
    ctx = vue_ponts.contexte_ponts()
    assert ctx[0]["libelle_etat"] == "actif"


def test_pont_orphelin_ouvert_mais_pas_suivi(monkeypatch):
    monkeypatch.setattr(
        ponts, "etat", lambda: [{"nom": "x", "ouvert": True, "suivi": False, "pid": 1, "descendants": 0, "dernier_usage": None}]
    )
    ctx = vue_ponts.contexte_ponts()
    assert ctx[0]["libelle_etat"] == "orphelin"


def test_pont_ferme(monkeypatch):
    monkeypatch.setattr(
        ponts, "etat", lambda: [{"nom": "x", "ouvert": False, "suivi": False, "pid": None, "descendants": 0, "dernier_usage": None}]
    )
    ctx = vue_ponts.contexte_ponts()
    assert ctx[0]["libelle_etat"] == "ferme"


def test_dernier_usage_none_texte_jamais_utilise(monkeypatch):
    monkeypatch.setattr(
        ponts, "etat", lambda: [{"nom": "x", "ouvert": True, "suivi": True, "pid": 1, "descendants": 0, "dernier_usage": None}]
    )
    ctx = vue_ponts.contexte_ponts()
    assert ctx[0]["dernier_usage_txt"] == "jamais utilise"


def test_dernier_usage_recent_texte_relatif(monkeypatch):
    import time

    il_y_a_5s = time.time() - 5
    monkeypatch.setattr(
        ponts, "etat", lambda: [{"nom": "x", "ouvert": True, "suivi": True, "pid": 1, "descendants": 0, "dernier_usage": il_y_a_5s}]
    )
    ctx = vue_ponts.contexte_ponts()
    assert ctx[0]["dernier_usage_txt"] in ("il y a 5s", "il y a 4s", "il y a 6s")  # tolérance timing


def test_fail_soft_ponts_leve_une_exception(monkeypatch):
    """Si ponts.etat() plante, contexte_ponts() ne doit JAMAIS lever — c'est une vue de monitoring."""

    def _casse():
        raise RuntimeError("superviseur indisponible")

    monkeypatch.setattr(ponts, "etat", _casse)
    assert vue_ponts.contexte_ponts() == []


def test_fail_soft_type_inattendu(monkeypatch):
    """ponts.etat() qui renverrait n'importe quoi (bug ailleurs) ne doit pas planter la vue."""
    monkeypatch.setattr(ponts, "etat", lambda: "pas une liste")
    assert vue_ponts.contexte_ponts() == []


def test_ne_mute_pas_lentree_originale(monkeypatch):
    original = {"nom": "x", "ouvert": True, "suivi": True, "pid": 1, "descendants": 0, "dernier_usage": None}
    monkeypatch.setattr(ponts, "etat", lambda: [original])
    vue_ponts.contexte_ponts()
    assert "libelle_etat" not in original  # copie, pas mutation de l'objet source
