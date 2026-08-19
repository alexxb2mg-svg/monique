"""Régression C3 : patcher `beecham.ATELIER` seul doit isoler TOUTES les écritures (journal,
mémoire, plan) — jamais fuir vers le vrai atelier de production. Cause racine corrigée :
JOURNAL/MEMOIRE/PLAN ne sont plus lus comme des chemins figés à l'import à l'intérieur des
fonctions, mais toujours recalculés depuis ATELIER (qui, lui, est déjà patché par ces tests)."""

import beecham


def test_atelier_seul_isole_journal_memoire_plan(tmp_path, monkeypatch):
    """Ne patcher QUE ATELIER (comme le font plusieurs tests existants de test_beecham.py) doit
    suffire — sans patcher JOURNAL/MEMOIRE/PLAN séparément, aucune écriture ne doit atteindre le
    vrai atelier de production."""
    atelier = tmp_path / "atelier"
    monkeypatch.setattr(beecham, "ATELIER", atelier)

    beecham.init_atelier()
    beecham.journal_ajouter("developpeur", "test isolation", "propose")
    beecham.chemin_memoire("chercheur")

    assert (atelier / "journal.md").exists()
    assert "test isolation" in (atelier / "journal.md").read_text(encoding="utf-8")
    assert (atelier / "memoire" / "chercheur.md").exists()
    assert (atelier / "plan.md").exists()


def test_lancer_agent_lit_plan_via_atelier_seul(tmp_path, monkeypatch):
    """Même régression pour _lancer_agent : le contexte injecté (plan.md) doit suivre ATELIER
    même si PLAN n'est pas patché séparément."""
    atelier = tmp_path / "atelier"
    monkeypatch.setattr(beecham, "ATELIER", atelier)
    atelier.mkdir(parents=True)
    (atelier / "plan.md").write_text("PLAN-ISOLE : contenu de test\n", encoding="utf-8")

    import superviseur

    monkeypatch.setattr(superviseur, "enregistrer", lambda *a, **k: None)
    monkeypatch.setattr(superviseur, "finir", lambda *a, **k: None)

    appels = []

    def faux_popen(cmd, **kwargs):
        appels.append(cmd)

        class FauxProc:
            pid = 424242
            returncode = 0

            def communicate(self, timeout=None):
                return ("", "")

            def kill(self):
                pass

        return FauxProc()

    monkeypatch.setattr(beecham.subprocess, "Popen", faux_popen)

    beecham._lancer_agent("developpeur", "fais X", tmp_path)

    assert len(appels) == 1
    prompt = appels[0][appels[0].index("-p") + 1]
    assert "PLAN-ISOLE : contenu de test" in prompt
