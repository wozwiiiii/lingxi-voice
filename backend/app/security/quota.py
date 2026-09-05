"""月度调用配额（防滥用，非计费）。

灵犀语伴的每次 TTS 合成、每页课件合成都要调用按量付费的云 API。如果只靠
JWT 鉴权，任何人拿到一个 token 就能写脚本无限调用，一夜之间烧光额度。
本模块在鉴权之后再加一层"按月计数"的闸门：按自然月统计每个用户的合成量，
超限直接 429 拒绝，到下月 1 日自动恢复。

不做支付、不做订阅、不做套餐——超限就拒绝，没有"充值加量"的路径。

为什么是两个独立计数器：
    TTS 与课件走的是两个计数器（``kind`` = ``tts`` / ``courseware``），
    因为两者的单位成本差一倍以上：1 次 TTS ≈ 1 次云调用；1 页课件 ≈
    LLM 预处理 + TTS 两次调用。混在一个计数器里要么课件用户被 TTS 挤占，
    要么 TTS 用户被课件拖死，业务口径也没法解释，所以分开统计、分开限额。

计数落在 db0（``get_redis()``），与 ``app/security/rate_limit.py`` 的限流
窗口一致——配额计数是可淘汰数据，Redis 满了被逐出只会让计数偏小（少拒绝
几个请求），可以接受；而 db1 留给 JWT 黑名单这类不可丢的安全状态。

两个已知取舍（都是刻意为之）：

1. ``consume_quota`` 先 INCR、后 EXPIRE，两步非原子。反过来（先 SET NX
   建 key 再 INCR）如果进程在两步之间崩溃，会留下一个值为 0 的 key，
   用户当月的额度被错误清零、用量统计错乱。先 INCR 的最坏后果只是崩在
   INCR 与 EXPIRE 之间——key 没有过期时间，会一直留到手动清理，配额只
   会偏严不会失效。宁可多设一次 EXPIRE，也不要留下脏 0 值。

2. Redis 不可用时一律"放行"（记日志后 return，不抛异常）。配额的目的是
   防滥用，属于保护性措施；Redis 故障时因为配额而让整个平台不可用，是
   保护手段反噬业务。降级到"不限额但可服务"明显好过"全员 503"。
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config import settings
from app.utils.redis_client import get_redis

logger = logging.getLogger(__name__)

QUOTA_KIND_TTS = "tts"
QUOTA_KIND_COURSEWARE = "courseware"

# user_id 可能是 int 主键或 UUID/字符串主键，统一交给 f-string 序列化
UserId = int | str


def _now_utc(now: datetime | None) -> datetime:
    """归一化到 UTC：None 取当前 UTC 时间；naive 时间按 UTC 解释。"""
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def month_key(now: datetime | None = None) -> str:
    """返回 UTC 自然月标识，格式 'YYYY-MM'。

    刻意固定用 UTC，而不是项目其他地方惯用的服务端本地时间（``func.now()``）：
    配额是运营口径，容器时区配置（或挂了宿主机 /etc/localtime）一变，跨月
    边界就会跟着漂移，导致同一笔调用被算进两个月、或月初用量莫名清零。
    UTC 是全体实例唯一共识。``now`` 参数便于测试 monkeypatch。
    """
    return _now_utc(now).strftime("%Y-%m")


def quota_key(user_id: UserId, kind: str, now: datetime | None = None) -> str:
    """配额计数 key：quota:monthly:{kind}:{user_id}:{YYYY-MM}。"""
    return f"quota:monthly:{kind}:{user_id}:{month_key(now)}"


def seconds_to_next_month(now: datetime | None = None) -> int:
    """距下月 1 日 00:00 UTC 的秒数，再 +86400 宽限。

    多给一天宽限是为了避免跨月边界上的巧合：若 key 正好在下月 1 日 00:00
    过期，而用户的请求在过期与新 key 建立之间的瞬间到达，用量会短暂归零。
    宁可让旧计数多活一天（配额偏严），也不要出现这个可钻的空档。
    """
    current = _now_utc(now)
    if current.month == 12:
        next_month = current.replace(
            year=current.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    else:
        next_month = current.replace(
            month=current.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    return int((next_month - current).total_seconds()) + 86400


def _default_limit(kind: str) -> int:
    """按 kind 取全局默认配额；未知 kind 按 TTS 处理。"""
    if kind == QUOTA_KIND_COURSEWARE:
        return int(settings.QUOTA_MONTHLY_COURSEWARE_PAGES)
    return int(settings.QUOTA_MONTHLY_TTS)


async def resolve_limit(user: object, kind: str) -> int:
    """解析用户的月度配额上限。

    用户级覆盖优先：``(user.quota_override or {}).get(kind)``，取不到则退回
    settings 全局默认值（TTS 用 QUOTA_MONTHLY_TTS，课件用
    QUOTA_MONTHLY_COURSEWARE_PAGES）。

    ``user`` 可能是任意对象（含 None），用 getattr 安全取值，不 import User
    模型以免循环导入（models 层会反过来依赖 security）。
    """
    override = getattr(user, "quota_override", None) or {}
    value = override.get(kind) if isinstance(override, dict) else None
    if value is None:
        return _default_limit(kind)
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning("invalid quota_override for kind=%s: %r, fallback to default", kind, value)
        return _default_limit(kind)


async def get_usage(user_id: UserId, kind: str) -> int:
    """当前月度用量；key 不存在（本月还没调用过）返回 0。"""
    try:
        redis = await get_redis()
        raw = await redis.get(quota_key(user_id, kind))
        return int(raw) if raw is not None else 0
    except Exception:
        # Redis 故障：放行，按"零用量"处理（见模块 docstring 取舍 2）
        logger.warning("quota get_usage failed, redis unavailable (kind=%s)", kind, exc_info=True)
        return 0


async def check_quota(user: object, kind: str, cost: int = 1) -> None:
    """检查配额是否足够；超限时抛 429，未超限无任何副作用（不计数）。

    收 ``user`` 对象而非裸 ``user_id``，是因为配额上限要读 ``user.quota_override``
    ——只给 id 的话用户级覆盖无从查起，全平台会被迫共用同一个默认额度。
    user_id 从 ``user.id`` 取，取不到（如游客传 None）时调用方应直接跳过检查。

    计数只由 ``consume_quota`` 负责：检查与扣减分离，避免一次预检就吃掉额度。
    """
    try:
        redis = await get_redis()
        raw = await redis.get(quota_key(getattr(user, "id", user), kind))
        usage = int(raw) if raw is not None else 0
    except Exception:
        # Redis 故障：放行，宁可不限额也不能拒绝服务（见模块 docstring 取舍 2）
        logger.warning("quota check skipped, redis unavailable (kind=%s)", kind, exc_info=True)
        return

    limit = await resolve_limit(user, kind)
    if usage + cost > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="本月合成配额已用尽，请下月再试",
            headers={"Retry-After": str(seconds_to_next_month())},
        )


async def consume_quota(user_id: UserId, kind: str, cost: int = 1) -> int:
    """扣减配额，返回 INCR 之后的用量。

    先 INCR 再（首次时）设 EXPIRE，原因见模块 docstring 取舍 1。"是否首次"
    用 ``返回值 == cost`` 判断，即 INCR 之前 key 的值为 0（或不存在）。
    """
    try:
        redis = await get_redis()
        usage = await redis.incrby(quota_key(user_id, kind), cost)
        if usage == cost:
            # 本月首次计数，给 key 挂上过期时间，避免历史计数永久堆积
            await redis.expire(quota_key(user_id, kind), seconds_to_next_month())
        return usage
    except Exception:
        # Redis 故障：放行，按"已扣减"返回（见模块 docstring 取舍 2）
        logger.warning("quota consume failed, redis unavailable (kind=%s)", kind, exc_info=True)
        return cost


async def refund_quota(user_id: UserId, kind: str, cost: int = 1) -> None:
    """回退配额，仅在任务提交失败（云 API 未被真正调用）时使用。

    用 DECRBY 而不是直接减后写回：并发下 DECRBY 是原子操作。减到 0 或负数
    时删掉 key，不留负值——负计数会让 get_usage 返回负数，也会让下一次
    "首次 EXPIRE"判断（usage == cost）错乱。
    """
    try:
        redis = await get_redis()
        usage = await redis.decrby(quota_key(user_id, kind), cost)
        if usage <= 0:
            await redis.delete(quota_key(user_id, kind))
    except Exception:
        # Redis 故障：放行，回退失败最多让用户少一点点额度（见模块 docstring 取舍 2）
        logger.warning("quota refund failed, redis unavailable (kind=%s)", kind, exc_info=True)
        return
