"""无浏览器单元测试：病害知识库与防治引擎。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.disease_catalog import DISEASE_DETAILS, get_treatment_extended, NAME_ALIASES
from scripts.treatment_engine import build_treatment_plan, resolve_disease_id, enrich_disease_list_entry
from scripts.utils import get_crop_type


def test_disease_catalog_at_least_30():
    assert len(DISEASE_DETAILS) >= 30
    assert len(DISEASE_DETAILS) >= 60


def test_every_disease_has_core_fields():
    for did, info in DISEASE_DETAILS.items():
        assert "name" in info and info["name"], f"id {did} missing name"
        assert "description" in info and info["description"], f"id {did} missing description"
        assert "suggestion" in info and info["suggestion"], f"id {did} missing suggestion"


def test_extended_treatment_for_sample_ids():
    for did in (0, 10, 20, 34, 43):
        ext = get_treatment_extended(did)
        assert ext is not None
        assert ext.get("prevention")
        assert ext.get("steps") or ext.get("chemical")


def test_build_treatment_plan_required_keys():
    plan = build_treatment_plan("玉米大斑病", severity="严重", disease_idx=10, risk_percent=78, confidence=0.91)
    for key in (
        "disease_name",
        "crop",
        "severity",
        "urgency",
        "quick_suggestion",
        "actionable_summary",
        "treatment_steps",
        "recheck_timeline",
        "chemical_treatment",
        "phytosanitary_notice",
    ):
        assert key in plan, f"missing {key}"
    assert "紧急" in plan["actionable_summary"] or plan["urgency"] == "高"


def test_resolve_disease_id_aliases():
    assert resolve_disease_id("tomato late blight") == 43
    assert resolve_disease_id("Apple___Black_rot") == 2
    assert resolve_disease_id("未知病害xyz") is None


def test_enrich_disease_list_entry():
    entry = enrich_disease_list_entry(10, DISEASE_DETAILS[10])
    assert entry["crop"] == get_crop_type(10)
    assert entry.get("phytosanitary_notice")


def test_healthy_plan():
    plan = build_treatment_plan("苹果健康", severity="健康", disease_idx=0, risk_percent=15, confidence=0.95)
    assert plan["is_healthy"] is True
    assert plan["urgency"] == "低"


if __name__ == "__main__":
    test_disease_catalog_at_least_30()
    test_every_disease_has_core_fields()
    test_extended_treatment_for_sample_ids()
    test_build_treatment_plan_required_keys()
    test_resolve_disease_id_aliases()
    test_enrich_disease_list_entry()
    test_healthy_plan()
    print("OK: all catalog/treatment tests passed")