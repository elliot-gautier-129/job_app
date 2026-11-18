# JobAppAgent

A personal tool that turns a structured knowledge base about me into **tailored, one-page, Overleaf-ready LaTeX CVs** for early-career data science / ML roles. Later phases add job discovery from ATS boards (Greenhouse, Lever, Ashby).

It never applies anywhere. I review each CV by editing the `.tex` in Overleaf, then apply manually.

## How it works

```
knowledge_base/*.json ──► manifest (which IDs go on the CV) ──► cv_engine/render.py ──► output/<job>/cv.tex
   (facts, bullets,          cv_engine/manifests/                 fixed template from          + cv.pdf preview
    skills, courses)         default_cv.json or per job           sources/baseline_cv.tex
```

- The **knowledge base** holds facts, achievements, CV bullet wording, skills and coursework (schema v1.3, validated by `tools/validate_kb.py`).
- A **manifest** lists the IDs to include, in order. The model picks IDs and wording; it never writes LaTeX.
- The **renderer** builds the `.tex` deterministically from the baseline template: same fonts and margins, safe escaping. It compiles the file, and if the page overflows it swaps in shorter variants or drops low-priority bullets until it fits on one page.
- Approval is automatic. New wording or new skills from a job description are saved and used straight away, and flagged in the `.tex` for my Overleaf pass.

## Setup

```
pip install -r requirements.txt
```
For the PDF preview and the one-page check you also need `pdflatex` with `fontawesome5`, `enumitem` and `titlesec` (TinyTeX: `tlmgr install fontawesome5 enumitem titlesec`). Without LaTeX, the `.tex` is still written.

## Commands

| Command | What it does |
|---|---|
| `python -m cv_engine.render` | Render the default CV to `output/default/` |
| `python -m cv_engine.render --manifest <file>` | Render a job-specific manifest to `output/<job_id>/` |
| `python -m cv_engine.render --clean` | Same, without the `% REVIEW:` comments |
| `python -m cv_engine.render --no-pdf` | Write the `.tex` only (no compile, no fit check) |
| `python tools/validate_kb.py` | Validate the knowledge base (must report 0 errors) |
| `python tools/validate_kb.py --manifest <file> --application-ready` | Also validate a manifest |
| `python tools/approve_bullets.py` | Bullet status overview |
| `python tools/approve_bullets.py --all --yes` | Stamp approval on every new or edited bullet |
| `python tools/approve_bullets.py --reject <id> --yes` | Take a bullet out of use for good |
| `python -m pytest -q` | Run the tests |

## The `output/` folder

```
output/
  default/            # or <job_id>/ for a tailored CV
    cv.tex            # ← the file you take to Overleaf
    cv.pdf            # local preview (if pdflatex is installed)
    manifest.json     # exactly what was rendered, after one-page fitting
    build/            # compile scratch (gitignored)
```

The console reports whether the CV fits on one page and how full it is. If it prints `OVER-LENGTH`, the `.tex` is still there; trim it in Overleaf.

## Taking a CV into Overleaf

1. In Overleaf: **New Project → Upload Project** and upload `output/<job>/cv.tex`, or replace `main.tex` in an existing project with its contents.
2. Make sure the compiler is **pdfLaTeX** (Menu → Compiler). The file is self-contained and uses only the packages from the original CV.
3. Search for `% REVIEW:`. Each comment sits right above the line it refers to:
   - `agent-written wording`: a bullet reworded for this job. Check the phrasing.
   - `new skill from job description (X)`: a skill added from the job ad. Keep it only if you really have it.
   - `metric not verified (…)`: a number not yet verified in the knowledge base. Check it before sending.
   The comments never show in the PDF. Delete them as you go.
4. Download the PDF and apply manually.

If a review turns up a fact that's wrong, fix it in `knowledge_base/` too, so the next CV is right.
