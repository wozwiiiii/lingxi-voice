"""Prompt 模板的 seed 与读取服务。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt import PromptTemplate
from app.preprocess.llm_pipeline import (
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
)

PROMPT_NAME_PREPROCESS = "llm_preprocess"


async def seed_default_prompt(db: AsyncSession) -> None:
    """幂等插入默认预处理 prompt（不存在时才建）。

    与 seed_preset_voices / seed_courseware_presets 同一模式：按 name 查重，
    存在则跳过。这样升级部署后不会覆盖运维已调整的 prompt。
    """
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.name == PROMPT_NAME_PREPROCESS)
    )
    if result.scalar_one_or_none() is not None:
        return
    db.add(
        PromptTemplate(
            name=PROMPT_NAME_PREPROCESS,
            version=1,
            content=DEFAULT_SYSTEM_PROMPT,
            model=DEFAULT_MODEL,
            temperature=DEFAULT_TEMPERATURE,
            is_active=True,
        )
    )
