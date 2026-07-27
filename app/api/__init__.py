from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

from app.api import assessments, auth, risk_rules, health, audit_logs  # noqa: F401, E402
