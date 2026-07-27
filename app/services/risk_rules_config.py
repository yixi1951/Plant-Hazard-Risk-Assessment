"""
风险分级与阈值规则配置 v1
================================

3 个固定风险等级: 低 / 中 / 高

匹配规则（按优先级从高到低）:
  1. 严重程度索引 >= 2 (严重) 且 置信度 > 80% → 高风险
  2. 严重程度索引 >= 1 (一般) 且 置信度 > 70% → 中风险
  3. 健康且置信度 > 85% → 低风险
  4. 其余 → 低风险

每条规则绑定:
  - suggestion_template: SOP 文本模板
  - default_responsible: 默认责任人
  - default_deadline_days: 默认截止天数
"""
from __future__ import annotations

from typing import Dict, List

# ── SOP 模板 ────────────────────────────────────────────────

SOP_TEMPLATES = {
    "high": (
        '【紧急防控】病害「{disease_name}」已达到严重级别（风险评分 {risk_score:.0f} 分）。\n'
        '建议措施：\n'
        '1. 立即隔离重病株/区域，避免病害扩散至健康植株\n'
        '2. 首选药剂：{chemical_treatment}\n'
        '3. 24-48 小时内完成首次用药\n'
        '4. 每 3 天拍照复查病斑面积\n'
        '5. 若 7 天内无好转，携带病样咨询当地植保站或农技专家\n'
        '6. 记录用药名称、浓度与施药时间'
    ),
    "medium": (
        '【积极防控】病害「{disease_name}」已达到一般级别（风险评分 {risk_score:.0f} 分）。\n'
        '建议措施：\n'
        '1. 清除病叶，改善通风透光条件\n'
        '2. 推荐药剂：{chemical_treatment}\n'
        '3. 7 天内完成首次用药\n'
        '4. 第 7-10 天复查，病斑未缩小则复喷\n'
        '5. 加强田间巡检频率至每 3 天一次'
    ),
    "low": (
        '【常规管理】当前病害「{disease_name}」风险较低（风险评分 {risk_score:.0f} 分）。\n'
        '建议措施：\n'
        '1. 常规健康巡检，每 7 天检查叶背与嫩梢\n'
        '2. 保持田间通风透光，合理控湿\n'
        '3. 平衡施肥，增强植株抗病力\n'
        '4. 关注天气预报，雨后及时排水\n'
        '5. 发现异常斑点立即报告'
    ),
    "healthy": (
        '【健康状态】当前作物状态良好（风险评分 {risk_score:.0f} 分）。\n'
        '建议措施：\n'
        '1. 继续保持常规巡检（每 7 天一次）\n'
        '2. 预防性喷施保护性杀菌剂（可选）\n'
        '3. 维持田间通风透光\n'
        '4. 记录本次巡检结果'
    ),
}

# ── 阈值规则定义 ────────────────────────────────────────────

RISK_RULES: List[Dict] = [
    {
        "rule_key": "high_severity",
        "description": "严重病害 + 高置信度 → 高风险",
        "severity_idx_min": 2,
        "confidence_min": 0.80,
        "risk_score_min": 75.0,
        "risk_tier": "高",
        "tier_key": "high",
        "priority": 10,
        "default_responsible": "植保站技术员",
        "default_deadline_days": 1,
    },
    {
        "rule_key": "medium_severity",
        "description": "一般病害 + 中高置信度 → 中风险",
        "severity_idx_min": 1,
        "confidence_min": 0.70,
        "risk_score_min": 45.0,
        "risk_tier": "中",
        "tier_key": "medium",
        "priority": 20,
        "default_responsible": "田间管理人员",
        "default_deadline_days": 3,
    },
    {
        "rule_key": "low_severity",
        "description": "轻度病害或低置信度 → 低风险",
        "severity_idx_min": 0,
        "confidence_min": 0.0,
        "risk_score_min": 0.0,
        "risk_tier": "低",
        "tier_key": "low",
        "priority": 30,
        "default_responsible": "巡检人员",
        "default_deadline_days": 7,
    },
    {
        "rule_key": "healthy",
        "description": "健康状态 → 低风险（常规管理）",
        "severity_idx_min": 0,
        "confidence_min": 0.85,
        "risk_score_min": 0.0,
        "risk_tier": "低",
        "tier_key": "healthy",
        "priority": 5,
        "default_responsible": "巡检人员",
        "default_deadline_days": 7,
    },
]


def match_risk_rule(
    severity_idx: int,
    disease_confidence: float,
    risk_score: float,
    is_healthy: bool = False,
) -> Dict:
    """
    根据严重程度、置信度、风险分匹配第一条满足的规则。

    返回规则配置（含模板），无匹配时返回默认低风险规则。
    """
    # 健康优先匹配
    if is_healthy and disease_confidence >= 0.85:
        for rule in RISK_RULES:
            if rule["rule_key"] == "healthy":
                return dict(rule)

    # 按优先级排序后匹配
    sorted_rules = sorted(RISK_RULES, key=lambda r: r.get("priority", 99))
    for rule in sorted_rules:
        if rule["rule_key"] == "healthy":
            continue  # 已在上面处理
        if severity_idx >= rule["severity_idx_min"] and disease_confidence >= rule["confidence_min"]:
            return dict(rule)

    # 保底：低风险
    for rule in RISK_RULES:
        if rule["rule_key"] == "low_severity":
            return dict(rule)
    return dict(RISK_RULES[-1])


def get_sop_text(tier_key: str, **kwargs) -> str:
    """获取 SOP 文本模板并填充变量。"""
    template = SOP_TEMPLATES.get(tier_key, SOP_TEMPLATES["low"])
    return template.format(**kwargs)


# ── 短等级标记 ──────────────────────────────────────────────

def short_tier(risk_tier: str) -> str:
    mapping = {"高风险": "高", "中风险": "中", "低风险": "低"}
    return mapping.get(risk_tier, risk_tier[:1])
