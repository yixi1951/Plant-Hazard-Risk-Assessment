"""统一病害风险评分：训练报告、Web 推理、批量导出共用同一套规则。"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

SEVERITY_LABELS = ("健康", "一般", "严重")


def is_healthy_label(name: str) -> bool:
    n = str(name).replace("_", " ").replace("-", " ").lower()
    return any(k in n for k in ("healthy", "health", "normal", "无病", "健康"))


def compute_disease_risk_percent(
    disease_probs: Sequence[float],
    class_names: Optional[Sequence[str]] = None,
    *,
    single_logit_prob: Optional[float] = None,
) -> Tuple[float, int, float]:
    """
    返回 (risk_percent 0–100, argmax_idx, top_confidence)。

    - 单 logit（sigmoid）: risk = prob * 100
    - 多类: 若有健康类，risk = (1 - sum(healthy_probs)) * 100；否则 risk = top_conf
    """
    if single_logit_prob is not None:
        p = float(single_logit_prob)
        return max(0.0, min(100.0, p * 100.0)), 0, p

    if not disease_probs:
        return 0.0, 0, 0.0

    probs = [float(x) for x in disease_probs]
    top_idx = max(range(len(probs)), key=lambda i: probs[i])
    top_conf = probs[top_idx]
    names = list(class_names or [])

    healthy_indices = [i for i, name in enumerate(names) if is_healthy_label(name)]
    if healthy_indices:
        healthy_prob = sum(probs[i] for i in healthy_indices if i < len(probs))
        risk = (1.0 - healthy_prob) * 100.0
    else:
        risk = top_conf * 100.0

    return max(0.0, min(100.0, risk)), top_idx, top_conf


def risk_tier_from_prediction(
    severity_idx: int,
    disease_confidence: float,
    *,
    severity_confidence: Optional[float] = None,
) -> str:
    """
    与 risk_assessment 报告生成、前端展示对齐的分档文案。
    severity_idx: 0=健康, 1=一般, 2=严重
    disease_confidence: 0–1（top 类概率或等效）
    """
    conf_pct = disease_confidence * 100.0
    if severity_idx >= 2 and conf_pct > 80:
        return "高风险（需紧急防控）"
    if severity_idx >= 1 and conf_pct > 70:
        return "中风险（需密切监测）"
    if severity_confidence is not None and severity_idx == 0 and severity_confidence > 0.85:
        return "低风险（常规管理）"
    return "低风险（常规管理）"


def risk_tier_short(severity_idx: int, risk_percent: float) -> str:
    """Web/API 简短等级。"""
    if severity_idx >= 2 or risk_percent >= 75:
        return "高"
    if severity_idx >= 1 or risk_percent >= 45:
        return "中"
    return "低"