"""Paths and read-only access to the knowledge base."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "knowledge_base"
SCHEMA_DIR = ROOT / "schemas"
ENGINE_DIR = ROOT / "cv_engine"
TEMPLATE_DIR = ENGINE_DIR / "templates"
OUTPUT_DIR = ROOT / "output"

sys.path.insert(0, str(ROOT / "tools"))
import validate_kb  # noqa: E402  (tools/validate_kb.py)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class KB:
    """Indexed, read-only view of the eight knowledge-base files."""

    def __init__(self, kb_dir: Path = KB_DIR):
        self.dir = Path(kb_dir)
        f = lambda n: load_json(self.dir / f"{n}.json")  # noqa: E731
        self.profile = f("profile")
        self.preferences = f("preferences")
        self.education = {e["id"]: e for e in f("education")["education"]}
        self.courses = {c["id"]: c for e in self.education.values() for c in e["coursework"]}
        self.experiences = {e["id"]: e for e in f("experiences")["experiences"]}
        self.projects = {p["id"]: p for p in f("projects")["projects"]}
        self.achievements = {a["id"]: a for a in f("achievements")["achievements"]}
        self.skills = {s["id"]: s for s in f("skills")["skills"]}
        self.bullets = {b["id"]: b for b in f("bullet_variants")["bullet_variants"]}
        self.interests = {i["id"]: i for i in self.profile["interests"]}

    def entry(self, entry_id: str):
        return self.experiences.get(entry_id) or self.projects.get(entry_id) or self.education.get(entry_id)

    def alternatives(self, bullet_id: str):
        """Other non-rejected variants that express exactly the same achievement set."""
        b = self.bullets[bullet_id]
        key = frozenset(b["achievement_ids"])
        return [o for o in self.bullets.values()
                if o["id"] != bullet_id and o["status"] != "rejected" and frozenset(o["achievement_ids"]) == key]
