import sqlite3
from datetime import datetime

from config import chemin_ecriture
from entrepot import connexion_ecriture


def compter(
    agent,
    model,
    provider,
    task,
    input_tokens,
    output_tokens,
    cache_read=0,
    cost_status="unknown",
    estimated_cost_usd=0.0,
    chemin=None,
) -> None:
    try:
        con = connexion_ecriture(chemin)
        try:
            now = datetime.now().isoformat()
            con.execute(
                """
              INSERT INTO secw_model_usage(agent, model, provider, task, input_tokens, output_tokens,
                cache_read_tokens, calls, estimated_cost_usd, cost_status, first_seen, last_seen)
              VALUES(?,?,?,?,?,?,?,1,?,?,?,?)
              ON CONFLICT(agent, model, provider, task) DO UPDATE SET
                input_tokens = input_tokens + excluded.input_tokens,
                output_tokens = output_tokens + excluded.output_tokens,
                cache_read_tokens = cache_read_tokens + excluded.cache_read_tokens,
                calls = calls + 1,
                estimated_cost_usd = estimated_cost_usd + excluded.estimated_cost_usd,
                cost_status = excluded.cost_status,
                last_seen = excluded.last_seen
            """,
                (
                    agent,
                    model,
                    provider,
                    task,
                    input_tokens,
                    output_tokens,
                    cache_read,
                    estimated_cost_usd,
                    cost_status,
                    now,
                    now,
                ),
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass  # best-effort : le comptage ne casse jamais un appel


_ZERO = {"input_tokens": 0, "output_tokens": 0, "calls": 0}


def total(agent, chemin=None) -> dict:
    # revue D : c'est un chemin de LECTURE (affiché sur GET) — connexion RO + fail-soft.
    # Jamais connexion_ecriture ici : pas de PRAGMA WAL/verrou d'écriture ni de fichier vide créé,
    # et JAMAIS de 500 sur une vue (SPEC §16). Table/fichier absent => compteurs à zéro.
    cible = chemin or chemin_ecriture()
    try:
        con = sqlite3.connect(f"file:{cible}?mode=ro", uri=True, timeout=8)
        con.row_factory = sqlite3.Row
        try:
            r = con.execute(
                "SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o, "
                "COALESCE(SUM(calls),0) c FROM secw_model_usage WHERE agent=?",
                (agent,),
            ).fetchone()
            return {"input_tokens": r["i"], "output_tokens": r["o"], "calls": r["c"]}
        finally:
            con.close()
    except Exception:
        return dict(_ZERO)
