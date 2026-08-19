import os
import sqlite3
from config import chemin_ecriture, chemin_lecture, mode

FONDATIONS_SQL = """
CREATE TABLE IF NOT EXISTS secw_model_usage(
  agent TEXT, model TEXT, provider TEXT, task TEXT,
  input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
  cache_read_tokens INTEGER DEFAULT 0, calls INTEGER DEFAULT 0,
  estimated_cost_usd REAL DEFAULT 0, cost_status TEXT DEFAULT 'unknown',
  first_seen TEXT, last_seen TEXT,
  PRIMARY KEY(agent, model, provider, task));

CREATE TABLE IF NOT EXISTS secw_turn_lease(
  cle TEXT PRIMARY KEY, owner_pid INTEGER, owner_started_at TEXT, acquired_at TEXT);

CREATE TABLE IF NOT EXISTS secw_delivery_obligations(
  id TEXT PRIMARY KEY, cible TEXT, contenu_hash TEXT,
  statut TEXT DEFAULT 'pending',          -- pending|attempting|delivered|failed|abandoned (revue §13.4)
  attempts INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT, delivered_at TEXT, note TEXT);

CREATE TABLE IF NOT EXISTS secw_pending_writes(
  id TEXT PRIMARY KEY, cible_porte TEXT, contenu TEXT, gist TEXT,
  statut TEXT DEFAULT 'en_attente', origine TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS secw_executions(
  id TEXT PRIMARY KEY, agent TEXT, statut TEXT DEFAULT 'claimed',
  pid INTEGER, process_started_at TEXT, started_at TEXT, finished_at TEXT,
  delivery_outcome TEXT, resultat TEXT);

-- Registre des PROCESSUS de Monique (superviseur, D-16) : tout ce que Monique lance s'y inscrit
-- (nom, proprietaire, but, PID, PID parent) et s'en retire en finissant. Le registre EST le tag :
-- le superviseur n'agit QUE sur ce qui est enregistré + ses descendants — jamais un process tiers.
-- statut : running | fini | orphelin | tue | unknown. process_started_at = heure de démarrage
-- exacte du PID (anti PID recyclé, via lease._debut_de).
CREATE TABLE IF NOT EXISTS secw_processus(
  id TEXT PRIMARY KEY, pid INTEGER, ppid INTEGER,
  nom TEXT, proprietaire TEXT, but TEXT,
  statut TEXT DEFAULT 'running',
  process_started_at TEXT, started_at TEXT, finished_at TEXT);

CREATE TABLE IF NOT EXISTS secw_taches_overlay(
  tache_id INTEGER PRIMARY KEY, statut TEXT, cloture_par TEXT, cloture_le TEXT);

CREATE TABLE IF NOT EXISTS secw_brouillons(
  id TEXT PRIMARY KEY, event_id INTEGER, canal TEXT, contexte TEXT, brouillon TEXT,
  attendu_json TEXT, hors_json TEXT, statut TEXT DEFAULT 'propose', cree_le TEXT, maj_le TEXT);

CREATE TABLE IF NOT EXISTS secw_parametres(
  cle TEXT PRIMARY KEY, valeur TEXT, maj_le TEXT);

CREATE TABLE IF NOT EXISTS secw_jobs(
  id TEXT PRIMARY KEY, module TEXT, libelle TEXT, cible_cmd TEXT, planning_json TEXT,
  enabled INTEGER DEFAULT 1, state TEXT DEFAULT 'scheduled', last_status TEXT,
  failure_streak INTEGER DEFAULT 0, cree_le TEXT);

CREATE TABLE IF NOT EXISTS secw_suggestions(
  signature TEXT PRIMARY KEY, compteur INTEGER DEFAULT 0, statut TEXT DEFAULT 'observe',
  exemples TEXT, maj_le TEXT);

-- Beecham (chef d'orchestre) : missions d'évolution de Monique, gardées (l'utilisateur valide).
-- statut : en_cours | propose | valide | rejete | echec. Tout vit en shadow ; le travail réel
-- se fait dans une branche git jetable (branche), jamais sur le vrai store.
CREATE TABLE IF NOT EXISTS secw_beecham_missions(
  id TEXT PRIMARY KEY, consigne TEXT, statut TEXT DEFAULT 'en_cours', branche TEXT,
  plan TEXT, agents_json TEXT, journal TEXT, diff TEXT, tests_json TEXT,
  suggestions_agents TEXT, cree_le TEXT, maj_le TEXT);
"""


def _appliquer_journal(con, propre: bool):
    con.execute("PRAGMA busy_timeout=8000")
    if not propre:
        return  # revue E1 : store vivant partagé => NE JAMAIS toucher journal_mode (rétrogradation à chaud interdite §13.1)
    # base propre (shadow, ou fichier dédié à la coquille) :
    corrige = sqlite3.sqlite_version_info >= (
        3,
        51,
        3,
    )  # revue §13.1 : WAL seulement si SQLite corrigé (#69784)
    con.execute(
        "PRAGMA journal_mode=WAL" if corrige else "PRAGMA journal_mode=TRUNCATE"
    )
    con.execute(
        "PRAGMA synchronous=FULL"
    )  # revue M4/§13.8 : durabilité des tables « ne pas perdre »


def _est_store_reel(chemin: str) -> bool:
    # revue F7 : comparaison normalisée (casse + slashes Windows) — un chemin explicite vers le
    # vrai store écrit différemment (casse ou slashes différents) ne doit pas contourner la garde.
    return os.path.normcase(os.path.abspath(chemin)) == os.path.normcase(
        os.path.abspath(chemin_lecture())
    )


def connexion_ecriture(chemin: str | None = None) -> sqlite3.Connection:
    cible = chemin or chemin_ecriture()
    vise_reel = _est_store_reel(cible)
    if (
        mode() == "test" and vise_reel
    ):  # revue §13.6 : jamais écrire le vrai store en test
        raise RuntimeError("écriture interdite sur le store réel en MODE=test")
    con = sqlite3.connect(cible, timeout=8)
    try:
        _appliquer_journal(
            con, propre=not vise_reel
        )  # revue E1 : journal propre seulement hors store vivant
        con.row_factory = sqlite3.Row
        return con
    except Exception:
        con.close()  # revue §13.8 : un PRAGMA qui lève ne doit pas fuiter la connexion
        raise


SCHEMA_CIBLE = 2  # revue migration C1 : incrémenter à chaque palier


def _ajouter_colonne(con, table, col, decl):
    # idempotent même si user_version est perdu (restauration d'un backup ancien).
    # No-op si la table n'existe pas encore (palier référençant une table d'une phase ultérieure —
    # ex. secw_jobs, créée en Phase 3 : sinon ALTER sur table absente => 'no such table').
    tables = {
        r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if table not in tables:
        return
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    if col not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def _migrer(con):
    v = con.execute("PRAGMA user_version").fetchone()[0]
    if v >= SCHEMA_CIBLE:
        return  # revue F6 : base d'un code futur (restauration croisée) — ne jamais rétrograder user_version
    if v < 1:  # colonnes anti-poison du ledger (revue REX §13.4)
        _ajouter_colonne(
            con, "secw_delivery_obligations", "attempts", "INTEGER DEFAULT 0"
        )
        _ajouter_colonne(con, "secw_delivery_obligations", "updated_at", "TEXT")
    if v < 2:  # garde-fou planificateur (revue M6, Phase 3)
        _ajouter_colonne(con, "secw_jobs", "cible_cmd", "TEXT")
    con.execute(f"PRAGMA user_version = {SCHEMA_CIBLE}")  # bump EN DERNIER


def init_fondations(chemin: str | None = None) -> None:
    con = connexion_ecriture(chemin)
    con.isolation_level = None
    try:
        con.executescript(FONDATIONS_SQL)  # baseline : CREATE TABLE IF NOT EXISTS
        con.execute(
            "BEGIN IMMEDIATE"
        )  # sérialise les migrations concurrentes (revue M2)
        _migrer(con)  # ALTER pour les bases préexistantes (revue C1)
        con.execute("COMMIT")
    finally:
        con.close()
