"""Actions concrètes de la secrétaire (Phase 2b) : amorcer/reprendre un brouillon,
cocher une tâche (overlay), mettre un envoi en file d'attente (JAMAIS d'envoi réel)."""

import hashlib
from datetime import datetime

import actions
import cerveau
import config
import contrats
import jsonutil
import overlays
import roles
from entrepot import connexion_ecriture
from garde import (
    encadrer_donnee,
)  # revue Orchestrateur MAJEUR-1 : source unique de la fence

PROFIL = cerveau.ProviderProfile(nom="claude", mode="claude_cli", model="sonnet")


def amorcer_brouillon(event_id, contenu, canal, chemin=None) -> dict:
    system = roles.charger("secretaire")
    consigne, bloc = encadrer_donnee(contenu)
    prompt = (
        consigne + "\n\n" + bloc + "\n\n"
        'Réponds UNIQUEMENT en JSON : {"brouillon": "...", '
        '"attendu": ["..."], "hors": ["..."]}. '
        "brouillon = réponse courte et vouvoyée ; attendu = ce que l'utilisateur doit faire ; "
        "hors = ce qui sort de ton périmètre. "
        "N'invente AUCUN prix, référence, IBAN ni montant absent du message ci-dessus."
    )
    r = cerveau.appeler(
        "secretaire", prompt, PROFIL, "brouillon", system=system, chemin=chemin
    )
    if not r["ok"]:
        return {"ok": False, "erreur": r["erreur"]}
    data = jsonutil.extraire(r["texte"])
    if not data:  # revue : pas de brouillon vide silencieux
        return {"ok": False, "erreur": "json_illisible"}
    brouillon = data.get("brouillon", "")
    attendu = data.get("attendu", [])
    hors = data.get("hors", [])
    overlays.enregistrer_brouillon(
        event_id, canal, contenu, brouillon, attendu, hors, chemin
    )
    return {"ok": True, "brouillon": brouillon, "attendu": attendu, "hors": hors}


def _canal_brouillon(b: dict) -> str:
    # le canal n'est pas relu par overlays.lire_brouillon (pas dans le SELECT *) ; défaut neutre,
    # sans impact fonctionnel Phase 2b (revue self-review PLAN_PHASE2B).
    return "gmail"


def reprendre_brouillon(event_id, consigne, chemin=None) -> dict:
    """« Parler à la secrétaire » : relit le brouillon courant + la consigne de l'utilisateur -> cerveau
    -> met à jour le brouillon shadow (Task 5)."""
    b = overlays.lire_brouillon(event_id, chemin)
    if not b:
        return {"ok": False, "erreur": "aucun_brouillon"}
    system = roles.charger("secretaire")
    prompt = (
        'Brouillon actuel :\n"""\n' + b["brouillon"] + '\n"""\n'
        "Consigne de l'utilisateur : " + (consigne or "") + "\n"
        'Renvoie UNIQUEMENT le JSON {"brouillon":"...","attendu":[...],"hors":[...]} '
        "avec le brouillon révisé."
    )
    r = cerveau.appeler(
        "secretaire", prompt, PROFIL, "brouillon", system=system, chemin=chemin
    )
    if not r["ok"]:
        return {"ok": False, "erreur": r["erreur"]}
    data = jsonutil.extraire(r["texte"]) or {}
    overlays.enregistrer_brouillon(
        event_id,
        _canal_brouillon(b),
        b["contexte"],
        data.get("brouillon", b["brouillon"]),
        data.get("attendu", b["attendu"]),
        data.get("hors", b["hors"]),
        chemin,
    )
    return {"ok": True}


def dispo_envoi() -> bool:
    """check_fn de l'action « envoyer » : vrai seulement en mode prod -> bouton masqué en test."""
    return config.mode() == "prod"


def envoyer_staging(event_id, chemin=None) -> dict:
    """« Envoyer » = staging ledger uniquement (Task 6). Enregistre une obligation `pending`
    dans secw_delivery_obligations et journalise « aurait envoyé ». N'ENVOIE RIEN."""
    b = overlays.lire_brouillon(event_id, chemin)
    if not b:
        return {"ok": False, "erreur": "aucun_brouillon"}
    # Contrats AVANT toute écriture : un refus ne doit laisser aucune trace en base.
    # `is_draft=True` = déclaration honnête de ce que fait cette fonction — rien ne part,
    # l'obligation reste `pending` jusqu'à un geste humain.
    ok, raison = contrats.valider(
        {"type": "envoi_externe", "is_draft": True, "texte": b["brouillon"] or ""}
    )
    if not ok:
        return {"ok": False, "erreur": "contrat_refuse", "raison": raison}
    con = connexion_ecriture(chemin)
    try:
        h = hashlib.sha1((b["brouillon"] or "").encode("utf-8", "replace")).hexdigest()[
            :12
        ]
        con.execute(
            "INSERT OR REPLACE INTO secw_delivery_obligations(id, cible, contenu_hash, statut, created_at, note) "
            "VALUES(?,?,?, 'pending', ?, 'aurait envoyé (mode test)')",
            (f"d{event_id}", b.get("id", ""), h, datetime.now().isoformat()),
        )
        con.commit()
    finally:
        con.close()
    return {"ok": True, "envoye_reellement": False}


# Enregistrement des actions du registre (Task 2), effectif dès l'import de ce module
# (importé au boot du serveur, cf. serveur.py) — cf. PLAN_PHASE2B Task 6.
actions.enregistrer(
    actions.Action("copier", "Copier le texte", handler=lambda **k: None)
)
actions.enregistrer(
    actions.Action("envoyer", "Envoyer", handler=envoyer_staging, check_fn=dispo_envoi)
)
