"""The only sanctioned way for the agent to add bullets and skills to the KB.

Auto-approval policy (2026-11-18, docs/DECISIONS.md):
- A new bullet variant is saved straight away as status "approved", with
  approved_at + approved_text_sha256 and source "agent_generated" or
  "claude_generated" so that it stays traceable. Elliot's review is his Overleaf edit;
  the renderer marks such bullets with "% REVIEW: agent-written wording".
- A skill found in a job description that isn't in skills.json is added with
  confirmation_status "unconfirmed" (tracking only) and cv_eligible true, and
  renders immediately with "% REVIEW: new skill from job description".

Hard limits that still apply:
- Rewording is fine; new claims are not. add_bullet_variant() refuses any
  number that does not already appear in the linked achievements' facts or
  metrics. The caller must also not introduce new technologies, employers,
  responsibilities, dates or links, and must never contradict docs/DECISIONS.md.
- add_skill() must not be called for a skill that clearly contradicts the KB.
  It returns the existing ID when the name or an alias already exists.

Every write keeps a .bak, writes atomically, re-runs the validator, and rolls
back if the validator reports an error.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from cv_engine.kb import KB_DIR, SCHEMA_DIR, load_json, sha256, validate_kb

AGENT_SOURCES = ("agent_generated", "claude_generated")
SKILL_CATEGORIES = ("programming", "machine_learning", "data_engineering", "cloud", "statistics",
                    "tools", "domain", "other", "spoken_language")


class KBWriteError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _numbers(text: str) -> set[str]:
    """Numeric tokens with thousands separators removed: '12,600' -> '12600'."""
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def _snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "x"


def _save(kb_dir: Path, name: str, data) -> None:
    path = kb_dir / f"{name}.json"
    backup = path.with_suffix(".json.bak")
    shutil.copy2(path, backup)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    rep = validate_kb.run(kb_dir, SCHEMA_DIR)
    if rep.errors:
        shutil.copy2(backup, path)
        raise KBWriteError(f"{name}.json write rolled back; validator errors: {rep.errors}")


def _all_ids(kb_dir: Path) -> set[str]:
    ids = set()
    for name in ("experiences", "projects", "achievements", "skills", "bullet_variants", "education"):
        for rec in load_json(kb_dir / f"{name}.json")[name]:
            ids.add(rec["id"])
            ids.update(c["id"] for c in rec.get("coursework", []))
    ids.update(i["id"] for i in load_json(kb_dir / "profile.json")["interests"])
    return ids


def add_bullet_variant(achievement_ids: list[str], text: str, *, source: str = "agent_generated",
                       priority: int = 3, skill_ids: list[str] | None = None,
                       emphasis: list[str] | None = None, bullet_id: str | None = None,
                       kb_dir: Path = KB_DIR) -> str:
    """Save a reworded bullet as an approved variant and return its ID.

    Returns the existing ID if a bullet with identical text already exists.
    """
    if source not in AGENT_SOURCES:
        raise KBWriteError(f"source must be one of {AGENT_SOURCES}")
    text = " ".join(text.split())
    if not text:
        raise KBWriteError("empty bullet text")
    if "\\" in text or "$" in text:
        raise KBWriteError("store plain Unicode text, not LaTeX")
    achs = {a["id"]: a for a in load_json(kb_dir / "achievements.json")["achievements"]}
    missing = [a for a in achievement_ids if a not in achs]
    if missing:
        raise KBWriteError(f"unknown achievement IDs: {missing}")
    parents = {(achs[a]["parent_type"], achs[a]["parent_id"]) for a in achievement_ids}
    if len(parents) != 1:
        raise KBWriteError("a bullet must link achievements from a single experience/project")

    # Guard against invented metrics: every number must already be in the evidence.
    corpus = " ".join(
        " ".join(achs[a]["facts"]) + " " + (achs[a]["description"] or "") + " "
        + " ".join(f"{m['value']} {m['unit']} {m['context'] or ''}" for m in achs[a]["metrics"])
        for a in achievement_ids)
    new_numbers = _numbers(text) - _numbers(corpus)
    if new_numbers:
        raise KBWriteError(f"numbers not supported by the linked achievements: {sorted(new_numbers)}")

    skills = {s["id"] for s in load_json(kb_dir / "skills.json")["skills"]}
    skill_ids = list(dict.fromkeys(skill_ids or []))
    if set(skill_ids) - skills:
        raise KBWriteError(f"unknown skill IDs: {sorted(set(skill_ids) - skills)}")

    data = load_json(kb_dir / "bullet_variants.json")
    for b in data["bullet_variants"]:
        if b["text"] == text:
            return b["id"]

    if bullet_id is None:
        stem = "bullet_" + re.sub(r"^ach_", "", achievement_ids[0]) + ("_ag" if source == "agent_generated" else "_cl")
        taken, n = _all_ids(kb_dir), 1
        while f"{stem}{n}" in taken:
            n += 1
        bullet_id = f"{stem}{n}"
    elif bullet_id in _all_ids(kb_dir):
        raise KBWriteError(f"ID '{bullet_id}' already exists")

    data["bullet_variants"].append({
        "id": bullet_id,
        "achievement_ids": list(achievement_ids),
        "text": text,
        "emphasis": list(dict.fromkeys(emphasis or [])),
        "skill_ids": skill_ids,
        "status": "approved",
        "source": source,
        "priority": int(priority),
        "approved_at": _now(),
        "approved_text_sha256": sha256(text),
    })
    _save(kb_dir, "bullet_variants", data)
    return bullet_id


def add_skill(name: str, category: str, *, aliases: list[str] | None = None,
              evidence_achievement_ids: list[str] | None = None, proficiency: str | None = None,
              skill_id: str | None = None, kb_dir: Path = KB_DIR) -> str:
    """Add a skill found in a job description (stored as unconfirmed, renders immediately).

    Returns the existing ID if the name or any alias is already known (case-insensitive).
    """
    name = name.strip()
    if not name:
        raise KBWriteError("empty skill name")
    if category not in SKILL_CATEGORIES:
        raise KBWriteError(f"category must be one of {SKILL_CATEGORIES}")
    if category == "spoken_language" and not proficiency:
        raise KBWriteError("spoken-language skills need a proficiency")
    aliases = [a.strip() for a in (aliases or []) if a.strip() and a.strip().lower() != name.lower()]
    data = load_json(kb_dir / "skills.json")
    wanted = {name.lower(), *(a.lower() for a in aliases)}
    for s in data["skills"]:
        known = {s["name"].lower(), *(a.lower() for a in s["aliases"])}
        if wanted & known:
            return s["id"]
    achs = {a["id"] for a in load_json(kb_dir / "achievements.json")["achievements"]}
    evidence = list(dict.fromkeys(evidence_achievement_ids or []))
    if set(evidence) - achs:
        raise KBWriteError(f"unknown achievement IDs: {sorted(set(evidence) - achs)}")
    skill_id = skill_id or f"skill_{_snake(name)}"
    if skill_id in _all_ids(kb_dir):
        raise KBWriteError(f"ID '{skill_id}' already exists")
    data["skills"].append({
        "id": skill_id,
        "name": name,
        "category": category,
        "aliases": list(dict.fromkeys(aliases)),
        "evidence_achievement_ids": evidence,
        "cv_eligible": True,
        "proficiency": proficiency if category == "spoken_language" else None,
        "confirmation_status": "unconfirmed",
    })
    _save(kb_dir, "skills", data)
    return skill_id
