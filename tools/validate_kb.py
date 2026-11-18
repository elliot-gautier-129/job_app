#!/usr/bin/env python3
"""Validate the job-agent knowledge base (schema v1.3).

Usage:
    python tools/validate_kb.py [--kb knowledge_base] [--schemas schemas]
                                [--manifest path.json [--application-ready]]

Runs JSON Schema validation on every file, then cross-file checks that JSON
Schema cannot express. Exits 1 if any ERROR is found; WARNINGs do not fail.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

KB_FILES = ["profile", "education", "experiences", "projects", "achievements",
            "skills", "bullet_variants", "preferences"]
SCHEMA_VERSION = "1.3"
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
INTERNAL_WORDS = re.compile(r"\b(unconfirmed|confirmed|needs_review|proposed|approved|rejected)\b", re.I)


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


# ----------------------------------------------------------------------------- helpers
def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_date(s):
    """Return (year, month|None, day|None) or raise ValueError for impossible dates."""
    parts = [int(p) for p in s.split("-")]
    y, m, d = (parts + [None, None])[:3]
    if m is not None and not 1 <= m <= 12:
        raise ValueError(f"invalid month in {s}")
    if d is not None and d > calendar.monthrange(y, m)[1]:
        raise ValueError(f"invalid day in {s}")
    return y, m, d


def date_key(t, end=False):
    y, m, d = t
    return (y, m if m is not None else (12 if end else 1), d if d is not None else (31 if end else 1))


def check_dates(rep, label, rec):
    start, end, disp = rec.get("start_date"), rec.get("end_date"), rec.get("date_display")
    parsed = {}
    for k, v in (("start_date", start), ("end_date", end)):
        if v is not None:
            try:
                parsed[k] = parse_date(v)
            except ValueError as e:
                rep.err(f"{label}: {k} {e}")
    if "start_date" in parsed and "end_date" in parsed:
        if date_key(parsed["start_date"]) > date_key(parsed["end_date"], end=True):
            rep.err(f"{label}: start_date {start} is after end_date {end}")
    if disp is None:
        if parsed:
            rep.warn(f"{label}: date_display is null; renderer will need a fallback")
        return
    stored = list(parsed.values())
    stored_years = {p[0] for p in stored}
    disp_years = {int(y) for y in re.findall(r"\b(\d{4})\b", disp)}
    if not disp_years <= stored_years:
        rep.err(f"{label}: date_display '{disp}' shows years {sorted(disp_years - stored_years)} not in stored dates")
    disp_months = [MONTHS[w.lower()] for w in re.findall(r"[A-Za-z]+", disp) if w.lower() in MONTHS]
    stored_months = {p[1] for p in stored if p[1] is not None}
    if disp_months and not stored_months:
        rep.err(f"{label}: date_display '{disp}' shows months but stored dates are year-only (invented precision)")
    elif disp_months and not set(disp_months) <= stored_months:
        rep.err(f"{label}: date_display '{disp}' months do not match stored dates")


# ----------------------------------------------------------------------------- main checks
def validate_schemas(rep, kb_dir, schema_dir, data):
    for name in KB_FILES:
        path = kb_dir / f"{name}.json"
        if not path.exists():
            rep.err(f"missing file {path}")
            continue
        data[name] = load(path)
        schema = load(schema_dir / f"{name}.schema.json")
        for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data[name]):
            rep.err(f"{name}.json schema: {'/'.join(map(str, e.absolute_path))}: {e.message}")
        if data[name].get("schema_version") != SCHEMA_VERSION:
            rep.err(f"{name}.json: schema_version is not {SCHEMA_VERSION}")


def cross_file(rep, d):
    exps = {e["id"]: e for e in d["experiences"]["experiences"]}
    projs = {p["id"]: p for p in d["projects"]["projects"]}
    achs = {a["id"]: a for a in d["achievements"]["achievements"]}
    skills = {s["id"]: s for s in d["skills"]["skills"]}
    bullets = {b["id"]: b for b in d["bullet_variants"]["bullet_variants"]}
    edus = {e["id"]: e for e in d["education"]["education"]}
    courses = {c["id"]: (e["id"], c) for e in edus.values() for c in e["coursework"]}
    interests = {i["id"]: i for i in d["profile"]["interests"]}

    # 1. unique IDs within and across namespaces
    all_ids = ([e["id"] for e in d["experiences"]["experiences"]] + [p["id"] for p in d["projects"]["projects"]]
               + [a["id"] for a in d["achievements"]["achievements"]] + [s["id"] for s in d["skills"]["skills"]]
               + [b["id"] for b in d["bullet_variants"]["bullet_variants"]] + [e["id"] for e in d["education"]["education"]]
               + [c["id"] for e in d["education"]["education"] for c in e["coursework"]]
               + [i["id"] for i in d["profile"]["interests"]])
    for i, n in Counter(all_ids).items():
        if n > 1:
            rep.err(f"duplicate id '{i}' ({n} occurrences)")

    # 2. parent <-> achievement mapping
    parents = {("experience", k): v for k, v in exps.items()}
    parents.update({("project", k): v for k, v in projs.items()})
    listed = Counter()
    for (ptype, pid), p in parents.items():
        for aid in p["achievement_ids"]:
            listed[aid] += 1
            a = achs.get(aid)
            if a is None:
                rep.err(f"{pid}: achievement '{aid}' does not exist")
            elif (a["parent_type"], a["parent_id"]) != (ptype, pid):
                rep.err(f"{pid}: lists '{aid}' but that achievement's parent is {a['parent_type']}:{a['parent_id']}")
    for aid, a in achs.items():
        if (a["parent_type"], a["parent_id"]) not in parents:
            rep.err(f"{aid}: parent {a['parent_type']}:{a['parent_id']} does not exist")
        if listed[aid] != 1:
            rep.err(f"{aid}: listed {listed[aid]} times by parents (expected exactly 1)")
        for sid in a["skill_ids"]:
            if sid not in skills:
                rep.err(f"{aid}: skill '{sid}' does not exist")
        if a["verification_status"] == "verified" and any(m["verification_status"] != "verified" for m in a["metrics"]):
            rep.err(f"{aid}: achievement marked verified but has unverified metrics")
        if not a["evidence"]:
            rep.warn(f"{aid}: no evidence recorded")

    # 3. projects' own skill references
    for pid, p in projs.items():
        for sid in p["skill_ids"]:
            if sid not in skills:
                rep.err(f"{pid}: skill '{sid}' does not exist")

    # 4. skills
    for sid, s in skills.items():
        if s["category"] != "spoken_language" and s["proficiency"] is not None:
            rep.err(f"{sid}: proficiency must be null for non-spoken-language skills")
        for aid in s["evidence_achievement_ids"]:
            if aid not in achs:
                rep.err(f"{sid}: evidence achievement '{aid}' does not exist")
            elif sid not in achs[aid]["skill_ids"]:
                rep.warn(f"{sid}: evidence '{aid}' does not list this skill in its skill_ids")
        linked = {aid for aid, a in achs.items() if sid in a["skill_ids"]}
        if linked - set(s["evidence_achievement_ids"]):
            rep.warn(f"{sid}: achievements {sorted(linked - set(s['evidence_achievement_ids']))} use this skill but are not in evidence_achievement_ids")
    names = Counter(s["name"].lower() for s in skills.values())
    for n, c in names.items():
        if c > 1:
            rep.err(f"skill name '{n}' appears {c} times")

    # 5. bullets
    texts = Counter(b["text"] for b in bullets.values())
    for bid, b in bullets.items():
        if texts[b["text"]] > 1:
            rep.err(f"{bid}: duplicate bullet text")
        parent_set = set()
        ach_skills = set()
        for aid in b["achievement_ids"]:
            a = achs.get(aid)
            if a is None:
                rep.err(f"{bid}: achievement '{aid}' does not exist")
                continue
            parent_set.add((a["parent_type"], a["parent_id"]))
            ach_skills |= set(a["skill_ids"])
        if len(parent_set) > 1:
            rep.err(f"{bid}: links achievements from different parents {sorted(parent_set)}")
        for sid in b["skill_ids"]:
            if sid not in skills:
                rep.err(f"{bid}: skill '{sid}' does not exist")
            elif sid not in ach_skills:
                rep.warn(f"{bid}: skill '{sid}' not supported by its linked achievements' skill_ids")
        if b["status"] == "approved":
            digest = hashlib.sha256(b["text"].encode("utf-8")).hexdigest()
            if b["approved_text_sha256"] != digest:
                rep.err(f"{bid}: approved_text_sha256 does not match current text (approval invalid)")
        if "\\" in b["text"] or "$" in b["text"]:
            rep.err(f"{bid}: text contains LaTeX markup; store plain Unicode text")

    # 6. dates
    for e in d["education"]["education"]:
        check_dates(rep, e["id"], e)
    for e in d["experiences"]["experiences"]:
        check_dates(rep, e["id"], e)
    for p in d["projects"]["projects"]:
        check_dates(rep, p["id"], p)

    # 7. coursework
    for cid, (eid, c) in courses.items():
        if c["status"] in ("planned", "in_progress") and c["grade"] is not None:
            rep.warn(f"{cid}: {c['status']} course has a grade")

    # 8. profile contact profiles
    for code, cp in d["profile"]["contact_profiles"].items():
        if cp["location"] is None or cp["phone"] is None:
            rep.warn(f"contact profile {code}: missing location or phone")
    for k, v in d["profile"]["contact"].items():
        if k in ("linkedin", "github", "website") and v and not v.startswith(("https://", "http://")):
            rep.err(f"profile.contact.{k}: URL must include https:// scheme")

    return dict(exps=exps, projs=projs, achs=achs, skills=skills, bullets=bullets,
                edus=edus, courses=courses, interests=interests)


def check_manifest(rep, path, schema_dir, idx, application_ready):
    m = load(path)
    schema = load(schema_dir / "cv_manifest.schema.json")
    for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(m):
        rep.err(f"manifest schema: {'/'.join(map(str, e.absolute_path))}: {e.message}")
    secs = Counter(s["section"] for s in m.get("sections", []))
    for s, n in secs.items():
        if n > 1:
            rep.err(f"manifest: section '{s}' appears {n} times")
    for sec in m.get("sections", []):
        kind = sec["section"]
        for entry in sec["entries"]:
            eid = entry["entry_id"]
            if kind == "education":
                if eid not in idx["edus"]:
                    rep.err(f"manifest: education entry '{eid}' not found")
                    continue
                for cid in entry.get("coursework_ids", []):
                    owner = idx["courses"].get(cid)
                    if owner is None or owner[0] != eid:
                        rep.err(f"manifest: course '{cid}' does not belong to '{eid}'")
                    elif application_ready and not owner[1]["verified"]:
                        rep.err(f"manifest: course '{cid}' is not verified")
                if "bullet_ids" in entry:
                    rep.err(f"manifest: education entry '{eid}' must use coursework_ids")
            else:
                pool = idx["exps"] if kind == "experience" else idx["projs"]
                ptype = "experience" if kind == "experience" else "project"
                if eid not in pool:
                    rep.err(f"manifest: {kind} entry '{eid}' not found")
                    continue
                if not pool[eid]["cv_eligible"]:
                    rep.err(f"manifest: '{eid}' is not cv_eligible")
                for bid in entry.get("bullet_ids", []):
                    b = idx["bullets"].get(bid)
                    if b is None:
                        rep.err(f"manifest: bullet '{bid}' not found")
                        continue
                    owners = {(idx["achs"][a]["parent_type"], idx["achs"][a]["parent_id"]) for a in b["achievement_ids"] if a in idx["achs"]}
                    if owners != {(ptype, eid)}:
                        rep.err(f"manifest: bullet '{bid}' does not belong to '{eid}'")
                    if b["status"] == "rejected":
                        rep.err(f"manifest: bullet '{bid}' is rejected")
                    elif application_ready and b["status"] != "approved":
                        rep.err(f"manifest: bullet '{bid}' is {b['status']}, not approved")
                if "coursework_ids" in entry:
                    rep.err(f"manifest: {kind} entry '{eid}' must use bullet_ids")
        seen, labels = Counter(), Counter()
        for g in sec.get("skill_groups", []):
            labels[g["label"]] += 1
            for sid in g["skill_ids"]:
                seen[sid] += 1
        for sid in sec.get("skill_ids", []):
            seen[sid] += 1
        for lbl, n in labels.items():
            if n > 1:
                rep.err(f"manifest: skill group label '{lbl}' repeated")
        for sid, n in seen.items():
            s = idx["skills"].get(sid)
            if s is None:
                rep.err(f"manifest: skill '{sid}' not found")
                continue
            if n > 1:
                rep.err(f"manifest: skill '{sid}' appears {n} times")
            if application_ready and (s["confirmation_status"] != "confirmed" or not s["cv_eligible"]):
                rep.err(f"manifest: skill '{sid}' is not confirmed + cv_eligible")
        for iid in sec.get("interest_ids", []):
            if iid not in idx["interests"]:
                rep.err(f"manifest: interest '{iid}' not found")
            elif application_ready and not idx["interests"][iid]["cv_eligible"]:
                rep.err(f"manifest: interest '{iid}' is not cv_eligible")


def check_rendered_text(rep, text: str):
    """Call on generated .tex/PDF text: internal metadata must never be rendered."""
    for match in INTERNAL_WORDS.finditer(text):
        rep.err(f"rendered output contains internal metadata word '{match.group(0)}'")


def main(argv=None):
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("--kb", type=Path, default=root / "knowledge_base")
    ap.add_argument("--schemas", type=Path, default=root / "schemas")
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--application-ready", action="store_true")
    args = ap.parse_args(argv)

    rep, data = Report(), {}
    validate_schemas(rep, args.kb, args.schemas, data)
    if len(data) == len(KB_FILES):
        idx = cross_file(rep, data)
        if args.manifest:
            check_manifest(rep, args.manifest, args.schemas, idx, args.application_ready)
    for w in rep.warnings:
        print("WARNING:", w)
    for e in rep.errors:
        print("ERROR:  ", e)
    print(f"\n{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
