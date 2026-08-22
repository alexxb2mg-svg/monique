"""Ce qu'une mission produit de cher et jetait jusqu'ici : sa CONSOMMATION et le VERDICT complet.

A — l'usage réel de la session claude (événement `result` du flux stream-json) doit arriver dans
    `secw_model_usage` ; aucune mission Beecham n'y écrivait, les coûts étaient calculés à la main.
B — la raison du contrôleur (2 500 à 5 000 caractères) n'était stockée nulle part : `executions`
    n'en garde que 200. Elle est désormais écrite ENTIÈRE dans atelier/verdicts/<mission>.md.

Dans les deux cas, la comptabilité ne doit JAMAIS faire échouer une mission.
"""

import json
import sqlite3
import subprocess
from pathlib import Path

import beecham
import brief
import config
import entrepot
from fastapi.testclient import TestClient
from serveur import app


# --- A : la consommation --------------------------------------------------------------------

_USAGE = {
    "input_tokens": 10,
    "output_tokens": 120,
    "cache_creation_input_tokens": 22366,
    "cache_read_input_tokens": 16036,
}


def _flux(evenements):
    return "\n".join(json.dumps(e) for e in evenements)


def _popen_qui_repond(stdout):
    def faux_popen(cmd, **kwargs):
        class FauxProc:
            pid = 424242
            returncode = 0

            def communicate(self, input=None, timeout=None):
                return (stdout, "")

            def kill(self):
                pass

        return FauxProc()

    return faux_popen


def _session_claude(tmp_path, monkeypatch, stdout):
    """Lance `_lancer_agent` sans jamais lancer claude, sur une base jetable. Renvoie son résultat."""
    import superviseur

    garde = tmp_path / "garde"
    garde.mkdir()
    (garde / "garde.py").write_text("# garde", encoding="utf-8")
    (garde / "settings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(beecham, "GARDE_DIR", garde)
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    monkeypatch.setattr(beecham, "DB_COURRIER", tmp_path / "nulle_part" / "c.sqlite")
    monkeypatch.setattr(beecham, "DB_COORDINATION", tmp_path / "nulle_part" / "f.sqlite")
    monkeypatch.setattr(superviseur, "enregistrer", lambda *a, **k: None)
    monkeypatch.setattr(superviseur, "finir", lambda *a, **k: None)
    monkeypatch.setattr(beecham.subprocess, "Popen", _popen_qui_repond(stdout))
    return beecham._lancer_agent(
        "developpeur", "fais X", tmp_path, _relancer_rapport=False, modele="claude-haiku-4-5-20251001"
    )


def _base_jetable(tmp_path, monkeypatch):
    """La write-DB du mode test pointe vers tmp — `usage.compter` n'a pas d'argument `chemin` ici."""
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    monkeypatch.setattr(config, "SHADOW", db)
    return db


def _ligne_usage(db):
    con = entrepot.connexion_ecriture(db)
    try:
        return con.execute("SELECT * FROM secw_model_usage").fetchall()
    finally:
        con.close()


def test_usage_de_la_session_arrive_en_base(tmp_path, monkeypatch):
    """L'usage émis par la CLI atterrit dans secw_model_usage, cache_read compris (poste dominant :
    16 036 tokens contre 10 d'input sur la mesure de référence). Sans ce test, on peut retirer
    l'appel à usage.compter et garder tout le reste vert — retour à l'optimisation à l'aveugle."""
    db = _base_jetable(tmp_path, monkeypatch)
    flux = _flux(
        [
            {"type": "system", "session_id": "SID-1"},
            {"type": "result", "result": "fait", "usage": _USAGE, "total_cost_usd": 0.048},
        ]
    )
    res = _session_claude(tmp_path, monkeypatch, flux)
    assert res["ok"]

    lignes = _ligne_usage(db)
    assert len(lignes) == 1
    l = lignes[0]
    assert l["agent"] == "beecham:developpeur"  # le rôle reste distinguable dans la clé agrégée
    assert l["model"] == "claude-haiku-4-5-20251001"  # ...et le modèle aussi (Haiku vs Opus)
    assert l["input_tokens"] == 10 + 22366  # création de cache comptée avec l'input (pas de colonne)
    assert l["output_tokens"] == 120
    assert l["cache_read_tokens"] == 16036
    assert l["calls"] == 1
    assert abs(l["estimated_cost_usd"] - 0.048) < 1e-9


def test_flux_sans_usage_ne_fait_pas_echouer_la_mission(tmp_path, monkeypatch):
    """Fail-soft : `result` sans `usage` (ou malformé) => aucune ligne, mais la mission passe."""
    db = _base_jetable(tmp_path, monkeypatch)
    flux = _flux(
        [
            {"type": "result", "result": "fait"},
            {"type": "result", "result": "fait", "usage": "pas un objet"},
        ]
    )
    res = _session_claude(tmp_path, monkeypatch, flux)
    assert res["ok"]
    assert res["texte"] == "fait"
    assert _ligne_usage(db) == []


# --- B : le verdict complet -----------------------------------------------------------------


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _repo(tmp_path):
    repo = tmp_path / "monique"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "test_smoke.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo


def _mission_rejetee(tmp_path, monkeypatch, raison, atelier=None):
    """Une mission dont le contrôleur rejette le travail — renvoie (mission_id, atelier)."""
    repo = _repo(tmp_path)
    atelier = atelier or tmp_path / "atelier"
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    monkeypatch.setattr(beecham, "ATELIER", atelier)
    monkeypatch.setattr(beecham, "MEMOIRE", atelier / "memoire")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("mission à verdict", db)

    def agent(role, consigne, worktree, reprendre=None, modele=None):
        (Path(worktree) / "app" / "x.py").write_text("Y = 1\n", encoding="utf-8")
        return {"ok": True, "journal": [], "texte": "fait"}

    def controleur(scope, diff, tests_resume, worktree):
        return {"verdict": "rejeter", "raison": raison}

    r = beecham.executer_mission(mid, chemin=db, _agent=agent, _controleur=controleur)
    return mid, atelier, r


def test_verdict_ecrit_en_entier_jamais_tronque(tmp_path, monkeypatch):
    """La raison complète est conservée : `executions.finir` n'en garde que 200 caractères, et il a
    fallu RELANCER un contrôleur entier le 22/08 pour relire un verdict déjà produit."""
    raison = "VERDICT: REJETÉ\n" + "détail de la démonstration. " * 40 + "\nFIN-DU-VERDICT"
    assert len(raison) > 200
    mid, atelier, r = _mission_rejetee(tmp_path, monkeypatch, raison)
    assert r["statut"] == "rejete"

    fichier = atelier / "verdicts" / f"{mid}.md"
    contenu = fichier.read_text(encoding="utf-8")
    assert "FIN-DU-VERDICT" in contenu  # la QUEUE est là : rien n'a été coupé à 200 caractères
    assert raison in contenu
    assert "rejeter" in contenu and "developpeur" in contenu  # en-tête : verdict + rôle


def test_echec_ecriture_du_verdict_ne_casse_pas_la_mission(tmp_path, monkeypatch):
    """`atelier/verdicts` occupé par un FICHIER : l'écriture est impossible, la mission aboutit
    quand même (fail-soft, même principe que journal_ajouter)."""
    atelier = tmp_path / "atelier"
    (atelier / "memoire").mkdir(parents=True)
    (atelier / "verdicts").write_text("je ne suis pas un dossier", encoding="utf-8")
    _mid, _atelier, r = _mission_rejetee(tmp_path, monkeypatch, "peu importe", atelier=atelier)
    assert r["statut"] == "rejete"


# --- B (suite) : l'accueil montre POURQUOI ----------------------------------------------------

_BRIEF = {
    "mails_a_traiter": 0,
    "relances": 0,
    "taches_retard": 0,
    "phrase": "rien de spécial",
    "systeme": {"vivants": 1, "orphelins": 0, "noms": []},
    "chantier": {
        "disponible": True,
        "en_cours": [],
        "fusionnes": [],
        "compte": {"en_cours": 0, "fusionnes": 0, "rates": 1},
    },
}


def test_accueil_montre_la_raison_d_une_mission_bloquee(monkeypatch):
    """Une mission bloquée était comptée dans « rejetés / échecs » sans un mot. Elle doit dire
    pourquoi, sur l'accueil, sans nouvelle page."""
    monkeypatch.setattr(brief, "construire", lambda: _BRIEF)
    monkeypatch.setattr(
        beecham,
        "missions_bloquees",
        lambda: [{"id": "m1", "sujet": "brancher le comparateur", "raison": "RAISON-DU-BLOCAGE"}],
    )
    r = TestClient(app).get("/vue/jour")
    assert r.status_code == 200
    assert "brancher le comparateur" in r.text
    assert "RAISON-DU-BLOCAGE" in r.text


def test_accueil_sans_mission_bloquee_n_affiche_rien(monkeypatch):
    monkeypatch.setattr(brief, "construire", lambda: _BRIEF)
    monkeypatch.setattr(beecham, "missions_bloquees", lambda: [])
    r = TestClient(app).get("/vue/jour")
    assert r.status_code == 200
    assert "Bloqué —" not in r.text


def _qui_leve(*a, **k):
    raise sqlite3.OperationalError("database is locked")


def test_missions_bloquees_ne_leve_jamais_sur_un_chemin_de_rendu(tmp_path, monkeypatch):
    """SPEC §16 : jamais un 500 sur une vue. Deux étages vérifiés séparément —
    un verdict illisible ne coûte QUE sa raison (UnicodeDecodeError n'est pas une OSError, le
    piège) ; une source cassée rend une liste vide au lieu de faire tomber l'accueil."""
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    monkeypatch.setattr(config, "SHADOW", db)
    atelier = tmp_path / "atelier"
    monkeypatch.setattr(beecham, "ATELIER", atelier)
    mid = beecham.demarrer_mission("mission illisible", db)
    beecham._maj(mid, db, statut="bloque")
    (atelier / "verdicts").mkdir(parents=True)
    (atelier / "verdicts" / f"{mid}.md").write_bytes(b"\xff\xfe pas de l'utf-8 \x00\x9c")

    bloquees = beecham.missions_bloquees()
    assert [b["id"] for b in bloquees] == [mid]  # la mission reste affichée...
    assert bloquees[0]["raison"] == ""  # ...seule sa raison manque

    monkeypatch.setattr(beecham, "lister_missions", _qui_leve)
    assert beecham.missions_bloquees() == []  # source cassée : liste vide, jamais d'exception


def test_accueil_reste_debout_si_la_source_des_bloquees_casse(monkeypatch):
    """Le garde-fou est branché sur le VRAI chemin de rendu : le gabarit appelle la fonction."""
    monkeypatch.setattr(brief, "construire", lambda: _BRIEF)
    monkeypatch.setattr(beecham, "lister_missions", _qui_leve)
    r = TestClient(app).get("/vue/jour")
    assert r.status_code == 200
    assert "Bloqué —" not in r.text


def test_missions_bloquees_lit_le_verdict_ecrit(tmp_path, monkeypatch):
    """Bout en bout de l'affichage : la liste servie à l'accueil lit bien le fichier de verdict."""
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    monkeypatch.setattr(config, "SHADOW", db)
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    mid = beecham.demarrer_mission("brancher le comparateur", db)
    beecham._maj(mid, db, statut="bloque")
    beecham.ecrire_verdict(mid, "controleur", "corriger", "il manque le cas vide")

    bloquees = beecham.missions_bloquees()
    assert [b["id"] for b in bloquees] == [mid]
    assert "il manque le cas vide" in bloquees[0]["raison"]
    assert "brancher le comparateur" in bloquees[0]["sujet"]
