import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin, UUIDMixin


class SynthesisTask(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "synthesis_tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    voice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("voices.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_processed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    output_audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output_format: Mapped[str] = mapped_column(String(10), default="wav")
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user = relationship("User", back_populates="tasks")
    voice = relationship("Voice", back_populates="tasks")
