from pydantic import BaseModel


class VoiceResponse(BaseModel):
    id: str
    name: str
    type: str
    provider: str
    is_public: bool
    description: str | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_voice(cls, v):
        return cls(
            id=str(v.id), name=v.name, type=v.type,
            provider=v.provider, is_public=v.is_public,
            description=v.description,
        )
