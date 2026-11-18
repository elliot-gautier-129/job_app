# Schema v1.3 — migration notes

> **Update (2026-11-18):** see `docs/DECISIONS.md` → "Auto-approval + Overleaf-first output". **No schema change.** The runtime rules changed: `confirmation_status` is tracking only (unconfirmed skills render, flagged by a `% REVIEW` comment), and bullets are approved automatically (`kb_writer` sets `approved_at` + hash). Statements below have been updated where they conflicted.

v1.3 supersedes v1.2. It makes exactly three structural changes, all approved by the user on 2026-11-17. Everything else is unchanged from v1.2 apart from `schema_version` (now `"1.3"` in all nine schemas), `$id` and `title`.

## Changes

### 1. `skills[].confirmation_status` (required)
- `enum: ["confirmed", "unconfirmed"]`. Exactly two states.
- `confirmed`: the user has explicitly verified they have the skill. `unconfirmed`: added from a job description; since 2026-11-18 it renders straight away and is reviewed in Overleaf (tracking only, never a gate).
- Independent of `evidence_achievement_ids`: a confirmed skill can have no supporting achievement.
- `cv_eligible` keeps its own meaning (allowed on a CV at all) and is still enforced.
- ~~Rejected suggestions are **not** stored in `skills.json`. Keep a rejected-suggestions list in review/tracking data so the agent doesn't re-suggest them.~~ *(Superseded 2026-11-18; to drop a skill, delete it or set `cv_eligible: false`.)*

### 2. `profile.contact_profiles.{US,UK}.work_authorization_display` (required, nullable)
- Exact header text for CVs that use that contact profile, e.g. US: `"Eligible for OPT + STEM OPT"`.
- `null`: no authorization line (single-line header layout).
- This is display text. The structured eligibility data used for job matching stays in `preferences.work_authorization`.

### 3. `education[].coursework[].status` may be `null`
- Still `completed | in_progress | planned` for named courses.
- `null` = not tracked. Used for topic-level coursework (e.g. Berkeley entries such as "Machine Learning", which are topics, not official course titles).
- A user-confirmed topic entry is stored with `verified: true`. "Approved" is expressed through `verified`, not through `status`.

## Runtime rules added (Python, not expressible in JSON Schema)
1. ~~Application-ready manifests may only reference skills with `confirmation_status: "confirmed"` and `cv_eligible: true`. Review previews may include unconfirmed skills, flagged in the review UI only.~~ **Since 2026-11-18:** application-ready manifests require `cv_eligible: true` only; unconfirmed skills render and get a `% REVIEW: new skill from job description (…)` comment in the `.tex`.
2. The renderer must never output internal metadata. A test (`tests/test_cv_engine.py`) asserts that the generated `.tex` (comments included) contains no `confirmed`/`unconfirmed`/approval/verification labels.
3. Coursework with `status: null` is rendered as plain coursework (no completion wording). Coursework with `planned`/`in_progress` must never be presented as completed.
4. The header layout depends on the selected contact profile: a three-line header when `work_authorization_display` is set, otherwise the single-line header.

## Unchanged v1.2 rules
Flexible dates + `date_display`, project `subtitle`, `skill_groups`, spoken-language skills, the 17 existing bullet candidates (all approved 2026-11-18), approval hashes set by `tools/approve_bullets.py` or `cv_engine/kb_writer.py` (auto-approval), no summary, US/UK contact profiles, English only, manual applications, one-page fitting (the `.tex` is written even if fitting fails).

## Files
Nine `*.schema.json` files, `VALIDATION_SMOKE_TEST.json` (minimal valid documents) and `VALIDATION_EXAMPLE_v1_3.json`. The example covers each new field: a confirmed and an unconfirmed skill, the US authorization line, and a topic course with `status: null` next to a named course that is `in_progress`.
