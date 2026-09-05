"""Prompt 模板模型：让 LLM 的 system prompt 与模型参数脱离代码、可热更新。

背景：生产级 AI 应用要求「Prompt 不能写死在代码里」——AI 产品的迭代频率
是「一天调 5 次 Prompt」，每次都改代码 + 发版会让迭代跑不起来。本表把
system prompt、模型名、temperature 存进数据库，切换 active 版本无需重新
发版部署。

设计取舍（极简单行，而非多版本并存）：
    当前只有一条 LLM 预处理链，不需要「多版本灰度 + 回滚」的完整体系，
    故用「一条 is_active 行 + 内存缓存」即可满足「不改代码换 Prompt」的
    核心诉求。将来需要 A/B 或回滚时再扩展 version 列即可。
"""

from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PromptTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "prompt_templates"

    # 用途标识，如 "llm_preprocess"（后续可扩展其他场景的 prompt）
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # 版本号（人类可读，便于归因时追溯「当时用的哪版 prompt」）
    version: Mapped[int] = mapped_column(default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False, default="deepseek-chat")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
