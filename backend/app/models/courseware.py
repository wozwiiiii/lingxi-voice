import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin, UUIDMixin


class CoursewareProject(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "courseware_projects"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_pptx_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    slides_count: Mapped[int] = mapped_column(Integer, default=0)
    voice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("voices.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    output_zip_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 项目级错误聚合：存在任一 provider_unavailable/timeout 页 →
    # provider_unavailable（值得重试）；否则 content_error。
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 最近更新时间：onupdate 自动刷新，供「卡死任务收敛」判断项目是否僵死
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    slides = relationship("CoursewareSlide", back_populates="project",
                          cascade="all, delete-orphan")
    voice = relationship("Voice")  # intentionally one-way: Voice is a shared resource
    user = relationship("User")


class CoursewareSlide(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "courseware_slides"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courseware_projects.id"),
        nullable=False, index=True
    )
    slide_index: Mapped[int] = mapped_column(Integer, nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_processed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("voices.id"), nullable=True
    )
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    emotion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    instruction: Mapped[str | None] = mapped_column(String(200), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synthesis_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("synthesis_tasks.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # 失败时写入（见 utils/error_codes.py）：区分「重试有用」与「重试没用」
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    project = relationship("CoursewareProject", back_populates="slides")
    voice = relationship("Voice")  # intentionally one-way: Voice is a shared resource
    synthesis_task = relationship("SynthesisTask")
