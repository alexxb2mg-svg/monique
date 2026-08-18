<p align="center">
  <img src="app/static/avatars/secretaire.png" alt="Monique" width="360">
</p>

<h1 align="center">Monique</h1>

<p align="center"><em>Your delightfully paranoid AI secretary. She reads everything, writes nothing you didn't approve, and physically cannot email your ex.</em></p>

---

Meet **Monique** — a local-first, human-in-the-loop shell for running AI agents on *your own* data (your inbox, your files, your little business) without the classic *"oops, the AI just sent 400 emails"* incident.

Monique has exactly one deeply held belief: **read the real world, write only in her sandbox notebook** — until *you* say otherwise. Everything she does in production hides behind a single switch that you, and only you, get to flip.

## Her four house rules

1. **She reads reality; she writes in pencil.** Your real data is opened strictly read-only. Everything Monique writes lands in a sandbox (`MODE=test`, the default). Flip `SECRETAIRE_MODE=prod` the day you trust her. There's a guard that literally *raises an exception* if any code so much as tries to write your real store while in test mode. She takes this seriously.

2. **Her brain lives in a padded cell.** The LLM runs with `--strict-mcp-config` and **zero tools** — no files, no shell, no send button. She *cannot* email, delete, or leak anything, because we took away her scissors. Delegating to a sub-agent is safe by construction: there's simply nothing dangerous to delegate *with*.

3. **An orchestrator that knows who does what.** An incoming request is routed by where it came from (no LLM needed), then by a constrained `claude -p` classifier if she's unsure, then by a safe default (the secretary herself). She even notices recurring work nobody handles and politely suggests hiring a new agent for it.

4. **Nothing leaves the building without your signature.** Draft replies, reminders, follow-ups — Monique *proposes*, you *approve*. The "Send" button doesn't even show up unless you're in prod. She would rather ask twice than send once by mistake.

## What Monique is *not*

A chatbot. An autonomous agent doing things while you sleep. Married to a single AI vendor. Accidentally in production. (She boots in `test` mode and touches absolutely nothing.)

## Her desk

Nine tabs, from *today's briefing* and *the inbox* to *tasks*, *follow-ups*, *monitoring*, plus **Settings**, a **Scheduler**, a **Providers & Keys** vault, and **Agents** — where the whole pixel-art crew lives.

## Quick start

```bash
pip install -r app/requirements.txt
cp .env.example .env              # optional — sensible defaults otherwise
cd app && python -m pytest -q     # 106 tests, all green
python -m uvicorn serveur:app --host 127.0.0.1 --port 8770
```

Open `http://127.0.0.1:8770`. In test mode she scribbles in a sandbox (`monique_shadow.db`) and sends nothing. Pinky promise.

## Configuration

Everything is set via environment variables with safe defaults — see [`.env.example`](.env.example). No machine paths are hardcoded; every install points at its own.

## Security

Monique is paranoid, and we mean that as the highest compliment:

- **Secrets** live in a vault *outside* the repo (never in code, never in a log, never echoed back).
- **The brain has no tools**, so a malicious email can't trick her into reading the vault and pasting it into a draft.
- **The repo itself** is guarded by `gitleaks` (signature secrets), two homemade sentinels — one for real names, one for machine paths — running in pre-commit *and* CI, plus **CodeQL**, **pip-audit**, and **Dependabot**.

Details in [`SECURITY.md`](SECURITY.md).

## Stack

FastAPI + HTMX (no build step, no npm, no bundler), SQLite, Python 3.10. 106 tests. That's the whole party.

## License

MIT — see [`LICENSE`](LICENSE). Monique believes in your freedom. She just wishes you'd let her draft the release notes.
