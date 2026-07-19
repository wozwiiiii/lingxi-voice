"""LLM preprocessing pipeline: rule detect → (if needed) LLM correct → rule fallback."""

import json
import logging

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.preprocess.rule_engine import PreprocessResult, rule_preprocess

logger = logging.getLogger(__name__)


class LLMPreprocessOutput(BaseModel):
    corrected_text: str = Field(description="处理后的文本，含 CosyVoice2 标记")
    explanation: str = Field(description="处理说明")


SYSTEM_PROMPT = """你是教学文本语音合成预处理助手。将输入文本转换为适合语音合成的内容。

规则：
1. 数学符号转中文读法：∂→偏导数，∫→积分，∑→求和，√→根号，∞→无穷大，≈→约等于
2. 化学式展开：H₂O→水，H₂SO₄→硫酸，NaCl→氯化钠
3. 多音字消歧：根据上下文选正确读音
4. 插入 CosyVoice2 标记：[laughter]笑声前，[breath]停顿处，<strong>内容</strong>强调

输出必须是 JSON：{"corrected_text": "...", "explanation": "..."}"""


class LLMPipeline:
    _client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
        return self._client

    async def process(self, text: str) -> str:
        rule_result = rule_preprocess(text)
        if not rule_result.needs_llm:
            return text

        last_error = None
        for attempt in range(3):
            try:
                response = await self._get_client().chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": (
                            f"处理以下教学文本，使之适合语音合成：\n\n"
                            f"原始文本：{text}\n\n"
                            f"检测到的内容：{', '.join(rule_result.detected_issues)}\n\n"
                            f"请返回 JSON。"
                        )},
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
                result = LLMPreprocessOutput.model_validate_json(content)
                logger.info(f"LLM preprocess OK (attempt {attempt + 1}): {result.explanation}")
                return result.corrected_text
            except (ValidationError, json.JSONDecodeError) as e:
                last_error = e
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
            except Exception as e:
                last_error = e
                logger.error(f"LLM attempt {attempt + 1} unexpected: {e}")

        logger.error(f"LLM all retries failed, falling back to raw text: {last_error}")
        return text


llm_pipeline = LLMPipeline()
