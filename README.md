# Spyglass

竞品分析 Agent 工作台。产品、技术、视觉和任务顺序分别以根目录 `PRD.md`、`TECHNICAL.md`、`DESIGN.md`、`prompt.md` 为准。

当前范围：**Slice 0 + Slice 1**。Web → FastAPI → PostgreSQL/pgvector、Redis 实际连通；已实现注册、登录、登出、默认个人 Tenant、服务器解析的成员权限、持久会话与隔离的 Project/Thread API。前端包含登录守卫、账户设置、项目创建/列表/搜索/详情及首页真实近期项目。Skills、LangGraph、报告生成和导出将在 Slice 2–6 实现，当前不能从输入生成报告。

## 本地开发（Windows PowerShell / Linux）

需要 Node.js ≥22.12、Python 3.13、uv 0.11.2 和可用的 Docker Compose。已锁定 npm 与 Python 依赖，当前使用 React 19/Vite/TailwindCSS/Zustand/React Router/TanStack Query/Framer Motion 与 FastAPI/SQLAlchemy/Alembic。

1. 创建 `.env`；若已有提供商密钥，保留现有文件，无需覆盖。未配置数据库时使用 `127.0.0.1:55432`、Redis `127.0.0.1:56379` 的本地开发默认值，避免干扰已有 5432 服务。开发数据库默认凭据仅用于本地。

   ```powershell
   Copy-Item .env.example .env
   ```

2. 安装锁定依赖、启动数据库与缓存、迁移：

   ```powershell
   uv sync --frozen
   npm ci
   docker compose up -d postgres redis
   uv run alembic -c apps/api/alembic.ini upgrade head
   ```

3. 两个终端分别运行：

   ```powershell
   uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --loop app.core.event_loop:database_event_loop
   ```

   ```powershell
   npm run dev
   ```

访问 [工作台](http://127.0.0.1:5173)、[OpenAPI](http://127.0.0.1:8000/docs)。Windows 的 psycopg 异步连接必须使用上面的 selector event loop，不能省略 `--loop`。连接采用有限超时；资源随 API lifespan 关闭。

## Docker Compose

```powershell
docker compose up -d --build
docker compose ps
```

访问 [容器 Web](http://127.0.0.1:8080)，首次访问会进入登录页，可自行注册账户。API 容器启动前自动执行显式 Alembic 迁移；web 经 Nginx 同源代理 `/api/`。四个服务端口均仅绑定本机。已有 `.env` 通过 `env_file` 注入 API，不进入镜像；前端不读取密钥。开发默认数据库密码应在共享环境替换，同时设置匹配的 `DATABASE_URL`。当前 Compose 为 HTTP 本地开发配置；生产环境必须使用 HTTPS、`APP_ENV=production`、`SESSION_COOKIE_SECURE=true` 和明确的 CORS 白名单。

首次镜像构建依赖网络下载；Dockerfile 使用指定版本与依赖锁。PostgreSQL/Redis 镜像还固定了已拉取的 digest。数据使用命名卷持久化；普通停止使用 `docker compose down`，不要加 `-v`，后者会删除数据。

## 验证

先启动 PostgreSQL/Redis 并迁移。全部验证可执行：

```powershell
pwsh -File scripts/verify.ps1
```

或逐项执行：

```powershell
uv run ruff format --check apps/api scripts
uv run ruff check apps/api scripts
uv run mypy
uv run pytest -q
uv run alembic -c apps/api/alembic.ini check
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

`pytest` 默认包含真实基础设施测试，要求 PostgreSQL/Redis 可用，不会静默跳过。集成测试创建随机 `spyglass_test_*` 空库，实际验证迁移前 503、升级后 200、pgvector 运算、Redis PING 及 downgrade/upgrade，随后只删除自己创建的测试库；不清理业务数据库。无需基础设施的快速检查可用 `uv run pytest -m "not integration" -q`，这不等于完成全部验收。

`npm run test:e2e` 通过 Python runner 新建独立 `spyglass_e2e_*` 数据库、迁移并启动专用 API 8001/Web 5174，完成后只删除该测试数据库；不会复用 8000/8080 的业务会话。检查桌面和手机、真实登录/注册/登出、刷新恢复、项目创建/搜索/保存/跨账户 UUID 拒绝、模板填充、模式切换和键盘操作。截图在忽略目录 `.artifacts/screenshots/`；测试轨迹和 HTML 报告分别在 `test-results/`、`playwright-report/`。直接运行 `playwright test` 不会创建隔离数据库，请使用 npm 入口。

## API 与类型

- `GET /api/v1/health/live`：公开存活探针，`schema_version=1`，不访问外部服务。
- `GET /api/v1/health/ready`：公开基础设施探针，检查 PostgreSQL、Redis、pgvector 和迁移版本；就绪 200、降级 503。配置状态只表示密钥存在，**不代表供应商已联网验证**。当前 `research_available=false`。
- 通用 401/403/404/405/409/422/429/500/503：`{error:{code,message,details?,request_id}}`，返回 `X-Request-ID`。验证错误不回显用户输入，500 不暴露异常和连接串；429 包含 Retry-After。
- `POST /auth/register`、`POST /auth/login`（均带 `/api/v1` 前缀）：邮箱/密码认证，注册还需 display_name。密码 15–128 字符，使用 Argon2id。邮箱规范化后唯一；注册、个人 Tenant、owner 成员及会话在同一事务创建。
- `GET /users/me`：当前真实用户及成员关系解析出的个人 Tenant。令牌为 256 位随机值，数据库只存 SHA-256 摘要；sg_session 为 HttpOnly/SameSite=Lax Cookie，默认过期 24 小时。没有 JWT/localStorage 令牌。
- `POST /auth/logout`：数据库撤销当前会话并清除 Cookie；旧令牌不能继续访问。
- `GET/POST /research`、`GET /research/{id}`、`POST /threads`、`GET /threads/{id}`、`GET /threads/{id}/messages`：私有资源都要求认证和有效成员关系；查询强制 Tenant 过滤，跨账户猜 UUID 返回 404。请求不接受 tenant_id。
- 所有写请求要求准确匹配白名单的 Origin；已认证写请求还需从 sg_csrf Cookie 读取并通过 X-CSRF-Token 提交，服务器校验绑定会话的摘要。登录/注册有 Redis 原子计数限流（默认每来源 IP/接口 5 次/60 秒）；Redis 不可用时认证写入失败关闭，不降级成无限尝试。外部 API 客户端也需显式设置可信 Origin。
- 创建 Project/Thread 必须带 8–128 字符 Idempotency-Key；同键同内容返回原实体，同键不同内容返回 409。鉴权接口依赖邮箱唯一约束和会话撤销，不将注册或登出重试伪装成新业务实体。

当前迁移 `0002_auth_workspace` 包含 users/tenants/tenant_members/sessions/research_projects/threads/runs/messages。复合外键阻止跨租户关联；角色/状态有 CHECK；Run 活动状态部分唯一索引保证每 Thread 最多一个活动 Run。**尚无 Run 创建或执行 API**，不会因有 runs 表就宣称调研运行能力完成。完整团队管理、邮箱验证、密码重置尚未实现。

契约变更后运行 `npm run api:types`，从 FastAPI OpenAPI 生成并格式化 `apps/web/src/types/api.generated.ts`。页面只通过 services 访问 API；TanStack Query 管理请求和会话状态，Zustand 保存草稿与模式；切换账户及登出清理缓存/草稿。

## 外部 API 配置验证

```powershell
uv run python scripts/check_providers.py
```

这是**手动真实联网**诊断，会对 `.env` 中每组 `*_API_KEY` 发一次小请求，产生少量供应商用量；不会在普通测试/构建中执行。支持 Bocha 搜索与 OpenAI 兼容模型接口的 JSON/SSE 响应；模型请求并发执行，总超时 65 秒。只保存脱敏状态、真实 usage 与耗时到 `.artifacts/provider-check.json`，不记录请求头、密钥或模型隐藏推理。它不是应用的 ModelProvider，也不是报告生成实现。

2026-10-20 已真实验证 Bocha、DeepSeek、GLM、DeepSeek2 均 HTTP 200 且有有效结果。两组 DeepSeek 原模型名不可用，已在本地 `.env` 修正为供应商实际列出的 `deepseek-v4.1-flash`；密钥未改。部分网关即使 `stream=false` 仍返回 SSE。简短响应的耗时不代表报告生成耗时，不将当次供应商成功作为长期可用性保证。

## 视觉与后续范围

九张原始图保留于 `references/`，标准英文副本在 `assets/references/`；manifest 保存文件名映射和哈希。首页实现 Shell 与交互基线：白色/浅灰/深绿、232px 侧栏、欢迎区、输入框、六场景、模板及真实近期项目；侧栏没有场景技能。我的调研当前提供基础列表与项目保存，其完整指标/活动布局在 Slice 5 接入。其余业务页面明确禁用，场景卡仍只作视觉预览，正式单选与 Registry 在 Slice 2 接入。没有虚构运营统计、评论或报告。

用户新增性能要求已同步 PRD/TECHNICAL/prompt：Slice 3 的产品、定价、用户评价 LLM 必须并发，有全局并发限制、单请求超时、Run 总预算；SWOT、Writer、Reviewer 按数据依赖汇合。需在后续提供并发重叠、截止时间和真实端到端报告验收证据。
