#!/usr/bin/env python3
"""Review and approve CV bullet variants (schema v1.3).

Approval records the exact text you saw: status "approved", a UTC timestamp,
and the SHA-256 of the UTF-8 text. If the text changes later, the hash no
longer matches and the validator treats the approval as invalid.

Usage (run from the project root):
    python tools/approve_bullets.py                 # interactive review of all proposed bullets
    python tools/approve_bullets.py --list          # status overview
    python tools/approve_bullets.py --approve ID [ID ...]
    python tools/approve_bullets.py --reject  ID [ID ...]
    python tools/approve_bullets.py --revoke  ID [ID ...]   # back to proposed
Options:
    --kb PATH   knowledge_base directory (default: ./knowledge_base next to tools/)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(kb: Path, name: str):
    return json.loads((kb / f"{name}.json").read_text(encoding="utf-8"))


def save_bullets(kb: Path, data) -> None:
    path = kb / "bullet_variants.json"
    shutil.copy2(path, path.with_suffix(".json.bak"))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def state(b) -> str:
    if b["status"] == "approved" and b["approved_text_sha256"] != sha256(b["text"]):
        return "STALE"  # text edited after approval
    return b["status"]


def set_status(b, status: str) -> None:
    b["status"] = status
    if status == "approved":
        b["approved_at"] = now_utc()
        b["approved_text_sha256"] = sha256(b["text"])
    else:
        b["approved_at"] = None
        b["approved_text_sha256"] = None


class Context:
    def __init__(self, kb: Path):
        self.kb = kb
        self.data = load(kb, "bullet_variants")
        self.bullets = {b["id"]: b for b in self.data["bullet_variants"]}
        self.achs = {a["id"]: a for a in load(kb, "achievements")["achievements"]}
        names = {e["id"]: e["organization"] for e in load(kb, "experiences")["experiences"]}
        names.update({p["id"]: p["name"] for p in load(kb, "projects")["projects"]})
        self.parent_name = names

    def entry_of(self, b) -> str:
        parents = {self.achs[a]["parent_id"] for a in b["achievement_ids"] if a in self.achs}
        return ", ".join(self.parent_name.get(p, p) for p in sorted(parents))

    def show(self, b, n=None, total=None) -> None:
        head = f"[{n}/{total}] " if n else ""
        print("\n" + "=" * 78)
        print(f"{head}{b['id']}   ({self.entry_of(b)} · priority {b['priority']} · {state(b)})")
        print("-" * 78)
        print(textwrap.fill(b["text"], 78))
        print("-" * 78)
        for aid in b["achievement_ids"]:
            a = self.achs.get(aid)
            if not a:
                continue
            print(f"Supported by {aid} ({a['verification_status']}):")
            for f in a["facts"]:
                print(textwrap.fill(f, 76, initial_indent="  • ", subsequent_indent="    "))
            for m in a["metrics"]:
                flag = "" if m["verification_status"] == "verified" else "   <-- not yet verified"
                print(f"  # {m['value']} {m['unit']}{flag}")


def cmd_list(ctx: Context) -> None:
    order = {"proposed": 0, "STALE": 1, "approved": 2, "rejected": 3}
    for b in sorted(ctx.bullets.values(), key=lambda x: (order[state(x)], ctx.entry_of(x), x["id"])):
        print(f"{state(b):9} {b['id']:40} {ctx.entry_of(b)}")
    counts = {}
    for b in ctx.bullets.values():
        counts[state(b)] = counts.get(state(b), 0) + 1
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))


def cmd_batch(ctx: Context, ids, status: str, assume_yes: bool) -> int:
    missing = [i for i in ids if i not in ctx.bullets]
    if missing:
        print("Unknown bullet IDs:", ", ".join(missing))
        return 1
    for n, i in enumerate(ids, 1):
        ctx.show(ctx.bullets[i], n, len(ids))
    verb = {"approved": "Approve", "rejected": "Reject", "proposed": "Revoke approval for"}[status]
    if not assume_yes:
        ans = input(f"\n{verb} these {len(ids)} bullet(s) exactly as shown? [y/N] ").strip().lower()
        if ans != "y":
            print("Nothing changed.")
            return 0
    for i in ids:
        set_status(ctx.bullets[i], status)
    save_bullets(ctx.kb, ctx.data)
    print(f"{verb.split()[0]}d {len(ids)} bullet(s). Backup: bullet_variants.json.bak")
    return 0


def cmd_interactive(ctx: Context) -> int:
    queue = [b for b in ctx.bullets.values() if state(b) in ("proposed", "STALE")]
    if not queue:
        print("No bullets waiting for review.")
        return 0
    print(f"{len(queue)} bullet(s) to review. a = approve, r = reject, s = skip, q = save and quit.")
    changed = 0
    for n, b in enumerate(queue, 1):
        ctx.show(b, n, len(queue))
        while True:
            ans = input("[a]pprove / [r]eject / [s]kip / [q]uit > ").strip().lower()
            if ans in ("a", "r", "s", "q"):
                break
        if ans == "q":
            break
        if ans == "a":
            set_status(b, "approved")
            changed += 1
        elif ans == "r":
            set_status(b, "rejected")
            changed += 1
    if changed:
        save_bullets(ctx.kb, ctx.data)
        print(f"\nSaved {changed} decision(s). Backup: bullet_variants.json.bak")
    else:
        print("\nNothing changed.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", type=Path, default=ROOT / "knowledge_base")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--list", action="store_true")
    g.add_argument("--approve", nargs="+", metavar="ID")
    g.add_argument("--reject", nargs="+", metavar="ID")
    g.add_argument("--revoke", nargs="+", metavar="ID")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt for batch commands")
    args = ap.parse_args(argv)

    ctx = Context(args.kb)
    if args.list:
        cmd_list(ctx)
        return 0
    if args.approve:
        rc = cmd_batch(ctx, args.approve, "approved", args.yes)
    elif args.reject:
        rc = cmd_batch(ctx, args.reject, "rejected", args.yes)
    elif args.revoke:
        rc = cmd_batch(ctx, args.revoke, "proposed", args.yes)
    else:
        rc = cmd_interactive(ctx)

    # Re-validate the whole knowledge base after any change.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import validate_kb
        print("\nValidating knowledge base…")
        rc = validate_kb.main(["--kb", str(args.kb), "--schemas", str(args.kb.parent / "schemas")]) or rc
    except ImportError:
        pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
