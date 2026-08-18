import cerveau
import orchestrateur as O


def test_deleguer_renvoie_resume(monkeypatch):
    vu = {}

    def faux(agent, prompt, prof, task, system=None, chemin=None):
        vu["prompt"] = prompt
        return {
            "ok": True,
            "texte": "Résumé : 3 fournisseurs comparés.",
            "erreur": None,
            "usage": None,
        }

    monkeypatch.setattr(cerveau, "appeler", faux)
    r = O.deleguer("comparer 3 fournisseurs pour la réf X")
    assert r["ok"] and "3 fournisseurs" in r["resume"]
    assert (
        "comparer 3 fournisseurs" in vu["prompt"]
    )  # le prompt est fabriqué à partir du but


def test_deleguer_cerveau_ko(monkeypatch):
    monkeypatch.setattr(
        cerveau,
        "appeler",
        lambda *a, **k: {"ok": False, "texte": "", "erreur": "estop", "usage": None},
    )
    r = O.deleguer("x")
    assert r["ok"] is False
