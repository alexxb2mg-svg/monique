import json

import pytest

import dolibarr


@pytest.fixture(autouse=True)
def _coffre_isole(tmp_path, monkeypatch):
    # isolation totale : jamais le vrai ~/.monique_secrets de la machine (pourrait
    # contenir une vraie clé Dolibarr) ni le vrai environnement du shell.
    monkeypatch.setattr(dolibarr.Path, "home", lambda: tmp_path)
    monkeypatch.delenv("DOLAPIKEY", raising=False)
    monkeypatch.delenv("DOLIBARR_URL", raising=False)


def _ecrire_coffre(tmp_path, **cles):
    dossier = tmp_path / ".monique_secrets"
    dossier.mkdir(parents=True, exist_ok=True)
    contenu = "\n".join(f"{k}={v}" for k, v in cles.items())
    (dossier / "secretaire.env").write_text(contenu, encoding="utf-8-sig")


class _FausseReponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _urlopen_json(payload):
    def _fake(_req, **_kw):
        return _FausseReponse(json.dumps(payload).encode("utf-8"))

    return _fake


def _urlopen_leve(_req, **_kw):
    raise TimeoutError("connexion refusée")


# --- is_configured() / _cfg() ---------------------------------------------


def test_is_configured_false_sans_env_ni_coffre():
    assert dolibarr.is_configured() is False


def test_precedence_env_sur_coffre(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    monkeypatch.setenv("DOLAPIKEY", "sk-env")
    _, cle = dolibarr._cfg()
    assert cle == "sk-env"


def test_lecture_coffre_seul_sans_env(tmp_path):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    _, cle = dolibarr._cfg()
    assert cle == "sk-fichier"
    assert dolibarr.is_configured() is True


# --- ping() ------------------------------------------------------------


def test_ping_sans_cle_ne_leve_pas():
    r = dolibarr.ping()
    assert r == {
        "ok": False,
        "configured": False,
        "message": "clé Dolibarr absente (coffre .monique_secrets/secretaire.env)",
    }


def test_ping_ok_si_urlopen_repond(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    monkeypatch.setattr(
        dolibarr.urllib.request, "urlopen", _urlopen_json({"success": True})
    )
    r = dolibarr.ping()
    assert r["configured"] is True
    assert r["ok"] is True


def test_ping_pas_ok_si_urlopen_leve(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    monkeypatch.setattr(dolibarr.urllib.request, "urlopen", _urlopen_leve)
    r = dolibarr.ping()
    assert r["configured"] is True
    assert r["ok"] is False


# --- list_devis_a_relancer() / list_factures_impayees() ----------------


def test_list_devis_vide_si_urlopen_leve(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    monkeypatch.setattr(dolibarr.urllib.request, "urlopen", _urlopen_leve)
    assert dolibarr.list_devis_a_relancer() == []


def test_list_factures_vide_si_urlopen_leve(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    monkeypatch.setattr(dolibarr.urllib.request, "urlopen", _urlopen_leve)
    assert dolibarr.list_factures_impayees() == []


def test_list_devis_decode_liste_json(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    payload = [{"ref": "D26070009", "montant": 4120}]
    monkeypatch.setattr(dolibarr.urllib.request, "urlopen", _urlopen_json(payload))
    assert dolibarr.list_devis_a_relancer() == payload


def test_list_factures_decode_liste_json(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    payload = [{"ref": "F26060004", "montant": 1690}]
    monkeypatch.setattr(dolibarr.urllib.request, "urlopen", _urlopen_json(payload))
    assert dolibarr.list_factures_impayees() == payload


def test_list_devis_vide_si_reponse_pas_une_liste(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    monkeypatch.setattr(
        dolibarr.urllib.request, "urlopen", _urlopen_json({"error": "message"})
    )
    assert dolibarr.list_devis_a_relancer() == []


def test_list_factures_vide_si_reponse_pas_une_liste(tmp_path, monkeypatch):
    _ecrire_coffre(tmp_path, DOLAPIKEY="sk-fichier")
    monkeypatch.setattr(
        dolibarr.urllib.request, "urlopen", _urlopen_json({"error": "message"})
    )
    assert dolibarr.list_factures_impayees() == []
