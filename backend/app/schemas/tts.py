from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice_id: str
    speed: float = Field(default=1.0, ge=0.5, le=3.0)
    pitch: float = Field(default=0.0, ge=-12.0, le=12.0)
    volume: float = Field(default=1.0, ge=0.1, le=2.0)
    emotion: str | None = None
    style: str | None = None
    language: str = "zh"
    instruction: str | None = Field(default=None, max_length=200)
    output_format: str = "wav"
    stream: bool = False


class TTSResponse(BaseModel):
    task_id: str
    status: str
    audio_url: str | None = None
    cached: bool = False
    provider_used: str | None = None
    duration_ms: int | None = None
    processed_text: str | None = None
