"""
病害防治方案引擎 — 根据识别结果生成个性化分步防治方案。
"""

from scripts.utils import DISEASE_DETAILS, get_crop_type
from scripts.disease_catalog import NAME_ALIASES, get_treatment_extended

PHYTOSANITARY_NOTICE = (
    "用药提示：请严格按标签浓度与安全间隔期施药；遵守当地禁限用农药规定；"
    "穿戴口罩、手套与护目镜；避免顺风飘移与水源污染；采食前务必满足间隔期，"
    "不确定时咨询当地植保站或持证农技员。"
)

_SEVERITY_MULTIPLIERS = {
    "健康": {"urgency": "低", "step_boost": 0, "recheck_days": [14, 30], "action_prefix": "预防性"},
    "一般": {"urgency": "中", "step_boost": 1, "recheck_days": [3, 7, 14], "action_prefix": "积极"},
    "严重": {"urgency": "高", "step_boost": 2, "recheck_days": [1, 3, 7, 14], "action_prefix": "紧急"},
}


def resolve_disease_id(disease_name, disease_idx=None):
    """将模型输出的病害名称映射到知识库 ID。"""
    if disease_idx is not None and disease_idx in DISEASE_DETAILS:
        return disease_idx

    if not disease_name:
        return None

    import re
    normalized = re.sub(r"\s+", " ", str(disease_name).replace("_", " ").replace("-", " ").strip().lower())
    if normalized in NAME_ALIASES:
        return NAME_ALIASES[normalized]

    for alias, did in NAME_ALIASES.items():
        if alias in normalized or normalized in alias:
            return did

    for did, info in DISEASE_DETAILS.items():
        if info["name"] in disease_name or disease_name in info["name"]:
            return did

    return None


def _is_healthy(disease_id, disease_name):
    if disease_id is not None:
        info = DISEASE_DETAILS.get(disease_id, {})
        if "健康" in info.get("name", ""):
            return True
    name = str(disease_name or "").lower()
    return any(k in name for k in ("healthy", "health", "健康"))


def _build_actionable_summary(base_info, extended, severity, is_healthy, crop):
    """生成更具体的田间执行摘要（非套话）。"""
    if is_healthy:
        steps = extended.get("steps") or []
        patrol = next((s for s in steps if "巡检" in s.get("action", "")), None)
        patrol_txt = patrol["action"] if patrol else "每 7 天巡检叶背与嫩梢"
        return (
            f"【{crop}·健康】{patrol_txt}。"
            f"预防：{(extended.get('prevention') or ['保持通风'])[0]}。"
            f"{base_info.get('suggestion', '')}"
        )

    chem = (extended.get("chemical") or [base_info.get("suggestion")])[0]
    first_step = (extended.get("steps") or [{}])[0]
    first_action = first_step.get("action") or base_info.get("suggestion", "清除病叶并用药")
    timing = first_step.get("timing") or "24h 内"

    if severity == "严重":
        return (
            f"【紧急·{crop}】{timing}：{first_action}。"
            f"首选药剂：{chem}。"
            f"3 天内复查病斑面积；若扩展>20%，立即换药复喷并隔离重病株。"
        )
    if severity == "一般":
        return (
            f"【{crop}·一般】{timing}：{first_action}。"
            f"推荐：{chem}；7 天拍照复查，病斑未缩小则第 10–14 天复喷。"
        )
    return base_info.get("suggestion") or first_action


def build_treatment_plan(disease_name, severity="一般", disease_idx=None,
                         risk_percent=50.0, confidence=0.9, mc_std=None):
    """生成个性化防治方案，包含分步操作、复查时间线、成本估算等。"""
    disease_id = resolve_disease_id(disease_name, disease_idx)
    base_info = DISEASE_DETAILS.get(disease_id, {
        "name": disease_name or "未知病害",
        "description": "该病害暂未收录详细防治方案，建议结合当地农技指导。",
        "suggestion": "清除病叶，改善通风，携带病样咨询当地植保站。",
    }) if disease_id is not None else {
        "name": disease_name or "未知病害",
        "description": "该病害暂未收录详细防治方案，建议结合当地农技指导。",
        "suggestion": "清除病叶，改善通风，携带病样咨询当地植保站。",
    }

    extended = get_treatment_extended(disease_id) if disease_id is not None else None
    if not extended:
        extended = {
            "symptoms": [base_info.get("description", "")],
            "causes": ["具体病因需结合田间调查"],
            "prevention": ["加强田间管理", "选用抗病品种", "清除病残体"],
            "chemical": [base_info.get("suggestion", "咨询农技人员")],
            "organic": ["改善通风透光", "平衡施肥"],
            "steps": [
                {"phase": "立即", "action": base_info.get("suggestion", "采取常规防治"), "timing": "发现后"},
                {"phase": "复查", "action": "观察病情变化，评估防治效果", "timing": "7 天后"},
            ],
            "cost": "约 20–50 元/亩",
            "duration": "2–4 周",
            "season_tips": "根据当地气候和作物生育期调整防治时机。",
        }

    sev_cfg = _SEVERITY_MULTIPLIERS.get(severity, _SEVERITY_MULTIPLIERS["一般"])
    is_healthy = _is_healthy(disease_id, disease_name)
    crop = get_crop_type(disease_id if disease_id is not None else disease_name)

    steps = list(extended.get("steps", []))
    if severity == "严重" and not is_healthy:
        steps.insert(0, {
            "phase": "紧急隔离",
            "action": "立即隔离重病株/区域，避免孢子或害虫扩散至健康植株",
            "timing": "立即执行",
        })
        steps.append({
            "phase": "专家会诊",
            "action": "若 7 天内无好转，携带病样咨询当地植保站或农技专家",
            "timing": "7 天后",
        })
    elif severity == "一般" and not is_healthy and len(steps) > 4:
        steps = steps[:4] + [s for s in steps if s.get("phase") in ("复查", "第2次用药")][:2]

    recheck_timeline = []
    for days in sev_cfg["recheck_days"]:
        recheck_timeline.append({
            "day": days,
            "label": f"第 {days} 天复查",
            "action": (
                "同一叶片拍照对比病斑面积；记录用药名称与浓度"
                if not is_healthy else "常规健康巡检，关注蚜虫与湿度"
            ),
            "priority": "高" if days <= 3 and severity == "严重" else "中",
        })

    confidence_level = "高"
    if confidence < 0.7:
        confidence_level = "低"
    elif confidence < 0.85:
        confidence_level = "中"
    uncertainty_note = None
    if mc_std is not None and mc_std > 8:
        uncertainty_note = f"模型不确定性较高（std={mc_std:.1f}%），建议人工复核后再大规模用药。"

    urgency_score = risk_percent
    if severity == "严重":
        urgency_score = min(100, risk_percent + 15)
    elif severity == "健康" or is_healthy:
        urgency_score = max(0, risk_percent - 20)

    actionable = _build_actionable_summary(base_info, extended, severity, is_healthy, crop)

    return {
        "disease_id": disease_id,
        "disease_name": base_info["name"],
        "crop": crop,
        "severity": severity,
        "is_healthy": is_healthy,
        "urgency": sev_cfg["urgency"],
        "urgency_score": round(urgency_score, 1),
        "confidence_level": confidence_level,
        "uncertainty_note": uncertainty_note,
        "description": base_info.get("description", ""),
        "quick_suggestion": actionable,
        "actionable_summary": actionable,
        "symptoms": extended.get("symptoms", []),
        "causes": extended.get("causes", []),
        "prevention": extended.get("prevention", []),
        "chemical_treatment": extended.get("chemical", []),
        "organic_treatment": extended.get("organic", []),
        "treatment_steps": steps,
        "estimated_cost": extended.get("cost", "请咨询当地农资店"),
        "treatment_duration": extended.get("duration", "2–4 周"),
        "season_tips": extended.get("season_tips", ""),
        "recheck_timeline": recheck_timeline,
        "innovation_tags": _build_innovation_tags(severity, is_healthy, confidence, mc_std),
        "phytosanitary_notice": PHYTOSANITARY_NOTICE,
    }


def _build_innovation_tags(severity, is_healthy, confidence, mc_std):
    tags = ["AI 多任务联合诊断", "严重程度自适应方案", "可执行用药剂量建议"]
    if not is_healthy:
        tags.append("分步防治路线图")
        tags.append("智能复查时间线")
    if mc_std is not None:
        tags.append("MC Dropout 不确定性量化")
    if confidence >= 0.9:
        tags.append("高置信度快速决策")
    if severity == "严重":
        tags.append("紧急处置优先策略")
    return tags


def enrich_disease_list_entry(disease_id, info):
    """为 API 病害列表返回完整防治信息。"""
    extended = get_treatment_extended(disease_id) or {}
    return {
        "id": disease_id,
        "name": info["name"],
        "crop": get_crop_type(disease_id),
        "description": info["description"],
        "suggestion": info["suggestion"],
        "symptoms": extended.get("symptoms", []),
        "prevention": extended.get("prevention", []),
        "chemical_treatment": extended.get("chemical", []),
        "organic_treatment": extended.get("organic", []),
        "estimated_cost": extended.get("cost", ""),
        "treatment_duration": extended.get("duration", ""),
        "phytosanitary_notice": PHYTOSANITARY_NOTICE,
    }