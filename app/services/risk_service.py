"""
风险评估核心服务层。
封装所有风险计算逻辑，与 Flask 解耦，可独立测试。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.models.assessment import Assessment
from app.models.database import get_db_session
from app.services.risk_rules_config import (
    RISK_RULES,
    get_sop_text,
    match_risk_rule,
    short_tier,
)

logger = logging.getLogger("zhinong.risk_service")

SEVERITY_LABELS = ("健康", "一般", "严重")


def assess(
    *,
    disease_name: str,
    severity_label: str,
    severity_idx: int,
    disease_confidence: float,
    severity_confidence: float,
    risk_percent: float,
    is_healthy: bool = False,
    crop: str = "",
    chemical_treatment: str = "",
    model_version: str = "",
    user_id: Optional[int] = None,
    input_filename: Optional[str] = None,
    input_source: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    核心风险评估函数。

    返回包含评估结果、风险等级、处置建议、责任人、截止日期的结构化 dict。
    """
    # 1. 匹配风险规则
    rule = match_risk_rule(
        severity_idx=severity_idx,
        disease_confidence=disease_confidence,
        risk_score=risk_percent,
        is_healthy=is_healthy,
    )

    risk_tier = rule["risk_tier"]
    tier_key = rule["tier_key"]
    responsible = rule.get("default_responsible", "巡检人员")
    deadline_days = rule.get("default_deadline_days", 7)

    # 2. 生成 SOP 建议文本
    sop_text = get_sop_text(
        tier_key,
        disease_name=disease_name,
        risk_score=risk_percent,
        chemical_treatment=chemical_treatment or "咨询农技人员",
    )

    # 3. 构建结果
    result = {
        "risk_score": round(risk_percent, 1),
        "risk_tier": risk_tier,
        "risk_tier_short": short_tier(risk_tier),
        "severity": severity_label,
        "severity_idx": severity_idx,
        "disease_name": disease_name,
        "disease_confidence": round(disease_confidence, 4),
        "severity_confidence": round(severity_confidence, 4),
        "crop": crop,
        "is_healthy": is_healthy,
        "suggestion": sop_text,
        "responsible_person": responsible,
        "deadline_days": deadline_days,
        "rule_key": rule["rule_key"],
        "model_version": model_version,
        "assessed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    # 4. 持久化到数据库
    _save_assessment(
        user_id=user_id,
        case_id=case_id,
        input_filename=input_filename,
        input_source=input_source,
        disease_name=disease_name,
        disease_id=None,
        crop=crop,
        severity=severity_label,
        severity_idx=severity_idx,
        risk_score=result["risk_score"],
        risk_tier=risk_tier,
        disease_confidence=disease_confidence,
        severity_confidence=severity_confidence,
        suggestion=sop_text,
        responsible_person=responsible,
        deadline_days=deadline_days,
        demo=False,
        model_version=model_version,
    )

    logger.info(
        "Assessment: disease=%s severity=%s risk=%.1f tier=%s responsible=%s deadline=%dd",
        disease_name, severity_label, risk_percent, risk_tier, responsible, deadline_days,
    )

    return result


def _save_assessment(**kwargs) -> Optional[int]:
    """保存评估记录到数据库。"""
    try:
        with get_db_session() as session:
            assessment = Assessment(**{k: v for k, v in kwargs.items() if v is not None})
            session.add(assessment)
            session.flush()
            assessment_id = assessment.id
        return assessment_id
    except Exception as exc:
        logger.warning("Failed to save assessment to DB: %s", exc)
        return None


def get_assessment(assessment_id: int) -> Optional[Dict[str, Any]]:
    """按 ID 查询评估记录。"""
    try:
        with get_db_session() as session:
            assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
            if assessment:
                return assessment.to_dict()
        return None
    except Exception as exc:
        logger.warning("Failed to query assessment %s: %s", assessment_id, exc)
        return None


def list_assessments(
    page: int = 1,
    per_page: int = 20,
    user_id: Optional[int] = None,
    risk_tier: Optional[str] = None,
) -> Tuple[list, int]:
    """分页查询评估历史。"""
    try:
        with get_db_session() as session:
            query = session.query(Assessment)
            if user_id is not None:
                query = query.filter(Assessment.user_id == user_id)
            if risk_tier:
                query = query.filter(Assessment.risk_tier == risk_tier)

            total = query.count()
            query = query.order_by(Assessment.created_at.desc())
            query = query.offset((page - 1) * per_page).limit(per_page)
            items = [a.to_dict() for a in query.all()]
        return items, total
    except Exception as exc:
        logger.warning("Failed to list assessments: %s", exc)
        return [], 0


def get_risk_rules() -> list:
    """获取当前风险规则列表。"""
    return RISK_RULES
