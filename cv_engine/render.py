#!/usr/bin/env python3
"""Deterministic CV renderer: manifest + knowledge base → Overleaf-ready .tex (+ PDF preview).

Usage (from the project root):
    python -m cv_engine.render                                   # default CV → output/default/
    python -m cv_engine.render --manifest path/to/manifest.json  # → output/<job_id>/
    python -m cv_engine.render --clean                           # no "% REVIEW:" comments
    python -m cv_engine.render --no-pdf                          # .tex only, no compile / fit check

Outputs in output/<job_id or "default">/:
    cv.tex          main artefact: self-contained and compiles unchanged on Overleaf (pdflatex)
    cv.pdf          local preview, when pdflatex is available
    manifest.json   the manifest actually rendered (after any one-page fitting)

The .tex carries "% REVIEW: ..." comments (never visible in the PDF) for
agent-written wording, new skills from job descriptions, and metrics that are
not yet verified. The model chooses IDs; this module writes all LaTeX, with
escaping, into the fixed template from sources/baseline_cv.tex. It never changes fonts or margins.

One-page fitting: if the PDF runs over, the renderer swaps in shorter approved
variants of the same achievement, then drops the lowest-priority bullets from
unlocked entries, recompiling each time (up to cv_constraints.max_fit_attempts).
If it still doesn't fit, it writes the .tex anyway and reports OVER-LENGTH.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cv_engine.kb import (ENGINE_DIR, KB, KB_DIR, OUTPUT_DIR, ROOT, SCHEMA_DIR, TEMPLATE_DIR,  # noqa: E402
                          load_json, validate_kb)
from cv_engine.latex import comment, escape as E, escape_url  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_MANIFEST = ENGINE_DIR / "manifests" / "default_cv.json"
AGENT_SOURCES = {"agent_generated", "claude_generated"}
SEP = r" \quad \textbar{} \quad"
MIN_SWAP_SAVING = 15  # characters; smaller swaps rarely save a line


def _numbers(text: str) -> set[str]:
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def metric_in_text(metric: dict, text: str) -> bool:
    """Heuristic: does this bullet state this metric?"""
    norm = lambda s: s.replace("~", "∼").replace(",", "")  # noqa: E731
    value = str(metric["value"])
    if norm(value) in norm(text):
        return True
    nums = _numbers(value)
    return bool(nums) and nums <= _numbers(text)


# ----------------------------------------------------------------------------- rendering
class Renderer:
    def __init__(self, kb: KB, config: dict, review: bool = True):
        self.kb, self.cfg, self.review = kb, config, review
        self.template = (TEMPLATE_DIR / config["template_file"]).read_text(encoding="utf-8")
        self.review_count = 0

    def _review(self, text: str, indent: str = "") -> list[str]:
        if not self.review:
            return []
        self.review_count += 1
        return [indent + comment("REVIEW: " + text)]

    # -- header ---------------------------------------------------------------
    def header(self, cp_id: str) -> list[str]:
        p, c = self.kb.profile, self.kb.profile["contact"]
        cp = p["contact_profiles"][cp_id]
        contacts = []
        if c.get("email"):
            contacts.append(rf"\faEnvelope\ \href{{mailto:{escape_url(c['email'])}}}{{{E(c['email'])}}}")
        if cp.get("phone"):
            contacts.append(rf"\faPhone\ {E(cp['phone'])}")
        if c.get("linkedin"):
            contacts.append(rf"\faLinkedin\ \href{{{escape_url(c['linkedin'])}}}{{{E(p['full_name'])}}}")
        if c.get("github"):
            handle = c["github"].rstrip("/").rsplit("/", 1)[-1]
            contacts.append(rf"\faGithub\ \href{{{escape_url(c['github'])}}}{{{E(handle)}}}")
        if c.get("website"):
            shown = re.sub(r"^https?://(www\.)?", "", c["website"]).rstrip("/")
            contacts.append(rf"\faGlobe\ \href{{{escape_url(c['website'])}}}{{{E(shown)}}}")
        loc = [E(cp["location"])] if cp.get("location") else []
        join = (SEP + "\n    ").join
        out = [r"\begin{center}", rf"    {{\LARGE \textbf{{{E(p['full_name'])}}}}} \\[3pt]"]
        if cp.get("work_authorization_display"):
            out.append("    " + join(loc + [E(cp["work_authorization_display"])]) + r" \\[2pt]")
            out.append("    " + join(contacts))
        else:
            out.append("    " + join(loc + contacts))
        out.append(r"\end{center}")
        return out

    # -- sections -------------------------------------------------------------
    def section_title(self, key: str) -> list[str]:
        title = self.cfg["section_titles"][key]
        bar = "% " + "=" * 57
        return ["", bar, f"% {title}", bar, "", rf"\section*{{{E(title)}}}", ""]

    @staticmethod
    def itemize(items: list[list[str]]) -> list[str]:
        if not items:
            return []
        out = [r"\begin{itemize}"]
        for i, item in enumerate(items):
            if i:
                out.append("")
            out.extend(item)
        out.append(r"\end{itemize}")
        return out

    @staticmethod
    def two_sided(left: str, right: str | None, style: str, end: str = r"\\") -> str:
        line = rf"\{style}{{{left}}}"
        if right:
            line += rf" \hfill \{style}{{{right}}}"
        return line + end

    def education(self, entry: dict) -> list[str]:
        e = self.kb.education[entry["entry_id"]]
        out = [self.two_sided(E(e["institution"].upper()), E(e["location"]) if e["location"] else None, "textbf"),
               self.two_sided(E(f"{e['degree']} {e['field']}"),
                              E(e["date_display"]) if e["date_display"] else None, "textit", "")]
        items = []
        honors, grade = list(e["honors"]), e["grade"]
        if honors:
            extra = ([grade] if grade else []) + honors[1:]
            items.append([r"    \item " + E(honors[0] + (f" ({' - '.join(extra)})" if extra else ""))])
        elif grade:
            items.append([r"    \item " + E(grade)])
        courses = [self.kb.courses[c] for c in entry["coursework_ids"]]
        if courses:
            topics_only = all(c["status"] is None for c in courses)
            label = "Coursework" if topics_only else "Relevant Courses"
            items.append([r"    \item " + E(f"{label}: " + ", ".join(self._course(c) for c in courses))])
        return out + self.itemize(items)

    @staticmethod
    def _course(c: dict) -> str:
        extra = []
        if c["status"] is not None and c.get("grade") is not None:
            extra.append(str(c["grade"]))
        if c.get("annotation"):
            extra.append(c["annotation"])
        if c["status"] in ("in_progress", "planned"):
            extra.append(c["status"].replace("_", " "))  # never shown as completed
        return c["name"] + (f" ({'; '.join(extra)})" if extra else "")

    def bullets(self, bullet_ids: list[str]) -> list[str]:
        items = []
        for bid in bullet_ids:
            b = self.kb.bullets[bid]
            item = []
            if b["source"] in AGENT_SOURCES:
                item += self._review("agent-written wording", "    ")
            for aid in b["achievement_ids"]:
                for m in self.kb.achievements[aid]["metrics"]:
                    if m["verification_status"] != "verified" and metric_in_text(m, b["text"]):
                        item += self._review(f"metric not verified ({m['value']} {m['unit']})", "    ")
            item.append(r"    \item " + E(b["text"]))
            items.append(item)
        return self.itemize(items)

    def experience(self, entry: dict) -> list[str]:
        x = self.kb.experiences[entry["entry_id"]]
        out = [self.two_sided(E(x["organization"].upper()), E(x["location"]) if x["location"] else None, "textbf"),
               self.two_sided(E(x["title"]), E(x["date_display"]) if x["date_display"] else None, "textit", ""),
               ""]
        return out + self.bullets(entry["bullet_ids"])

    def project(self, entry: dict) -> list[str]:
        p = self.kb.projects[entry["entry_id"]]
        end = r"\\" if p["subtitle"] else ""
        out = [rf"\textbf{{{E(p['name'].upper())}}}" + (rf" \hfill \textit{{{E(p['date_display'])}}}" if p["date_display"] else "") + end]
        if p["subtitle"]:
            out.append(rf"\textit{{{E(p['subtitle'])}}}")
        return out + [""] + self.bullets(entry["bullet_ids"])

    def skill_names(self, ids: list[str]) -> tuple[list[str], list[str]]:
        nested = self.cfg.get("nested_skills", {})
        present = set(ids)
        consumed = {k for parent, kids in nested.items() if parent in present for k in kids if k in present}
        shown, new = [], []
        for sid in ids:
            if sid in consumed:
                continue
            s = self.kb.skills[sid]
            name = E(s["name"])
            if s["category"] == "spoken_language" and s["proficiency"]:
                name += f" ({E(s['proficiency'])})"
            kids = [k for k in nested.get(sid, []) if k in present]
            if kids:
                name += " (" + ", ".join(E(self.kb.skills[k]["name"])
                                         for k in kids) + ")"
            shown.append(name)
        for sid in ids:
            if self.kb.skills[sid]["confirmation_status"] != "confirmed":
                new.append(self.kb.skills[sid]["name"])
        return shown, new

    def skills(self, sec: dict, interest_ids: list[str]) -> list[str]:
        rows = [(g["label"], g["skill_ids"]) for g in sec["skill_groups"]]
        if sec["skill_ids"]:
            rows.append((self.cfg["ungrouped_skills_label"], sec["skill_ids"]))
        items = []
        for label, ids in rows:
            shown, new = self.skill_names(ids)
            item = []
            for n in new:
                item += self._review(f"new skill from job description ({n})", "    ")
            item.append(rf"    \item \textbf{{{E(label)}:}} " + ", ".join(shown) + ".")
            items.append(item)
        if interest_ids:
            items.append(self.interests_item(interest_ids))
        return self.itemize(items)

    def interests_item(self, ids: list[str]) -> list[str]:
        parts = []
        for iid in ids:
            i = self.kb.interests[iid]
            parts.append(E(i["name"] + (f" ({i['detail']})" if i["detail"] else "")))
        return [rf"    \item \textbf{{{E(self.cfg['interests_label'])}:}} " + ", ".join(parts) + "."]

    # -- document -------------------------------------------------------------
    def render(self, manifest: dict) -> str:
        self.review_count = 0
        sections = {s["section"]: s for s in manifest["sections"]}
        interests = sections.get("interests", {}).get("interest_ids", [])
        body = ["% " + "=" * 57, "% HEADER", "% " + "=" * 57, ""] + self.header(manifest["contact_profile_id"])
        for sec in manifest["sections"]:
            kind = sec["section"]
            if kind == "interests":
                if "skills" not in sections and interests:
                    body += self.section_title("interests") + self.itemize([self.interests_item(interests)])
                continue
            if kind == "skills":
                body += self.section_title("skills") + self.skills(sec, interests)
                continue
            if not sec["entries"]:
                continue
            body += self.section_title(kind)
            build = {"education": self.education, "experience": self.experience, "projects": self.project}[kind]
            for n, entry in enumerate(sec["entries"]):
                if n:
                    body.append("")
                body += build(entry)
        tex = self.template.replace("%%CONTENT%%", "\n".join(body).lstrip("\n") + "\n")
        if self.review:
            intro = [
                f"% Generated by JobAppAgent from manifest '{manifest['manifest_id']}' on {date.today().isoformat()}.",
                "% Compiles unchanged on Overleaf (pdflatex). Lines starting with \"% REVIEW:\" flag",
                "% things to check before applying; they never appear in the PDF. Delete them when done.",
                "",
            ]
            tex = "\n".join(intro) + tex
        return tex


# ----------------------------------------------------------------------------- compile + fit
def compile_pdf(tex: str, build_dir: Path) -> dict | None:
    """Compile with pdflatex; return pages, fill ratio and PDF path (None if no pdflatex)."""
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        return None
    build_dir.mkdir(parents=True, exist_ok=True)
    probe = "\\par\\typeout{JOBAPP-FILL \\the\\pagetotal\\space\\the\\pagegoal}\n\\end{document}"
    (build_dir / "cv.tex").write_text(tex.replace(r"\end{document}", probe), encoding="utf-8")
    for stale in ("cv.pdf", "cv.log"):
        (build_dir / stale).unlink(missing_ok=True)
    subprocess.run([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "cv.tex"],
                   cwd=build_dir, capture_output=True, timeout=300)
    log_path = build_dir / "cv.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    m = re.search(r"Output written on \S+ \((\d+) pages?", log)
    pages = int(m.group(1)) if m else None
    fill = None
    f = re.search(r"JOBAPP-FILL ([\d.]+)pt ([\d.]+)pt", log)
    if f and pages == 1 and float(f.group(2)) > 0:
        fill = float(f.group(1)) / float(f.group(2))
    errors = [line for line in log.splitlines() if line.startswith("!") or ":error" in line.lower()]
    return {"pages": pages, "fill": fill, "pdf": build_dir / "cv.pdf", "errors": errors[:5]}


def shrink_step(manifest: dict, kb: KB, protected: set[str]) -> str | None:
    """One fitting action: best shorter-variant swap, else drop the lowest-value unlocked bullet."""
    used = {b for s in manifest["sections"] for e in s["entries"] for b in e.get("bullet_ids", [])}
    best = None
    for sec in manifest["sections"]:
        if sec["section"] not in ("experience", "projects"):
            continue
        for entry in sec["entries"]:
            for i, bid in enumerate(entry["bullet_ids"]):
                cur = len(kb.bullets[bid]["text"])
                for alt in kb.alternatives(bid):
                    if alt["status"] != "approved" or alt["id"] in used or alt["id"] in protected:
                        continue
                    saving = cur - len(alt["text"])
                    if saving >= MIN_SWAP_SAVING and (best is None or saving > best[0]):
                        best = (saving, entry, i, bid, alt["id"])
    if best:
        saving, entry, i, old, new = best
        entry["bullet_ids"][i] = new
        return f"swapped {old} → {new} (−{saving} chars)"

    victims = []
    for sec in manifest["sections"]:
        if sec["section"] not in ("experience", "projects"):
            continue
        for entry in sec["entries"]:
            if entry["locked"]:
                continue
            for bid in entry["bullet_ids"]:
                b = kb.bullets[bid]
                victims.append((b["priority"], -len(b["text"]), sec, entry, bid))
    if not victims:
        return None
    _, _, sec, entry, bid = min(victims, key=lambda v: (v[0], v[1]))
    entry["bullet_ids"].remove(bid)
    if not entry["bullet_ids"]:
        sec["entries"].remove(entry)
        return f"dropped {bid} and its now-empty entry {entry['entry_id']}"
    return f"dropped {bid} (priority {kb.bullets[bid]['priority']})"


# ----------------------------------------------------------------------------- CLI
def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "job"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--name", help="output folder name (default: job_id, or 'default')")
    ap.add_argument("--clean", action="store_true", help="omit the '% REVIEW:' comments")
    ap.add_argument("--no-pdf", action="store_true", help="skip compiling and one-page fitting")
    ap.add_argument("--max-fit-attempts", type=int)
    args = ap.parse_args(argv)

    rep = validate_kb.run(KB_DIR, SCHEMA_DIR, args.manifest, application_ready=True)
    for w in rep.warnings:
        print("WARNING:", w)
    if rep.errors:
        for e in rep.errors:
            print("ERROR:  ", e)
        print(f"\n{len(rep.errors)} validation error(s); nothing rendered.")
        return 1

    kb = KB()
    manifest = load_json(args.manifest)
    config = load_json(TEMPLATE_DIR / f"{manifest['template_id']}.json")
    protected = set(load_json(ENGINE_DIR / "selection_policy.json")["do_not_auto_select"])
    for s in manifest["sections"]:
        for e in s["entries"]:
            for bid in set(e.get("bullet_ids", [])) & protected:
                print(f"WARNING: manifest uses {bid}, whose wording contradicts docs/DECISIONS.md "
                      f"(see cv_engine/selection_policy.json)")

    name = args.name or (slug(manifest["job_id"]) if manifest["job_id"] else "default")
    out_dir = OUTPUT_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(kb, config, review=not args.clean)
    max_attempts = args.max_fit_attempts
    if max_attempts is None:
        max_attempts = kb.preferences["cv_constraints"]["max_fit_attempts"]

    work = copy.deepcopy(manifest)
    actions, result = [], None
    while True:
        tex = renderer.render(work)
        if args.no_pdf:
            break
        result = compile_pdf(tex, out_dir / "build")
        if result is None or result["pages"] is None or result["pages"] <= 1 or len(actions) >= max_attempts:
            break
        action = shrink_step(work, kb, protected)
        if action is None:
            break
        actions.append(action)
        print("fit:", action)

    leak = validate_kb.Report()
    validate_kb.check_rendered_text(leak, tex)
    if leak.errors:
        for e in leak.errors:
            print("ERROR:  ", e)
        return 1

    (out_dir / "cv.tex").write_text(tex, encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(work, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "cv.pdf").unlink(missing_ok=True)
    rel = lambda p: p.relative_to(ROOT).as_posix()  # noqa: E731
    print(f"\nWrote {rel(out_dir / 'cv.tex')}  ({renderer.review_count} REVIEW comment(s){', clean' if args.clean else ''})")

    if args.no_pdf:
        print("PDF: skipped (--no-pdf); one-page fit not checked.")
    elif result is None:
        print("PDF: pdflatex not found; .tex written but one-page fit not checked.")
    elif result["pages"] is None:
        print("PDF: compile FAILED locally. The .tex is still written. First errors:")
        for line in result["errors"]:
            print("   ", line)
    else:
        shutil.copy2(result["pdf"], out_dir / "cv.pdf")
        print(f"Wrote {rel(out_dir / 'cv.pdf')}  ({result['pages']} page(s))")
        if result["pages"] > 1:
            print(f"OVER-LENGTH: {result['pages']} pages after {len(actions)} fit action(s). Fix it in Overleaf.")
        elif result["fill"] is not None:
            pct = round(result["fill"] * 100)
            note = "  (underfilled: room to add content back)" if result["fill"] < config["underfill_threshold"] else ""
            print(f"Fits on one page, ~{pct}% full{note}.")
        if actions:
            print("Fit actions: " + "; ".join(actions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
