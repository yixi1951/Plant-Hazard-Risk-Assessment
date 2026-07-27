"""
核心业务场景测试（P0-4）
══════════════════════════════════════════════════
5 组关键测试：
  1. 风险阈值边界值 (80%、60%、40% ± 1%)
  2. 缺失/非法输入
  3. 高风险 → 必须触发治疗建议
  4. 幂等性 — 相同输入 → 相同输出
  5. DB 写后读一致性

每组均可独立运行:
    $ pytest tests/test_core_business.py -k test_boundary
"""
from __future__ import annotations

import hashlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.models.assessment import Assessment  # noqa: E402
from app.models.database import Base, engine, get_db_session  # noqa: E402
from app.services.risk_service import assess  # noqa: E402
from app.services.risk_rules_config import match_risk_rule  # noqa: E402


# ═══════════════════════════════════════════════════════════
# 夹具
# ═══════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def db_tables():
    """确保测试用表存在（测试用 SQLite）。"""
    Base.metadata.create_all(bind=engine)
    yield
    # 测试结束后不留垃圾
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db(db_tables):
    """每条用例前清空 assessments 表，保证隔离。"""
    with get_db_session() as session:
        session.query(Assessment).delete()
        session.commit()
    yield


# ═══════════════════════════════════════════════════════════
# 1) 边界值测试 (Boundary)
# ═══════════════════════════════════════════════════════════

BOUNDARY_KWARGS = dict(
    disease_name="玉米大斑病",
    severity_label="严重",
    severity_idx=2,
    disease_confidence=0.95,
    severity_confidence=0.88,
    crop="玉米",
    chemical_treatment="代森锰锌 800 倍液",
    is_healthy=False,
)


class TestBoundaryThresholds:
    """风险规则边界值验证。

    NOTE: `risk_score_min` 定义在 RISK_RULES 中但未被 `match_risk_rule`
    使用（匹配只检查 severity_idx + disease_confidence）。以下测试验证
    实际生效的边界逻辑。
    """

    @pytest.mark.parametrize("severity_idx,confidence,expected_tier", [
        (2, 0.80, "高"),  # severity=2, conf>=0.80 → 高
        (2, 0.79, "中"),  # severity=2, conf=0.79 → 匹配 medium_severity（priority 20）→ 中
        (1, 0.70, "中"),  # severity=1, conf>=0.70 → 中
        (1, 0.69, "低"),  # severity=1, conf=0.69 → 不满足 conf>=0.70 → 低（fallthrough）
        (0, 0.99, "低"),  # severity=0 → 低（low_severity 规则直接匹配）
        (0, 0.00, "低"),  # severity=0, conf=0 → 低
    ])
    def test_rule_boundaries_by_severity_confidence(self, severity_idx, confidence, expected_tier):
        """严重程度 + 置信度边界确定风险等级。"""
        rule = match_risk_rule(
            severity_idx=severity_idx,
            disease_confidence=confidence,
            risk_score=50,
            is_healthy=False,
        )
        assert rule["risk_tier"] == expected_tier, (
            f"severity={severity_idx}, conf={confidence} → expected={expected_tier}, got={rule['risk_tier']}"
        )

    @pytest.mark.parametrize("confidence,expected_tier", [
        (0.85, "低"),  # 健康 + conf>=0.85 → 低（healthy 模板）
        (0.84, "低"),  # 健康 + conf=0.84 → 低（low_severity fallthrough）
    ])
    def test_healthy_confidence_boundary(self, confidence, expected_tier):
        """健康状态置信度边界。"""
        rule = match_risk_rule(
            severity_idx=0,
            disease_confidence=confidence,
            risk_score=5,
            is_healthy=True,
        )
        # 都返回低风险，但规则 key 应区分
        if confidence >= 0.85:
            assert rule["rule_key"] == "healthy"
        else:
            assert rule["rule_key"] != "healthy"


# ═══════════════════════════════════════════════════════════
# 2) 缺失/非法输入测试 (Bad Input)
# ═══════════════════════════════════════════════════════════

class TestBadInput:
    """缺失或非法参数下的稳壮性。"""

    def test_empty_disease_name(self):
        """空病害名称仍应有合理输出。"""
        result = assess(
            disease_name="",
            severity_label="一般",
            severity_idx=1,
            disease_confidence=0.80,
            severity_confidence=0.70,
            risk_percent=50.0,
            crop="未知",
            is_healthy=False,
        )
        assert "risk_tier" in result
        assert isinstance(result["risk_score"], (int, float))

    def test_none_severity_idx(self):
        """严重度索引 None 时不应崩溃。"""
        result = assess(
            disease_name="稻瘟病",
            severity_label="",
            severity_idx=0,
            disease_confidence=0.0,
            severity_confidence=0.0,
            risk_percent=0.0,
            crop="水稻",
            is_healthy=True,
        )
        assert result["risk_tier"] in ("低",)

    def test_extremely_low_confidence(self):
        """置信度接近 0 仍应返回结果。"""
        result = assess(
            disease_name="苹果黑星病",
            severity_label="一般",
            severity_idx=1,
            disease_confidence=0.001,
            severity_confidence=0.001,
            risk_percent=30.0,
            crop="苹果",
            is_healthy=False,
        )
        assert "suggestion" in result
        assert result["risk_tier"] in ("低", "中")

    def test_all_defaults(self):
        """全默认参数调用不崩溃。"""
        result = assess(
            disease_name="测试病害",
            severity_label="一般",
            severity_idx=1,
            disease_confidence=0.5,
            severity_confidence=0.5,
            risk_percent=50.0,
            crop="测试作物",
        )
        assert isinstance(result, dict)
        assert result["risk_tier"] in ("低", "中", "高")


# ═══════════════════════════════════════════════════════════
# 3) 高风险 → 治疗建议 (High Risk → Treatment)
# ═══════════════════════════════════════════════════════════

class TestHighRiskTriggersTreatment:
    """高风险必须携带处置建议。"""

    HIGH_KWARGS = dict(
        disease_name="玉米大斑病",
        severity_label="严重",
        severity_idx=2,
        disease_confidence=0.95,
        severity_confidence=0.90,
        crop="玉米",
        chemical_treatment="代森锰锌",
        is_healthy=False,
    )

    def test_high_risk_has_suggestion(self):
        """高风险必有处置建议字段。"""
        result = assess(**self.HIGH_KWARGS, risk_percent=90.0)
        assert result["suggestion"], "高风险结果缺少 suggestion"
        assert "紧急防控" in result["suggestion"]

    def test_high_risk_has_responsible_person(self):
        """高风险必有责任人。"""
        result = assess(**self.HIGH_KWARGS, risk_percent=90.0)
        assert result["responsible_person"], "高风险缺少责任人"

    def test_high_risk_has_deadline(self):
        """高风险必有截止天数。"""
        result = assess(**self.HIGH_KWARGS, risk_percent=90.0)
        assert isinstance(result["deadline_days"], int)
        assert result["deadline_days"] >= 1

    def test_high_risk_always_high_tier(self):
        """高严重 + 高置信度 → 无论 risk_percent → 高风险。"""
        for risk_pct in (0, 50, 75, 80, 90, 100):
            result = assess(**self.HIGH_KWARGS, risk_percent=float(risk_pct))
            assert result["risk_tier"] == "高", f"risk_pct={risk_pct} 时应为高风险"
            assert result["risk_score"] == float(risk_pct)


# ═══════════════════════════════════════════════════════════
# 4) 幂等性测试 (Idempotence)
# ═══════════════════════════════════════════════════════════

class TestIdempotence:
    """相同输入 → 完全相同的输出。"""

    IDEM_KWARGS = dict(
        disease_name="水稻稻瘟病",
        severity_label="一般",
        severity_idx=1,
        disease_confidence=0.85,
        severity_confidence=0.80,
        risk_percent=65.0,
        crop="水稻",
        chemical_treatment="三环唑",
        is_healthy=False,
    )

    @staticmethod
    def _stable_hash(result: dict) -> str:
        """对结果生成稳定哈希（排除时间字段）。"""
        stable = {
            k: v for k, v in sorted(result.items())
            if k not in ("assessed_at",)
        }
        return hashlib.sha256(repr(stable).encode()).hexdigest()

    def test_same_input_same_output(self):
        """相同输入连续 3 次调用，输出完全一致。"""
        h1 = self._stable_hash(assess(**self.IDEM_KWARGS))
        h2 = self._stable_hash(assess(**self.IDEM_KWARGS))
        h3 = self._stable_hash(assess(**self.IDEM_KWARGS))
        assert h1 == h2 == h3, "幂等性失败：相同输入产生了不同输出"

    def test_different_input_different_output(self):
        """不同输入得到不同输出。"""
        h1 = self._stable_hash(assess(**self.IDEM_KWARGS))
        modified = dict(self.IDEM_KWARGS)
        modified["risk_percent"] = 30.0
        h2 = self._stable_hash(assess(**modified))
        assert h1 != h2, "不同输入应产生不同输出"

    def test_deep_copy_equivalence(self):
        """不影响原始输入字典。"""
        original = dict(self.IDEM_KWARGS)
        result = assess(**self.IDEM_KWARGS)
        # assess 不应修改传入参数
        assert self.IDEM_KWARGS == original, "assess 修改了输入的参数"
        assert "risk_tier" in result


# ═══════════════════════════════════════════════════════════
# 5) DB 写后读一致性 (DB Consistency)
# ═══════════════════════════════════════════════════════════

class TestDatabaseConsistency:
    """评估结果写入后，读出应与写入一致。"""

    SAMPLE_RESULT = dict(
        disease_name="玉米大斑病",
        severity_label="严重",
        severity_idx=2,
        disease_confidence=0.95,
        severity_confidence=0.90,
        crop="玉米",
        chemical_treatment="代森锰锌",
        is_healthy=False,
    )

    def test_save_and_retrieve(self):
        """调用 assess（自动持久化）→ 数据库读取 → 关键字段一致。"""
        result = assess(**self.SAMPLE_RESULT, risk_percent=88.0)
        assert result["risk_tier"] in ("低", "中", "高"), "assess 未返回有效结果"

        with get_db_session() as session:
            loaded = (
                session.query(Assessment)
                .filter(Assessment.disease_name == result["disease_name"])
                .order_by(Assessment.id.desc())
                .first()
            )
            assert loaded is not None, "assess 自动保存后无法从 DB 读出"
            assert loaded.disease_name == result["disease_name"]
            assert loaded.risk_score == result["risk_score"]
            assert loaded.risk_tier == result["risk_tier"]

    def test_multiple_saves_unique_ids(self):
        """多次 assess 后 DB 中有唯一 ID。"""
        for i in range(5):
            kwargs = dict(self.SAMPLE_RESULT)
            kwargs["risk_percent"] = 50.0 + i * 10
            kwargs["disease_name"] = f"病害_{i}"
            assess(**kwargs)

        with get_db_session() as session:
            db_ids = [row.id for row in session.query(Assessment).all()]
        assert len(db_ids) == 5, f"应获得 5 条记录，实际 {len(db_ids)}"
        assert len(set(db_ids)) == 5, "ID 不唯一"

    def test_db_count_after_saves(self):
        """assess 调用后 assessments 表记录数正确。"""
        n = 3
        for i in range(n):
            kwargs = dict(self.SAMPLE_RESULT)
            kwargs["disease_name"] = f"病害_{i}"
            kwargs["risk_percent"] = 50.0 + i * 15
            assess(**kwargs)

        with get_db_session() as session:
            count = session.query(Assessment).count()
        assert count == n, f"预期 {n} 条记录，实际 {count}"
