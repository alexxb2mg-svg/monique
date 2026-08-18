"""Client Dolibarr minimal, stdlib (urllib), FAIL-SOFT.

Intégration optionnelle : aucune fonction ne lève. En l'absence de clé ou si
Dolibarr est injoignable, on renvoie []/None (la vue Relances reste vide, sans erreur).
Config : env DOLIBARR_URL / DOLAPIKEY, sinon coffre ~/.monique_secrets/secretaire.env.
La clé n'est JAMAIS écrite ailleurs (secrets au coffre seulement).

Filtres sqlfilters : propositions ouvertes fk_statut=1 ; factures validées impayées
fk_statut=1 & paye=0.
"""

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

TIMEOUT = 15


def _cfg() -> tuple[str, str | None]:
    url = os.environ.get("DOLIBARR_URL")
    key = os.environ.get("DOLAPIKEY")
    if not key:
        coffre = Path.home() / ".monique_secrets" / "secretaire.env"
        if coffre.exists():
            for ligne in coffre.read_text(encoding="utf-8-sig").splitlines():
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#") or "=" not in ligne:
                    continue
                k, v = ligne.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "DOLAPIKEY" and not key:
                    key = v
                if k == "DOLIBARR_URL" and not url:
                    url = v
    url = (url or "http://127.0.0.1:8080").rstrip("/")
    return url + "/api/index.php", key


def is_configured() -> bool:
    _, key = _cfg()
    return bool(key)


def _get(path: str, params: dict | None = None):
    base, key = _cfg()
    if not key:
        return None
    q = "?" + urllib.parse.urlencode(params) if params else ""
    req = urllib.request.Request(
        base + path + q,
        headers={"DOLAPIKEY": key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def ping() -> dict:
    if not is_configured():
        return {
            "ok": False,
            "configured": False,
            "message": "clé Dolibarr absente (coffre .monique_secrets/secretaire.env)",
        }
    data = _get("/status")
    return {
        "ok": data is not None,
        "configured": True,
        "message": "Dolibarr accessible"
        if data is not None
        else "Dolibarr injoignable",
    }


def list_devis_a_relancer(jours_min: int = 0, limit: int = 200) -> list:
    data = _get("/proposals", {"sqlfilters": "(t.fk_statut:=:1)", "limit": limit})
    return data if isinstance(data, list) else []


def list_factures_impayees(echues_seulement: bool = True, limit: int = 200) -> list:
    data = _get(
        "/invoices",
        {"sqlfilters": "(t.fk_statut:=:1) and (t.paye:=:0)", "limit": limit},
    )
    return data if isinstance(data, list) else []
