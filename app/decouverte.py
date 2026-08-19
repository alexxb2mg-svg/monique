import sqlite3
from config import chemin_lecture

# besoin abstrait d'un module → tables réelles candidates (ordre de préférence)
# NB : "synthese"/"sec_synthese" retiré (diagnostic_decouverte_orphelin.md §3) — besoin
# anticipé jamais consommé par aucun module de app/*.py ; le laisser signalerait un manque
# en permanence, jamais actionnable, ce qui rendrait le futur signal "manques" inutilisable.
BESOINS = {
    "evenements_entrants": ["sys_incoming_events"],
    "taches": ["sec_taches"],
    "constantes": ["sys_constants"],
}


def carte_schema(chemin: str | None = None) -> dict:
    chemin = chemin or chemin_lecture()
    con = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        tables = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        return {
            t: [c[1] for c in con.execute(f"PRAGMA table_info({t})").fetchall()]
            for t in tables
        }
    finally:
        con.close()


def resoudre(besoin: str, carte: dict) -> str | None:
    for cand in BESOINS.get(besoin, []):
        if cand in carte:
            return cand
    return None


def diagnostic(chemin: str | None = None) -> dict:
    carte = carte_schema(chemin)
    manques = [b for b in BESOINS if resoudre(b, carte) is None]
    return {"tables": len(carte), "manques": manques, "carte": carte}
