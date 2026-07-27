"""风险规则 API。"""
from __future__ import annotations

from flask import jsonify

from app.api import api_bp
from app.services.risk_service import get_risk_rules


@api_bp.route("/risk-rules", methods=["GET"])
def list_risk_rules():
    """获取当前风险规则列表。"""
    rules = get_risk_rules()
    return jsonify({
        "ok": True,
        "rules": rules,
    })
