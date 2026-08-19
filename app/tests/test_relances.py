import pytest

import relances


@pytest.fixture(autouse=True)
def _vide_cache_relances():
    # le cache 60s de etat() persiste au niveau module -> le vider avant chaque test,
    # sinon un test récupère le résultat caché du précédent.
    relances._CACHE["v"] = None
    yield


class FauxDoli:
    def __init__(self, ok):
        self._ok = ok

    def is_configured(self):
        return self._ok

    def ping(self):
        return {"ok": self._ok, "message": "ok" if self._ok else "no key"}

    def list_devis_a_relancer(self, **k):
        return [{"ref": "D26070009", "montant": 4120}]

    def list_factures_impayees(self, **k):
        return [{"ref": "F26060004", "montant": 1690}]


def test_relances_disponible(monkeypatch):
    monkeypatch.setattr(relances, "doli", FauxDoli(True))
    e = relances.etat()
    assert e["disponible"] is True
    assert e["devis"][0]["ref"] == "D26070009"
    assert e["factures"][0]["ref"] == "F26060004"


def test_relances_indisponible_sans_crash(monkeypatch):
    monkeypatch.setattr(relances, "doli", FauxDoli(False))
    e = relances.etat()
    assert e["disponible"] is False
    assert e["devis"] == [] and e["factures"] == []
    assert "no key" in e["message"]
