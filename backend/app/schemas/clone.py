from pydantic import BaseModel, Field


class CloneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    purpose: str = Field(min_length=5, max_length=500, description="声音用途说明（授权声明）")
