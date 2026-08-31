"""受签名保护的媒体文件访问（P2-5）。

/media 曾直接挂载 StaticFiles——文件名虽是 UUID 不可枚举，但 URL 一旦
泄露（分享/截图/浏览器历史）任何人可永久访问私有音频。现在 URL 携带
与文件路径绑定的短时效 HMAC 签名（与 S3 预签名 URL 同一模式）：

    /media/{path}?e={expires_unix}&s={hmac_sha256(secret, path:expires)}

为什么不用 Authorization 头：前端用 <audio src> 播放，媒体请求由浏览器
发起、无法携带自定义头。短时效签名 URL 是该场景的标准解法；与 SSE 旧
方案（P2-7，把长效 JWT 放 query）本质不同：签名只授权单个文件、且会过期。

生产环境 nginx 的 /media/ 反代到本服务（见 deploy/nginx/nginx.conf），
应用层校验对生产同样生效。
"""

import hashlib
import hmac
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.utils.storage import storage

router = APIRouter(tags=["media"])

# 签名有效期：与 TTS 结果缓存 TTL（约 24h）对齐——文件本身也在缓存
# 过期后可能被清理，签名活得比文件更久没有意义。
MEDIA_URL_TTL_S = 86400


def _signature(path: str, expires: int) -> str:
    msg = f"{path}:{expires}".encode()
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(), msg, hashlib.sha256
    ).hexdigest()


def sign_media_url(path: str, ttl_s: int = MEDIA_URL_TTL_S) -> str:
    """为媒体相对路径生成带过期时间的签名 URL。"""
    expires = int(time.time()) + ttl_s
    return f"/media/{path}?e={expires}&s={_signature(path, expires)}"


@router.get("/media/{file_path:path}")
async def get_media(file_path: str, e: int = 0, s: str = ""):
    if not e or not s:
        raise HTTPException(status_code=401, detail="缺少媒体访问签名")
    if e < int(time.time()):
        raise HTTPException(status_code=401, detail="媒体链接已过期，请重新合成")
    if not hmac.compare_digest(_signature(file_path, e), s):
        raise HTTPException(status_code=403, detail="媒体签名无效")

    # 路径穿越防护：解析后的绝对路径必须仍在媒体根目录内
    root = storage.root.resolve()
    abs_path = (storage.root / file_path).resolve()
    try:
        abs_path.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="非法路径")

    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(abs_path)
