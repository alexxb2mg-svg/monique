import roles


def test_parse_role_entete(tmp_path, monkeypatch):
    d = tmp_path / "agents" / "secretaire"
    d.mkdir(parents=True)
    (d / "ROLE.md").write_text(
        "---\nname: secretaire\n"
        "triggers_deterministes: [canal=email, tag=rdv]\n"
        "description_routage: mails, RDV, relances\n---\n"
        "Tu es la secrétaire.",
        encoding="utf-8",
    )
    monkeypatch.setattr(roles, "RACINE_AGENTS", tmp_path / "agents")
    r = roles.parse_role("secretaire")
    assert r["name"] == "secretaire"
    assert "canal=email" in r["triggers"] and "tag=rdv" in r["triggers"]
    assert "mails" in r["description"]
    assert r["corps"].strip() == "Tu es la secrétaire."


def test_carte_agents_scan(tmp_path, monkeypatch):
    for nom in ("secretaire", "chercheur"):
        d = tmp_path / "agents" / nom
        d.mkdir(parents=True)
        (d / "ROLE.md").write_text(
            f"---\nname: {nom}\ndescription_routage: x\n---\ncorps", encoding="utf-8"
        )
    monkeypatch.setattr(roles, "RACINE_AGENTS", tmp_path / "agents")
    c = roles.carte_agents()
    assert set(c.keys()) == {"secretaire", "chercheur"}


def test_charger_retire_lentete_de_routage(tmp_path, monkeypatch):
    # revue B1 (régression) : charger NE doit PAS laisser fuiter l'en-tête dans le system prompt
    d = tmp_path / "agents" / "secretaire"
    d.mkdir(parents=True)
    (d / "ROLE.md").write_text(
        "---\nname: secretaire\ntriggers_deterministes: [canal=email]\n"
        "description_routage: mails\n---\nTu es la secrétaire.",
        encoding="utf-8",
    )
    monkeypatch.setattr(roles, "RACINE_AGENTS", tmp_path / "agents")
    corps = roles.charger("secretaire")
    assert corps.strip() == "Tu es la secrétaire."
    assert "triggers_deterministes" not in corps and "---" not in corps


def test_parse_role_tolere_le_bom(tmp_path, monkeypatch):
    # revue M-3 : ROLE.md enregistré avec BOM (Notepad « UTF-8 ») doit parser son en-tête
    d = tmp_path / "agents" / "secretaire"
    d.mkdir(parents=True)
    contenu = (
        "---\nname: secretaire\ntriggers_deterministes: [canal=email]\n"
        "description_routage: mails\n---\nCorps."
    )
    (d / "ROLE.md").write_bytes(b"\xef\xbb\xbf" + contenu.encode("utf-8"))
    monkeypatch.setattr(roles, "RACINE_AGENTS", tmp_path / "agents")
    r = roles.parse_role("secretaire")
    assert "canal=email" in r["triggers"]  # en-tête bien parsé malgré le BOM
    assert r["corps"].strip() == "Corps."


def test_parse_role_refuse_nom_non_canonique():
    # revue M4 : un nom d'agent hostile ne doit pas servir à un path traversal
    r = roles.parse_role("../../secrets")
    assert r["triggers"] == [] and r["corps"] == roles.DEFAUT


def test_chef_dev_visible_dans_annuaire_et_departement_informatique():
    # V8-1 (Lot chef_dev) : agents/chef_dev/ROLE.md existe dans le VRAI dossier agents/ du
    # dépôt (pas de tmp_path/monkeypatch ici, comme carte_agents() en production) — le rôle
    # est déjà fusionné côté beecham.py/tests, seul le ROLE.md manquait à l'annuaire.
    carte = roles.carte_agents()
    assert "chef_dev" in carte
    assert roles.parse_role("chef_dev")["departement"] == "Informatique"
    assert "chef_dev" in roles.carte_departements()["Informatique"]


def test_vision_visible_dans_annuaire_et_departement_qualite():
    # D-12 étape 1 : agents/vision/ROLE.md existe dans le VRAI dossier agents/ du dépôt
    # (pas de tmp_path/monkeypatch ici, comme carte_agents() en production).
    carte = roles.carte_agents()
    assert "vision" in carte
    assert roles.parse_role("vision")["departement"] == "Qualité"
    assert "vision" in roles.carte_departements()["Qualité"]
