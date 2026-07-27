"""评估相关 API。"""
from __future__ import annotations

import logging
import uuid

from flask import jsonify, request

from app.api import api_bp
from app.services.audit_service import log_action
from app.services.risk_service import assess, get_assessment, list_assessments
from app.services.report_service import export_assessment_excel

logger = logging.getLogger("zhinong.api.assessments")


def _get_current_user_id() -> int:
    """从 JWT 提取用户 ID（简化版，后续统一 middleware）。"""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    if not token:
        return 0
    from app.services.auth_service import decode_access_token
    payload = decode_access_token(token)
    if payload:
        return int(payload["sub"])
    return 0


@api_bp.route("/assessments", methods=["POST"])
def create_assessment():
    """提交风险评估。
    POST body: {
        "disease_name": "...",
        "severity": "一般",
        "severity_idx": 1,
        "disease_confidence": 0.92,
        "severity_confidence": 0.85,
        "risk_percent": 65.0,
        "is_healthy": false,
        "crop": "玉米",
        "chemical_treatment": "代森锰锌 800 倍液",
        "input_filename": "...",
        "input_source": "upload"
    }
    """
    data = request.get_json(silent=True) or {}

    # 输入校验
    required_fields = ["disease_name", "severity", "severity_idx", "disease_confidence"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"ok": False, "error": f"缺少必填字段: {', '.join(missing)}"}), 400

    # 数值范围校验
    sev_idx = int(data.get("severity_idx", 0))
    if sev_idx < 0 or sev_idx > 2:
        return jsonify({"ok": False, "error": "severity_idx 必须为 0/1/2"}), 400
    conf = float(data.get("disease_confidence", 0))
    if conf < 0 or conf > 1:
        return jsonify({"ok": False, "error": "disease_confidence 必须在 0-1 之间"}), 400

    user_id = _get_current_user_id()
    case_id = str(uuid.uuid4().hex[:12])

    result = assess(
        disease_name=str(data["disease_name"]),
        severity_label=str(data.get("severity", "一般")),
        severity_idx=sev_idx,
        disease_confidence=conf,
        severity_confidence=float(data.get("severity_confidence", 0)),
        risk_percent=float(data.get("risk_percent", 50)),
        is_healthy=bool(data.get("is_healthy", False)),
        crop=str(data.get("crop", "")),
        chemical_treatment=str(data.get("chemical_treatment", "")),
        model_version=str(data.get("model_version", "")),
        user_id=user_id or None,
        input_filename=str(data.get("input_filename", "")),
        input_source=str(data.get("input_source", "api")),
        case_id=case_id,
    )

    log_action(
        action="create_assessment",
        resource_type="assessment",
        resource_id=case_id,
        user_id=user_id or None,
        ip_address=request.remote_addr,
        detail={"disease_name": data["disease_name"], "risk_tier": result.get("risk_tier")},
    )

    return jsonify({"ok": True, "case_id": case_id, "result": result}), 201


@api_bp.route("/assessments/<int:assessment_id>", methods=["GET"])
def get_assessment_by_id(assessment_id: int):
    """按 ID 查询评估结果。"""
    result = get_assessment(assessment_id)
    if not result:
        return jsonify({"ok": False, "error": "评估记录不存在"}), 404
    return jsonify({"ok": True, "assessment": result})


@api_bp.route("/assessments", methods=["GET"])
def list_assessments_api():
    """分页查询评估历史。
    Query params: page, per_page, risk_tier
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    risk_tier = request.args.get("risk_tier")

    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    items, total = list_assessments(
        page=page,
        per_page=per_page,
        risk_tier=risk_tier,
    )

    return jsonify({
        "ok": True,
        "assessments": items,
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@api_bp.route("/assessments/export", methods=["POST"])
def export_assessment():
    """导出评估报告为 Excel 文件。"""
    data = request.get_json(silent=True) or {}
    buf = export_assessment_excel(
        summary=data.get("summary", ""),
        disease_risk_percent=float(data.get("disease_risk_percent", 0)),
        severity=data.get("severity", ""),
        device=data.get("device", ""),
        probabilities=data.get("probabilities"),
        risk_tier=data.get("risk_tier", "低风险"),
        responsible_person=data.get("responsible_person", ""),
        deadline_days=data.get("deadline_days", ""),
        treatment_plan=data.get("treatment_plan"),
    )
    if buf is None:
        return jsonify({"ok": False, "error": "Excel 导出服务不可用（openpyxl 未安装）"}), 500

    log_action(
        action="export_excel",
        resource_type="assessment",
        user_id=_get_current_user_id() or None,
        ip_address=request.remote_addr,
        detail={"summary_len": len(data.get("summary", ""))},
    )

    from flask import send_file
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="assessment_report.xlsx",
    )
