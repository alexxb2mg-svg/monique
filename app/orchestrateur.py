"""Orchestrateur : routage d'une demande entrante vers le bon agent-persona durable.

Déterministe par provenance d'abord (score de spécificité sur les triggers de l'en-tête
de rôle), classifieur LLM contraint en secours sur le résidu, défaut sûr `secretaire`.
Le routeur ne lit jamais le corps d'un rôle, seulement son en-tête.
"""

import re
import sqlite3
from datetime import datetime

import cerveau
import garde
import jsonutil
import roles
from config import chemin_ecriture
from entrepot import connexion_ecriture

_CANAL = {
    "gmail": "email",
    "mail": "email",
    "whatsapp": "whatsapp",
    "wa": "whatsapp",
    "sms": "sms",
}


def _match_trigger(trigger: str, signaux: dict) -> bool:
    if "=" not in trigger:
        return False
    cle, val = trigger.split("=", 1)
    cle, val = (
        cle.strip().lower(),
        val.strip().lower(),
    )  # MINEUR-7 : normalisation casse des deux côtés
    if cle == "tag":
        return val in [str(t).lower() for t in (signaux.get("tags") or [])]
    cible = signaux.get(cle)
    if isinstance(cible, (list, tuple, set)):
        return val in [str(x).lower() for x in cible]
    return str(cible).lower() == val


def router_deterministe(signaux: dict, agents: dict) -> str | None:
    scores = {
        nom: sum(1 for t in f.get("triggers", []) if _match_trigger(t, signaux))
        for nom, f in agents.items()
    }
    top = max(scores.values(), default=0)
    if top == 0:
        return None  # aucun trigger => résidu (LLM)
    gagnants = [n for n, s in scores.items() if s == top]
    return (
        gagnants[0] if len(gagnants) == 1 else None
    )  # revue M1 : ambiguïté => defer (jamais l'ordre disque)


def signaux_depuis(event: dict) -> dict:
    src = (event.get("source") or "").lower()
    tags = [
        str(t).lower() for t in (event.get("tags") or [])
    ]  # MINEUR-7 : tags normalisés
    return {"canal": _CANAL.get(src, src), "tags": tags}


def _signature(event: dict) -> str:
    # libellé grossier du motif non routé (canal + mots-clés) — à raffiner plus tard
    s = signaux_depuis(event)
    mots = re.findall(r"[a-zàâéèêîôûùç]{4,}", (event.get("contenu") or "").lower())[:3]
    return (s.get("canal") or "?") + ":" + "-".join(sorted(set(mots)))


def _defaut(agents: dict) -> str:
    return "secretaire" if "secretaire" in agents else next(iter(agents), "secretaire")


def classifier_llm(message: str, agents: dict, chemin=None) -> dict:
    # revue B2 : renvoie {agent, repli}. repli=True => pas de match franc => signal de suggestion.
    catalogue = "\n".join(
        f"- {n} : {f.get('description', '')}" for n, f in agents.items()
    )
    # MAJEUR-1 (SPEC §14 C1) : le message tiers est une DONNÉE, encadré à nonce — pas d'évasion de fence.
    consigne, bloc = garde.encadrer_donnee((message or "")[:2000])
    prompt = (
        "Agents disponibles :\n"
        + catalogue
        + "\n\n"
        + consigne
        + "\n\n"
        + bloc
        + "\n\nEn te fondant sur le message ci-dessus, réponds UNIQUEMENT en JSON "
        '{"agent": "<nom exact>"}. Si tu hésites, choisis "secretaire".'
    )
    prof = cerveau.ProviderProfile(nom="claude", mode="claude_cli", model="sonnet")
    r = cerveau.appeler("orchestrateur", prompt, prof, "routage", chemin=chemin)
    if not r.get("ok"):
        # MINEUR-5 : panne cerveau (estop/binaire absent/rate limit) => défaut, mais PAS un « non-routé »
        # (une panne d'infra ne doit pas fabriquer de suggestion d'agent).
        return {"agent": _defaut(agents), "repli": False}
    choix = (jsonutil.extraire(r.get("texte", "")) or {}).get("agent")
    if choix in agents:
        return {"agent": choix, "repli": False}
    return {"agent": _defaut(agents), "repli": True}


def router(event: dict, chemin=None) -> str:
    agents = roles.carte_agents()
    det = router_deterministe(signaux_depuis(event), agents)
    if det:
        return det  # provenance claire => zéro LLM
    res = classifier_llm(event.get("contenu", ""), agents, chemin)
    if res["repli"]:
        sig = _signature(event)
        if not sig.endswith(
            ":"
        ):  # MINEUR-4 : pas de mots discriminants => pas de suggestion
            try:
                noter_non_route(sig, (event.get("contenu") or "")[:200], chemin=chemin)
            except Exception:
                pass  # défensif : le routage ne doit jamais échouer sur la suggestion
    return res["agent"]


def noter_non_route(signature, exemple="", seuil=5, chemin=None) -> None:
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "INSERT INTO secw_suggestions(signature, compteur, exemples, maj_le) VALUES(?,1,?,?) "
            "ON CONFLICT(signature) DO UPDATE SET compteur=compteur+1, maj_le=excluded.maj_le",
            (signature, exemple, datetime.now().isoformat()),
        )
        con.execute(
            "UPDATE secw_suggestions SET statut='a_proposer' WHERE signature=? AND compteur>=? AND statut='observe'",
            (signature, seuil),
        )
        con.commit()
    finally:
        con.close()


def suggerer(chemin=None) -> list:
    # lecture pure => connexion RO fail-soft (Angle 5) : ne crée pas de fichier 0-octet,
    # ne prend pas de verrou d'écriture, ne lève jamais sur une base/table absente.
    cible = chemin or chemin_ecriture()
    try:
        con = sqlite3.connect(f"file:{cible}?mode=ro", uri=True, timeout=8)
        con.row_factory = sqlite3.Row
        try:
            return [
                dict(r)
                for r in con.execute(
                    "SELECT signature, compteur, exemples FROM secw_suggestions WHERE statut='a_proposer' "
                    "ORDER BY compteur DESC"
                )
            ]
        finally:
            con.close()
    except Exception:
        return []


def deleguer(but: str, contexte="", chemin=None) -> dict:
    system = (
        "Tu es un sous-agent focalisé sur UNE tâche déléguée. "
        "Fais exactement ce qui est demandé, puis renvoie un RÉSUMÉ serré. "
        "Tu n'envoies rien, tu ne délègues pas plus loin."
    )
    prompt = "TÂCHE :\n" + but + (("\n\nCONTEXTE :\n" + contexte) if contexte else "")
    prof = cerveau.ProviderProfile(nom="claude", mode="claude_cli", model="sonnet")
    r = cerveau.appeler(
        "delegation", prompt, prof, "delegation", system=system, chemin=chemin
    )
    if not r.get("ok"):
        return {"ok": False, "erreur": r.get("erreur")}
    return {"ok": True, "resume": r["texte"]}
