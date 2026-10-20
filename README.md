# Spyglass

竞品分析 Agent 工作台。产品、技术、视觉和任务顺序分别以根目录 `PRD.md`、`TECHNICAL.md`、`DESIGN.md`、`prompt.md` 为准。

当前范围：**Slice 0–3**。认证、个人 Tenant、项目/Thread、13 个版本化 Skill 已实现；现已接入真实 LangGraph 研究图、DeepSeek 兼容模型/DeepSeek Search、受限网页读取、证据与结构化报告持久化、Reviewer 定向返工及 PostgreSQL Checkpoint。产品/定价/用户评价并发，SWOT 和无相互依赖的增强项并发；模型/Run 有超时和容量限制。项目详情可读取已保存报告、证据、产物修订及真实调用记录。

**公共 Run 创建、SSE 和前端输入到执行入口仍属于 Slice 4**；当前开始分析保持禁用，不把内部执行器当作已完成前端研究链路。自动增强选择仍是明确标识的清单规则，真实 Planner 当前负责竞品与研究范围。PDF、完整报告/竞品/Trace 中心等仍待后续切片。

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

当前迁移 head 为 `0005_langgraph_checkpoint`。0004 新增实际来源、证据、竞品快照、评论、分析产物、Claim/ClaimEvidence、报告版本、质量审查及调用审计表，Run 保存请求；0005 在独立 langgraph schema 初始化 SDK 检查点迁移。SDK 的并发索引初始化只在部署迁移时执行，不在并行 Run 内建表。0005 必须在线迁移，明确拒绝 `--sql` 离线生成，拒绝前不会连接数据库。复合外键阻止跨租户关联；Run 活动状态部分唯一索引保证每 Thread 最多一个活动 Run。技能版本由数据库触发器禁止 UPDATE/DELETE。

- `GET /skills?kind=scenario|core|advanced`：真实清单加当前租户配置，固定 6/4/3。
- `GET /skills/{id}?version=0.1.0`：当前详情或已保存的历史版本，含专业指导、三个 JSON Schema、校验和及工具许可。历史定义的配置为该版本默认值，不宣称是历史 Run 参数；实际运行参数在 Run 快照中。
- `PATCH /skills/{id}/config`：需 CSRF、可信 Origin、Idempotency-Key 和 expected_revision；支持 enabled/config，拒绝停用基础或场景、未知参数、版本冲突及过期修订。相同请求重试返回原响应，JSON 对象键顺序不影响幂等判断。配置版本变化会显示 migration_required，确认参数并保存后方可解析。
- `POST /skills/resolve`：带 CSRF 的计划预览；后端固定补齐四项基础，只允许一个场景。自动选择是显式 Manifest 规则，记录选择原因，不宣称已运行 LLM Planner；不创建 Run、不调用模型。

内部 `RunPreparation.prepare` 在同一事务锁定 Thread、检查权限/幂等/活动 Run、冻结技能快照并保存用户消息；已通过真实数据库并发和重试测试。它尚未接入公共执行入口，前端开始分析保持禁用。

- `GET /research/{id}/reports`：当前 Tenant 项目的真实报告列表；没有报告时返回空数组。
- `GET /reports/{id}`：当前持久化版本、结构化章节/Claim、产物修订、质检历史和脱敏调用信息；不存在或跨 Tenant 返回 404。
- `GET /evidence/{id}`：原始引用、来源 URL、定位、采集时间和摘要/网页类型；需要有效身份和 Tenant 归属。

## 研究 Runtime 与真实联网验收

技能版本校验已兼容 Windows CRLF / Linux LF；旧版本内容和校验和保持原样，新 Run 引用实际保存的版本。技能加载失败会显示服务端原因，实际内容变化仍返回版本冲突。

`LocalRunExecutor` 是有界进程内任务管理器；独立于读取请求，有内部提交/取消/状态接口。Graph State 仅保存实体引用和受控审查结果；执行使用数据库冻结的指导、Schema 与工具许可。写入按 Run/阶段/修订的稳定 ID 去重，报告历史版本不覆盖。缺少证据、Schema 错误、供应商失败、超时或无变化的返工均不能伪装通过。运行时不执行任意代码；未配置 embedding 时证据工具为关键词/结构化检索。

```powershell
uv run python scripts/check_research.py
```

这是**手动、付费的真实模型/搜索调用**：创建 `spyglass_live_*` 临时库并迁移，用真实 Provider 执行合法竞品任务，读取报告和检查点，最后仅删除该临时库；不会在普通构建/测试中执行，也不在业务库预置账号。脱敏结果保存在忽略目录 `.artifacts/live-research.json`，不含 API Key 或登录令牌。

2026-10-20 联网过程实际观察到：兼容网关 `stream=false` 只返回 usage 帧，现已使用显式流式请求并收集正文/真实 usage；一轮采集 20 条证据、生成 5 节报告并执行质量返工，最终 240.47 秒因总预算保留 needs_review；另一轮 Planner 60.22 秒超时，明确保存不足报告。**没有把这些需复核结果宣称为质量通过或供应商稳定可用。** 默认全局 LLM 并发 3、单调用 60 秒、Run 240 秒、最多 2 次返工、本地容量 2；超时后最多 15 秒无模型清理，配置见 `.env.example`。本切片验收详见 `docs/slices/slice-3.md`。

契约变更后运行 `npm run api:types`，从 FastAPI OpenAPI 生成并格式化 `apps/web/src/types/api.generated.ts`。页面只通过 services 访问 API；TanStack Query 管理请求和会话状态，Zustand 保存草稿、模式和技能选择；切换账户及登出清理私有缓存及选择状态。

## 外部 API 配置验证

```powershell
uv run python scripts/check_providers.py
```

这是**手动真实联网**诊断，会对 `.env` 中指定的模型供应商发一次小请求，并使用 `DEEPSEEK3_API_KEY` 验证 DeepSeek Search，产生少量供应商用量；不会在普通测试/构建中执行。仅支持 DeepSeek Search 搜索与 OpenAI 兼容模型接口的 JSON/SSE 响应；模型请求并发执行，总超时 65 秒。只保存脱敏状态、真实 usage 与耗时到 `.artifacts/provider-check.json`，不记录请求头、密钥或模型隐藏推理。它不是应用的 ModelProvider，也不是报告生成实现。

2026-10-20 早期历史验证（Bocha 已移除）：当时已验证 Bocha、DeepSeek、GLM、DeepSeek2 均 HTTP 200 且有有效结果。两组 DeepSeek 原模型名不可用，已在本地 `.env` 修正为供应商实际列出的 `deepseek-v4.1-flash`；密钥未改。部分网关即使 `stream=false` 仍返回 SSE。简短响应的耗时不代表报告生成耗时，不将当次供应商成功作为长期可用性保证。

## 视觉与后续范围

九张原始图保留于 `references/`，标准英文副本在 `assets/references/`；manifest 保存文件名映射和哈希。首页采用白色/浅灰/深绿、232px 侧栏、欢迎区、输入框、六场景、模板及真实近期项目；侧栏没有场景技能。技能中心遵循原图 07 的概览、筛选、分类卡片结构，实际展示 6/4/3；版本/工具/Schema 及配置有真实服务。没有复制原图虚构使用量或多余行业技能。我的调研完整指标/活动布局在 Slice 5 接入，其余业务页面明确禁用。没有虚构运营统计、评论或报告。

用户新增性能要求已同步 PRD/TECHNICAL/prompt：Slice 3 的产品、定价、用户评价 LLM 已并发，有全局并发限制、单请求超时、Run 总预算；SWOT、Writer、Reviewer 按数据依赖汇合。实际并发重叠、截止时间和后端联网结果见 Slice 3 验收记录；前端提交到报告的完整链路仍由 Slice 4 接入。


## DeepSeek Search 原生来源

按用户 2026-10-20 要求，搜索已改为 DeepSeek 官方 `/v1/tools/search`，使用 `DEEPSEEK3_API_KEY`；聊天模型仍使用已有模型配置。应用不再读取 BOCHA 配置，也没有 Bocha 网络回退。本地旧 `.env` 可保留，示例环境文件已移除 Bocha 项。

LLM 内容只使用 `summary`；列表使用 `snippet`。`date` 是唯一发布时间来源，未知显示未知，有日期的有效证据优先近期。保存原始 `rerank_score`（0–3）和 `authority`（-1 未知、0–4）；来源置信度参考指数采用 70% 相关性归一化 + 30% 权威度归一化，未知评分不补值。这不代表事实真实性概率。相关性低于 1.5 或缺少长摘要的候选仍可查看，但不进入分析。详细协议见 TECHNICAL 第 16 节。

6 场景 Skill 升版 0.1.1，历史版本不改写。此变更没有宣称真实报告质量验收已通过：此前模型 3000 Token 输出截断的问题仍需单独修复，前端公开 Run/SSE 入口仍待 Slice 4。
