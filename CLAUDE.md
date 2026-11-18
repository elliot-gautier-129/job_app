# JobAppAgent: guide for Claude Code

Personal system for **Elliot Gautier** (M.A. Statistics and Data Science, UC Berkeley, 2026–27; B.Sc. MORSE, Warwick). It discovers early-career DS/ML jobs and generates **tailored one-page English CVs as Overleaf-ready `.tex` files** from a knowledge base and his existing LaTeX template. Elliot downloads each `.tex`, edits it in Overleaf (**that edit is the review step**), and **applies to every job manually**. There is no auto-apply, no form filling and no account creation.

Read these when relevant:
- `docs/DECISIONS.md`: all confirmed facts and policies. **Authoritative; do not reopen closed items.** The 2026-11-18 entry "Auto-approval + Overleaf-first output" supersedes the older approval-gating policy.
- `docs/HIGH_LEVEL_DESIGN_v2.md`: architecture, pipeline and phases.
- `docs/SCHEMA_v1_3_MIGRATION_NOTES.md`: current schema and runtime rules.
- `docs/STAGE_B_REVIEW_REPORT.md`: knowledge-base contents and open facts.

## Repository layout
```
knowledge_base/      8 JSON files (schema v1.3), the single source of truth about Elliot
schemas/             9 JSON Schemas (Draft 2020-12): the field-level contract. Don't redesign them without asking.
tools/validate_kb.py      schema + cross-file validation (also validates manifests)
tools/approve_bullets.py  approval bookkeeping (stamps approved_at + SHA-256; --all, --reject, --revoke)
cv_engine/render.py       deterministic renderer: manifest → output/<job>/cv.tex (+ cv.pdf preview)
cv_engine/kb_writer.py    the only way the agent adds bullets/skills (auto-approved / tracked)
cv_engine/latex.py        Unicode → LaTeX escaping
cv_engine/selection_policy.json  bullets the agent must never auto-select (they contradict DECISIONS.md)
cv_engine/manifests/      CV selection manifests (default_cv.json = the baseline CV)
cv_engine/templates/      baseline_onepage.tex (fixed preamble from sources/baseline_cv.tex) + .json renderer config
output/<job>/             cv.tex (main artefact), cv.pdf, manifest.json; build/ is gitignored scratch
sources/             baseline_cv.tex (visual source of truth) + original CV/transcript PDFs
tests/               pytest suite (escaping, rendering, kb_writer, validator policy)
docs/                design, decisions, reports
```

## Commands
```
pip install -r requirements.txt
python tools/validate_kb.py                                  # must report 0 errors after any KB change
python tools/validate_kb.py --manifest cv_engine/manifests/default_cv.json --application-ready
python -m cv_engine.render                                   # default CV → output/default/cv.tex (+ cv.pdf)
python -m cv_engine.render --manifest <path> [--clean] [--no-pdf] [--name <folder>]
python tools/approve_bullets.py                              # status overview (non-interactive)
python tools/approve_bullets.py --all --yes                  # stamp every proposed/STALE bullet
python -m pytest -q
```
A local LaTeX toolchain (`pdflatex` with `fontawesome5`, `enumitem`, `titlesec`) is only needed for the PDF preview and the one-page fit check; the `.tex` is always written.

## Hard rules
1. **Never invent facts.** No new metrics, dates, technologies, employers, responsibilities, course titles or links. Rewording existing facts is fine; new claims are not. Missing information → `null` / `needs_review`, then ask Elliot.
2. **Never contradict `docs/DECISIONS.md`** (e.g. football log loss 8.8%, not 12.8%; QRT is pairs trading, not arbitrage; Elliot built and tuned the lost-package LightGBM model; preferred carrier-pricing framing). Never auto-select bullets listed in `cv_engine/selection_policy.json`.
3. **Approval is automatic and never blocks CV generation.** New or reworded bullets go through `cv_engine/kb_writer.add_bullet_variant()`. It saves them as `status: "approved"` with `approved_at`, `approved_text_sha256` and `source: "agent_generated"` or `"claude_generated"`, and refuses numbers that aren't in the linked achievements. The hash now only detects text edited after it was stamped; a mismatch is a validator error, so re-stamp with `tools/approve_bullets.py --approve <id> --yes`. `rejected` bullets are still never used.
4. **Skills from job descriptions** that aren't in `skills.json` are added with `kb_writer.add_skill()` and used straight away. They're stored as `confirmation_status: "unconfirmed"` (tracking only, never a gate) and marked in the `.tex` with `% REVIEW: new skill from job description`. Don't add a skill that clearly contradicts the KB. `cv_eligible: false` still excludes a skill.
5. **The model picks IDs and wording; the deterministic renderer writes all LaTeX** with safe escaping. Never hand-write LaTeX into the KB or edit the template with the model. Never change the template's fonts, margins or packages: only the packages in `sources/baseline_cv.tex`.
6. **Output is an Overleaf-ready `.tex`** in `output/<job_id or default>/cv.tex`, self-contained and compiling unchanged with pdflatex. `% REVIEW:` comments flag agent-written wording, new skills and unverified metrics; `--clean` omits them. Never render internal metadata words ("confirmed", "unconfirmed", "approved", "proposed", …) in the `.tex` (comments included) or the PDF.
7. **One page.** The fit loop swaps in shorter approved variants, then drops the lowest-priority bullets from unlocked entries. If it still doesn't fit, write the `.tex` anyway and report OVER-LENGTH in the console; Elliot fixes it in Overleaf. Add content back when the page is noticeably underfilled (the renderer reports fill %).
8. Keep IDs stable, snake_case and globally unique. Run the validator after every KB edit.
9. **Personal data:** English only, no summary, manual applications only. Keep this repo private. Don't commit secrets; contact details live only in `knowledge_base/profile.json`.

## Current status (2026-11-18)
- ✅ Phase 1 / Stage B: knowledge base populated (13 achievements, 43 skills, 29 courses, 17 bullets).
- ✅ All 17 bullets approved (auto-approval policy). 3 of them are in `selection_policy.json` because their wording contradicts DECISIONS.md: `bullet_qrt_arbitrage_s2`, `bullet_amazon_lost_package_s2`, `bullet_amazon_carrier_pricing_s3`.
- ✅ Stage C: `cv_engine/manifests/default_cv.json` mirrors the baseline CV (US profile; education → experience → projects → skills → interests; football uses `bullet_football_lightgbm_s2`). Education and jobs are locked; projects are unlocked.
- ✅ Phase 2: renderer done. `python -m cv_engine.render` reproduces the baseline layout without the summary and with the corrections, on one page (~97% full), with US/UK headers, nested skills and escaping.
- **Next: Phase 3:** tailoring from job descriptions. Analyse the JD, select IDs into a job manifest (`job_id` set), reword via `kb_writer` where useful, add JD skills via `kb_writer.add_skill`, render to `output/<job_id>/cv.tex`.
- Later: Phase 4 ATS discovery (Greenhouse/Lever/Ashby) with OPT-aware eligibility; Phase 5 Streamlit review.
- Open facts (`needs_review`, flagged in the `.tex` as REVIEW comments): see `docs/DECISIONS.md` § Open facts.
