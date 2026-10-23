# 灵犀语伴 LingXi Voice · AI 语音课件应用

> 帮老师把 PPT 变成带配音的有声课件：支持声音克隆、逐页试听、教学文本的符号/多音字智能转译。

**项目定位（如实声明）**：本项目源自第 16 届中国大学生服务外包创新创业大赛 **全国三等奖** 作品（赛题 A09「基于 AI 语音合成的教学声音处理软件」，企业命题方锐捷网络，团队 4 人，本人负责后端 + 语音合成 + 模型部署）。当前代码库为赛后基于大赛文档的**重构版本**——核心增量在工程化与安全加固，而非模型本身从零研发。

## 架构概览

```
浏览器（Vue 3 SPA）
  │ HTTPS
Nginx（静态资源 / 反向代理）
  ▼
FastAPI（port 8000，不映射宿主机端口） ──▶ Celery Worker / Beat
  │                                        │ progress → Redis → SSE
  ├── PostgreSQL 16
  └── Redis 7
       │
       └── TTSProvider 抽象
            ├── LocalCosyVoiceProvider → WSL2 GPU 推理（CosyVoice2-0.5B）
            └── SiliconFlowProvider    → 云 CosyVoice API
```

- **双 Provider 策略**：能力探测驱动前端控件渲染、降级链、熔断器（CLOSED/OPEN/HALF_OPEN，状态存 Redis）
- **LLM 文本预处理三级降级**：规则引擎 → LLM 纠正（JSON 结构化 + Pydantic 校验重试）→ 本地确定性替换兜底；Prompt 外置数据库支持热更新
- **纵深防御**：JWT 双 token 轮换、多层限流（克隆日限额存 DB 防绕过）、HMAC 签名 URL、ZIP 炸弹防御、defusedxml 等

## 测试与质量

| 维度 | 数据 |
|---|---|
| Python 单元测试 | 144 个 test 函数（17 个测试文件，fakeredis + SQLite 内存，无需真实服务） |
| 契约检查 | 22 项真实 HTTP 栈契约检查（httpx 走完整 FastAPI 栈） |
| Java 参考实现 | 123 个 JUnit（含 MCP Server 模块，未做端到端联调） |
| 前端 | Vue 3 + TypeScript，vue-tsc 类型检查通过 |

## 部署

Docker Compose 六服务一键启动（前端 / API / Worker / Beat / PostgreSQL / Redis，含 Celery Beat 定时清理）。API 容器不映射宿主机端口，统一走 Nginx 反代入口；代码随镜像构建进入容器。

## 如实声明的已知限制

1. **单 GPU 串行推理**：RTX 4060 仅够单请求推理，线上靠云 API 并发，本地 Celery 排队串行
2. **流式延迟**：CosyVoice2 官方 150ms 首包在 A100 上，4060 上 RTF 约 0.3–1.0
3. **WSL2/Docker 硬依赖**：CosyVoice2 官方只保 Linux
4. **GPU 版 compose 未闭环**：`deploy/` 下 GPU 编排引用的 `Dockerfile.inference` 与 `../inference` 目录在本仓库中不存在，无法直接启动（声明了部署形态，缺推理服务源码与镜像定义）
5. **明确不做**：MOS 主观评测（需 20–30 人盲测）、订阅/支付、OpenTelemetry 分布式追踪

## 技术栈

FastAPI · CosyVoice2 · Celery · Redis · PostgreSQL · SQLAlchemy 2.0（异步）· Vue 3 · Docker Compose · Nginx · pytest
