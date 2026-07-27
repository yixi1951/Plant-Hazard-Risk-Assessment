"""风险规则与版本化管理。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class RiskRule(Base):
    """风险分级规则配置（当前生效的规则）。"""
    __tablename__ = "risk_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 规则标识
    rule_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # 阈值配置
    severity_idx_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 最低严重程度索引
    confidence_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)    # 最低置信度 (0-1)
    risk_score_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)    # 最低风险分 (0-100)

    # 输出
    risk_tier: Mapped[str] = mapped_column(String(16), nullable=False)  # 低 / 中 / 高
    suggestion_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_responsible: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    default_deadline_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 优先级 (数值越小优先级越高，用于规则匹配顺序)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_key": self.rule_key,
            "description": self.description,
            "severity_idx_min": self.severity_idx_min,
            "confidence_min": self.confidence_min,
            "risk_score_min": self.risk_score_min,
            "risk_tier": self.risk_tier,
            "suggestion_template": self.suggestion_template,
            "default_responsible": self.default_responsible,
            "default_deadline_days": self.default_deadline_days,
            "priority": self.priority,
            "is_active": self.is_active,
        }


class RiskRuleVersion(Base):
    """风险规则版本历史（审计追溯）。"""
    __tablename__ = "risk_rule_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)

    # 变更前快照
    previous_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # 变更后快照
    new_config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON

    # 变更人
    changed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
