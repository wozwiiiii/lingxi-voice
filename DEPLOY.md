# 灵犀语伴 — 完整运行指南

> 适用于 Python 版（主）。Java 版为「扩展预留」的契约对齐样例，不作为可用
> 服务运行——下方仅保留其单测验证说明，不提供部署指引。

---

## 目录

- [Python 版](#python-版)
  - [本地测试（零外部依赖，2 分钟跑通）](#python-本地测试)
  - [本地运行（Docker 全栈，推荐）](#python-本地运行docker)
  - [本地运行（无 Docker，仅 API）](#python-本地运行无docker)
  - [远程上线（腾讯云/阿里云轻量服务器）](#python-远程上线)
- [Java 版（扩展预留）](#java-版扩展预留)
- [前置准备清单](#前置准备清单)

---

## 前置准备清单

### 你需要注册的免费账号（5 分钟）

| 服务 | 网址 | 用途 | 费用 |
|---|---|---|---|
| **DeepSeek API** | https://platform.deepseek.com | LLM 文本预处理 | 按量计费，注册送额度 |
| **硅基流动 SiliconFlow** | https://siliconflow.cn | 云端 TTS 语音合成 | 注册送免费额度 |

注册后在各自控制台获取 API Key（一串以 `sk-` 开头的字符），后面配置时会用到。

### 你的电脑上需要安装的软件

| 软件 | 检查命令 | 没有的话 |
|---|---|---|
| Python 3.10+ | `python --version` | 去 https://python.org 下载安装 |
| Node.js 20+ | `node --version` | 去 https://nodejs.org 下载 LTS 版 |
| Git | `git --version` | 去 https://git-scm.com 下载 |
| Docker Desktop（可选） | `docker --version` | 去 https://docker.com 下载（本地全栈运行需要） |
| JDK 21（仅 Java 契约样例） | `java --version` | 去 https://adoptium.net 下载 Temurin 21 |
| Maven 3.9+（仅 Java 契约样例） | `mvn --version` | 去 https://maven.apache.org 下载 |

---

## Python 版

### Python 本地测试

> **不需要 Docker、不需要 Redis、不需要数据库。** 测试用内存数据库 + 模拟 Redis，Python 装好就能跑。

```bash
# 1. 打开终端（PowerShell 或 Git Bash），进入项目
cd D:\AI_Program\fuchuang_project\lingxi-voice\backend

# 2. 安装 Python 依赖（只需要做一次）
pip install -r requirements.txt -r requirements-dev.txt

# 3. 生成测试用的 PPT 文件（只需要做一次）
cd tests\fixtures
python generate_sample.py
cd ..\..

# 4. 运行全部 149 个测试
python -m pytest tests/ -v
```

**你应该看到：**
```
======================== 149 passed, ~16s ========================
```

**如果测试不过**，常见问题：

| 错误 | 解决方法 |
|---|---|
| `ModuleNotFoundError: No module named 'xxx'` | 重新运行步骤 2：`pip install -r requirements.txt -r requirements-dev.txt` |
| `sample.pptx not generated` | 运行步骤 3 生成测试文件 |

#### 只跑某一个测试

```bash
# 只跑认证测试
python -m pytest tests/test_auth.py -v

# 只跑一个测试函数
python -m pytest tests/test_auth.py::test_register_success -v
```

---

### Python 本地运行（Docker）

> **推荐方式。** Docker 一键启动全部服务（API + Worker + Beat + PostgreSQL + Redis + Nginx），和线上环境一致。

#### 第一次启动

```bash
# 1. 进入 Docker 配置目录
cd D:\AI_Program\fuchuang_project\lingxi-voice\deploy

# 2. 复制环境变量模板
copy .env.example .env
# 如果提示文件不存在，用这个：
# cp .env.example .env

# 3. 编辑 .env 文件（用记事本或 VS Code 打开）
#    必须修改以下三项：
#      DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
#      SILICONFLOW_API_KEY=sk-你的硅基流动密钥
#      JWT_SECRET_KEY=随机64个字符（用 https://passwordsgenerator.net 生成）

# 4. 确保 Docker Desktop 正在运行（任务栏右下角有 Docker 图标）
#    如果没有，先启动 Docker Desktop

# 5. 启动所有服务
docker compose up -d

# 6. 等 15 秒让数据库启动，然后运行数据库迁移
docker compose exec api alembic upgrade head

# 7. 验证：打开浏览器访问
#    http://localhost:8000/api/health
#    应该看到：{"status":"ok"}
```

#### 验证各功能是否正常

```bash
# 健康检查
curl http://localhost:8000/api/health

# API 文档页面（浏览器打开）
# http://localhost:8000/docs

# 注册一个测试用户
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser","password":"password123"}'

# 登录获取 token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

#### 启动前端（可选）

```bash
cd D:\AI_Program\fuchuang_project\lingxi-voice\frontend

# 安装依赖（只需要做一次）
npm install

# 启动开发服务器
npm run dev

# 浏览器打开 http://localhost:5173
```

#### 停止和重启

```bash
# 停止（数据不会丢失）
cd D:\AI_Program\fuchuang_project\lingxi-voice\deploy
docker compose down

# 重新启动
docker compose up -d

# 完全删除（包括数据库数据，谨慎！）
docker compose down -v
```

---

### Python 本地运行（无 Docker）

> 如果你不想装 Docker，只能跑 API 部分（没有数据库和 Redis，功能受限）。

```bash
cd D:\AI_Program\fuchuang_project\lingxi-voice\backend

# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置环境变量（Windows PowerShell）
$env:DATABASE_URL="sqlite+aiosqlite:///lingxi.db"
$env:JWT_SECRET_KEY="dev-secret-at-least-32-characters-long-12345"
$env:DEEPSEEK_API_KEY="sk-你的密钥"
$env:SILICONFLOW_API_KEY="sk-你的密钥"
$env:TTS_PROVIDER_CHAIN="cloud:siliconflow"

# 3. 启动（无 Redis 时缓存/限流不可用，但 API 能跑）
uvicorn app.main:app --reload --port 8000

# 4. 验证
# 浏览器打开 http://localhost:8000/api/health
```

> **注意**：无 Docker 模式下，以下功能不可用：
> - TTS 缓存（每次都会调 API）
> - 限流保护
> - 课件批量合成（需要 Celery Worker）
> - 声音克隆（需要 Celery Worker）
>
> **但 149 个测试完全不受影响**——测试用内存模拟一切。

---

### Python 远程上线

> 使用腾讯云/阿里云轻量应用服务器（2核4G，Ubuntu 22.04，约 ¥50-80/月）

#### 第一步：买服务器

1. 打开 [腾讯云轻量应用服务器](https://cloud.tencent.com/product/lighthouse) 或 [阿里云轻量应用服务器](https://www.aliyun.com/product/swas)
2. 选择：**2核4G、Ubuntu 22.04、上海/北京/广州**（离你最近的）
3. 购买后，在控制台找到 **公网 IP**（如 `123.456.789.0`）和 **root 密码**

#### 第二步：登录服务器

在本地终端：

```bash
ssh root@你的服务器公网IP
# 输入密码（控制台提供的 root 密码）
```

#### 第三步：初始化服务器

以下命令全部在服务器上执行：

```bash
# 1. 更新系统
apt update && apt upgrade -y

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 3. 安装 Docker Compose
apt install docker-compose-plugin -y

# 4. 验证
docker --version
# 输出类似：Docker version 27.x.x
```

#### 第四步：上传项目

在**本地终端**执行（不是在服务器上）：

```bash
# 进入项目目录
cd D:\AI_Program\fuchuang_project\lingxi-voice

# 打包项目（排除不需要的文件）
# PowerShell:
tar --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' --exclude='.git' --exclude='frontend/dist' -czf lingxi-voice.tar.gz .

# 上传到服务器
scp lingxi-voice.tar.gz root@你的服务器IP:/opt/
```

#### 第五步：在服务器上配置和启动

```bash
# SSH 到服务器
ssh root@你的服务器IP

# 1. 解压
cd /opt
mkdir lingxi-voice
tar -xzf lingxi-voice.tar.gz -C lingxi-voice
cd lingxi-voice/deploy

# 2. 生成随机 JWT 密钥
echo "JWT_SECRET_KEY=$(openssl rand -base64 64)" >> .env

# 3. 编辑 .env 填写 API 密钥
nano .env
# 或 vim .env
# 修改这两行：
#   DEEPSEEK_API_KEY=sk-你的密钥
#   SILICONFLOW_API_KEY=sk-你的密钥

# 4. 启动服务
docker compose up -d

# 5. 数据库迁移
docker compose exec api alembic upgrade head

# 6. 验证
curl http://localhost:8000/api/health
# 应该返回 {"status":"ok"}
```

#### 第六步：配置 HTTPS（免费 SSL 证书）

```bash
# 1. 先确保你有域名（如果没有，这步可以跳过，用 http://IP:8000 访问）
# 2. 在你的域名 DNS 中添加一条 A 记录，指向服务器 IP

# 3. 安装 certbot
apt install certbot python3-certbot-nginx -y

# 4. 获取证书（把 your-domain.com 换成你的域名）
certbot --nginx -d your-domain.com

# 5. certbot 会自动配置 Nginx 并设置证书自动续期
```

#### 第七步：验证上线

浏览器访问 `https://你的域名/api/health`（或 `http://你的IP:8000/api/health`）

#### 成本估算

| 项目 | 月费用 |
|---|---|
| 轻量服务器 2C4G | ¥50-80 |
| 硅基流动 API（CosyVoice2） | ¥10-30（轻量使用） |
| DeepSeek API（LLM） | ¥5-15 |
| 域名（可选） | ¥5 |
| **合计** | **¥70-130** |

> **省钱技巧**：面试期间开服务器，不面试时关机（轻量服务器按量计费模式，关机不计费）。

#### 上线前检查清单

- [ ] `deploy/.env` 中的 `JWT_SECRET_KEY` 已更换为随机 64 字符
- [ ] API 密钥已填入真实值（不是 `sk-your-key-here`）
- [ ] 执行了 `docker compose exec api alembic upgrade head`
- [ ] `curl http://localhost:8000/api/health` 返回 `{"status":"ok"}`
- [ ] 注册 → 登录 → TTS 合成全链路正常
- [ ] 防火墙只开放 80 和 443 端口（22 端口仅限你的 IP）

---

## Java 版（扩展预留）

> ⚠️ **Java 版不是可用服务**，是「双语言契约对齐」的工程样例：核心 Provider
> 为存根（`synthesize` 返回空音频）、MCP 工具未做真实注解、未做端到端联调。
> 项目实际运行**只支持 Python 版**。Java 版仅用于验证 API 契约跨语言一致性。

```bash
# 唯一有意义的用法：跑单测验证契约（需要 JDK 21 + Maven）
cd lingxi-voice-java
mvn test
# 应看到 Tests run: 80+, Failures: 0
```

如果未来要启用 Java 版，需补全 `SiliconFlowProvider`（当前返回空音频）、
`TtsService`（当前不存在）、`TtsTool` 的 Spring AI MCP 注解。在这些补全之前，
不要把它当作可部署的服务。

---

## 快速参考表

| 操作 | Python 版（唯一可运行版） |
|---|---|
| 跑测试 | `cd backend && python -m pytest tests/ -v` |
| 本地启动 | `cd deploy && docker compose up -d` |
| 健康检查 | `curl localhost:8000/api/health` |
| API 文档 | http://localhost:8000/docs |
| 远程部署 | rsync + Docker Compose |
| 月成本 | ¥70-130（含 AI API 费用） |

---

*最后更新：2026-09-03。Python 版在 Windows 11 + Python 3.10 + Docker Desktop 上验证通过；Java 版为契约对齐样例（仅单测验证）。*
