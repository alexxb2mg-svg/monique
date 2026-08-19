import re

_RE_DEBUT = re.compile(r"^- \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+ · ", re.MULTILINE)
_RE_AGENT = re.compile(r"^- \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+ · (\S+) · ")


def digest_texte(texte_journal: str, n_dernieres: int = 20) -> dict:
    """Résume les n_dernieres entrées d'un journal (texte brut) : compte par statut.

    Une entrée commence par une ligne '- AAAA-MM-JJThh:mm:ss.ffffff · <agent> · ...'
    mais peut s'étendre sur plusieurs lignes physiques (résumé multi-paragraphe) —
    elle se termine juste avant le début de l'entrée suivante, ou la fin du texte.
    Le statut est toujours le dernier segment après le dernier ' · ' de l'entrée
    entière, quelle que soit la ligne physique où il se trouve.

    Fonction pure (ne lit aucun fichier) — même patron que
    vue_missions.contexte_missions_actives().
    """
    if not texte_journal or not texte_journal.strip():
        return {"total": 0, "compte": {}, "entrees": []}

    debuts = [m.start() for m in _RE_DEBUT.finditer(texte_journal)]
    blocs = []
    for i, debut in enumerate(debuts):
        fin = debuts[i + 1] if i + 1 < len(debuts) else len(texte_journal)
        blocs.append(texte_journal[debut:fin].rstrip("\n\r"))

    dernieres = blocs[-n_dernieres:] if n_dernieres > 0 else []

    compte: dict = {}
    entrees = []
    for bloc in dernieres:
        m = _RE_AGENT.match(bloc)
        agent = m.group(1) if m else ""
        if " · " in bloc:
            statut = bloc.rsplit(" · ", 1)[-1].strip()
        else:
            statut = ""
        compte[statut] = compte.get(statut, 0) + 1
        entrees.append({"agent": agent, "statut": statut})

    return {"total": len(dernieres), "compte": compte, "entrees": entrees}
