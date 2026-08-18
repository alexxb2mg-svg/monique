import planif


def test_traducteur_daily():
    assert planif.cron_vers_schtasks({"kind": "daily", "heure": "08:00"}) == [
        "/SC",
        "DAILY",
        "/ST",
        "08:00",
    ]


def test_traducteur_interval():
    assert planif.cron_vers_schtasks({"kind": "interval", "minutes": 30}) == [
        "/SC",
        "MINUTE",
        "/MO",
        "30",
    ]


def test_traducteur_weekly():
    got = planif.cron_vers_schtasks(
        {"kind": "weekly", "jours": ["MON", "TUE"], "heure": "07:00"}
    )
    assert got == ["/SC", "WEEKLY", "/D", "MON,TUE", "/ST", "07:00"]


def test_lister_parse(monkeypatch):
    monkeypatch.setattr(
        planif,
        "_interroger_schtasks",
        lambda: (
            "TaskName: \\Monique_Secretaire\nNext Run Time: 18/08/2026 19:00:00\nStatus: Ready\n"
        ),
    )
    t = planif.lister_taches()
    assert any(x["nom"].endswith("Monique_Secretaire") for x in t)


def test_lister_parse_fr(monkeypatch):
    # revue F2 : sortie réelle d'un Windows FR — champ « Statut », valeur horodatée avec « : »
    monkeypatch.setattr(
        planif,
        "_interroger_schtasks",
        lambda: (
            "Nom de la tâche: \\Monique_Secretaire\n"
            "Prochaine exécution: 19/08/2026 02:00:00\nStatut: Prêt\n"
        ),
    )
    t = planif.lister_taches()
    assert any(x["nom"].endswith("Monique_Secretaire") for x in t)
    cible = next(x for x in t if x["nom"].endswith("Monique_Secretaire"))
    assert cible["statut"] == "Prêt"
    assert cible["prochaine"] == "19/08/2026 02:00:00"
