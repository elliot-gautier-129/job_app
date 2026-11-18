# AI Job Discovery & CV Tailoring System
## High-Level Design Document — Version 2.0

> **Note (2026-11-18):** This document predates schema v1.3. Where it says "Knowledge Base Schema v1.0", the current contract is `schemas/` (v1.3). See `docs/DECISIONS.md` and `docs/SCHEMA_v1_3_MIGRATION_NOTES.md`. Phase 1 (knowledge-base population) is complete. Its §11 "Immediate instruction" is historical.

**Status:** Design agreed; knowledge-base population and renderer implementation pending  
**Primary development environment:** Local computer  
**Primary language:** Python  
**Purpose of this document:** Provide Claude with the full project context and architectural boundaries before populating the personal knowledge base.  
**Supersedes:** The earlier design that included automated job application submission.

## 1. Executive summary

Build a personal AI-assisted system that discovers suitable early-career jobs, evaluates them against a verified professional knowledge base, and generates a tailored, professional, one-page English CV for each selected opportunity. The user reviews the opportunities and CVs and **submits every application manually**. The system does not create accounts, fill application forms, or submit applications.

The most important early deliverable is a reliable CV tailoring engine built on a structured, reviewable knowledge base and the user's existing Overleaf/LaTeX CV template. The system must prioritize factual accuracy, explainable selection, consistent formatting, and reproducible output over unconstrained generative writing.

## 2. Goals and non-goals

### Goals

1. Maintain a structured, comprehensive record of education, professional experience, projects, skills, achievements, and approved CV wording.
2. Analyze a job description and identify relevant verified qualifications and achievements.
3. Select and organize the strongest approved content for that job, including relevant coursework.
4. Generate a selection manifest and render a tailored CV using the existing LaTeX template.
5. Compile and inspect the PDF, iteratively adjusting optional content until it fits one page without changing established typography or margins.
6. Later, periodically discover, normalize, deduplicate, filter, and rank new jobs.
7. Provide a review interface with job details, fit rationale, tailored CV, application link, and optional application tracking.
8. Preserve provenance, approvals, and reproducibility of each generated CV.

### Explicit non-goals

- No automatic application submission, browser form filling, or account creation.
- No automatic approval of newly generated bullet wording.
- No invented experience, metrics, qualifications, skills, or responsibilities.
- No multilingual CV generation: **English only**.
- No need for LangGraph, a vector database, or a production cloud database in the initial implementation.
- No statistical learning from application outcomes until sufficient data and a justified methodology exist.

## 3. Intended user workflow

**Near-term, on-demand:** The user supplies a job description or URL. The system analyzes the job, selects verified/approved CV content, compiles a tailored one-page PDF, and presents the CV and selection rationale for review. If stronger wording is needed, it may propose new bullet variants for explicit approval; these cannot appear in the final CV until approved.

**Longer-term, scheduled:** Job collectors discover new postings from supported ATS APIs and company career pages. Eligibility filters and relevance scoring prioritize opportunities. The system prepares tailored CVs for promising jobs and presents them in a dashboard. The user decides which roles to pursue and manually applies. Airtable/Gmail integration is optional and downstream.

## 4. High-level architecture

```text
Job descriptions / ATS job collectors
                |
                v
      Normalize + deduplicate
                |
                v
    Eligibility and fit scoring <---- Preferences + verified knowledge base
                |
                v
   Content retrieval and ranking <---- Approved bullet variants + coursework
                |
                v
     CV selection manifest
                |
                v
   Deterministic LaTeX renderer <---- Existing Overleaf template
                |
                v
       PDF compilation
                |
                v
   One-page fit check / revise selection
                |
                v
  Review dashboard + tailored PDF
                |
                v
       User applies manually
```

The AI component interprets job requirements, scores relevance, selects content IDs, and proposes new wording when needed. Deterministic Python code validates references, approval states, and rendering rules. The LLM should **not** directly edit the LaTeX template or fabricate raw CV content outside the knowledge-base workflow.

## 5. Knowledge Base

The authoritative knowledge base is a set of eight local JSON files:

```text
knowledge_base/
  profile.json
  education.json
  experiences.json
  projects.json
  achievements.json
  skills.json
  bullet_variants.json
  preferences.json
```

A separate `cv_engine/manifests/default_cv.json` describes the content and ordering of the baseline CV. Job-specific manifests are generated separately. The project also includes nine JSON Schema definitions (eight data schemas and one manifest schema) and Python cross-file validation.

**Authoritative contract:** The schema package in `schemas/` defines the exact field names, required fields, nullability, allowed values, and manifest structure. Do not infer or redesign those details from this high-level document. If this overview and the schema package differ on field-level specifics, follow the schema package and flag the discrepancy.

### 5.1 Entity responsibilities

- **Profile:** Stable professional identity and CV contact information.
- **Education:** Institutions, degrees, distinctions, and individually selectable coursework with verification status.
- **Experiences:** Employment/internship/research roles and links to achievements.
- **Projects:** Personal and academic projects and links to achievements.
- **Achievements:** Distinct accomplishments, underlying factual claims, skills, optional metrics, and evidence/provenance.
- **Skills:** Skills supported, where possible, by achievements or projects.
- **Bullet variants:** Exact English CV-ready wording linked to one or more achievements, with approval state and provenance.
- **Preferences:** Target roles, locations, eligibility constraints, and CV rendering limits.
- **CV manifests:** The precise section, entry, bullet, skill, and coursework IDs selected for one CV.

### 5.2 Design invariants

- Stable IDs and valid cross-file references; avoid duplicate facts and achievements.
- Separate **facts** from **achievements**, and both from **CV wording**.
- Claims and metrics must be traceable to verified facts; uncertainty is explicitly flagged.
- Schema validation checks shape, not truth; human review is required for factual approval.
- New or changed bullet text begins as `proposed`; explicit user approval is necessary before use in a final tailored CV.
- Approval applies to the **exact wording**; the schema package specifies approval metadata and text hashing.
- The renderer uses approved variants only. Rejected or proposed bullets must not silently enter final output.
- Coursework selection is permitted only from verified course records.
- Mandatory/locked content is controlled by the **manifest**, not a global bullet property.
- No translation or language-specific variant machinery is required.

## 6. CV tailoring pipeline

1. **Input:** Receive a normalized job description, job metadata, preferences, and the validated knowledge base.
2. **Analyze:** Extract role requirements, preferred qualifications, responsibilities, and salient technical themes. Identify hard eligibility questions and unknowns.
3. **Retrieve:** Find relevant verified achievements, skills, education/coursework, and approved bullet variants.
4. **Rank:** Estimate job-specific relevance, importance, redundancy, and space cost. Preserve a distinction between default importance and role-specific fit.
5. **Select:** Produce a structured CV manifest referencing existing IDs; never insert invented bullet text directly into the manifest.
6. **Validate:** Check schema, referential integrity, approved statuses, verified coursework, permitted sections, duplicates, and locked entries.
7. **Render:** Resolve IDs and generate LaTeX using the user's existing Overleaf formatting, then compile a PDF.
8. **Fit:** Confirm that the PDF has exactly one page. If not, try shorter **approved** variants and then remove the lowest-value **unlocked** optional content; recompile after each change. Respect a configured attempt limit. Never silently shrink fonts or margins.
9. **Deliver:** Save the job-specific manifest, generated LaTeX/PDF, selection explanation, and validation/fitting outcome. If fitting fails, report failure instead of presenting an overlength PDF as successful.

The optimization goal is **maximum job relevance subject to factual, approval, structural, and one-page constraints**. Approximate bullet lengths may help ranking, but actual compiled PDF measurements are authoritative. Layout measurements may be cached by template revision and text hash; they do not belong in Claude-authored knowledge records.

## 7. Baseline CV and Overleaf integration

The existing Overleaf project is the visual source of truth for typography, margins, custom commands, and section design. The baseline CV should be reproducible from the knowledge base and `default_cv.json` before intelligent tailoring is added.

The implementation should preserve a static LaTeX template and generate only its variable content, using a deterministic Python renderer and safe escaping. The LLM chooses content identifiers, not raw LaTeX. The renderer must be tested against the existing CV for visual consistency.

The baseline manifest must be derived from the **actual current CV source**, not reconstructed from memory. Existing bullet wording must be imported exactly and explicitly approved by the user before it is eligible for final CV generation.

## 8. Technology choices

**Initial stack:** Python, JSON, JSON Schema Draft 2020-12, Pydantic/Python cross-file checks, Git, LaTeX, a local TeX compiler, and a straightforward Python orchestration pipeline. Jinja2 is an option for templating, provided the output is deterministic and safely escaped.

**Later stack:** SQLite for discovered jobs and generation records; ATS posting APIs such as Greenhouse, Lever, and Ashby; Streamlit for review; scheduled execution; optional Airtable and Gmail integrations. Cloud hosting can be considered once continuous execution is useful.

**Not initially required:** LangGraph, Playwright/browser application automation, PostgreSQL/Supabase, vector search, or a large distributed architecture.

Development and knowledge-base storage should be local rather than on Berkeley SCF machines. Keep secrets, sensitive personal information, and private employment records out of public repositories.

## 9. Development roadmap and acceptance criteria

### Phase 1 — Knowledge-base population and validation ✅ (done 2026-11-17)

- Review Claude's inventory of professional facts and identify gaps or contradictions.
- Populate the eight JSON files against the exact provided schemas.
- Review metrics, dates, responsibilities, technical skills, and wording.
- Validate each file structurally and all cross-file references programmatically.
- **Acceptance:** The knowledge base is schema-valid, internally consistent, and reviewed; unverified claims remain flagged and unapproved bullets remain proposed.

### Phase 2 — Baseline renderer

- Import the actual Overleaf template and exact existing CV content.
- Create and review the default CV manifest.
- Render a baseline PDF from structured data.
- **Acceptance (agreed revision):** Reproduce the baseline CV layout, excluding the professional summary and incorporating the confirmed factual corrections, with correct content, ordering, and one-page layout.

### Phase 3 — Job-specific tailoring and fitting

- Analyze job descriptions and select relevant approved content/coursework.
- Generate validated manifests and role-specific PDFs.
- Implement the iterative one-page fitting loop and approval workflow for proposed bullets.
- **Acceptance:** A user-supplied job description yields a factual, relevant, correctly formatted one-page CV, or a clear validation/fitting failure.

### Phase 4 — Discovery and ranking

- Add supported ATS collectors, normalization, deduplication, eligibility filters, and interpretable fit scores.
- **Acceptance:** New opportunities can be reviewed with grounded reasons for their ranking and without duplicate postings.

### Phase 5 — Review interface and scheduled operation

- Add Streamlit review, saved CVs, application links, scheduling, and optional tracking integrations.
- **Acceptance:** The user can review recommended jobs and download tailored CVs, then apply manually.

## 10. Data governance and review policy

Claude is a **knowledge extraction and drafting assistant**, not the authority that approves professional claims. It may use the actual CVs, course descriptions, and conversation context accessible to it, but must state when information is missing. Do not assume Claude can access every historical conversation. Source documents and the user's explicit corrections take precedence over unsupported model recollection.

Preserve exact existing CV text when importing; mark new or unapproved variants as proposed. Never fabricate dates, quantitative impact, or technologies.

Each tailored output should be reproducible from a recorded knowledge-base revision, template revision, and selection manifest. The user retains final editorial control and submits all applications manually.
