from fastapi.testclient import TestClient

import config
import blueprint
import fournisseurs
import orchestrateur
import parametres
import planif
import roles
from serveur import app


def _client():
    return TestClient(app)


# --- Réglages -------------------------------------------------------------------------


def test_vue_reglages_affiche_valeurs(monkeypatch):
    monkeypatch.setattr(
        config,
        "cfg_get",
        lambda s, c, d=None: {"veille_freq": "3x/jour", "canaux": "mail,wa"}.get(c, d),
    )
    r = _client().get("/vue/reglages")
    assert r.status_code == 200
    assert "Fréquence de veille" in r.text and "mail,wa" in r.text


def test_maj_reglages_appelle_definir_sans_ecrire_reel(monkeypatch):
    vus = []
    monkeypatch.setattr(
        parametres, "definir", lambda cle, val, chemin=None: vus.append((cle, val))
    )
    monkeypatch.setattr(config, "cfg_get", lambda s, c, d=None: d)
    r = _client().post("/reglages", data={"veille_freq": "1x/jour", "canaux": "mail"})
    assert r.status_code == 200 and "enregistrés" in r.text
    assert ("secretaire.veille_freq", "1x/jour") in vus and (
        "secretaire.canaux",
        "mail",
    ) in vus


# --- Planificateur --------------------------------------------------------------------


def test_vue_planif_masque_appliquer_en_test(monkeypatch):
    monkeypatch.setattr(
        planif,
        "lister_taches",
        lambda: [
            {
                "nom": "\\Monique_Secretaire",
                "prochaine": "19/08 02:00",
                "statut": "Prêt",
            }
        ],
    )
    monkeypatch.setattr(config, "mode", lambda: "test")
    r = _client().get("/vue/planif")
    assert r.status_code == 200 and "Monique_Secretaire" in r.text
    assert (
        'title="câblage prod' not in r.text
    )  # prod-gate : le BOUTON « Appliquer » est masqué en test
    assert "Mode test" in r.text  # bandeau d'isolation présent


def test_vue_planif_montre_appliquer_en_prod(monkeypatch):
    monkeypatch.setattr(planif, "lister_taches", lambda: [])
    monkeypatch.setattr(config, "mode", lambda: "prod")
    r = _client().get("/vue/planif")
    assert (
        'title="câblage prod' in r.text
    )  # bouton présent seulement en prod (et désactivé)


def test_creer_planif_appelle_blueprint(monkeypatch):
    vus = []
    monkeypatch.setattr(
        blueprint,
        "creer_job",
        lambda module, libelle, planning, **kw: (
            vus.append((module, libelle, planning)) or "id1"
        ),
    )
    monkeypatch.setattr(planif, "lister_taches", lambda: [])
    monkeypatch.setattr(config, "mode", lambda: "test")
    r = _client().post(
        "/planif/creer",
        data={
            "module": "chercheur",
            "libelle": "veille nocturne",
            "modele": "quotidien",
            "valeur": "23:00",
        },
    )
    assert r.status_code == 200 and "veille nocturne" in r.text
    assert vus == [
        ("chercheur", "veille nocturne", {"kind": "daily", "heure": "23:00"})
    ]


def test_creer_planif_heure_invalide_montre_erreur(monkeypatch):
    appels = []
    monkeypatch.setattr(
        blueprint, "creer_job", lambda *a, **k: appels.append(a) or "id"
    )
    monkeypatch.setattr(planif, "lister_taches", lambda: [])
    monkeypatch.setattr(config, "mode", lambda: "test")
    r = _client().post(
        "/planif/creer",
        data={
            "module": "chercheur",
            "libelle": "veille",
            "modele": "quotidien",
            "valeur": "99:99",
        },
    )
    assert r.status_code == 200 and "Heure invalide" in r.text  # feedback explicite
    assert appels == []  # aucun job créé sur entrée invalide


def test_creer_planif_champs_vides_montre_erreur(monkeypatch):
    monkeypatch.setattr(planif, "lister_taches", lambda: [])
    monkeypatch.setattr(config, "mode", lambda: "test")
    r = _client().post(
        "/planif/creer",
        data={
            "module": " ",
            "libelle": "   ",
            "modele": "quotidien",
            "valeur": "08:00",
        },
    )
    assert "requis" in r.text


def test_vue_agents_affiche_brigade_et_suggestions(monkeypatch):
    monkeypatch.setattr(
        roles,
        "carte_agents",
        lambda: {
            "secretaire": {"triggers": ["canal=email"], "description": "mails et RDV"},
            "chercheur": {"triggers": ["tag=veille"], "description": "veilles"},
        },
    )
    monkeypatch.setattr(
        orchestrateur,
        "suggerer",
        lambda chemin=None: [
            {
                "signature": "email:facture-fournisseur",
                "compteur": 6,
                "exemples": "un mail de facture",
            }
        ],
    )
    r = _client().get("/vue/agents")
    assert r.status_code == 200
    assert "secretaire" in r.text and "chercheur" in r.text and "mails et RDV" in r.text
    assert "canal=email" in r.text  # déclencheur de routage affiché
    assert (
        "email:facture-fournisseur" in r.text and "×6" in r.text
    )  # suggestion affichée


def test_vue_agents_regroupe_par_departement(monkeypatch):
    monkeypatch.setattr(
        roles,
        "carte_departements",
        lambda: {
            "Secrétariat": {"secretaire": {"description": "mails", "triggers": []}},
            "Recherche": {"chercheur": {"description": "veille", "triggers": []}},
        },
    )
    monkeypatch.setattr(orchestrateur, "suggerer", lambda chemin=None: [])
    r = _client().get("/vue/agents")
    assert r.status_code == 200
    assert "Secrétariat" in r.text and "secretaire" in r.text
    assert "Recherche" in r.text and "chercheur" in r.text
    # le département apparaît comme titre AU-DESSUS de ses agents
    assert r.text.index("Secrétariat") < r.text.index("secretaire")


def test_reglages_autoescape(monkeypatch):
    # revue F : régression XSS — un canal malveillant doit être échappé, jamais rendu brut
    monkeypatch.setattr(
        config,
        "cfg_get",
        lambda s, c, d=None: '"><script>alert(1)</script>' if c == "canaux" else d,
    )
    r = _client().get("/vue/reglages")
    assert "<script>alert(1)" not in r.text  # brut absent
    assert "&lt;script&gt;" in r.text or "&amp;lt;" in r.text


# --- Fournisseurs & clés --------------------------------------------------------------


def test_vue_fournisseurs_affiche_usage(monkeypatch):
    monkeypatch.setattr(
        fournisseurs,
        "usage_par_agent",
        lambda agent, chemin=None: {
            "input_tokens": 100,
            "output_tokens": 40,
            "calls": 2,
        },
    )
    monkeypatch.setattr(fournisseurs, "lire_cle", lambda env_var, coffre=None: None)
    r = _client().get("/vue/fournisseurs")
    assert r.status_code == 200 and "claude" in r.text and "included" in r.text
    assert ">2<" in r.text  # le compteur d'appels


def test_maj_cle_ne_reflete_jamais_la_valeur(monkeypatch):
    ecrites = []
    monkeypatch.setattr(
        fournisseurs,
        "ecrire_cle",
        lambda env_var, valeur, coffre=None: ecrites.append((env_var, valeur)),
    )
    monkeypatch.setattr(fournisseurs, "lire_cle", lambda env_var, coffre=None: "x")
    monkeypatch.setattr(
        fournisseurs,
        "usage_par_agent",
        lambda agent, chemin=None: {"input_tokens": 0, "output_tokens": 0, "calls": 0},
    )
    r = _client().post(
        "/fournisseurs/cle",
        data={"env_var": "OPENAI_API_KEY", "valeur": "sk-ultrasecret"},
    )
    assert r.status_code == 200 and "enregistrée" in r.text
    assert ecrites == [("OPENAI_API_KEY", "sk-ultrasecret")]
    assert "sk-ultrasecret" not in r.text  # la clé n'est JAMAIS réaffichée
