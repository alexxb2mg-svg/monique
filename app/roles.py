"""Chargement du fichier de rôle d'un agent (agents/<nom>/ROLE.md), avec défaut de secours.

Le fichier de rôle porte un en-tête (front-matter) de routage optionnel suivi du corps
(system prompt). `parse_role`/`carte_agents` lisent l'en-tête pour le routage (jamais le
corps, cf. isolation orchestrateur) ; `charger` renvoie le corps seul, pour l'injection
en system prompt de `cerveau`.
"""

import re
from pathlib import Path

RACINE_AGENTS = Path(__file__).parent.parent / "agents"
_NOM_AGENT = re.compile(
    r"^[a-z0-9_-]+$"
)  # M4 : nom d'agent canonique (jamais de path traversal)
DEFAUT = (
    "Tu es la secrétaire de l'entreprise. Tu débroussailles les messages entrants : "
    "tu rattaches au contexte, amorces une réponse vouvoyée, listes ce qui est "
    "attendu et ce qui sort de ton périmètre. Tu proposes, tu n'envoies jamais."
)


def _parse_frontmatter(texte: str) -> tuple[dict, str]:
    # front-matter minimal, sans dépendance YAML (règle supply-chain)
    if not texte.startswith("---"):
        return {}, texte
    fin = texte.find("\n---", 3)
    if fin == -1:
        return {}, texte
    entete, corps = texte[3:fin], texte[fin + 4 :]
    meta = {}
    for ligne in entete.splitlines():
        if ":" not in ligne:
            continue
        cle, val = ligne.split(":", 1)
        cle, val = cle.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            meta[cle] = [x.strip() for x in val[1:-1].split(",") if x.strip()]
        else:
            meta[cle] = val
    return meta, corps


def parse_role(agent: str) -> dict:
    # M4 : refuser tout nom non canonique (empêche RACINE_AGENTS/../.. ou une entrée de route hostile)
    if not _NOM_AGENT.match(agent or ""):
        return {"name": agent, "triggers": [], "description": "", "corps": DEFAUT}
    f = RACINE_AGENTS / agent / "ROLE.md"
    # M-3 : utf-8-sig => un ROLE.md enregistré avec BOM (Notepad Windows) parse quand même son en-tête.
    texte = f.read_text(encoding="utf-8-sig") if f.exists() else ""
    meta, corps = _parse_frontmatter(texte)
    return {
        "name": meta.get("name", agent),
        "triggers": meta.get("triggers_deterministes", []),
        "description": meta.get("description_routage", ""),
        "departement": meta.get(
            "departement", "Non affecté"
        ),  # org vivante : Beecham fait grandir
        "corps": corps or DEFAUT,
    }


def carte_agents() -> dict:
    out = {}
    if RACINE_AGENTS.exists():
        for d in RACINE_AGENTS.iterdir():
            if (d / "ROLE.md").exists():
                out[d.name] = parse_role(d.name)
    return out


def carte_departements() -> dict:
    """Agents groupés par département (nav vivante à 2 niveaux). L'ordre des départements
    suit leur première apparition ; Beecham peut ajouter agents et départements."""
    out = {}
    for nom, fiche in carte_agents().items():
        out.setdefault(fiche.get("departement") or "Non affecté", {})[nom] = fiche
    return out


def charger(agent: str) -> str:
    # revue B1 : REMPLACE le charger de Phase 2b. Renvoie le CORPS seul (front-matter retiré),
    # sinon l'en-tête de routage polluerait le system prompt injecté dans cerveau.
    try:
        return parse_role(agent)["corps"]
    except Exception:
        return DEFAUT
