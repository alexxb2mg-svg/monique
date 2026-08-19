import httpx

import entrepot
import cerveau
import estop
import fournisseurs
import superviseur
import tarifs


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


PROF = cerveau.ProviderProfile(nom="claude", mode="claude_cli", model="sonnet")
PROF_OPENAI_COMPAT = cerveau.ProviderProfile(
    nom="openai_compat",
    mode="openai_compat",
    model="gpt-x",
    base_url="http://exemple.test",
    env_var="OPENAI_API_KEY",
)


class _ReponseFausse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_appel_claude_cli_compte_usage(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(estop, "engage", lambda: False)
    monkeypatch.setattr(
        cerveau,
        "_lancer_claude_cli",
        lambda prompt, system, prof, agent=None, task=None: {
            "texte": "Bonjour",
            "input_tokens": 12,
            "output_tokens": 3,
        },
    )
    r = cerveau.appeler("secretaire", "salut", PROF, "brouillon", chemin=db)
    assert r["ok"] and r["texte"] == "Bonjour"
    con = entrepot.connexion_ecriture(db)
    try:
        c = con.execute(
            "SELECT calls, input_tokens, estimated_cost_usd FROM secw_model_usage"
            " WHERE agent='secretaire'"
        ).fetchone()
    finally:
        con.close()
    assert c["calls"] == 1 and c["input_tokens"] == 12
    attendu = tarifs.estimer_cout_usd("sonnet", 12, 3)
    assert c["estimated_cost_usd"] > 0
    assert c["estimated_cost_usd"] == attendu


def test_estop_bloque(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(estop, "engage", lambda: True)
    r = cerveau.appeler("secretaire", "salut", PROF, "brouillon", chemin=db)
    assert r["ok"] is False and r["erreur"] == "estop"


def test_classifier_erreur():
    assert cerveau.classifier_erreur("HTTP 429 rate limit exceeded") == "rate_limit"
    assert cerveau.classifier_erreur("overloaded_error 529") == "overloaded"
    assert cerveau.classifier_erreur("tout va bien") == "ok"


def test_openai_compat_succes(monkeypatch):
    monkeypatch.setattr(fournisseurs, "lire_cle", lambda env_var, coffre=None: "cle-test")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, headers=None, json=None, timeout=None: _ReponseFausse(
            200,
            {
                "choices": [{"message": {"content": "Bonjour"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            },
        ),
    )
    r = cerveau._lancer_openai_compat("salut", None, PROF_OPENAI_COMPAT)
    assert r == {
        "ok": True,
        "texte": "Bonjour",
        "input_tokens": 10,
        "output_tokens": 4,
    }


def test_openai_compat_cle_absente(monkeypatch):
    monkeypatch.setattr(fournisseurs, "lire_cle", lambda env_var, coffre=None: None)
    r = cerveau._lancer_openai_compat("salut", None, PROF_OPENAI_COMPAT)
    assert r == {"ok": False, "erreur": "cle_absente", "texte": ""}


def test_openai_compat_http_erreur(monkeypatch):
    monkeypatch.setattr(fournisseurs, "lire_cle", lambda env_var, coffre=None: "cle-test")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, headers=None, json=None, timeout=None: _ReponseFausse(500),
    )
    r = cerveau._lancer_openai_compat("salut", None, PROF_OPENAI_COMPAT)
    assert r == {"ok": False, "erreur": "http_500", "texte": ""}


def test_appeler_route_vers_openai_compat(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(estop, "engage", lambda: False)
    monkeypatch.setattr(
        cerveau,
        "_lancer_openai_compat",
        lambda prompt, system, prof: {
            "ok": True,
            "texte": "Bonjour",
            "input_tokens": 10,
            "output_tokens": 4,
        },
    )
    r = cerveau.appeler(
        "secretaire", "salut", PROF_OPENAI_COMPAT, "brouillon", chemin=db
    )
    assert r["ok"] and r["texte"] == "Bonjour"
    con = entrepot.connexion_ecriture(db)
    try:
        c = con.execute(
            "SELECT calls, input_tokens FROM secw_model_usage WHERE agent='secretaire'"
        ).fetchone()
    finally:
        con.close()
    assert c["calls"] == 1 and c["input_tokens"] == 10


def test_appeler_modele_non_tarife_cost_status_unknown(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(estop, "engage", lambda: False)
    monkeypatch.setattr(
        cerveau,
        "_lancer_openai_compat",
        lambda prompt, system, prof: {
            "ok": True,
            "texte": "Bonjour",
            "input_tokens": 10,
            "output_tokens": 4,
        },
    )
    r = cerveau.appeler(
        "secretaire", "salut", PROF_OPENAI_COMPAT, "brouillon", chemin=db
    )
    assert r["ok"] and r["texte"] == "Bonjour"
    con = entrepot.connexion_ecriture(db)
    try:
        c = con.execute(
            "SELECT cost_status, estimated_cost_usd FROM secw_model_usage"
            " WHERE agent='secretaire'"
        ).fetchone()
    finally:
        con.close()
    assert c["cost_status"] == "unknown"
    assert c["estimated_cost_usd"] == 0.0


def _subprocess_popen_claude_cli(ligne_result):
    """Remplace cerveau.subprocess.Popen : faux process dont stdout nourrit le thread
    lecteur avec une seule ligne JSON (même esprit que _subprocess_popen_capture dans
    test_beecham.py, adapté ici pour un stdout ITÉRABLE — pas juste communicate())."""

    class FauxProc:
        pid = 424242
        stdout = [ligne_result]

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    return lambda *a, **k: FauxProc()


def test_lancer_claude_cli_enregistre_et_desenregistre_au_superviseur(monkeypatch):
    """D-16 : le process claude -p est inscrit au superviseur (Trou A, diagnostic
    diagnostic_d16_registre_taches.md §3 M1) et désinscrit en finally, quel que soit
    l'agent/tâche appelant."""
    appels_enr = []
    appels_fin = []

    def faux_enregistrer(pid, nom, proprietaire, but, ppid=None, chemin=None):
        appels_enr.append(
            {"pid": pid, "nom": nom, "proprietaire": proprietaire, "but": but}
        )
        return "pTEST1234"

    def faux_finir(rid, statut="fini", chemin=None):
        appels_fin.append(rid)

    monkeypatch.setattr(superviseur, "enregistrer", faux_enregistrer)
    monkeypatch.setattr(superviseur, "finir", faux_finir)
    monkeypatch.setattr(
        cerveau.subprocess,
        "Popen",
        _subprocess_popen_claude_cli(
            '{"type": "result", "result": "Bonjour",'
            ' "usage": {"input_tokens": 1, "output_tokens": 1}}\n'
        ),
    )

    r = cerveau._lancer_claude_cli(
        "salut", None, PROF, agent="secretaire", task="brouillon test"
    )

    assert len(appels_enr) == 1
    assert appels_enr[0]["proprietaire"] == "secretaire"
    assert appels_enr[0]["but"].startswith("brouillon test")
    assert appels_fin == ["pTEST1234"]  # même rid que celui rendu par enregistrer
    assert r == {"texte": "Bonjour", "input_tokens": 1, "output_tokens": 1}


def test_spillover_tronque(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cerveau, "SPILL_DIR", tmp_path / "spill"
    )  # pas de résidu dans le coffre
    gros = "x" * 20000
    # NOTE déviation plan : seuil abaissé (le plan disait 8000 tout en asseyant len<500,
    # impossible puisque spillover renvoie propre[:seuil] ; l'implémentation sécurité reste EXACTE).
    ap = cerveau.spillover(gros, seuil=200)
    assert "spillover/" in ap and len(ap) < 500
    assert (tmp_path / "spill").exists()
