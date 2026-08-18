import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
# Store réel (« le vivant ») : configurable par variable d'environnement, défaut portable.
# Aucun chemin de poste en dur — chaque installation pointe le sien via MONIQUE_STORE.
REEL = os.environ.get("MONIQUE_STORE") or str(Path.home() / ".monique" / "store.db")
# Bac à sable : tout ce que Monique écrit en MODE=test. Jamais versionné.
SHADOW = os.environ.get("MONIQUE_SHADOW") or str(BASE.parent / "monique_shadow.db")

DEFAUTS = {
    "systeme": {"mode": "test"},
    "secretaire": {"veille_freq": "2x/jour", "canaux": "mail,wa,sms"},
}


def _sys_constant(cle: str):
    try:
        con = sqlite3.connect(f"file:{REEL}?mode=ro", uri=True)
        try:
            r = con.execute(
                "SELECT value FROM sys_constants WHERE key=?", (cle,)
            ).fetchone()
            return r[0] if r else None
        finally:
            con.close()
    except Exception:
        return None


def _param_shadow(cle: str):
    # revue B1 : la garde anti-récursion est la clé systeme.mode (return None ci-dessous),
    # PAS un chemin en dur — la chaîne cfg_get -> mode -> chemin_ecriture -> cfg_get(systeme.mode)
    # se ferme sur elle. Pour toute autre clé on lit la write-DB DU MODE COURANT
    # (SHADOW en test, REEL en prod — l'intention « write-DB » du plan §Task1),
    # en mode=ro : lecture pure, jamais de fichier vide créé, jamais de handle RW sur le store réel.
    if cle == "systeme.mode":
        return None  # le mode ne se lit jamais dans secw_parametres
    try:
        con = sqlite3.connect(f"file:{chemin_ecriture()}?mode=ro", uri=True, timeout=8)
        try:
            r = con.execute(
                "SELECT valeur FROM secw_parametres WHERE cle=?", (cle,)
            ).fetchone()
            return r[0] if r else None
        finally:
            con.close()
    except Exception:
        return None


def cfg_get(section: str, cle: str, default=None):
    # revue F5 : le mode ne se lit QUE via SECRETAIRE_MODE (cf. mode()), jamais via la couche
    # env générique SYSTEME_MODE — sinon second interrupteur d'isolation non documenté.
    if (section, cle) != ("systeme", "mode"):
        env = os.environ.get(f"{section.upper()}_{cle.upper()}")
        if env is not None:
            return env
    v = _param_shadow(f"{section}.{cle}")
    if v is not None:
        return v
    v = _sys_constant(f"{section}.{cle}")
    if v is not None:
        return v
    return DEFAUTS.get(section, {}).get(cle, default)


def mode() -> str:
    m = os.environ.get("SECRETAIRE_MODE") or cfg_get("systeme", "mode", "test")
    return "prod" if m == "prod" else "test"


def chemin_lecture() -> str:
    return REEL


def chemin_ecriture() -> str:
    return REEL if mode() == "prod" else SHADOW
