"""LLM preprocessing pipeline: rule detect → (if needed) LLM correct → rule fallback."""

import asyncio
import json
import logging
import time

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.preprocess.rule_engine import rule_fallback, rule_preprocess
from app.utils.metrics import LLM_RULE_HIT_TOTAL, observe_llm

logger = logging.getLogger(__name__)


class LLMPreprocessOutput(BaseModel):
    corrected_text: str = Field(description="处理后的文本，含 CosyVoice2 标记")
    explanation: str = Field(description="处理说明")


# 默认 prompt：DB 无 active 记录时的兜底（保证不依赖 seed 也能跑）
DEFAULT_SYSTEM_PROMPT = """你是教学文本语音合成预处理助手。将输入文本转换为适合语音合成的内容。

规则：
1. 数学符号转中文读法：∂→偏导数，∫→积分，∑→求和，√→根号，∞→无穷大，≈→约等于
2. 化学式展开：H₂O→水，H₂SO₄→硫酸，NaCl→氯化钠
3. 多音字消歧：根据上下文选正确读音
4. 插入 CosyVoice2 标记：[laughter]笑声前，[breath]停顿处，<strong>内容</strong>强调

输出必须是 JSON：{"corrected_text": "...", "explanation": "..."}"""

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TEMPERATURE = 0.1

# Prompt 缓存 TTL：每 60s 重新读一次 DB，让 prompt 更新在 1 分钟内生效，
# 又不会每次 LLM 调用都打一次 DB 查询（课件合成是逐页调 LLM 的热路径）。
PROMPT_CACHE_TTL_S = 60.0


class LLMPipeline:
    _client: AsyncOpenAI | None = None
    # 内存缓存：{name: (content, model, temperature, fetched_at)}
    _prompt_cache: dict[str, tuple[str, str, float, float]] = {}

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            # timeout 必须显式指定：SDK 默认 600s，一次 hang 住的调用就能占满
            # worker 的并发槽（--concurrency=2 时两个请求即全站停摆）。
            # max_retries=0 是因为外层 process() 已有自己的重试循环，
            # 若保留 SDK 默认的 2 次重试，最坏请求数会变成 3 × 3 = 9。
            self._client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                timeout=settings.LLM_TIMEOUT_S,
                max_retries=0,
            )
        return self._client

    async def _get_prompt(self) -> tuple[str, str, float]:
        """从 DB 读 active prompt，带 60s 内存缓存。

        返回 (system_prompt, model, temperature)。DB 不可用或无可读记录时
        回退到默认值，保证预处理链路不因配置表缺失而中断。
        """
        cache_key = "llm_preprocess"
        cached = self._prompt_cache.get(cache_key)
        if cached and time.monotonic() - cached[3] < PROMPT_CACHE_TTL_S:
            return cached[0], cached[1], cached[2]

        content, model, temp = DEFAULT_SYSTEM_PROMPT, DEFAULT_MODEL, DEFAULT_TEMPERATURE
        try:
            from sqlalchemy import select

            from app.database import AsyncSessionLocal
            from app.models.prompt import PromptTemplate

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PromptTemplate)
                    .where(PromptTemplate.name == cache_key, PromptTemplate.is_active.is_(True))
                    .order_by(PromptTemplate.version.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    content, model, temp = row.content, row.model, row.temperature
        except Exception as e:
            # Prompt 读取失败不阻断合成：用默认值兜底，避免配置表故障拖垮主链路
            logger.warning(f"Failed to load prompt from DB, using default: {e}")

        self._prompt_cache[cache_key] = (content, model, temp, time.monotonic())
        return content, model, temp

    async def process(self, text: str) -> str:
        rule_result = rule_preprocess(text)
        LLM_RULE_HIT_TOTAL.labels(str(rule_result.needs_llm)).inc()
        if not rule_result.needs_llm:
            return text

        system_prompt, model, temperature = await self._get_prompt()

        last_error = None
        for attempt in range(settings.LLM_MAX_ATTEMPTS):
            is_last = attempt == settings.LLM_MAX_ATTEMPTS - 1
            try:
                async with observe_llm() as outcome:
                    response = await self._get_client().chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": (
                                f"处理以下教学文本，使之适合语音合成：\n\n"
                                f"原始文本：{text}\n\n"
                                f"检测到的内容：{', '.join(rule_result.detected_issues)}\n\n"
                                f"请返回 JSON。"
                            )},
                        ],
                        temperature=temperature,
                        response_format={"type": "json_object"},
                    )
                    content = response.choices[0].message.content
                    result = LLMPreprocessOutput.model_validate_json(content)
                    outcome["success"] = True
                logger.info(f"LLM preprocess OK (attempt {attempt + 1}): {result.explanation}")
                return result.corrected_text
            except (ValidationError, json.JSONDecodeError) as e:
                last_error = e
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
            except Exception as e:
                last_error = e
                logger.error(f"LLM attempt {attempt + 1} unexpected: {e}")

            # 指数退避：原实现连续重试无间隔，上游限流时会把 429 打得更狠。
            # 最后一次失败后无需再等，直接走兜底。
            if not is_last:
                await asyncio.sleep(
                    settings.LLM_RETRY_BACKOFF_BASE_S * (2**attempt)
                )

        # P2-9：LLM 三次重试全失败后的兜底是确定性规则替换（符号读音/
        # 常见化学式），不再是原样输出——符号至少能被正确读出来。
        logger.error(f"LLM all retries failed, using rule fallback: {last_error}")
        return rule_fallback(text)


llm_pipeline = LLMPipeline()
