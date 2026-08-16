# 灵犀语伴 (LingXi Voice)

基于 CosyVoice2 的 AI 语音合成教学平台，源自第 16 届全国大学生服务外包创新创业大赛全国三等奖项目（依据 OPIC 实习经历重构）。提供用户注册登录、文本转语音（TTS）、有声课件制作等模块。

**两个后端实现**：

| 版本 | 目录 | 状态 |
|------|------|------|
| Python 后端（主） | `backend/` | ✅ 已实现、96 测试通过、Docker 部署验证通过 |
| Java 后端 | `lingxi-voice-java/` | ⚠️ 契约已对齐前端（123 测试通过），功能为参考实现，未做端到端联调 |

## 功能

- **用户体系**：注册 / 登录 / Token 自动续期 / 登出（拉黑双 token）
- **文本转语音**：多声音、历史记录、音频播放与下载（游客可试用）
- **课件合成**：上传 PPTX → 逐页编辑 → Celery 异步合成 → SSE 实时进度 → ZIP 打包下载
- **声音库**：预设声音 + 用户克隆（官方示例课件库）

## 快速开始（Docker 生产部署）

前置：Docker Desktop 已启动。

```bash
# 1. 配置环境变量
cp deploy/.env.example deploy/.env
# 编辑 deploy/.env：填入 DEEPSEEK_API_KEY、SILICONFLOW_API_KEY、
# 并把 JWT_SECRET_KEY、REDIS_PASSWORD、POSTGRES_PASSWORD 改为强随机值

# 2. 构建并启动（前端 + API + Worker + Postgres + Redis，共 5 服务）
cd deploy && docker compose up -d --build

# 3. 数据库迁移（初始化表结构）
docker compose exec api alembic upgrade head

# 4. 访问
# 前端:      http://localhost          （nginx 托管 SPA）
# API 文档:  http://localhost:8000/docs
```

停止 / 恢复：

```bash
docker compose stop    # 暂停（保留数据）
docker compose start   # 恢复
docker compose down    # 移除容器（数据卷保留）
```

## 本地开发（无 Docker）

后端依赖 PostgreSQL + Redis。若本机无这两个服务，可用测试基础设施验证逻辑（见"测试"一节），或安装后启动：

```bash
# 后端（需 PostgreSQL + Redis 在 localhost:5432/6379）
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev    # 访问 http://localhost:5173，/api 代理到 :8000
```

> ⚠️ 生产部署时 `frontend/vite.config.ts` 仅用于开发代理；生产由 nginx 直接托管 `dist`。

## 技术栈

| 层 | 技术 |
|---|---|
| 模型推理 | CosyVoice2-0.5B (本地 GPU) + SiliconFlow API (云端) |
| LLM 管线 | DeepSeek API (OpenAI 兼容协议) |
| 后端 | Python 3.10 + FastAPI + Celery + PostgreSQL 16 + Redis 7 |
| 前端 | Vue 3 + TypeScript + Pinia + Ant Design Vue 4 + Vite |
| 部署 | Docker Compose (5 服务: 前端 + API + Worker + PG + Redis) + Nginx |
| 测试 | pytest (Python 96) / JUnit+Mockito (Java 123) / vue-tsc + Vite (前端) |

## 架构亮点

- **混合推理**：TTSProvider 抽象 + Local/Cloud 双实现 + 熔断器 + 降级链
- **LLM 预处理管线**：规则检测 → LLM 纠正 → 规则兜底（符号转译/多音字/标记生成）
- **安全纵深防御**：多层限流（真实 IP 识别）、缓存三防护、音频上传校验链、JWT 双 token + 自动续期 + 登出双 token 拉黑
- **异步课件合成**：Celery 任务 + 信号量并发 + SSE 进度推送，同步接口不阻塞
- **契约验证**：`backend/scripts/contract_check.py` 用真实 HTTP 栈验证前端依赖的全部 API 契约

## 项目结构

```
lingxi-voice/
├── backend/           # FastAPI + Celery + Provider 实现
│   ├── app/
│   │   ├── api/       # auth, tts, voices, capabilities, courseware
│   │   ├── models/    # User, Voice, Consent, SynthesisTask, Courseware*
│   │   ├── providers/ # TTSProvider ABC + Local/SiliconFlow + CircuitBreaker
│   │   ├── preprocess/# LLM Pipeline + Rule Engine + Audio Quality
│   │   ├── security/  # JWT + Rate Limit + Dependencies
│   │   ├── services/  # Auth + TTS + Clone + Voice + Courseware
│   │   └── tasks/     # Celery 任务（课件合成、孤儿清理）
│   ├── scripts/       # contract_check.py（端到端契约验证）
│   └── tests/         # 96 个 pytest 测试
├── lingxi-voice-java/ # Java 后端（参考实现，契约已对齐）
├── frontend/          # Vue 3 SPA
├── deploy/            # Docker Compose + Nginx + Dockerfiles
└── docs/              # 规格 + 计划 + ADR
```

## 环境变量

参考 `deploy/.env.example`。关键变量：

| 变量 | 说明 |
|---|---|
| `TTS_PROVIDER_CHAIN` | Provider 链：`cloud:siliconflow` 或 `local:cosyvoice2,cloud:siliconflow` |
| `DEEPSEEK_API_KEY` | LLM 管线 API key |
| `SILICONFLOW_API_KEY` | 云端 TTS API key |
| `JWT_SECRET_KEY` | JWT 签名密钥（**生产必须改为 ≥32 位强随机值**） |
| `REDIS_PASSWORD` | Redis 密码（**生产必须改**，需与 `REDIS_URL` 一致） |
| `POSTGRES_PASSWORD` | 数据库密码（**生产必须改**） |
| `CORS_ORIGINS` | 允许的前端来源，生产改为实际域名 |
| `MEDIA_ROOT` | 音频/课件存储目录 |

## 测试

### Python 后端（96 测试，无需真实服务）

```bash
cd backend
python -m pytest tests/ -v              # 全量
python -m pytest tests/test_auth.py -v  # 单文件
python -m pytest tests/test_auth.py::test_register_success -v  # 单用例
```

### 端到端 API 契约验证（真实 HTTP 栈，SQLite + fakeredis）

```bash
cd backend
JWT_SECRET_KEY="<任意≥32位字符串>" python scripts/contract_check.py
# 输出: 22 通过, 0 失败
```

### Java 后端（123 测试，需 Maven + JDK 21）

```bash
cd lingxi-voice-java
mvn test
```

### 前端（类型检查 + 构建）

```bash
cd frontend
npm run build   # vue-tsc --noEmit && vite build
```

### Docker 完整栈冒烟测试

```bash
cd deploy && docker compose up -d --build
curl -s http://localhost/api/health            # {"status":"ok"}
curl -s http://localhost/                      # 前端 HTML
docker compose exec api alembic upgrade head   # 首次需迁移
```

## 许可

MIT License — 基于大赛文档重建。
