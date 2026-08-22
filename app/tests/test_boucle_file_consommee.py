"""La file de vague doit être CONSOMMÉE à la lecture, pas seulement lue.

Bug réel du 20/08 : `planifier()` lisait `file_attente.json` sans jamais le retirer. Quand le chef
ne réécrivait rien (mission « livré, rien à fusionner »), la vague suivante rejouait la file
précédente à l'identique — 10 vagues jumelles entre 02:33 et 03:02, 40 missions pour rien — et
`vides >= 2` ne pouvait jamais se déclencher puisque la file n'était jamais vide.
"""

import json

import beecham
from harnais import boucle


def _preparer(tmp_path, monkeypatch, contenu):
    """Chef muet : il tourne mais n'écrit rien — exactement le cas qui déclenchait le rejeu."""
    monkeypatch.setattr(boucle, "ATELIER", tmp_path)
    monkeypatch.setattr(boucle, "INCIDENTS", tmp_path / "incidents.jsonl")  # rien dans le vrai atelier
    monkeypatch.setattr(boucle, "_echecs_recents", lambda: "")
    monkeypatch.setattr(beecham, "demarrer_mission", lambda consigne: 1)
    monkeypatch.setattr(beecham, "executer_mission", lambda mid, role=None: None)
    (tmp_path / "file_attente.json").write_text(contenu, encoding="utf-8")


def test_deux_vagues_sans_reecriture_du_chef_ne_rejouent_pas(tmp_path, monkeypatch):
    _preparer(
        tmp_path,
        monkeypatch,
        json.dumps([{"agent": "developpeur", "consigne": "faire X", "fichiers": ["app/x.py"]}]),
    )

    premier = boucle.planifier(1)
    second = boucle.planifier(2)

    assert [m["consigne"] for m in premier] == ["faire X"]
    assert second == []  # le chef n'a rien réécrit -> vague à vide, pas un rejeu
    assert not (tmp_path / "file_attente.json").exists()
    assert (tmp_path / "file_attente.1.consommee.json").exists()  # trace gardée


def test_file_illisible_consommee_aussi(tmp_path, monkeypatch):
    """Sinon une file corrompue se relit en boucle sans jamais rendre de mission ni de tour à vide."""
    _preparer(tmp_path, monkeypatch, "{ pas du json")

    assert boucle.planifier(1) == []
    assert not (tmp_path / "file_attente.json").exists()
