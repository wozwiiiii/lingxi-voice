# 灵犀语伴 — 完整运行指南

> 适用于 Python 版和 Java 版。从零开始，一步一步，每步都有验证方法。

---

## 目录

- [Python 版](#python-版)
  - [本地测试（零外部依赖，2 分钟跑通）](#python-本地测试)
  - [本地运行（Docker 全栈，推荐）](#python-本地运行docker)
  - [本地运行（无 Docker，仅 API）](#python-本地运行无docker)
  - [远程上线（腾讯云/阿里云轻量服务器）](#python-远程上线)
- [Java 版](#java-版)
  - [本地测试](#java-本地测试)
  - [本地运行](#java-本地运行)
  - [远程上线](#java-远程上线)
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
| JDK 21（仅 Java 版） | `java --version` | 去 https://adoptium.net 下载 Temurin 21 |
| Maven 3.9+（仅 Java 版） | `mvn --version` | 去 https://maven.apache.org 下载 |

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

# 4. 运行全部 81 个测试
python -m pytest tests/ -v
```

**你应该看到：**
```
======================== 81 passed in 3.16s ========================
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

> **推荐方式。** Docker 一键启动全部服务（API + Worker + PostgreSQL + Redis + Nginx），和线上环境一致。

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
> **但 81 个测试完全不受影响**——测试用内存模拟一切。

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

## Java 版

### Java 本地测试

> 需要 JDK 21 + Maven。测试用 H2 内存数据库，不需要 PostgreSQL。

```bash
# 1. 进入项目
cd D:\AI_Program\fuchuang_project\lingxi-voice-java

# 2. 确认 Java 和 Maven 可用
java --version
# 应该显示：openjdk 21.x.x

mvn --version
# 应该显示：Apache Maven 3.9.x

# 3. 运行全部测试
mvn test
```

**你应该看到：**
```
Tests run: 80+, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

**如果测试不过**，常见问题：

| 错误 | 解决方法 |
|---|---|
| `JAVA_HOME is not set` | 设置环境变量 `JAVA_HOME` 指向 JDK 21 安装目录 |
| `mvn: command not found` | Maven 未安装或未加入 PATH |
| `Connection refused` | 测试中的 Repository 测试需要 H2 内存数据库，应该自动创建 |

#### 只跑某一个测试

```bash
# 只跑认证测试
mvn test -Dtest=AuthServiceTest

# 只跑一个测试方法
mvn test -Dtest=AuthServiceTest#registersNewUser
```

---

### Java 本地运行

> 需要 PostgreSQL 数据库。推荐用 Docker 启动数据库，然后 IDE 或命令行启动应用。

#### 第一步：启动数据库（Docker）

```bash
# 启动 PostgreSQL + Redis
docker run -d --name lingxi-postgres \
  -e POSTGRES_USER=lingxi \
  -e POSTGRES_PASSWORD=lingxi \
  -e POSTGRES_DB=lingxi \
  -p 5432:5432 \
  postgres:16-alpine

docker run -d --name lingxi-redis \
  -p 6379:6379 \
  redis:7-alpine

# 验证数据库可用
docker ps
# 应该看到两个容器都在运行
```

#### 第二步：配置环境变量

创建 `src/main/resources/application-local.yml`（或在启动时传入）：

```bash
# Windows PowerShell:
$env:DATABASE_URL="jdbc:postgresql://localhost:5432/lingxi"
$env:POSTGRES_USER="lingxi"
$env:POSTGRES_PASSWORD="lingxi"
$env:JWT_SECRET_KEY="local-dev-secret-key-at-least-32-chars-long"
$env:DEEPSEEK_API_KEY="sk-你的密钥"
$env:SILICONFLOW_API_KEY="sk-你的密钥"
$env:TTS_PROVIDER_CHAIN="cloud:siliconflow"
```

#### 第三步：启动应用

```bash
cd D:\AI_Program\fuchuang_project\lingxi-voice-java

# 编译并启动
mvn spring-boot:run
```

**你应该看到：**
```
Started LingxiVoiceApplication in 5.234 seconds
```

#### 第四步：验证

```bash
# 另一个终端
curl http://localhost:8080/api/health
# → {"status":"ok"}

curl http://localhost:8080/actuator/health
# → {"status":"UP"}

curl http://localhost:8080/api/capabilities
# → [{"provider":"cloud:siliconflow","capabilities":{...}}]
```

---

### Java 远程上线

> 与 Python 版基本相同——上传 jar 包而非源码。

#### 第一步：服务器准备工作

同 Python 版第三步——安装 Docker。

#### 第二步：打包

```bash
cd D:\AI_Program\fuchuang_project\lingxi-voice-java

# 打包成可执行的 jar
mvn package -DskipTests

# 产物在 target/lingxi-voice-0.1.0.jar
```

#### 第三步：上传到服务器

```bash
scp target/lingxi-voice-0.1.0.jar root@你的服务器IP:/opt/lingxi-voice-java/
```

#### 第四步：在服务器上启动

```bash
ssh root@你的服务器IP

cd /opt/lingxi-voice-java

# 启动（nohup 表示后台运行，关闭终端不会停）
nohup java -jar \
  -DDATABASE_URL=jdbc:postgresql://localhost:5432/lingxi \
  -DJWT_SECRET_KEY=你的64位随机密钥 \
  -DDEEPSEEK_API_KEY=sk-你的密钥 \
  -DSILICONFLOW_API_KEY=sk-你的密钥 \
  lingxi-voice-0.1.0.jar > app.log 2>&1 &

# 查看日志
tail -f app.log

# 验证
curl http://localhost:8080/api/health
```

---

## 快速参考表

| 操作 | Python 版 | Java 版 |
|---|---|---|
| 跑测试 | `cd backend && python -m pytest tests/ -v` | `cd lingxi-voice-java && mvn test` |
| 本地启动 | `cd deploy && docker compose up -d` | `mvn spring-boot:run` |
| 健康检查 | `curl localhost:8000/api/health` | `curl localhost:8080/api/health` |
| API 文档 | http://localhost:8000/docs | 无（SpringDoc 未集成） |
| 远程部署 | rsync + Docker | scp + java -jar |
| 月成本 | ¥70-130 | ¥50-80（无 AI API 费用，LLM/TTS 单独计费） |

---

*最后更新：2026-07-19。两个版本均在 Windows 11 + Python 3.12 + Docker Desktop + JDK 21 上验证通过。*
