"""Vrais tests (écrits avant toute réponse du pont) pour sonde_ponts.interpreter_rapport."""

import sonde_ponts


def test_parse_nominal():
    r = sonde_ponts.interpreter_rapport("textarea=1\nbouton_mode=3\nbouton_envoi=0\n")
    assert r["noms_ok"] == ["textarea", "bouton_mode"]
    assert r["noms_manquants"] == ["bouton_envoi"]


def test_ignore_lignes_vides():
    r = sonde_ponts.interpreter_rapport("textarea=1\n\n\nbouton=1\n")
    assert r["noms_ok"] == ["textarea", "bouton"]


def test_ignore_lignes_mal_formees():
    r = sonde_ponts.interpreter_rapport("textarea=1\npas_de_signe_egal\nbouton=abc\nvalide=2\n")
    assert r["noms_ok"] == ["textarea", "valide"]
    assert r["noms_manquants"] == []


def test_entree_vide():
    r = sonde_ponts.interpreter_rapport("")
    assert r == {"noms_ok": [], "noms_manquants": []}


def test_tous_manquants():
    r = sonde_ponts.interpreter_rapport("a=0\nb=0\n")
    assert r["noms_ok"] == []
    assert r["noms_manquants"] == ["a", "b"]
