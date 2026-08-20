"""Clique un élément d'ACTION dans un pont (via CDP), sans envoyer de message LLM — p. ex. le bouton
« nouvelle conversation ». Simule un clic humain sur un sélecteur. Python 3.14 (Playwright).

Appelé en sous-processus par ponts.py. Codes : 0 OK, 2 cdp_down, 4 page/élément absent."""
from __future__ import annotations

import argparse
import sys

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--host-hint", default="")
    ap.add_argument("--selecteur", default="", help="Sélecteur Playwright de l'élément à cliquer")
    ap.add_argument("--goto", default="", help="URL vers laquelle naviguer (au lieu de cliquer)")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERR] playwright non installe pour cet interpreteur.", file=sys.stderr)
        return 4

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{args.port}")
        except Exception as e:
            print(f"[ERR] cdp_down : {e}", file=sys.stderr)
            return 2
        ctx = browser.contexts[0]
        page = next(
            (pg for pg in ctx.pages if args.host_hint in (pg.url or "")),
            ctx.pages[0] if ctx.pages else None,
        )
        if page is None:
            print("[ERR] aucune page trouvee.", file=sys.stderr)
            return 4
        page.bring_to_front()
        if args.goto:  # navigation directe (repart vierge, indépendant de la sidebar/boutons)
            try:
                page.goto(args.goto, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                print(f"[ERR] navigation echouee : {e}", file=sys.stderr)
                return 4
            print("goto OK")
            return 0
        el = page.locator(args.selecteur).first
        try:
            el.wait_for(state="visible", timeout=6000)
            el.click()
        except Exception as e:
            print(f"[ERR] element introuvable/non cliquable : {e}", file=sys.stderr)
            return 4
        print("clic OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
