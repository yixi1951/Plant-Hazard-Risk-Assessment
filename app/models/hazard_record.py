"""灾害记录模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class HazardRecord(Base):
    """灾害/病害事件记录。"""
    __tablename__ = "hazard_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # 灾害基本信息
    crop: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    disease_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # 地理位置/区域
    region: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    field_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 损失估算
    affected_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 亩
    estimated_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 元

    # 处置记录
    action_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(16), default="pending")  # pending / resolved / monitoring

    reported_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
