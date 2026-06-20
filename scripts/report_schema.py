"""
诊断报告 JSON 顶层字段规范（v1）。
写入 reports/*.json 时统一结构，便于聚合与筛选。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

REPORT_SCHEMA_VERSION = 1


def normalize_report_object(
    *,
    summary: str,
    probabilities: dict,
    meta: dict,
    treatment_plan: Optional[dict] = None,
    generated_at: Optional[str] = None,
    demo: bool = False,
    source: str = "web_predict",
    batch_id: Optional[str] = None,
    input_filename: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """构建符合 schema 的报告对象。"""
    tp = treatment_plan or (meta or {}).get("treatment_plan") or {}
    meta = dict(meta or {})
    if tp and "treatment_plan" not in meta:
        meta["treatment_plan"] = tp

    ts = generated_at or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    obj: Dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": ts,
        "demo": bool(demo or meta.get("demo")),
        "source": source,
        "summary": summary,
        "probabilities": probabilities or {},
        "meta": meta,
        "treatment_plan": tp,
    }
    if batch_id:
        obj["batch_id"] = batch_id
    if input_filename:
        obj["input_filename"] = input_filename
    if case_id:
        obj["case_id"] = case_id
    return obj


def enrich_meta_from_treatment(meta: dict) -> dict:
    """从 treatment_plan 补全 meta 中常用聚合字段。"""
    meta = dict(meta or {})
    tp = meta.get("treatment_plan") or {}
    if not meta.get("crop") and tp.get("crop"):
        meta["crop"] = tp["crop"]
    if not meta.get("urgency") and tp.get("urgency"):
        meta["urgency"] = tp["urgency"]
    if not meta.get("disease_name") and tp.get("disease_name"):
        meta["disease_name"] = tp["disease_name"]
    return meta