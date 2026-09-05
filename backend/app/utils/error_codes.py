"""Slide 级错误分类：给失败页打上「是否值得重试」的标签。

`CoursewareSlide` 之前只有一个裸的 ``status="failed"``，前端无法区分
「供应商挂了，重试有用」和「你的文本不合法，重试没用」。本模块定义
error_code 的取值集合，并把异常对象映射到对应类别。

映射原则是**白名单**：只有明确可归类的异常才标记为可重试
（``provider_unavailable`` / ``timeout``），其余一律保守归为
``content_error``。宁可让用户手动检查内容，也不要让一个未知异常触发
无脑自动重试、反复烧云 API 费用。
"""

import asyncio
from enum import Enum

from app.providers.errors import ContentError, ProviderUnavailableError


class SlideErrorCode(str, Enum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # 供应商不可用，可重试
    CONTENT_ERROR = "content_error"  # 内容/参数错误，重试无意义
    TIMEOUT = "timeout"  # 超时，可重试


def classify_exc(exc: BaseException) -> SlideErrorCode:
    """把异常映射为 slide 级 error_code。

    注意 ``RuntimeError``（provider chain 的 "All TTS providers are
    unavailable"）归为 provider_unavailable：这是熔断打开或链配置错误的
    信号，与供应商故障同属「等一会儿再试」的范畴。
    """
    if isinstance(exc, ContentError):
        return SlideErrorCode.CONTENT_ERROR
    if isinstance(exc, asyncio.TimeoutError):
        return SlideErrorCode.TIMEOUT
    if isinstance(exc, (ProviderUnavailableError, RuntimeError)):
        return SlideErrorCode.PROVIDER_UNAVAILABLE
    return SlideErrorCode.CONTENT_ERROR
