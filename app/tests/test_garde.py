import planif


def test_job_dangereux_detecte():
    assert planif.job_dangereux("schtasks /create /tn X /tr y")
    assert planif.job_dangereux("Stop-Service secretaire")
    assert planif.job_dangereux("taskkill /im pythonw.exe")
    assert not planif.job_dangereux("relève les mails et prépare les brouillons")


def test_job_dangereux_variantes_reelles():
    # revue A : bypass qui passaient avant (denylist trop étroit)
    dangereux = [
        "schtasks.exe /delete /tn X /f",
        r"C:\Windows\System32\schtasks.exe /create /tn X",
        '"schtasks" /change /tn X',
        "sc stop AcmeService",
        "sc.exe stop X",
        "powershell Stop-Process -Name pythonw -Force",
        "Restart-Computer",
        "Stop-Computer",
        "schtasks /end /tn Monique_Secretaire",
        "net stop W32Time",
        "wmic process where name='x' delete",
        "kill -KILL 1234",
    ]
    for cmd in dangereux:
        assert planif.job_dangereux(cmd), f"non détecté (bypass): {cmd!r}"


def test_job_dangereux_pas_de_faux_positif():
    # revue B : sous-chaînes de flags / noms de fichiers légitimes NE doivent PAS bloquer
    sains = [
        "python veille.py --no-shutdown-check",
        "pythonw surveille_taskkill_events.py",
        "python nettoyage.py --keep-remove-item-log",
        "relève les mails et prépare les brouillons",
        "python run_chercheur.py --mode nuit",
    ]
    for cmd in sains:
        assert not planif.job_dangereux(cmd), f"faux positif: {cmd!r}"


def test_appliquer_refuse_en_test(monkeypatch):
    monkeypatch.delenv("SECRETAIRE_MODE", raising=False)  # test
    r = planif.appliquer_job("j1", ["/SC", "DAILY", "/ST", "08:00"])
    assert r["applique"] is False and r["raison"] == "mode_test"


def test_appliquer_refuse_job_dangereux(monkeypatch):
    monkeypatch.setenv("SECRETAIRE_MODE", "prod")
    monkeypatch.setattr(
        planif, "_cible_job", lambda jid, chemin=None: "schtasks /create ..."
    )
    r = planif.appliquer_job("j1", ["/SC", "DAILY", "/ST", "08:00"])
    assert r["applique"] is False and r["raison"] == "dangereux"
