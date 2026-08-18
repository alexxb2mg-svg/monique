<p align="center">
  <img src="app/static/avatars/secretaire.png" alt="Monique" width="360">
</p>

<h1 align="center">Monique</h1>

<p align="center"><em>Your delightfully paranoid AI secretary. She reads everything, forgets nothing, writes only what you approved, and — crucially — physically cannot email your ex.</em></p>

<p align="center">🚧 <strong>Status: gloriously unfinished.</strong> Works, tested, and has never once been trusted with the real world. On purpose. 🚧</p>

---

Meet **Monique** — a local-first, human-in-the-loop shell for running AI agents on *your own* data (your inbox, your files, your small business) without the classic *"oh no, the AI just CC'd the entire client list"* incident.

She's an unapologetically **DIY, self-hosted love letter to Nous Research's Hermes Agent** — same spirit, smaller budget, more duct tape, and one very specific personality. Built in a garage (well, for a small electrical business), held together by 106 tests and stubbornness.

**Fair warning:** this is early days. Monique is not a polished SaaS. She's a hobby project with strong opinions and a security streak, still being sanded down. But she boots, she's honest about what she does, and she won't set anything on fire.

## So… what state is she actually in?

- ✅ **The shell works** — nine tabs, an orchestrator, a confined brain, 106 green tests.
- ✅ **She reads your real data** (strictly read-only) and drafts real work.
- 🧪 **She has never been let loose on production** — and right now she *can't* be, by design. Everything she writes goes to a sandbox notebook.
- 🔜 **Growing up is on the roadmap:** actually sending that email, actually scheduling that task, a second AI provider, a self-review loop. All designed, none unleashed. That's the *"still to be perfected"* part, and it's most of the fun.

Think of the sandbox not as a prison sentence but as *training wheels*. One environment variable promotes her to production the day you're brave enough. (`SECRETAIRE_MODE=prod`. There, now you know the magic word. Use it responsibly.)

## Her four house rules

1. **She reads reality; she writes in pencil.** Real data is opened strictly read-only. Everything she writes lands in a sandbox (`MODE=test`, the default). There's a guard that *throws an actual exception* if any code tries to write your real store while in test mode. She would rather crash than color outside the lines.

2. **Her brain lives in a padded cell.** The LLM runs with `--strict-mcp-config` and **zero tools** — no files, no shell, no send button. She *cannot* email, delete, or leak anything, because we confiscated the scissors. Handing a task to a sub-agent is safe by construction: there's nothing dangerous to hand it *with*.

3. **An orchestrator that knows who does what.** Incoming request → routed by where it came from (no LLM, no tokens burned) → a constrained `claude -p` classifier if she's unsure → a safe default (herself). She even notices recurring work nobody handles and, very politely, suggests you hire a new agent for it.

4. **Nothing leaves the building without your signature.** Drafts, reminders, follow-ups — she *proposes*, you *approve*. The "Send" button doesn't even render unless you're in prod. Monique would rather ask twice than send once by mistake. (She's seen things.)

## What Monique is *not*

A chatbot. An autonomous agent doing things while you sleep. Married to one AI vendor. Finished. Accidentally in production (she literally boots in `test` and touches nothing).

## Her desk

Nine tabs: *today's briefing*, *the inbox*, *tasks*, *follow-ups*, *monitoring*, plus **Settings**, a **Scheduler**, a **Providers & Keys** vault, and **Agents** — where the whole pixel-art crew clocks in.

## Quick start

```bash
pip install -r app/requirements.txt
cp .env.example .env              # optional — sensible defaults otherwise
cd app && python -m pytest -q     # 106 tests, all green (we double-checked)
python -m uvicorn serveur:app --host 127.0.0.1 --port 8770
```

Open `http://127.0.0.1:8770`. In test mode she scribbles in a sandbox (`monique_shadow.db`) and sends exactly nothing. Pinky promise, legally binding.

## Configuration

Everything via environment variables with safe defaults — see [`.env.example`](.env.example). No machine paths hardcoded; every install points at its own. She's portable, unlike most secretaries.

## Security

Monique is paranoid, and we mean that as the highest compliment:

- **Secrets** live in a vault *outside* the repo — never in code, never in a log, never read back to you.
- **The brain has no tools**, so a malicious email can't sweet-talk her into reading the vault and pasting it into a reply.
- **The repo itself** is patrolled by `gitleaks` (signature secrets) and two homemade sentinels — one that sniffs out real names, one that sniffs out machine paths — running in pre-commit *and* CI, backed by **CodeQL**, **pip-audit**, and **Dependabot**.

Full paranoia manifest in [`SECURITY.md`](SECURITY.md).

## Roadmap (a.k.a. "still to be perfected")

- Actually sending things (Gmail), for real, in prod — currently a very deliberate placeholder.
- Actually applying scheduled tasks to the OS — read-only for now, on purpose.
- A second AI provider (bring-your-own-API-key), alongside the Claude-via-CLI brain.
- A passive self-review loop that proposes what's worth remembering.
- Less duct tape. (This one's aspirational.)

## Stack

FastAPI + HTMX (no build step, no npm, no bundler, no tears), SQLite, Python 3.10. 106 tests. That's the entire guest list.

## Credits

Spiritually indebted to **Nous Research's Hermes Agent**. Monique is the scrappy home-cooked cousin who reads the same books but insists on doing the dishes by hand.

## License

MIT — see [`LICENSE`](LICENSE). Monique believes in your freedom. She just wishes you'd let her proofread this README first.
