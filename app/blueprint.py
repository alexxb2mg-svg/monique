import hashlib
import json
import re
from datetime import datetime

from entrepot import connexion_ecriture

_JOURS_OUVRES = ["MON", "TUE", "WED", "THU", "FRI"]
_HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")  # HH:MM 24h (revue E)


def _heure_valide(v) -> str:
    if not _HEURE.match(str(v or "")):
        raise ValueError("Heure invalide (attendu HH:MM, 24h).")
    return v


def remplir(modele: str, valeurs: dict) -> dict:
    if modele == "quotidien":
        return {"kind": "daily", "heure": _heure_valide(valeurs.get("heure"))}
    if modele == "toutes_les_n_min":
        try:
            m = int(valeurs["minutes"])
        except (TypeError, ValueError, KeyError):
            raise ValueError("Minutes invalides (entier attendu).")
        if m <= 0:
            raise ValueError("Minutes invalides (doit être > 0).")
        return {"kind": "interval", "minutes": m}
    if modele == "jours_ouvres":
        return {
            "kind": "weekly",
            "jours": list(_JOURS_OUVRES),
            "heure": _heure_valide(valeurs.get("heure")),
        }
    raise ValueError(f"modèle inconnu: {modele}")


def creer_job(module, libelle, planning, *, cible_cmd="", chemin=None) -> str:
    # revue F4 : cible_cmd/chemin keyword-only — un 4e argument positionnel (le plan passait `db`)
    # se lierait sinon à cible_cmd et le job partirait dans le shadow ambiant.
    con = connexion_ecriture(chemin)
    try:
        # revue M4 : id déterministe (sha1 module:libelle), idempotent d'un redémarrage à l'autre
        jid = f"{module}-{hashlib.sha1(f'{module}:{libelle}'.encode()).hexdigest()[:8]}"
        # revue F3 : UPSERT — INSERT OR REPLACE (DELETE+INSERT) remettrait enabled/failure_streak/
        # last_status à leur DEFAULT à chaque re-déclaration. On met à jour la DÉFINITION,
        # on PRÉSERVE l'état opérationnel et cree_le.
        con.execute(
            "INSERT INTO secw_jobs(id, module, libelle, cible_cmd, planning_json, cree_le) "
            "VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET libelle=excluded.libelle, "
            "cible_cmd=excluded.cible_cmd, planning_json=excluded.planning_json",
            (
                jid,
                module,
                libelle,
                cible_cmd,
                json.dumps(planning, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        con.commit()
        return jid
    finally:
        con.close()
