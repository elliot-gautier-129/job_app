# Decisions log

Every decision below was confirmed by Elliot during the claude.ai planning sessions (2026-11-17/18). They override anything older. Do **not** reopen closed items unless Elliot raises them.

## 2026-11-18 — Auto-approval + Overleaf-first output
Policy change from Elliot. It **supersedes the Bullet policy below and the gating parts of the Skills policy** (marked inline).

- **Objective:** the main output is an Overleaf-ready `.tex` per CV, which Elliot downloads and edits. **His Overleaf edit is the review step.** CV generation is never blocked waiting for approval.
- **Bullets:** everything is approved automatically. The 17 imported bullets were stamped on 2026-11-18 with `tools/approve_bullets.py --yes --approve …`. New or reworded variants from the agent are saved straight away as `status: "approved"`, with `approved_at`, `approved_text_sha256` and `source: "agent_generated"` / `"claude_generated"` (via `cv_engine/kb_writer.py`), so they stay traceable. The hash now only detects text that changed after it was stamped; a mismatch is still a validator error. `rejected` still means never used.
- **Skills:** skills found in a job description that aren't in `skills.json` are added and used straight away. `confirmation_status` stays as **tracking only**: new skills are stored as `unconfirmed` and still render, with a `% REVIEW` comment. No skill that clearly contradicts the KB is added. `cv_eligible: false` still excludes a skill.
- **Validator:** all structural and cross-file checks stay. In `--application-ready` mode, a missing approval is a warning and unconfirmed skills are not flagged; a hash mismatch is an error.
- **Output:** `output/<job_id or default>/cv.tex` is self-contained (only the packages in `sources/baseline_cv.tex`) and compiles unchanged on Overleaf; `cv.pdf` is a convenience preview. The `.tex` carries `% REVIEW: agent-written wording`, `% REVIEW: new skill from job description (…)` and `% REVIEW: metric not verified (…)` comments, and `--clean` omits them. Internal metadata words never appear in comments or output.
- **One page:** the fit loop stays. If it can't fit, the `.tex` is still written and the console reports OVER-LENGTH, instead of failing.
- **No schema change:** `cv_constraints.allow_unapproved_bullets` stays `false`, because everything is approved.
- **Still binding:** never invent facts (rewording is fine, new claims are not); never contradict this file; the model picks content, the deterministic renderer writes LaTeX; fonts and margins never change; English only, no summary, manual applications, private repo.
- **Approved but never auto-selected** (`cv_engine/selection_policy.json`), because their wording contradicts the decisions below: `bullet_qrt_arbitrage_s2` ("arbitrage"), `bullet_amazon_lost_package_s2` ("Applied", not built and tuned), `bullet_amazon_carrier_pricing_s3` (drops the preferred carrier framing and adds unverified "SQL row-count validation"). Rejecting them with `--reject` would also be consistent.

## Sources
- **S1** `sources/baseline_cv.tex`: current Overleaf CV, the authoritative baseline.
- **S2** `sources/Elliot Gautier CV.pdf`: older UK-oriented version.
- **S3** `sources/Elliot Gautier Resume de.pdf`: in English despite the name; US-oriented (Berkeley, +1, OPT line).
- **S4** `sources/CourseDescriptionWarwick.pdf`: Warwick modules + grades, copied from the official transcript (so verified).

## Schema history
v1.0 → v1.1 (US/UK contact profiles, interests, coursework annotations; summary/headline removed) → v1.2 (flexible dates + `date_display`, project `subtitle`, `skill_groups`, spoken-language skills) → **v1.3 (current)**: `skills[].confirmation_status`, `contact_profiles.*.work_authorization_display`, nullable coursework `status`. See `SCHEMA_v1_3_MIGRATION_NOTES.md`.

## Factual decisions (closed)
| Topic | Decision |
|---|---|
| Football results | Accurate bullet: "Trained a LightGBM multiclass model using walk-forward cross-validation, reducing log loss by 8.8% relative to a naive baseline and benchmarking predictions against bookmaker odds in a Streamlit dashboard." The S1 ablation bullet (form/Elo/xG/rest, 12.8%) is **inaccurate and was dropped**; no achievement exists for it. |
| Amazon lost-package model | Elliot built and tuned it; F1 0.43 → 0.61 confirmed. |
| Amazon carrier pricing | Preferred framing: "drove the cross-team fix to zero duplicate lanes". |
| QRT | Call it **pairs trading** (not "arbitrage"). |
| Berkeley | Title "M.A. Statistics and Data Science"; "4.0 GPA" ("expected" removed); 2026-08 → 2027-05. Coursework entries are **topics, not course titles**: `status: null`, `verified: true`. |
| Warwick | 25 modules from S4, all `completed` + `verified`. First Class Honours, 80%, Top 5% of cohort (the last from the CV only). |
| Contacts | US profile: Berkeley, CA · +1 (510) 570-5964 · header line "Eligible for OPT + STEM OPT". UK profile: London, UK · +44 7884972450 · no authorization line. LinkedIn stored with `https://`. |
| Summary / headline | None on the CV. |
| Interests | `profile.interests` (Rugby, Football, Tennis, Athletics with details), rendered as a row in the skills block. |
| Languages | French (fluent), Spanish (intermediate) as `spoken_language` skills in a "Languages" skill group. |

## Preferences
- Countries: United States, United Kingdom.
- Roles, in priority order (array order = priority): (1) Data Scientist / ML Scientist / Applied Scientist; (2) ML Engineer / AI Engineer; (3) Forward Deployed / Deployment / Solutions Engineer at AI or data companies; (4) Data Analyst / BI with substantial ML or analytical content.
- Seniority: graduate, new grad, entry level, early career.
- Work authorization: US = "F-1 student; eligible for OPT + STEM OPT", `requires_sponsorship: null` (depends on now vs. future). Matching must separate OPT/STEM OPT-compatible roles from roles that need unrestricted authorization. UK = British citizen, no sponsorship.

## Skills policy
- Exactly two states: `confirmed` (Elliot has verified it) / `unconfirmed` (~~suggested, awaiting review~~ added from a job description; tracking only since 2026-11-18). Evidence links are independent of confirmation.
- Every skill on any of S1–S3 is `confirmed`, including dbt, Dagster (S3 misspells it "Dragster"), XGBoost, PyTorch, DuckDB, Quarto, pytest.
- ~~Agent behaviour: extract skills/keywords from each job description, select confirmed skills, and propose missing important ones as `unconfirmed` for review. Elliot confirms or rejects. Rejected suggestions are **not** stored in `skills.json`; keep a rejected-suggestions list in review/tracking data so they aren't suggested again.~~ **Superseded 2026-11-18:** missing skills are added as `unconfirmed` and used straight away; Elliot reviews them in Overleaf.
- ~~Application-ready CVs: only skills that are `confirmed` + `cv_eligible`. Unconfirmed skills may appear only in internal previews.~~ **Superseded 2026-11-18:** only `cv_eligible` gates a skill.
- **Never** print "confirmed"/"unconfirmed" (or any approval/verification metadata) in `.tex`/PDF output, comments included. *(Still in force.)*

## Bullet policy
> **Superseded 2026-11-18** by "Auto-approval + Overleaf-first output" (top of this file). Kept for history; the storage format (plain Unicode text, SHA-256 of the UTF-8 text) is unchanged.

- 17 bullets imported from existing CVs (12 S1 + 5 older alternatives), all `proposed`, `source: existing_cv`. No new wording during population. *(All 17 approved 2026-11-18.)*
- Text is stored as plain Unicode (–, ∼, %, −, ×, &). The renderer escapes it to LaTeX. Approval hash = SHA-256 of the stored UTF-8 text.
- ~~Only Elliot approves, via `tools/approve_bullets.py`. Claude must never set `approved`, `approved_at` or `approved_text_sha256`.~~
- Recommended for rejection: `bullet_qrt_arbitrage_s2`, `bullet_amazon_lost_package_s2`. *(Now approved but listed in `cv_engine/selection_policy.json`, so never auto-selected.)*

## Renderer rules (Phase 2)
- **No schema changes needed** for these. Nested skills: a template-level config maps parent → children (e.g. `skill_sql → [skill_redshift, skill_duckdb]`). When the parent and at least one child are in the same group, print `SQL (Redshift, DuckDB)` at the parent's position.
- Header: if the contact profile has `work_authorization_display`, use the three-line layout (name / "location | authorization line" / contact row); otherwise use the single-line layout.
- Topic coursework (`status: null`) is printed without any completion wording.
- Education lines: Berkeley "Coursework:", Warwick "Relevant Courses: Name (grade; annotation)"; honours line "First Class Honours (80% - Top 5% of cohort)".
- Fixed typography/margins from S1; never shrink fonts or margins to fit. If fitting fails, still write the `.tex` and report OVER-LENGTH (2026-11-18).
- **Phase 2 acceptance:** reproduce the baseline layout, excluding the summary and including the confirmed corrections. *(Met 2026-11-18: `python -m cv_engine.render` → `output/default/cv.tex`, one page.)*

## Open (non-blocking) facts, still `needs_review`
£30k/week, ETL 6–8 h → ∼30 min and 100+ stakeholders, 8M rows, £1.5M, −3.4%, 80 files / 12,600 matches, role on the multi-agent system, SQL row-count validation, Cover team details, QRT exact dates, project repo links.
