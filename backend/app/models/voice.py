import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Voice(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "voices"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    reference_audio_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    consent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consents.id"), nullable=True
    )

    owner = relationship("User", back_populates="voices")
    consent = relationship("Consent", back_populates="voice", uselist=False)
    tasks = relationship("SynthesisTask", back_populates="voice")
