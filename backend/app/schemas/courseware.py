from pydantic import BaseModel, Field, field_validator


class SlideUpdate(BaseModel):
    edited_text: str | None = None
    voice_id: str | None = None
    speed: float | None = None
    emotion: str | None = None
    style: str | None = None
    instruction: str | None = None


class BulkSettingsUpdate(BaseModel):
    voice_id: str | None = None
    speed: float | None = None
    emotion: str | None = None
    style: str | None = None


class CoursewareProjectResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    slides_count: int
    status: str
    progress: dict | None = None
    voice_id: str | None = None
    created_at: str

    model_config = {"from_attributes": True}

    @field_validator("id", "voice_id", "created_at", mode="before")
    @classmethod
    def coerce_to_str(cls, v):
        return str(v) if v is not None else None


class CoursewareSlideResponse(BaseModel):
    id: str
    slide_index: int
    original_text: str | None = None
    edited_text: str | None = None
    voice_id: str | None = None
    speed: float
    emotion: str | None = None
    style: str | None = None
    audio_path: str | None = None
    audio_duration_ms: int | None = None
    status: str

    model_config = {"from_attributes": True}

    @field_validator("id", "voice_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else None


class CoursewareListResponse(BaseModel):
    projects: list[CoursewareProjectResponse]
    total: int


class SynthesizeResponse(BaseModel):
    project_id: str
    status: str
    message: str
    progress_ticket: str | None = None
