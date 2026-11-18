# JobAppAgent: guide for Claude Code

Personal system for **Elliot Gautier** (M.A. Statistics and Data Science, UC Berkeley, 2026–27; B.Sc. MORSE, Warwick). It discovers early-career DS/ML jobs and generates **tailored one-page English CVs** from a verified knowledge base and his existing LaTeX template. **Elliot applies to every job manually.** There is no auto-apply, no form filling and no account creation.

Read these when relevant:
- `docs/DECISIONS.md`: all confirmed facts and policies. **Authoritative; do not reopen closed items.**
- `docs/HIGH_LEVEL_DESIGN_v2.md`: architecture, pipeline and phases.
- `docs/SCHEMA_v1_3_MIGRATION_NOTES.md`: current schema changes and runtime rules.
- `docs/STAGE_B_REVIEW_REPORT.md`: knowledge-base contents, bullet recommendations, open facts.

## Repository layout
```
knowledge_base/      8 JSON files (schema v1.3), the single source of truth about Elliot
schemas/             9 JSON Schemas (Draft 2020-12): the field-level contract. Don't redesign them without asking.
tools/validate_kb.py      schema + cross-file validation (also validates manifests)
tools/approve_bullets.py  Elliot's bullet approval tool (records timestamp + SHA-256)
sources/             baseline_cv.tex (visual source of truth) + original CV/transcript PDFs
cv_engine/manifests/ CV selection manifests (default_cv.json goes here, Stage C)
cv_engine/templates/ LaTeX template + renderer config (Phase 2)
docs/                design, decisions, reports
```

## Commands
```
pip install -r requirements.txt
python tools/validate_kb.py                                  # must report 0 errors after any KB change
python tools/validate_kb.py --manifest cv_engine/manifests/default_cv.json [--application-ready]
python tools/approve_bullets.py --list                       # bullet approval status
```
A LaTeX toolchain (`latexmk`/`pdflatex` with `fontawesome5`) is needed from Phase 2 on.

## Hard rules
1. **Never invent facts:** no new metrics, dates, technologies, responsibilities, course titles or links. Missing information → `null` / `needs_review`, then ask Elliot.
2. **Never approve anything.** Do not set `status: "approved"`, `approved_at` or `approved_text_sha256`. Only Elliot does that, via `tools/approve_bullets.py`.
3. **No new bullet wording in the KB without proposal.** New or changed text is a new variant with `status: "proposed"`. Editing an approved bullet's text invalidates its approval.
4. **The LLM picks IDs, never raw LaTeX.** Manifests reference KB IDs; a deterministic Python renderer produces LaTeX with safe escaping. Don't hand-edit the template's content programmatically with the model.
5. **Application-ready CVs** use only approved bullets (hash matches), verified coursework and `confirmed` + `cv_eligible` skills. Never render internal metadata words ("confirmed", "unconfirmed", "proposed", …).
6. **One page.** Fit by swapping in shorter approved variants or dropping the lowest-value unlocked content; add content back when the page is noticeably underfilled. Never change fonts or margins; report failure instead of producing an overlength PDF.
7. Keep IDs stable, snake_case and globally unique. Run the validator after every KB edit.
8. **Personal data:** keep this repo private. Don't commit secrets; contact details live only in `knowledge_base/profile.json`.

## Current status (2026-11-18)
- ✅ Phase 1 / Stage B: knowledge base populated; 0 validation errors. 13 achievements, 43 skills (all confirmed), 29 courses, 17 bullets (all `proposed`).
- ⏳ **Elliot is approving bullets** with `tools/approve_bullets.py`.
- **Next: Stage C:** build `cv_engine/manifests/default_cv.json` from `sources/baseline_cv.tex`. Use the US contact profile by default. Sections: education → experience → projects → skills (groups: "Programming & Data", "Python", "Tools", "Languages") → interests. Football uses `bullet_football_lightgbm_s2` + S1 pipeline + S1 market-benchmark bullets. There is no summary. It stays a draft until the bullets are approved.
- **Then Phase 2:** a deterministic renderer (template from `baseline_cv.tex` with the summary removed, a US/UK header variant, the nested-skills config, Unicode → LaTeX escaping), compiling to one page. Acceptance: reproduce the baseline layout minus the summary, with the corrected content.
- Later: Phase 3 tailoring from job descriptions (with the unconfirmed-skill suggestion loop), Phase 4 ATS discovery (Greenhouse/Lever/Ashby) with OPT-aware eligibility, Phase 5 Streamlit review.
