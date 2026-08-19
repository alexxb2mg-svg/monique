from fastapi.testclient import TestClient

import boite
import overlays
import serveur


def test_detail_montre_brouillon(monkeypatch, tmp_path):
    monkeypatch.setattr(
        boite,
        "lire_boite",
        lambda **k: [
            {
                "id": 7,
                "source": "gmail",
                "apercu": "Question devis",
                "timestamp": "…",
                "traite": False,
            }
        ],
    )
    monkeypatch.setattr(
        overlays,
        "lire_brouillon",
        lambda eid, chemin=None: {
            "id": "b7",
            "brouillon": "Bonjour…",
            "contexte": "ctx",
            "attendu": ["valider"],
            "hors": [],
            "statut": "propose",
        },
    )
    r = TestClient(serveur.app).get("/boite/7")
    assert r.status_code == 200 and "Bonjour" in r.text and "valider" in r.text


def test_detail_montre_le_message_integral_pas_seulement_lapercu(monkeypatch):
    # revue backlog Alex D-6 : « affiche des clés/identifiants, pas l'échange lui-même » —
    # le détail doit rendre le texte COMPLET (lire_event), pas les 140/60 caractères de l'aperçu.
    message_complet = ("x" * 150) + "FIN DU MESSAGE COMPLET"
    monkeypatch.setattr(
        boite,
        "lire_boite",
        lambda **k: [
            {
                "id": 42,
                "source": "gmail",
                "apercu": "Question devis",
                "timestamp": "…",
                "traite": False,
            }
        ],
    )
    monkeypatch.setattr(
        boite,
        "lire_event",
        lambda event_id, chemin=None: {
            "id": 42,
            "source": "gmail",
            "contenu": message_complet,
            "status": "nouveau",
            "timestamp": "…",
            "traite": False,
        },
    )
    monkeypatch.setattr(overlays, "lire_brouillon", lambda eid, chemin=None: None)
    r = TestClient(serveur.app).get("/boite/42")
    assert r.status_code == 200
    assert "FIN DU MESSAGE COMPLET" in r.text


def test_detail_sans_brouillon_propose_amorcer(monkeypatch):
    monkeypatch.setattr(
        boite,
        "lire_boite",
        lambda **k: [
            {
                "id": 8,
                "source": "gmail",
                "apercu": "Question devis",
                "timestamp": "…",
                "traite": False,
            }
        ],
    )
    monkeypatch.setattr(overlays, "lire_brouillon", lambda eid, chemin=None: None)
    r = TestClient(serveur.app).get("/boite/8")
    assert r.status_code == 200 and "Amorcer un brouillon" in r.text
    assert 'hx-post="/boite/8/amorcer"' in r.text


def test_dispatcher_generique_appelle_le_handler_enregistre(monkeypatch):
    monkeypatch.setattr(
        boite,
        "lire_boite",
        lambda **k: [
            {
                "id": 9,
                "source": "gmail",
                "apercu": "x",
                "timestamp": "…",
                "traite": False,
            }
        ],
    )
    monkeypatch.setattr(overlays, "lire_brouillon", lambda eid, chemin=None: None)

    appele = {}

    def _handler(**k):
        appele.update(k)
        return {"fait": True}

    serveur.actions_mod.enregistrer(
        serveur.actions_mod.Action("marquer", "Marquer", handler=_handler)
    )
    try:
        r = TestClient(serveur.app).post("/boite/9/marquer")
        assert r.status_code == 200
        assert appele == {"event_id": 9}
    finally:
        serveur.actions_mod.registre.pop("marquer", None)


def test_dispatcher_generique_ignore_les_noms_reserves(monkeypatch):
    # revue red-team M5 : "amorcer"/"parler" ne doivent JAMAIS être traités comme une
    # action générique du registre, même si on les y enregistrait par erreur.
    monkeypatch.setattr(boite, "lire_boite", lambda **k: [])
    monkeypatch.setattr(overlays, "lire_brouillon", lambda eid, chemin=None: None)

    piege = {"appele": False}

    def _piege(**k):
        piege["appele"] = True

    serveur.actions_mod.enregistrer(
        serveur.actions_mod.Action("amorcer", "x", handler=_piege)
    )
    try:
        # appel direct de la fonction handler (contourne volontairement le routage FastAPI,
        # pour prouver que le GARDE EXPLICITE protège même hors ordre de déclaration des routes)
        from fastapi import HTTPException

        try:
            serveur.action_generique(request=None, event_id=1, nom="amorcer")
            assert False, "devait lever 404"
        except HTTPException as e:
            assert e.status_code == 404
        assert piege["appele"] is False
    finally:
        serveur.actions_mod.registre.pop("amorcer", None)
