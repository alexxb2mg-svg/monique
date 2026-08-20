"""Tests déterministes de boucle_ponts.implementer_et_corriger — ponts.lancer/extraire_code et
subprocess.run sont mockés (aucun réseau, aucun Chrome, aucun vrai pytest imbriqué)."""

import boucle_ponts
import ponts


class _FauxTest:
    """Simule subprocess.CompletedProcess pour une séquence de résultats de test successifs."""

    def __init__(self, *codes_retour):
        self.codes = list(codes_retour)

    def __call__(self, *a, **k):
        rc = self.codes.pop(0) if self.codes else 0
        return type(
            "R", (), {"returncode": rc, "stdout": f"stdout rc={rc}", "stderr": ""}
        )()


def _mock_gemini_ok(monkeypatch, codes):
    """ponts.lancer('developpeur', ..., nom='gemini') réussit toujours ; ponts.extraire_code
    renvoie successivement les éléments de `codes` (une chaîne par appel)."""
    it = iter(codes)
    monkeypatch.setattr(ponts, "lancer", lambda role, *a, **k: {"ok": True, "texte": "ok", "journal": []})
    monkeypatch.setattr(ponts, "extraire_code", lambda nom: next(it, ""))


def test_succes_du_premier_coup(tmp_path, monkeypatch):
    cible = tmp_path / "cible.py"
    _mock_gemini_ok(monkeypatch, ["def f(): return 1"])
    monkeypatch.setattr(boucle_ponts.subprocess, "run", _FauxTest(0))

    r = boucle_ponts.implementer_et_corriger(str(cible), "une fonction f", ["pytest"], max_essais=3)

    assert r["ok"] is True
    assert r["essais"] == 1
    assert cible.read_text(encoding="utf-8").strip() == "def f(): return 1"


def test_corrige_apres_un_echec(tmp_path, monkeypatch):
    cible = tmp_path / "cible.py"
    _mock_gemini_ok(monkeypatch, ["def f(): return 0  # bug", "def f(): return 1  # corrige"])
    monkeypatch.setattr(boucle_ponts.subprocess, "run", _FauxTest(1, 0))  # échoue puis réussit

    r = boucle_ponts.implementer_et_corriger(str(cible), "une fonction f", ["pytest"], max_essais=3)

    assert r["ok"] is True
    assert r["essais"] == 2
    assert "corrige" in cible.read_text(encoding="utf-8")


def test_echec_definitif_restaure_le_fichier_existant(tmp_path, monkeypatch):
    cible = tmp_path / "cible.py"
    cible.write_text("def f(): return 42  # ORIGINAL\n", encoding="utf-8")
    _mock_gemini_ok(monkeypatch, ["def f(): return 0", "def f(): return 0", "def f(): return 0"])
    monkeypatch.setattr(boucle_ponts.subprocess, "run", _FauxTest(1, 1, 1))  # jamais vert

    r = boucle_ponts.implementer_et_corriger(str(cible), "x", ["pytest"], max_essais=3)

    assert r["ok"] is False
    assert "ORIGINAL" in cible.read_text(encoding="utf-8")  # jamais laissé dans un état pire


def test_echec_definitif_sans_original_supprime_le_fichier(tmp_path, monkeypatch):
    cible = tmp_path / "neuf.py"  # n'existait pas avant l'appel
    _mock_gemini_ok(monkeypatch, ["def f(): return 0", "def f(): return 0"])
    monkeypatch.setattr(boucle_ponts.subprocess, "run", _FauxTest(1, 1))

    r = boucle_ponts.implementer_et_corriger(str(cible), "x", ["pytest"], max_essais=2)

    assert r["ok"] is False
    assert not cible.exists()  # zéro résidu cassé


def test_extraction_vide_ne_corrompt_pas_le_flux_puis_reussit(tmp_path, monkeypatch):
    """Si extraire_code renvoie vide (Gemini n'a pas produit de bloc code), on doit RETENTER une
    implémentation propre au tour suivant, pas envoyer un prompt de correction avec code vide."""
    cible = tmp_path / "cible.py"
    _mock_gemini_ok(monkeypatch, ["", "def f(): return 1"])  # vide puis code valide
    monkeypatch.setattr(boucle_ponts.subprocess, "run", _FauxTest(0))

    r = boucle_ponts.implementer_et_corriger(str(cible), "x", ["pytest"], max_essais=3)

    assert r["ok"] is True
    assert r["essais"] == 2
    assert "return 1" in cible.read_text(encoding="utf-8")


def test_echec_envoi_gemini_est_journalise_et_retente(tmp_path, monkeypatch):
    cible = tmp_path / "cible.py"
    appels = {"n": 0}

    def faux_lancer(role, *a, **k):
        appels["n"] += 1
        if appels["n"] == 1:
            return {"ok": False, "texte": "", "journal": ["timeout"]}
        return {"ok": True, "texte": "ok", "journal": []}

    monkeypatch.setattr(ponts, "lancer", faux_lancer)
    monkeypatch.setattr(ponts, "extraire_code", lambda nom: "def f(): return 1")
    monkeypatch.setattr(boucle_ponts.subprocess, "run", _FauxTest(0))

    r = boucle_ponts.implementer_et_corriger(str(cible), "x", ["pytest"], max_essais=3)

    assert r["ok"] is True
    assert any("échec envoi Gemini" in ligne for ligne in r["journal"])
