"""Porte de sortie sur le rapport de fin de mission (D-15).

Format des 4 rubriques repris d'Hermes Agent (contrat de sortie de leurs sous-agents : tasks
performed / results found / files modified / issues encountered) plutôt qu'inventé ici.
"""

import beecham
import contrats

_RAPPORT_OK = (
    "FAIT : ajout du module\n"
    "RESULTAT : les tests passent\n"
    "FICHIERS : app/x.py\n"
    "PROBLEMES : aucun"
)


def test_rapport_complet_passe():
    assert contrats.valider_rapport_mission(_RAPPORT_OK) == (True, "")


def test_rapport_tolere_les_decorations_du_llm():
    """Leçon reference_ponts_format_parsable : un LLM décore (gras, puces, titres, accents)."""
    for variante in [
        "**FAIT** : a\n- **RÉSULTAT** : b\nFICHIERS - c\nPROBLÈMES : d",
        "## FAIT : a\n## RESULTAT : b\n## FICHIERS : c\n## PROBLEMES : d",
        "fait: a\nresultat: b\nfichiers: c\nproblemes: d",
    ]:
        ok, raison = contrats.valider_rapport_mission(variante)
        assert ok is True, f"aurait dû accepter : {variante!r} ({raison})"


def test_rapport_en_prose_libre_est_refuse():
    ok, raison = contrats.valider_rapport_mission("J'ai ajouté le module et les tests passent.")
    assert ok is False
    assert "FAIT" in raison


def test_rubrique_manquante_est_nommee():
    ok, raison = contrats.valider_rapport_mission(
        "FAIT : a\nRESULTAT : b\nFICHIERS : c"
    )
    assert ok is False
    assert "PROBLEMES" in raison


def test_rubrique_vide_naspire_pas_la_ligne_suivante():
    """Bug réel attrapé au test avant livraison : `\\s*` après le séparateur traversait le saut de
    ligne, donc une rubrique laissée vide absorbait la suivante et passait pour remplie."""
    ok, raison = contrats.valider_rapport_mission(
        "FAIT :\nRESULTAT : b\nFICHIERS : c\nPROBLEMES : d"
    )
    assert ok is False
    assert "FAIT" in raison


def test_rapport_vide_refuse():
    assert contrats.valider_rapport_mission("")[0] is False
    assert contrats.valider_rapport_mission("   ")[0] is False


def test_porte_laisse_passer_un_rapport_conforme():
    journal = []
    texte, journal_final = beecham._porte_rapport(
        "developpeur", _RAPPORT_OK, "/wt", "sess-1", journal, True
    )
    assert texte == _RAPPORT_OK
    assert journal_final == []  # rien à signaler


def test_porte_relance_sur_rapport_non_conforme(monkeypatch):
    """L'agent est renvoyé à SA session (--resume) avec le motif exact, sans refaire le travail."""
    appels = []

    def faux_lancer(role, consigne, worktree, reprendre=None, _relancer_rapport=True, modele=None):
        appels.append({"consigne": consigne, "reprendre": reprendre, "relancer": _relancer_rapport})
        return {"ok": True, "journal": ["relance"], "texte": _RAPPORT_OK, "session_id": reprendre}

    monkeypatch.setattr(beecham, "_lancer_agent", faux_lancer)
    texte, journal = beecham._porte_rapport(
        "developpeur", "juste une phrase", "/wt", "sess-1", [], True
    )

    assert len(appels) == 1
    assert appels[0]["reprendre"] == "sess-1"  # reprise, pas une session à froid
    assert appels[0]["relancer"] is False  # pas de boucle de relance
    assert "refusé" in appels[0]["consigne"] or "refuse" in appels[0]["consigne"]
    assert "AUCUN travail" in appels[0]["consigne"]  # ne pas refaire le travail
    assert texte == _RAPPORT_OK
    assert any("porte de sortie" in ligne for ligne in journal)


def test_porte_ne_jette_pas_la_mission_si_la_relance_echoue(monkeypatch):
    """Un rapport mal formé ne doit pas faire perdre un travail qui peut être bon : la porte
    signale, elle ne détruit pas."""

    def faux_lancer(role, consigne, worktree, reprendre=None, _relancer_rapport=True, modele=None):
        return {"ok": True, "journal": [], "texte": "toujours pas conforme", "session_id": reprendre}

    monkeypatch.setattr(beecham, "_lancer_agent", faux_lancer)
    texte, journal = beecham._porte_rapport("developpeur", "prose", "/wt", "sess-1", [], True)

    assert texte == "toujours pas conforme"  # le résultat n'est pas jeté
    assert any("toujours non conforme" in ligne for ligne in journal)  # mais c'est signalé


def test_porte_ne_relance_pas_sans_session_id():
    texte, journal = beecham._porte_rapport("developpeur", "prose", "/wt", None, [], True)
    assert texte == "prose"
    assert any("non relancé" in ligne for ligne in journal)


def test_les_agents_recoivent_la_consigne_de_format():
    """Garde-fou contre la porte injuste : refuser un format qu'on n'a jamais demandé."""
    for rubrique in contrats.RUBRIQUES_RAPPORT:
        assert rubrique in beecham._CONSIGNE_RAPPORT
    assert "vérifié automatiquement" in beecham._CONSIGNE_RAPPORT
