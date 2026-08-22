"""Point d'entrée unique de l'accueil : Alex dit une intention, Monique décide qui s'en occupe.

Patron repris d'Hermes Agent (vérifié dans leur doc avant de coder) : pas de routage nommé côté
utilisateur, l'agent principal reçoit tout et délègue lui-même. Ici l'intention part au rôle
`chef`, l'orchestrateur — jamais à un persona choisi à la main.
"""

import pytest
from fastapi.testclient import TestClient

import beecham
import serveur
from serveur import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _jamais_la_vraie_inbox(monkeypatch, tmp_path):
    """Garde-fou : aucun test de ce fichier ne doit écrire dans la VRAIE `demandes_alex.md`.

    Ça s'est produit — deux entrées de test se sont retrouvées dans l'inbox d'Alex parce qu'un
    test appelait la route sans mocker le dépôt. Le filet est ici, automatique, plutôt que
    dépendant de la vigilance à chaque nouveau test.
    """
    monkeypatch.setattr(beecham, "DEMANDES", tmp_path / "demandes_alex.md")


def test_l_accueil_propose_de_dire_quelque_chose_a_monique():
    page = client.get("/").text
    assert 'hx-post="/intention"' in page
    assert 'name="intention"' in page


def test_intention_lance_une_mission_chef(monkeypatch):
    """Le rôle n'est PAS choisi par l'utilisateur : tout va à l'orchestrateur."""
    lances = []
    monkeypatch.setattr(beecham, "deposer_demande", lambda t: None)  # jamais la vraie inbox
    monkeypatch.setattr(beecham, "demarrer_mission", lambda consigne: lances.append(consigne) or 1)

    class _FauxThread:
        def __init__(self, target=None, args=(), daemon=None):
            self.args = args
            lances.append(("role", args[1] if len(args) > 1 else None))

        def start(self):
            pass

    monkeypatch.setattr(serveur.threading, "Thread", _FauxThread)

    r = client.post("/intention", data={"intention": "il faudrait pouvoir filtrer les devis"})
    assert r.status_code == 200
    assert "il faudrait pouvoir filtrer les devis" in lances
    assert ("role", "chef") in lances


def test_intention_vide_ne_lance_rien(monkeypatch):
    appels = []
    monkeypatch.setattr(beecham, "demarrer_mission", lambda c: appels.append(c) or 1)

    r = client.post("/intention", data={"intention": "   "})
    assert r.status_code == 200
    assert appels == [], "une intention vide ne doit pas créer de mission"


# --- dépôt dans l'inbox produit -----------------------------------------------------------------


def test_deposer_demande_ecrit_dans_l_inbox(monkeypatch, tmp_path):
    """La demande doit SURVIVRE : une vague ultérieure la reprendra même si aucune boucle ne
    tourne au moment où Alex la formule (patron du Kanban Hermes)."""
    inbox = tmp_path / "demandes_alex.md"
    monkeypatch.setattr(beecham, "DEMANDES", inbox)
    monkeypatch.setattr(beecham, "init_atelier", lambda: tmp_path)

    beecham.deposer_demande("pouvoir filtrer les devis par client")

    contenu = inbox.read_text(encoding="utf-8")
    assert "pouvoir filtrer les devis par client" in contenu
    assert "## Demande du" in contenu  # horodatée, repérable dans le fichier


def test_deposer_demande_ajoute_sans_ecraser(monkeypatch, tmp_path):
    inbox = tmp_path / "demandes_alex.md"
    inbox.write_text("# Demandes existantes\ncontenu déjà là\n", encoding="utf-8")
    monkeypatch.setattr(beecham, "DEMANDES", inbox)
    monkeypatch.setattr(beecham, "init_atelier", lambda: tmp_path)

    beecham.deposer_demande("une nouvelle idée")

    contenu = inbox.read_text(encoding="utf-8")
    assert "contenu déjà là" in contenu, "l'inbox existante ne doit jamais être écrasée"
    assert "une nouvelle idée" in contenu


def test_deposer_demande_est_fail_soft(monkeypatch, tmp_path):
    """Une erreur d'écriture ne doit jamais faire échouer la requête d'Alex."""
    monkeypatch.setattr(beecham, "DEMANDES", tmp_path / "nulle_part" / "x.md")
    monkeypatch.setattr(beecham, "init_atelier", lambda: tmp_path)
    beecham.deposer_demande("ne doit pas lever")


def test_deposer_demande_ignore_le_vide(monkeypatch, tmp_path):
    inbox = tmp_path / "demandes_alex.md"
    monkeypatch.setattr(beecham, "DEMANDES", inbox)
    monkeypatch.setattr(beecham, "init_atelier", lambda: tmp_path)
    beecham.deposer_demande("   ")
    assert not inbox.exists()


def test_l_intention_est_deposee_dans_l_inbox(monkeypatch):
    """Bout en bout : ce qu'Alex tape sur l'accueil atterrit dans l'inbox produit."""
    deposees = []
    monkeypatch.setattr(beecham, "deposer_demande", lambda t: deposees.append(t))
    monkeypatch.setattr(beecham, "demarrer_mission", lambda c: 1)
    monkeypatch.setattr(serveur.threading, "Thread", lambda **kw: type("T", (), {"start": lambda s: None})())

    client.post("/intention", data={"intention": "ajouter un export comptable"})
    assert deposees == ["ajouter un export comptable"]
