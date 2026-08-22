"""Le choix des modèles est une DONNÉE (`atelier/modeles.json`), plus une table dans le code.

Alex avait donné un exemple (« Fable 5 au premier tour, des Opus et des Sonnet selon la
difficulté ») ; l'exemple avait été gravé en table Python. Son intention était « je veux pouvoir
choisir » — donc un fichier qu'il édite, relu à chaud, qui ne casse jamais rien s'il est mal
recollé mais qui ne l'ignore jamais en silence non plus.
"""

import json
import logging

import pytest

import beecham


@pytest.fixture(autouse=True)
def _atelier_isole(monkeypatch, tmp_path):
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    monkeypatch.setattr(beecham, "_DERNIER_FICHIER", "\x00jamais lu")
    return tmp_path / "atelier" / "modeles.json"


def _ecrire(fichier, contenu):
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(
        contenu if isinstance(contenu, str) else json.dumps(contenu, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.fixture
def alertes(caplog):
    caplog.set_level(logging.WARNING, logger="beecham")
    return caplog


# --- sans fichier : les défauts du code, et de quoi éditer -------------------------------------


def test_sans_fichier_on_retombe_sur_les_defauts_et_on_seme_un_exemple(_atelier_isole):
    assert beecham.modele_pour("chef") == "claude-fable-5"
    assert beecham.modele_pour("chercheur") == "sonnet"
    # Alex trouve un fichier à éditer plutôt qu'une page blanche...
    assert _atelier_isole.exists()
    depose = json.loads(_atelier_isole.read_text(encoding="utf-8"))
    assert depose["par_role"]["chef"] == "claude-fable-5"
    assert depose["_lisezmoi"]
    # ...et le relire ne change rien (le semis est cohérent avec le code).
    assert beecham.modele_pour("chef") == "claude-fable-5"


# --- fichier valide : il fait foi, à chaud ------------------------------------------------------


def test_le_fichier_prime_sur_le_code_et_est_relu_a_chaque_appel(_atelier_isole):
    _ecrire(
        _atelier_isole,
        {
            "defaut": "haiku",
            "par_role": {"chef": "claude-opus-5"},
            "offerts": {"claude-opus-5": "Opus 5"},
        },
    )
    assert beecham.modele_pour("chef") == "claude-opus-5"
    assert beecham.modele_pour("developpeur") == "haiku", "absent du fichier => défaut du fichier"
    assert beecham.modeles_offerts() == {"claude-opus-5": "Opus 5"}

    # à chaud : pas de redémarrage, pas de cache
    _ecrire(_atelier_isole, {"par_role": {"chef": "sonnet"}})
    assert beecham.modele_pour("chef") == "sonnet"


# --- fail-soft, mais jamais silencieux ----------------------------------------------------------


def test_json_casse_ne_bloque_rien_mais_est_signale(_atelier_isole, alertes):
    _ecrire(_atelier_isole, "{ceci n'est pas du JSON")
    assert beecham.modele_pour("chef") == "claude-fable-5"
    assert "JSON invalide" in alertes.text


def test_un_fichier_illisible_ne_bloque_rien_et_n_est_surtout_pas_ecrase(_atelier_isole, alertes):
    """Présent mais indécodable (octets non-UTF-8, ou droits refusés) : ce n'est PAS « absent ».
    `UnicodeDecodeError` hérite de ValueError, pas d'OSError — non attrapée, elle bloquait le
    lancement de tout agent. Et surtout : on ne sème rien par-dessus, ce serait écraser la config
    d'Alex à cause d'un ennui de lecture."""
    _atelier_isole.parent.mkdir(parents=True, exist_ok=True)
    octets = b'{"par_role": {"chef": "sonnet\xff\xfe"}}'
    _atelier_isole.write_bytes(octets)

    assert beecham.modele_pour("chef") == "claude-fable-5", "défauts du code, sans exception"
    assert _atelier_isole.read_bytes() == octets, "le fichier d'Alex doit être intact"
    assert "illisible" in alertes.text


def test_une_section_mal_typee_est_signalee(_atelier_isole, alertes):
    """Se tromper de TYPE de section est l'erreur la plus probable en éditant à la main : une
    liste au lieu d'un objet ne doit pas se traduire par un silence."""
    _ecrire(_atelier_isole, {"par_role": ["chef", "claude-opus-5"], "offerts": "opus"})
    assert beecham.modele_pour("chef") == "claude-fable-5", "table du code conservée"
    assert beecham.modeles_offerts() == beecham._OFFERTS_DEFAUT
    assert "« par_role » doit être un objet" in alertes.text
    assert "« offerts » doit être un objet" in alertes.text


def test_une_cle_de_section_mal_orthographiee_est_signalee(_atelier_isole, alertes):
    _ecrire(_atelier_isole, {"roles": {"chef": "sonnet"}, "menu": {}})
    assert beecham.modele_pour("chef") == "claude-fable-5"
    assert "clé inconnue « roles »" in alertes.text
    assert "clé inconnue « menu »" in alertes.text


def test_une_valeur_qui_ressemble_a_une_option_est_refusee(_atelier_isole, alertes):
    """Ces valeurs finissent en argument de `claude --model` : jamais de tiret en tête."""
    _ecrire(
        _atelier_isole,
        {
            "defaut": "--dangerously-skip-permissions",
            "par_role": {"chef": "-x", "developpeur": "sonnet 5; rm -rf", "auditeur": 42},
            "offerts": {"--rm": "piège", "claude-opus-5": "  "},
        },
    )
    assert beecham.modele_pour("chef") == "sonnet", "défaut du CODE, pas la valeur refusée"
    assert beecham.modele_pour("developpeur") == "sonnet"
    assert beecham.modele_pour("auditeur") == "sonnet"
    assert beecham.modeles_offerts() == beecham._OFFERTS_DEFAUT
    assert "« defaut » invalide" in alertes.text
    assert "« par_role.chef » invalide" in alertes.text
    assert "« offerts.--rm » invalide" in alertes.text


# --- l'avertissement ne se répète pas... mais ne se perd pas non plus ----------------------------


def test_le_meme_fichier_casse_n_alerte_qu_une_fois(_atelier_isole, alertes):
    _ecrire(_atelier_isole, "pas du JSON")
    beecham.modele_pour("chef")
    beecham.modele_pour("chef")
    beecham.modele_pour("chef")
    assert alertes.text.count("JSON invalide") == 1


def test_fichier_supprime_puis_recasse_a_l_identique_realerte(_atelier_isole, alertes):
    """Le piège de la dédup : Alex casse le JSON (signalé), SUPPRIME le fichier pour repartir des
    défauts, puis recolle exactement la même erreur. Contenu identique au dernier mémorisé => sans
    remise à zéro sur l'absence, le deuxième cassage passerait en silence."""
    _ecrire(_atelier_isole, "pas du JSON")
    beecham.modele_pour("chef")
    _atelier_isole.unlink()
    beecham.modele_pour("chef")  # absent : semé, rien à signaler
    _ecrire(_atelier_isole, "pas du JSON")
    beecham.modele_pour("chef")
    assert alertes.text.count("JSON invalide") == 2
