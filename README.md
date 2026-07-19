# 灵犀语伴 (LingXi Voice)

基于 CosyVoice2 的 AI 语音合成教学平台 — 第 16 届全国大学生服务外包创新创业大赛全国三等奖重建项目。

## 快速开始

```bash
# 1. 配置环境变量
cp deploy/.env.example deploy/.env
# 编辑 .env，填入 API keys（DeepSeek、SiliconFlow 等）

# 2. 启动服务
cd deploy && docker compose up -d

# 3. 数据库迁移
docker compose exec api alembic upgrade head

# 4. 访问
# API: http://localhost:8000
# API 文档: http://localhost:8000/docs
# 前端（开发模式）: cd frontend && npm install && npm run dev
```

## 技术栈

| 层 | 技术 |
|---|---|
| 模型推理 | CosyVoice2-0.5B (本地 GPU) + SiliconFlow API (云端) |
| LLM 管线 | DeepSeek API (OpenAI 兼容协议) |
| 后端 | Python 3.10 + FastAPI + Celery + PostgreSQL 16 + Redis 7 |
| 前端 | Vue 3 + TypeScript + Pinia + Ant Design Vue 4 + Vite |
| 部署 | Docker Compose (4 服务: API + Worker + PG + Redis) |
| CI | GitHub Actions (Ruff + mypy + pytest + vue-tsc) |

## 架构亮点

- **混合推理**：TTSProvider 抽象 + Local/Cloud 双实现 + 熔断器 + 降级链
- **LLM 预处理管线**：规则检测 → LLM 纠正 → 规则兜底（符号转译/多音字/标记生成）
- **安全纵深防御**：多层限流 + 缓存三防护 + 音频上传 7 层校验链 + JWT 双 token
- **企业级测试**：10/10 后端单元测试 + Provider 契约测试框架

## 项目结构

```
lingxi-voice/
├── backend/           # FastAPI + Celery + Provider 实现
│   ├── app/
│   │   ├── api/       # auth, tts, voices, capabilities
│   │   ├── models/    # User, Voice, Consent, SynthesisTask
│   │   ├── providers/ # TTSProvider ABC + Local/SiliconFlow + CircuitBreaker
│   │   ├── preprocess/# LLM Pipeline + Rule Engine + Audio Quality
│   │   ├── security/  # JWT + Rate Limit + Dependencies
│   │   └── services/  # Auth + TTS + Clone + Voice
│   └── tests/
├── inference/         # CosyVoice2 GPU 推理服务（独立进程）
├── frontend/          # Vue 3 SPA
├── deploy/            # Docker Compose + Nginx + Dockerfiles
└── docs/              # 规格 + 计划 + ADR
```

## 环境变量

参考 `deploy/.env.example`。关键变量：

| 变量 | 说明 |
|---|---|
| `TTS_PROVIDER_CHAIN` | Provider 链，逗号分隔：`cloud:siliconflow` 或 `local:cosyvoice2,cloud:siliconflow` |
| `DEEPSEEK_API_KEY` | LLM 管线 API key |
| `SILICONFLOW_API_KEY` | 云端 TTS API key |
| `JWT_SECRET_KEY` | JWT 签名密钥（生产环境必须更换） |

## 许可

MIT License — 基于 T2401927 大赛文档重建。
