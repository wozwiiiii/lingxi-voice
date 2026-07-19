from app.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("TTS_PROVIDER_CHAIN", "cloud:siliconflow")

    s = Settings()

    assert "postgresql+asyncpg" in s.DATABASE_URL
    assert s.REDIS_URL == "redis://localhost:6379/0"
    assert s.JWT_ALGORITHM == "HS256"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert s.TTS_PROVIDER_CHAIN == "cloud:siliconflow"
    assert s.tts_provider_chain_list == ["cloud:siliconflow"]


def test_provider_chain_parsing(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER_CHAIN", "local:cosyvoice2,cloud:siliconflow")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
    monkeypatch.setenv("REDIS_URL", "redis://localhost/0")
    monkeypatch.setenv("JWT_SECRET_KEY", "x")
    s = Settings()
    assert s.tts_provider_chain_list == ["local:cosyvoice2", "cloud:siliconflow"]


def test_default_cors_origins(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
    monkeypatch.setenv("REDIS_URL", "redis://localhost/0")
    monkeypatch.setenv("JWT_SECRET_KEY", "x")
    s = Settings()
    assert "http://localhost:5173" in s.cors_origin_list


def test_cors_origins_parsing(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,https://example.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
    monkeypatch.setenv("REDIS_URL", "redis://localhost/0")
    monkeypatch.setenv("JWT_SECRET_KEY", "x")
    s = Settings()
    assert "https://example.com" in s.cors_origin_list
    assert len(s.cors_origin_list) == 2
