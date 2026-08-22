"""Porte de consultation : un agent en doute POSE UNE QUESTION (`questions/*.json`), un conseil y
répond, le demandeur est relancé dans sa session. Une fois par mission, gratuit quand inutile.

INVARIANT testé sur CHAQUE fin de session : le dossier des questions est vide après. Les bases
du canal sont de VRAIES bases temporaires (pas des chemins absents avalés par le fail-soft).
"""

import json

import beecham
import coordination
import courrier

_RAPPORT_OK = "FAIT : a\nRESULTAT : b\nFICHIERS : aucun\nPROBLEMES : aucun"


def _question(wt, nom="q1.json", contenu='{"question": "Faut-il garder la colonne base ?"}'):
    (wt / beecham.DOSSIER_QUESTIONS).mkdir(exist_ok=True)
    (wt / beecham.DOSSIER_QUESTIONS / nom).write_text(contenu, encoding="utf-8")


def _sortant(wt, contenu):
    (wt / "courrier_sortant").mkdir(exist_ok=True)
    (wt / "courrier_sortant" / "m.json").write_text(contenu, encoding="utf-8")


def _dossier_vide(wt):
    d = wt / beecham.DOSSIER_QUESTIONS
    return not d.exists() or not any(d.iterdir())


def _brancher(monkeypatch, tmp_path, reponses):
    """Remplace Popen : chaque appel à `claude` consomme une entrée de `reponses`
    (texte, effet, rc) — `effet(worktree)` simule ce que l'agent écrit sur le disque pendant sa
    session. Renvoie la liste des appels {cmd, prompt} réellement faits."""
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    monkeypatch.setattr(beecham, "DB_COURRIER", tmp_path / "courrier.sqlite")
    monkeypatch.setattr(beecham, "DB_COORDINATION", tmp_path / "coordination.sqlite")
    monkeypatch.setattr(beecham, "_ecrire_garde", lambda: tmp_path / "settings.json")
    import superviseur

    monkeypatch.setattr(superviseur, "enregistrer", lambda *a, **k: None)
    monkeypatch.setattr(superviseur, "finir", lambda *a, **k: None)
    appels = []

    def faux_popen(cmd, **kwargs):
        class FauxProc:
            pid = 424242
            returncode = 0

            def communicate(self, input=None, timeout=None):
                if cmd[0] != "claude":
                    return ("", "")
                appels.append({"cmd": cmd, "prompt": input or ""})
                texte, effet, rc = reponses.pop(0)
                if effet:
                    effet(tmp_path / "wt")
                self.returncode = rc
                sid = f"sess-{len(appels)}"
                return (
                    json.dumps({"type": "result", "session_id": sid, "result": texte}) + "\n",
                    "",
                )

            def kill(self):
                pass

        return FauxProc()

    monkeypatch.setattr(beecham.subprocess, "Popen", faux_popen)
    (tmp_path / "wt").mkdir(exist_ok=True)  # rebranché plusieurs fois dans un même test
    return appels


def _opt(cmd, nom):
    return cmd[cmd.index(nom) + 1]


def test_sans_question_aucun_appel_supplementaire(monkeypatch, tmp_path):
    """LE test : le mécanisme est gratuit quand il ne sert pas."""
    appels = _brancher(monkeypatch, tmp_path, [(_RAPPORT_OK, None, 0)])
    res = beecham._lancer_agent("developpeur", "consigne", tmp_path / "wt")
    assert res["ok"] and len(appels) == 1
    assert _dossier_vide(tmp_path / "wt")


def test_une_question_consulte_puis_relance_le_demandeur(monkeypatch, tmp_path):
    appels = _brancher(
        monkeypatch,
        tmp_path,
        [
            ("PROBLEMES : j'attends", _question, 0),
            ("Garde la colonne, elle porte la reprise.", None, 0),
            (_RAPPORT_OK, None, 0),
        ],
    )
    res = beecham._lancer_agent(
        "developpeur", "consigne", tmp_path / "wt", modele="claude-opus-5"
    )
    assert len(appels) == 3
    conseil, relance = appels[1]["cmd"], appels[2]["cmd"]
    assert _opt(conseil, "--model") == "claude-fable-5"  # en dur : sinon tautologique
    assert _opt(conseil, "--allowedTools") == "Read,Glob,Grep"  # lecture seule
    assert _opt(conseil, "--append-system-prompt") == beecham.ROLES["stratege"]
    assert "--resume" not in conseil
    assert "Faut-il garder la colonne base ?" in appels[1]["prompt"]
    assert _opt(relance, "--resume") == "sess-1"  # le demandeur, dans SA session
    assert _opt(relance, "--model") == "claude-opus-5"
    assert "Garde la colonne" in appels[2]["prompt"]
    assert res["ok"] and res["texte"] == _RAPPORT_OK
    assert _dossier_vide(tmp_path / "wt")


def test_le_conseil_ne_degringole_pas_sur_le_modele_par_defaut(monkeypatch, tmp_path):
    """Config d'Alex telle qu'elle existe : un « par_role » qui ne connaît pas « conseil »."""
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    monkeypatch.setattr(beecham, "_DERNIER_FICHIER", "\x00jamais lu")
    (tmp_path / "atelier").mkdir()
    (tmp_path / "atelier" / "modeles.json").write_text(
        json.dumps({"defaut": "sonnet", "par_role": {"developpeur": "claude-opus-5"}}),
        encoding="utf-8",
    )
    assert beecham.modele_pour("conseil") == "sonnet"  # le piège, documenté
    assert beecham.modele_conseil() == "claude-fable-5"  # le conseil y échappe


def test_la_porte_utilise_le_modele_du_conseil_meme_sans_cle_dans_le_fichier(
    monkeypatch, tmp_path
):
    """Bout en bout : le même fichier réaliste, et le `--model` réellement passé au conseil."""
    appels = _brancher(
        monkeypatch,
        tmp_path,
        [("PROBLEMES : j'attends", _question, 0), ("réponse", None, 0), (_RAPPORT_OK, None, 0)],
    )
    monkeypatch.setattr(beecham, "_DERNIER_FICHIER", "\x00jamais lu")
    (tmp_path / "atelier").mkdir(exist_ok=True)
    (tmp_path / "atelier" / "modeles.json").write_text(
        json.dumps({"defaut": "sonnet", "par_role": {"developpeur": "claude-opus-5"}}),
        encoding="utf-8",
    )
    beecham._lancer_agent("developpeur", "consigne", tmp_path / "wt", modele="claude-opus-5")
    assert _opt(appels[1]["cmd"], "--model") == "claude-fable-5"


def test_une_seule_consultation_par_mission(monkeypatch, tmp_path):
    """Le demandeur relancé repose une question : drainée, jamais re-consultée."""
    appels = _brancher(
        monkeypatch,
        tmp_path,
        [("?", _question, 0), ("réponse", None, 0), (_RAPPORT_OK, _question, 0)],
    )
    beecham._lancer_agent("developpeur", "consigne", tmp_path / "wt")
    assert len(appels) == 3
    assert _dossier_vide(tmp_path / "wt")


def test_dossier_vide_apres_chaque_fin_de_session(monkeypatch, tmp_path):
    wt = tmp_path / "wt"
    # session en échec (rc != 0) : drainée, pas consultée
    appels = _brancher(monkeypatch, tmp_path, [("", _question, 1)])
    assert beecham._lancer_agent("developpeur", "c", wt)["ok"] is False
    assert len(appels) == 1 and _dossier_vide(wt)
    # tour de reprise (`reprendre`) : drainée, pas consultée
    appels = _brancher(monkeypatch, tmp_path, [(_RAPPORT_OK, _question, 0)])
    beecham._lancer_agent("developpeur", "c", wt, reprendre="sess-x")
    assert len(appels) == 1 and _dossier_vide(wt)
    # session de service : drainée, pas consultée
    appels = _brancher(monkeypatch, tmp_path, [("avis", _question, 0)])
    beecham._lancer_agent("stratege", "c", wt, service=True)
    assert len(appels) == 1 and _dossier_vide(wt)
    # relance de la porte de rapport : la question posée pendant la relance est drainée
    appels = _brancher(monkeypatch, tmp_path, [("prose", None, 0), (_RAPPORT_OK, _question, 0)])
    beecham._lancer_agent("developpeur", "c", wt)
    assert len(appels) == 2 and _dossier_vide(wt)
    # session qui ne démarre même pas (Popen lève)
    _question(wt)

    def popen_casse(*a, **k):
        raise OSError("claude introuvable")

    monkeypatch.setattr(beecham.subprocess, "Popen", popen_casse)
    assert beecham._lancer_agent("developpeur", "c", wt)["ok"] is False
    assert _dossier_vide(wt)


def test_le_conseil_ne_pille_pas_la_boite_du_stratege_ni_le_courrier_du_demandeur(
    monkeypatch, tmp_path
):
    courrier.deposer_courrier(
        str(tmp_path / "courrier.sqlite"), "stratege", "chef", "Cap", "Lis-moi, stratège."
    )
    _brancher(
        monkeypatch,
        tmp_path,
        [
            (
                "?",
                lambda wt: (
                    _question(wt),
                    _sortant(wt, '{"destinataire": "brigade", "corps": "Piste trouvée"}'),
                ),
                0,
            ),
            ("réponse", None, 0),
            (_RAPPORT_OK, None, 0),
        ],
    )
    beecham._lancer_agent("developpeur", "consigne", tmp_path / "wt")
    non_lus = courrier.lister_courrier(str(tmp_path / "courrier.sqlite"), "stratege")
    assert [m["corps"] for m in non_lus] == ["Lis-moi, stratège."]  # toujours non lu
    fil = coordination.lire_fil_non_lu(str(tmp_path / "coordination.sqlite"), "auditeur")
    assert len(fil) == 1 and fil[0]["auteur"] == "developpeur"  # une entrée, signée du demandeur


def test_le_conseil_recoit_un_prompt_de_conseil_pas_d_executant(monkeypatch, tmp_path):
    appels = _brancher(
        monkeypatch, tmp_path, [("?", _question, 0), ("réponse", None, 0), (_RAPPORT_OK, None, 0)]
    )
    beecham._lancer_agent("developpeur", "consigne", tmp_path / "wt")
    prompt = appels[1]["prompt"]
    for interdit in ("COPIE ISOLÉE", "FAIT :", "courrier_sortant"):
        assert interdit not in prompt


def test_une_consultation_qui_echoue_ne_fait_pas_echouer_la_mission(monkeypatch, tmp_path):
    appels = _brancher(monkeypatch, tmp_path, [(_RAPPORT_OK, _question, 0), ("", None, 1)])
    res = beecham._lancer_agent("developpeur", "consigne", tmp_path / "wt")
    assert len(appels) == 2  # conseil tenté, demandeur pas relancé
    assert res["ok"] and res["texte"] == _RAPPORT_OK
    assert any("sans réponse" in ligne for ligne in res["journal"])
    assert _dossier_vide(tmp_path / "wt")


def test_une_question_malformee_n_emporte_ni_les_autres_ni_la_mission(monkeypatch, tmp_path):
    def deux(wt):
        _question(wt, "a.json", "{pas du json")
        _question(wt, "b.json", '{"question": "La bonne ?"}')

    appels = _brancher(
        monkeypatch, tmp_path, [("?", deux, 0), ("réponse", None, 0), (_RAPPORT_OK, None, 0)]
    )
    res = beecham._lancer_agent("developpeur", "consigne", tmp_path / "wt")
    assert res["ok"] and len(appels) == 3
    assert "La bonne ?" in appels[1]["prompt"]
    assert _dossier_vide(tmp_path / "wt")  # le fichier cassé a disparu aussi


def test_relever_questions_consomme_meme_le_json_casse(tmp_path):
    _question(tmp_path, "a.json", "{cassé")
    assert beecham._relever_questions(tmp_path) == []
    assert _dossier_vide(tmp_path)


def test_les_agents_savent_qu_ils_peuvent_demander():
    fixes = beecham._consignes_fixes()
    assert f"{beecham.DOSSIER_QUESTIONS}/" in fixes
    assert "AVANT d'écrire" in fixes
    assert "INTENTION" in fixes


def test_le_dossier_des_questions_reste_hors_du_depot():
    from pathlib import Path

    racine = Path(__file__).parent.parent.parent
    assert "questions/" in (racine / ".gitignore").read_text(encoding="utf-8")
