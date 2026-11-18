"""Tests for the renderer, escaping and auto-approving KB writer. Run: python -m pytest -q"""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cv_engine import kb_writer  # noqa: E402
from cv_engine.kb import KB, TEMPLATE_DIR, load_json, sha256, validate_kb  # noqa: E402
from cv_engine.latex import escape  # noqa: E402
from cv_engine.render import DEFAULT_MANIFEST, Renderer, metric_in_text  # noqa: E402


@pytest.fixture
def kb_copy(tmp_path):
    dst = tmp_path / "knowledge_base"
    shutil.copytree(ROOT / "knowledge_base", dst, ignore=shutil.ignore_patterns("*.bak", "*.tmp"))
    return dst


def render_default(review=True, kb_dir=None):
    kb = KB(kb_dir) if kb_dir else KB()
    manifest = load_json(DEFAULT_MANIFEST)
    cfg = load_json(TEMPLATE_DIR / f"{manifest['template_id']}.json")
    return Renderer(kb, cfg, review=review).render(manifest)


def test_escape_specials_and_unicode():
    assert escape("R&D 50% $5 #1 a_b {x}") == r"R\&D 50\% \$5 \#1 a\_b \{x\}"
    assert escape("6–8 hours to ∼30 min, −3.4%, 2×, £30k") == r"6--8 hours to $\sim$30 min, $-$3.4\%, 2$\times$, \pounds{}30k"
    assert escape("Amazon’s café") == "Amazon's café"
    with pytest.raises(ValueError):
        escape("emoji 🚀")


def test_default_render_has_no_metadata_words_and_no_summary():
    for review in (True, False):
        tex = render_default(review)
        rep = validate_kb.Report()
        validate_kb.check_rendered_text(rep, tex)
        assert rep.errors == []
        assert "SUMMARY" not in tex
        assert "12.8" not in tex and "8.8\\%" in tex
        assert "arbitrage" not in tex.lower() and "pairs-trading" in tex


def test_clean_mode_drops_review_comments():
    assert "% REVIEW:" in render_default(review=True)
    assert "REVIEW" not in render_default(review=False)


def test_us_header_and_nested_skills():
    tex = render_default()
    assert "Eligible for OPT + STEM OPT" in tex
    assert "SQL (Redshift, DuckDB)" in tex
    assert "Redshift, DuckDB, " not in tex  # children not repeated on their own


def test_metric_detection():
    assert metric_in_text({"value": "£30k"}, "flagged an estimated £30k of packages")
    assert metric_in_text({"value": 12600}, "into 12,600 matches")
    assert not metric_in_text({"value": "£1.5M"}, "no numbers here")


def test_add_bullet_variant_is_auto_approved(kb_copy):
    bid = kb_writer.add_bullet_variant(
        ["ach_kirontech_streamlit_dashboard"],
        "Built a Streamlit dashboard presenting datasets and model results to fraud investigators.",
        kb_dir=kb_copy)
    b = {x["id"]: x for x in load_json(kb_copy / "bullet_variants.json")["bullet_variants"]}[bid]
    assert b["status"] == "approved" and b["source"] == "agent_generated"
    assert b["approved_text_sha256"] == sha256(b["text"]) and b["approved_at"]
    # same text again → same ID, no duplicate
    assert kb_writer.add_bullet_variant(["ach_kirontech_streamlit_dashboard"], b["text"], kb_dir=kb_copy) == bid
    # renders with an agent-wording REVIEW marker
    kb = KB(kb_copy)
    cfg = load_json(TEMPLATE_DIR / "baseline_onepage.json")
    out = Renderer(kb, cfg).bullets([bid])
    assert any("REVIEW: agent-written wording" in line for line in out)


def test_add_bullet_variant_rejects_invented_numbers(kb_copy):
    with pytest.raises(kb_writer.KBWriteError, match="numbers not supported"):
        kb_writer.add_bullet_variant(["ach_football_lightgbm_model"],
                                     "Trained a LightGBM model cutting log loss by 15% versus a naive baseline.",
                                     kb_dir=kb_copy)
    # numbers that are in the evidence are fine
    kb_writer.add_bullet_variant(["ach_football_lightgbm_model"],
                                 "Cut log loss by 8.8% versus a naive baseline with a walk-forward-validated LightGBM model.",
                                 kb_dir=kb_copy)


def test_add_skill_unconfirmed_but_renders(kb_copy):
    sid = kb_writer.add_skill("Kubernetes", "tools", aliases=["k8s"], kb_dir=kb_copy)
    s = {x["id"]: x for x in load_json(kb_copy / "skills.json")["skills"]}[sid]
    assert s["confirmation_status"] == "unconfirmed" and s["cv_eligible"] is True
    assert kb_writer.add_skill("k8s", "tools", kb_dir=kb_copy) == sid          # alias → existing
    assert kb_writer.add_skill("python", "programming", kb_dir=kb_copy) == "skill_python"
    cfg = load_json(TEMPLATE_DIR / "baseline_onepage.json")
    r = Renderer(KB(kb_copy), cfg)
    sec = {"section": "skills", "entries": [], "skill_ids": [], "interest_ids": [],
           "skill_groups": [{"label": "Tools", "skill_ids": ["skill_git", sid]}]}
    lines = r.skills(sec, [])
    text = "\n".join(lines)
    assert "Kubernetes" in text and "REVIEW: new skill from job description (Kubernetes)" in text
    assert "confirmed" not in text.lower()


def test_validator_application_ready_does_not_gate_on_approval(kb_copy, tmp_path):
    data = load_json(kb_copy / "bullet_variants.json")
    data["bullet_variants"][0].update(status="proposed", approved_at=None, approved_text_sha256=None)
    (kb_copy / "bullet_variants.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rep = validate_kb.run(kb_copy, ROOT / "schemas", DEFAULT_MANIFEST, application_ready=True)
    assert rep.errors == [] and any("no approval record" in w for w in rep.warnings)


def test_validator_still_errors_on_hash_mismatch(kb_copy):
    data = load_json(kb_copy / "bullet_variants.json")
    data["bullet_variants"][0]["text"] += " Edited."
    (kb_copy / "bullet_variants.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rep = validate_kb.run(kb_copy, ROOT / "schemas")
    assert any("hash mismatch" in e for e in rep.errors)
