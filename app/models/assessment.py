"""评估记录模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Assessment(Base):
    """单次病害评估结果。"""
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 评估主体信息
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)

    # 输入
    input_filename: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    input_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # upload / url / batch

    # 推理结果
    disease_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    disease_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    crop: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # 健康 / 一般 / 严重
    severity_idx: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 风险评分
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0–100
    risk_tier: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # 低 / 中 / 高
    disease_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    severity_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 处置建议
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responsible_person: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    deadline_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 报告引用
    report_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # 元数据
    demo: Mapped[bool] = mapped_column(default=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "case_id": self.case_id,
            "input_filename": self.input_filename,
            "input_source": self.input_source,
            "disease_name": self.disease_name,
            "disease_id": self.disease_id,
            "crop": self.crop,
            "severity": self.severity,
            "severity_idx": self.severity_idx,
            "risk_score": self.risk_score,
            "risk_tier": self.risk_tier,
            "disease_confidence": self.disease_confidence,
            "severity_confidence": self.severity_confidence,
            "suggestion": self.suggestion,
            "responsible_person": self.responsible_person,
            "deadline_days": self.deadline_days,
            "report_path": self.report_path,
            "demo": self.demo,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
