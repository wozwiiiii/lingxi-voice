CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    quota_override JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE voices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    type VARCHAR(20) NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    provider VARCHAR(50) NOT NULL,
    provider_metadata JSONB NOT NULL DEFAULT '{}',
    reference_audio_path VARCHAR(500),
    consent_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE consents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    audio_sha256 VARCHAR(64) NOT NULL,
    purpose TEXT NOT NULL,
    agreed_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE synthesis_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    voice_id UUID NOT NULL REFERENCES voices(id),
    type VARCHAR(20) NOT NULL,
    input_text TEXT,
    llm_processed_text TEXT,
    params JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    output_audio_path VARCHAR(500),
    output_format VARCHAR(10) NOT NULL DEFAULT 'wav',
    celery_task_id VARCHAR(100),
    progress INTEGER NOT NULL DEFAULT 0,
    error_code VARCHAR(50),
    error_message TEXT,
    cached BOOLEAN NOT NULL DEFAULT FALSE,
    provider_used VARCHAR(50),
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_voices_user_id ON voices(user_id);
CREATE INDEX idx_consents_user_id ON consents(user_id);
CREATE INDEX idx_consents_audio_sha256 ON consents(audio_sha256);
CREATE INDEX idx_synthesis_tasks_user_id ON synthesis_tasks(user_id);
