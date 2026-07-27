"""风险计算服务单元测试。"""
from __future__ import annotations

import pytest

from app.services.risk_service import assess
from app.services.risk_rules_config import (
    RISK_RULES,
    get_sop_text,
    match_risk_rule,
    short_tier,
)


class TestRiskRules:
    """风险规则匹配测试。"""

    def test_high_risk_match(self):
        """严重病害 + 高置信度 → 高风险"""
        rule = match_risk_rule(severity_idx=2, disease_confidence=0.90, risk_score=85, is_healthy=False)
        assert rule["risk_tier"] == "高"
        assert rule["rule_key"] == "high_severity"

    def test_medium_risk_match(self):
        """一般病害 + 中高置信度 → 中风险"""
        rule = match_risk_rule(severity_idx=1, disease_confidence=0.80, risk_score=60, is_healthy=False)
        assert rule["risk_tier"] == "中"
        assert rule["rule_key"] == "medium_severity"

    def test_low_risk_match(self):
        """轻度病害 → 低风险"""
        rule = match_risk_rule(severity_idx=0, disease_confidence=0.50, risk_score=20, is_healthy=False)
        assert rule["risk_tier"] == "低"

    def test_healthy_risk_match(self):
        """健康状态 + 高置信度 → 低风险（健康模板）"""
        rule = match_risk_rule(severity_idx=0, disease_confidence=0.95, risk_score=5, is_healthy=True)
        assert rule["risk_tier"] == "低"
        assert rule["rule_key"] == "healthy"

    def test_boundary_high_risk(self):
        """边界值：严重(2) + 置信度刚好 80% → 高风险"""
        rule = match_risk_rule(severity_idx=2, disease_confidence=0.80, risk_score=75, is_healthy=False)
        assert rule["risk_tier"] == "高"

    def test_boundary_below_high(self):
        """边界值：严重(2)但置信度 79% → 中风险（fallthrough）"""
        rule = match_risk_rule(severity_idx=2, disease_confidence=0.79, risk_score=70, is_healthy=False)
        # 置信度低于 80%，不应匹配 high_severity
        assert rule["rule_key"] != "high_severity"

    def test_severity_idx_validation(self):
        """严重程度索引越界时仍应有保底规则"""
        rule = match_risk_rule(severity_idx=99, disease_confidence=0.0, risk_score=0, is_healthy=False)
        assert rule["risk_tier"] in ("低",)

    def test_short_tier(self):
        assert short_tier("高风险") == "高"
        assert short_tier("中风险") == "中"
        assert short_tier("低风险") == "低"


class TestSOPTemplates:
    """SOP 文本模板测试。"""

    def test_high_sop(self):
        text = get_sop_text("high", disease_name="玉米大斑病", risk_score=90.0, chemical_treatment="代森锰锌")
        assert "紧急防控" in text
        assert "玉米大斑病" in text
        assert "代森锰锌" in text

    def test_medium_sop(self):
        text = get_sop_text("medium", disease_name="稻瘟病", risk_score=60.0, chemical_treatment="三环唑")
        assert "积极防控" in text
        assert "稻瘟病" in text

    def test_low_sop(self):
        text = get_sop_text("low", disease_name="苹果黑星病", risk_score=20.0, chemical_treatment="波尔多液")
        assert "常规管理" in text

    def test_healthy_sop(self):
        text = get_sop_text("healthy", disease_name="健康", risk_score=5.0, chemical_treatment="")
        assert "健康状态" in text


class TestAssessService:
    """风险评估服务集成测试。"""

    def test_assess_high_risk(self):
        result = assess(
            disease_name="玉米大斑病",
            severity_label="严重",
            severity_idx=2,
            disease_confidence=0.92,
            severity_confidence=0.88,
            risk_percent=85.0,
            is_healthy=False,
            crop="玉米",
            chemical_treatment="代森锰锌 800 倍液",
        )
        assert result["risk_tier"] == "高"
        assert result["risk_score"] == 85.0
        assert result["responsible_person"] == "植保站技术员"
        assert result["deadline_days"] == 1
        assert "紧急防控" in result["suggestion"]

    def test_assess_medium_risk(self):
        result = assess(
            disease_name="稻瘟病",
            severity_label="一般",
            severity_idx=1,
            disease_confidence=0.80,
            severity_confidence=0.75,
            risk_percent=55.0,
            is_healthy=False,
            crop="水稻",
            chemical_treatment="三环唑",
        )
        assert result["risk_tier"] == "中"
        assert result["responsible_person"] == "田间管理人员"
        assert result["deadline_days"] == 3

    def test_assess_low_risk(self):
        result = assess(
            disease_name="苹果黑星病",
            severity_label="健康",
            severity_idx=0,
            disease_confidence=0.50,
            severity_confidence=0.60,
            risk_percent=15.0,
            is_healthy=False,
            crop="苹果",
            chemical_treatment="",
        )
        assert result["risk_tier"] == "低"
        assert result["deadline_days"] == 7

    def test_assess_healthy(self):
        result = assess(
            disease_name="健康",
            severity_label="健康",
            severity_idx=0,
            disease_confidence=0.95,
            severity_confidence=0.90,
            risk_percent=5.0,
            is_healthy=True,
            crop="小麦",
            chemical_treatment="",
        )
        assert result["risk_tier"] == "低"
        assert "健康" in result["suggestion"]

    def test_risk_rules_count(self):
        """至少有 3 条风险规则。"""
        assert len(RISK_RULES) >= 3
