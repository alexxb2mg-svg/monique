import os
import re
from pathlib import Path

import usage as _usage
from cerveau import ProviderProfile

COFFRE_DEFAUT = Path.home() / ".monique_secrets"
FICHIER = "secretaire.env"
_ENV_VAR = re.compile(r"^[A-Z][A-Z0-9_]*$")  # nom de variable d'env canonique

REGISTRE = {
    "claude": ProviderProfile(nom="claude", mode="claude_cli", model="sonnet"),
    "openai_compat": ProviderProfile(
        nom="openai_compat",
        mode="openai_compat",
        model="",
        base_url="",
        env_var="OPENAI_API_KEY",
    ),
}


def _coffre_base(coffre=None):
    # priorité : argument explicite (tests) > env COFFRE (contrainte plan) > défaut ~/.monique_secrets
    return Path(coffre or os.environ.get("COFFRE") or COFFRE_DEFAUT)


def _fichier(coffre):
    return _coffre_base(coffre) / FICHIER


def lire_cle(env_var, coffre=None):
    v = os.environ.get(env_var)
    if v:
        return v
    f = _fichier(coffre)
    try:
        if f.exists():
            for ligne in f.read_text(encoding="utf-8-sig").splitlines():
                ligne = ligne.strip()
                if ligne and not ligne.startswith("#") and "=" in ligne:
                    k, val = ligne.split("=", 1)
                    if k.strip() == env_var:
                        return val.strip()
    except Exception:
        pass
    return None


def ecrire_cle(env_var, valeur, coffre=None):
    # revue C : refuser l'injection de ligne (\n/\r dans valeur) et un env_var non canonique —
    # sinon un champ écrit la clé d'un AUTRE provider ou empoisonne le coffre.
    if not _ENV_VAR.match(env_var or ""):
        raise ValueError("nom de variable d'environnement invalide")
    if valeur is None or "\n" in valeur or "\r" in valeur:
        raise ValueError("valeur de clé invalide (saut de ligne interdit)")
    d = _coffre_base(coffre)
    d.mkdir(parents=True, exist_ok=True)
    f = d / FICHIER
    lignes = []
    if f.exists():
        lignes = [
            ligne
            for ligne in f.read_text(encoding="utf-8-sig").splitlines()
            if not ligne.strip().startswith(env_var + "=")
        ]
    lignes.append(f"{env_var}={valeur}")
    f.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    try:
        os.chmod(f, 0o600)
    except Exception:
        pass  # chmod best-effort sous Windows


def usage_par_agent(agent, chemin=None) -> dict:
    return _usage.total(agent, chemin)
