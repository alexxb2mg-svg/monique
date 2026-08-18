import entrepot
import lease


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_acquisition_puis_conflit(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(lease, "_process_vivant", lambda pid, s: True)
    assert lease.acquerir("mail:42", db) is True
    assert lease.acquerir("mail:42", db) is False  # tenu par un process "vivant"


def test_lease_repris_si_process_mort(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(lease, "_process_vivant", lambda pid, s: True)
    lease.acquerir("mail:42", db)
    monkeypatch.setattr(
        lease, "_process_vivant", lambda pid, s: False
    )  # propriétaire mort
    assert lease.acquerir("mail:42", db) is True


def test_liberer(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(lease, "_process_vivant", lambda pid, s: True)
    lease.acquerir("mail:42", db)
    lease.liberer("mail:42", db)
    assert lease.acquerir("mail:42", db) is True
