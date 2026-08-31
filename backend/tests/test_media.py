"""P2-5 回归测试：/media 必须凭有效签名访问，防 URL 泄露后被永久访问。"""

import time

import pytest
from httpx import AsyncClient

from app.api.media import sign_media_url, _signature
from app.utils.storage import storage


async def _write_sample(key_prefix: str = "audio") -> str:
    path = await storage.save(b"\x00\x01\x02\x03", key_prefix, "mp3")
    return path


@pytest.mark.asyncio
async def test_media_without_signature_rejected(client: AsyncClient):
    path = await _write_sample()
    resp = await client.get(f"/media/{path}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_media_expired_signature_rejected(client: AsyncClient):
    path = await _write_sample()
    expires = int(time.time()) - 10
    sig = _signature(path, expires)
    resp = await client.get(f"/media/{path}?e={expires}&s={sig}")
    assert resp.status_code == 401
    assert "过期" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_media_tampered_signature_rejected(client: AsyncClient):
    path = await _write_sample()
    url = sign_media_url(path)
    # 篡改签名尾部一位
    assert url.endswith("0") or not url.endswith("0")
    tampered = url[:-1] + ("0" if url[-1] != "0" else "1")
    resp = await client.get(tampered)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_media_valid_signature_serves_file(client: AsyncClient):
    path = await _write_sample()
    url = sign_media_url(path)
    resp = await client.get(url)
    assert resp.status_code == 200
    assert resp.content == b"\x00\x01\x02\x03"


@pytest.mark.asyncio
async def test_media_path_traversal_rejected(client: AsyncClient):
    # 签名针对一个合法路径生成，但请求路径指向外部——签名不匹配在先，
    # 这里再显式验证穿越路径即使伪造 e/s 也到不了文件系统
    expires = int(time.time()) + 60
    sig = _signature("../secrets.txt", expires)
    resp = await client.get(f"/media/../../etc/passwd?e={expires}&s={sig}")
    assert resp.status_code in (401, 403, 404)
    assert resp.status_code != 200


@pytest.mark.asyncio
async def test_media_missing_file_404(client: AsyncClient):
    path = "audio/nonexistent-does-not-exist.mp3"
    url = sign_media_url(path)
    resp = await client.get(url)
    assert resp.status_code == 404
