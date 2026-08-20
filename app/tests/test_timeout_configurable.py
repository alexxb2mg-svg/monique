"""ponts.lancer(timeout_s=...) doit transmettre le timeout au sender ET laisser une marge côté
subprocess (ne pas tuer le sender pile à son propre délai) — bug réel (20/08/2026) : timeout fixe
de 120s codé en dur, insuffisant pour une synthèse sur un matériel volumineux (~36 000 caractères)."""

import journal_ponts
import ponts


def _isoler(monkeypatch):
    monkeypatch.setattr(ponts, "ouvrir", lambda nom: {"ok": True})
    monkeypatch.setattr(journal_ponts, "appels_aujourdhui", lambda nom: 0)
    monkeypatch.setattr(journal_ponts, "enregistrer_appel", lambda *a, **k: None)
    appels = []

    def faux_run(cmd, **kwargs):
        appels.append({"cmd": cmd, "timeout": kwargs.get("timeout")})
        return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(ponts.subprocess, "run", faux_run)
    return appels


def test_timeout_par_defaut_est_120(monkeypatch):
    appels = _isoler(monkeypatch)
    ponts.lancer("x", "y", nom="deepseek")

    assert "120" in appels[0]["cmd"]  # --timeout 120 transmis au sender
    assert appels[0]["timeout"] == 180  # marge de 60s côté subprocess (120+60)


def test_timeout_personnalise_est_transmis_avec_marge(monkeypatch):
    appels = _isoler(monkeypatch)
    ponts.lancer("x", "y", nom="deepseek", timeout_s=240)

    assert "240" in appels[0]["cmd"]
    assert appels[0]["timeout"] == 300  # 240+60
