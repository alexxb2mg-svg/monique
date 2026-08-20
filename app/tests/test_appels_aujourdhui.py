"""Vrais tests (avant dispatch) pour journal_ponts.appels_aujourdhui — plafond PERSISTANT (le
journal survit aux redémarrages de process, contrairement à un compteur en mémoire)."""

import json
import time

import journal_ponts


def _ligne(pont, horodatage):
    return json.dumps({"pont": pont, "horodatage": horodatage, "ok": True}) + "\n"


def test_compte_seulement_les_appels_du_jour_pour_ce_pont(tmp_path):
    chemin = tmp_path / "journal.jsonl"
    aujourdhui = time.strftime("%Y-%m-%d")
    chemin.write_text(
        _ligne("deepseek", f"{aujourdhui}T10:00:00")
        + _ligne("deepseek", f"{aujourdhui}T11:00:00")
        + _ligne("deepseek", "2020-01-01T10:00:00")  # un autre jour -> pas compté
        + _ligne("gemini", f"{aujourdhui}T10:00:00"),  # un autre pont -> pas compté
        encoding="utf-8",
    )
    assert journal_ponts.appels_aujourdhui("deepseek", chemin=str(chemin)) == 2


def test_fichier_absent_renvoie_zero(tmp_path):
    assert journal_ponts.appels_aujourdhui("deepseek", chemin=str(tmp_path / "absent.jsonl")) == 0
