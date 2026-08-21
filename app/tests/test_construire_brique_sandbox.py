"""Tests déterministes de construire_brique_sandbox — vérifie que proposer_ponts.proposer_a_alex
est appelé automatiquement dans TOUS les cas (échec précoce, succès, échec après orchestrer) :
un échec sur un sujet sensible doit rester visible, jamais silencieux (bug réel du 20/08/2026 :
la tentative sur le garde-fou de sécurité avait échoué SANS AUCUNE trace lisible pour Alex)."""

import boucle_beecham
import proposer_ponts


def test_echec_ecriture_tests_produit_quand_meme_une_proposition(monkeypatch, tmp_path):
    monkeypatch.setattr(boucle_beecham, "ecrire_tests_pour_brique", lambda *a, **k: False)
    appels = []
    monkeypatch.setattr(proposer_ponts, "proposer_a_alex", lambda r, d: appels.append((r, d)) or "chemin.md")

    res = boucle_beecham.construire_brique_sandbox("une brique risquée", str(tmp_path), 1)

    assert res["ok"] is False
    assert res["proposition_ecrite"] == "chemin.md"
    assert len(appels) == 1
    assert appels[0][0]["brique"] == "une brique risquée"
    assert appels[0][1] == boucle_beecham.DOSSIER_PROPOSITIONS


def test_succes_produit_une_proposition(monkeypatch, tmp_path):
    monkeypatch.setattr(boucle_beecham, "ecrire_tests_pour_brique", lambda *a, **k: True)
    monkeypatch.setattr(
        boucle_beecham.boucle_ponts, "orchestrer", lambda *a, **k: {"toutes_ok": True, "resultats": []}
    )
    appels = []
    monkeypatch.setattr(proposer_ponts, "proposer_a_alex", lambda r, d: appels.append(r) or "chemin.md")

    res = boucle_beecham.construire_brique_sandbox("brique ok", str(tmp_path), 1)

    assert res["proposition_ecrite"] == "chemin.md"
    assert len(appels) == 1
    assert appels[0]["toutes_ok"] is True
    # proposer_a_alex lit la clé "ok" (pas "toutes_ok") pour étiqueter succès/échec du rapport —
    # bug réel 21/08/2026 : la clé manquait, tout succès était étiqueté ÉCHEC dans le nom de fichier.
    assert appels[0]["ok"] is True


def test_crash_du_rapport_ne_fait_pas_perdre_le_resultat_de_construction(monkeypatch, tmp_path):
    """Bug réel (20/08/2026) : proposer_a_alex a levé OSError (nom de fichier trop long) et a fait
    planter TOUT le pipeline -- un résultat de construction VALIDE (5/5 tests passés) a été perdu.
    Doit maintenant rester fail-soft : le résultat est renvoyé, proposition_ecrite=None."""
    monkeypatch.setattr(boucle_beecham, "ecrire_tests_pour_brique", lambda *a, **k: True)
    monkeypatch.setattr(
        boucle_beecham.boucle_ponts, "orchestrer", lambda *a, **k: {"toutes_ok": True, "resultats": []}
    )

    def casse(*a, **k):
        raise OSError("nom de fichier trop long")

    monkeypatch.setattr(proposer_ponts, "proposer_a_alex", casse)

    res = boucle_beecham.construire_brique_sandbox("brique valide mais rapport casse", str(tmp_path), 1)

    assert res["toutes_ok"] is True  # le résultat de construction n'est PAS perdu
    assert res["proposition_ecrite"] is None


def test_echec_apres_orchestrer_produit_quand_meme_une_proposition(monkeypatch, tmp_path):
    """LE cas qui manquait ce soir : orchestrer échoue -> proposer_a_alex doit quand même tourner."""
    monkeypatch.setattr(boucle_beecham, "ecrire_tests_pour_brique", lambda *a, **k: True)
    monkeypatch.setattr(
        boucle_beecham.boucle_ponts, "orchestrer", lambda *a, **k: {"toutes_ok": False, "resultats": []}
    )
    appels = []
    monkeypatch.setattr(proposer_ponts, "proposer_a_alex", lambda r, d: appels.append(r) or "chemin.md")

    res = boucle_beecham.construire_brique_sandbox("brique sensible qui echoue", str(tmp_path), 1)

    assert res["proposition_ecrite"] == "chemin.md"
    assert len(appels) == 1
    assert appels[0]["brique"] == "brique sensible qui echoue"
