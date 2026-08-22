"""Garde-fou anti-boucle inspiré du « wrap-up budget » de Hermes (nousresearch/hermes-agent).

Chez eux, à 80 % du budget temps, un message « arrête d'explorer, produis le livrable » est
injecté DANS la boucle de conversation. Nos sessions `claude -p` sont atomiques (on ne possède
pas leur boucle : une fois `Popen` lancé, on ne peut plus leur parler), donc on PRÉ-CHARGE la
même consigne de convergence dans le prompt de mission. Ces tests vérifient qu'elle y est bien —
en session neuve ET en reprise (`--resume`), une session reprise pouvant aussi partir en boucle.
"""

import beecham


def _faux_popen(appels, prompts=None):
    def faux_popen(cmd, **kwargs):
        appels.append(cmd)

        class FauxProc:
            pid = 424242
            returncode = 0

            def communicate(self, input=None, timeout=None):
                if prompts is not None:
                    prompts.append(input or "")
                return ("", "")

            def kill(self):
                pass

        return FauxProc()

    return faux_popen


def _prompt_capture(prompts):
    """Le prompt voyage sur stdin, plus dans l'argv (limite Windows de 32 767 car. sur une ligne
    de commande — cf. beecham._lancer_agent)."""
    return prompts[-1] if prompts else ""


def _isoler(tmp_path, monkeypatch):
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    import superviseur

    monkeypatch.setattr(superviseur, "enregistrer", lambda *a, **k: None)
    monkeypatch.setattr(superviseur, "finir", lambda *a, **k: None)
    appels, prompts = [], []
    monkeypatch.setattr(beecham.subprocess, "Popen", _faux_popen(appels, prompts))
    return prompts


def test_convergence_injectee_session_neuve(tmp_path, monkeypatch):
    prompts = _isoler(tmp_path, monkeypatch)

    beecham._lancer_agent("developpeur", "fais X", tmp_path)

    prompt = _prompt_capture(prompts)
    assert "CONVERGENCE" in prompt  # la consigne de budget est bien pré-chargée
    assert "fais X" in prompt  # sans écraser la consigne de mission


def test_convergence_injectee_en_reprise(tmp_path, monkeypatch):
    prompts = _isoler(tmp_path, monkeypatch)

    beecham._lancer_agent("developpeur", "corrige Y", tmp_path, reprendre="sess-123")

    prompt = _prompt_capture(prompts)
    assert "CONVERGENCE" in prompt
    assert "corrige Y" in prompt
