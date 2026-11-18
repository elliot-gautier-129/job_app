# Stage B — Knowledge Base Review Report

> **Update (2026-11-18):** see `docs/DECISIONS.md` → "Auto-approval + Overleaf-first output". All 17 bullets are now **approved**. `bullet_qrt_arbitrage_s2`, `bullet_amazon_lost_package_s2` and `bullet_amazon_carrier_pricing_s3` are approved but listed in `cv_engine/selection_policy.json`, so they are never auto-selected. The "approve/reject" recommendations below are historical; Stage C and the approval tool notes have been updated in place. Open facts are now flagged in each generated `.tex` as `% REVIEW: metric not verified (…)`.

**Date:** 2026-11-17 · **Schema:** v1.3 (package built 2026-11-17) · **Status:** all 8 files schema-valid; cross-file validator: **0 errors, 0 warnings**.

## Contents

| File | Records |
|---|---|
| `profile.json` | Common contact info, US + UK contact profiles, 4 interests |
| `education.json` | 2 entries, 29 coursework records (Warwick 25 completed + verified; Berkeley 4 topics, `status: null`, verified) |
| `experiences.json` | Amazon, Kirontech, QRT |
| `projects.json` | Football Forecasting, Cover |
| `achievements.json` | 13 achievements, 12 metrics (3 verified) |
| `skills.json` | 43 skills, all `confirmed` (on at least one CV); 20 have no supporting achievement |
| `bullet_variants.json` | **17 bullets**: 12 from the current CV + 5 older alternatives; `source: existing_cv`; imported as `proposed`, all approved 2026-11-18 |
| `preferences.json` | Roles (priority order), US/UK, seniority, work authorization, CV constraints |

`tools/validate_kb.py` checks schemas plus cross-file rules: unique IDs across namespaces; parent ↔ achievement mapping; skill/achievement/bullet references; approval hash = SHA-256 of the exact text; calendar dates, date order, `date_display` consistency; proficiency rules; no LaTeX in stored text; https URLs. With `--manifest [--application-ready]` it also checks manifests (entry ownership, no rejected bullets, verified courses, `cv_eligible` skills, no repeated skills or groups; since 2026-11-18 missing approval is only a warning and unconfirmed skills are not gated). `check_rendered_text()` is ready for the renderer's metadata-leak test. A mutation test caught 15/15 injected faults.

## Bullets to approve (historical: all approved 2026-11-18)

Text is stored as plain Unicode. LaTeX was converted only in encoding: `--`→–, `$\sim$`→∼, `\%`→%, `$-$`→−, `$\times$`→×, `\&`→&. The renderer converts back. Approval hashes are computed on this stored text.

| ID | Source | Priority | Recommendation |
|---|---|---|---|
| bullet_amazon_etl_s1 | S1 | 5 | Approve if metrics correct |
| bullet_amazon_lost_package_s1 | S1 | 5 | Approve (F1 confirmed; £30k still unverified) |
| bullet_amazon_multiagent_s1 | S1 | 4 | Approve |
| bullet_amazon_carrier_pricing_s1 | S1 | 4 | Approve (your preferred framing) |
| bullet_kirontech_provider_graph_s1 | S1 | 3 | Approve if 8M correct |
| bullet_kirontech_fraud_detection_s1 | S1 | 4 | Approve if £1.5M correct |
| bullet_kirontech_dashboard_s1 | S1 | 2 | Approve |
| bullet_qrt_pairs_trading_s1 | S1 | 2 | Approve |
| bullet_football_pipeline_s1 | S1 | 3 | Approve |
| bullet_football_market_benchmark_s1 | S1 | 3 | Approve if −3.4% correct |
| bullet_cover_web_app_s1 | S1 | 3 | Approve |
| bullet_cover_pricing_model_s1 | S1 | 3 | Approve |
| bullet_football_lightgbm_s2 | S2/S3 | 4 | **Approve**: your confirmed football bullet |
| bullet_football_pipeline_s2 | S2/S3 | 3 | Optional shorter alternative to the S1 pipeline bullet |
| bullet_amazon_carrier_pricing_s3 | S3 | 3 | Keep proposed or reject: "SQL row-count validation" unconfirmed; weaker framing |
| bullet_amazon_lost_package_s2 | S2/S3 | 3 | **Recommend reject**: "Applied" understates that you built the model |
| bullet_qrt_arbitrage_s2 | S2/S3 | 1 | **Recommend reject**: "arbitrage" conflicts with "pairs trading" |

**Priority (1–5, general importance, not job-specific):** 5 = headline results with strong impact metrics at the most recent employer. 4 = distinctive technical work (multi-agent system, fraud detection, confirmed football model, cross-team data fix). 3 = solid supporting work. 2 = minor or supporting (dashboard, one-month QRT placement). 1 = a variant recommended for rejection. Alternatives score at or below their S1 counterpart.

## Decisions I made (please check)

1. **Football subtitle** comes from the baseline CV, as instructed: "Signal Research & Market-Efficiency Study". The older PDFs used "Probabilistic Football Forecasting & Market-Efficiency Model". Change it if "Signal Research" now feels tied to the dropped ablation work.
2. **Warwick course names** follow the transcript: "Mathematical Programming 1" (your CV says "Mathematical Programming"), "Python for Data-Analytic Tasks" (an extraction artifact in S4 was fixed).
3. **Warwick grade/honours:** `grade: "80%"`, `honors: ["First Class Honours", "Top 5% of cohort"]`. The renderer recombines them as "First Class Honours (80% - Top 5% of cohort)". "Top 5% of cohort" comes only from your CV.
4. **Berkeley topic capitalisation:** "High-Dimensional Statistics" (lowercase on the CV), to match the other entries.
5. **Skills beyond the CV skill rows:** under "any skill on any CV is confirmed", I added tools and methods named in bullets: AWS Bedrock, AWS Lambda, Amazon Kendra, Gemini, Excel, text-to-SQL, multi-agent AI systems, cross-validation, walk-forward CV, anomaly detection, graph analytics, backtesting, frequency-severity modelling, data quality validation. "Dragster" is stored as Dagster.
6. **No unsupported skill links:** DuckDB and pytest are not linked to the football project, even though it's likely they were used there. You can add the links if they're true.
7. **US `requires_sponsorship: null`:** the answer depends on whether a question asks about now or the future. The matching logic relies on the status text and notes.
8. **Experience/project `description`:** null everywhere, to avoid unverifiable prose.

## Facts still `needs_review` (non-blocking; flagged as `% REVIEW` comments in generated `.tex`)

Amazon ETL (6–8 h → ∼30 min, 100+ stakeholders, billion-row); lost-package £30k/week; your role on the multi-agent system; carrier detection via SQL row-count validation; Kirontech 8M rows and £1.5M; QRT "decade" of data and exact dates; football 80 files / 12,600 matches and −3.4%; Cover team size and contribution. Verified so far: F1 0.43 → 0.61, zero duplicate lanes, log-loss −8.8%.

## Follow-ups

- ✅ **Stage C (`default_cv.json`)** done 2026-11-18: reproduces the baseline with no summary, the confirmed football bullet, skill groups (Programming & Data / Python / Tools / Languages) and interests.
- ✅ **Renderer config** for nested skills (`skill_sql → [skill_redshift, skill_duckdb]`) lives in `cv_engine/templates/baseline_onepage.json`.
- **Approval tool:** `tools/approve_bullets.py`. Non-interactive by default (status list). `--all` stamps every proposed/STALE bullet, plus `--approve/--reject/--revoke ID…` and `--yes`; `--review` is optional. Records a UTC `approved_at` and the SHA-256 of the exact text, keeps a `.bak`, re-runs the validator, and flags bullets edited after stamping as STALE. Agent-written bullets are stamped automatically by `cv_engine/kb_writer.py`.
- Project repo links and anything not on any CV.
