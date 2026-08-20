"""Le plafond quotidien de ponts.lancer() s'appuie sur le journal PERSISTÉ (journal_ponts), pas une
mémoire de process — corrige un bug réel : un compteur en mémoire se réinitialise à chaque relance
et ne protégeait donc rien en usage réel (nos tests via `python -c` repartaient à zéro à chaque
appel). Mocks purs, zéro écriture dans le vrai journal."""

import journal_ponts
import ponts


def test_refuse_sans_ouvrir_si_plafond_atteint(monkeypatch):
    monkeypatch.setattr(journal_ponts, "appels_aujourdhui", lambda nom: ponts._PLAFOND_JOUR)
    r = ponts.lancer("x", "y", nom="deepseek")
    assert r["ok"] is False
    assert "plafond quotidien" in r["journal"][0]


def test_autorise_sous_le_plafond(monkeypatch):
    monkeypatch.setattr(journal_ponts, "appels_aujourdhui", lambda nom: ponts._PLAFOND_JOUR - 1)
    monkeypatch.setattr(ponts, "ouvrir", lambda nom: {"ok": False, "nom": nom, "erreur": "test_stop"})
    r = ponts.lancer("x", "y", nom="deepseek")
    # Le refus vient d'`ouvrir` (mocké), PAS du plafond -> preuve qu'on est bien passé au-delà.
    assert "plafond quotidien" not in r["journal"][0]
