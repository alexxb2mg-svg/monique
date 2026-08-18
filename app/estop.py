from pathlib import Path

SENTINELLE = Path.home() / ".monique_secrets" / "SECRETAIRE_PAUSE"


def engage() -> bool:
    try:
        return SENTINELLE.exists()
    except Exception:
        return True  # fail-safe : dans le doute, on pause
