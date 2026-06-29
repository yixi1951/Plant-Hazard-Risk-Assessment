"""统一风险评分规则单元测试。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.risk_score import (
    compute_disease_risk_percent,
    is_healthy_label,
    risk_tier_from_prediction,
    risk_tier_short,
)


def test_healthy_label_detection():
    assert is_healthy_label("Tomato_healthy")
    assert is_healthy_label("玉米_健康")
    assert not is_healthy_label("Corn_Common_rust")


def test_multiclass_with_healthy_class():
    probs = [0.7, 0.2, 0.1]
    names = ["healthy", "rust", "blight"]
    risk, idx, conf = compute_disease_risk_percent(probs, names)
    assert idx == 0
    assert abs(risk - 30.0) < 1e-5


def test_multiclass_no_healthy():
    probs = [0.1, 0.6, 0.3]
    names = ["a", "b", "c"]
    risk, idx, conf = compute_disease_risk_percent(probs, names)
    assert idx == 1
    assert abs(risk - 60.0) < 1e-5


def test_risk_tier_matches_training_report_logic():
    assert "高" in risk_tier_from_prediction(2, 0.85)
    assert "中" in risk_tier_from_prediction(1, 0.75)
    assert risk_tier_short(0, 20) == "低"