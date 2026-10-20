# Slice 0 验收记录 — 2026-10-20

## 已实现功能

- React 19 + TypeScript + Vite + TailwindCSS 可运行入口，React Router、Zustand 草稿/模式状态、TanStack Query 真实健康请求、Framer Motion 入场与悬停动效，并尊重减少动态效果设置。
- FastAPI 版本化公开健康 API、Pydantic 响应、统一安全错误、请求 ID、CORS 白名单。错误格式保留 405 的 Allow 等必要响应头，不返回验证输入或内部异常。
- SQLAlchemy/psycopg 异步 PostgreSQL 与 Redis 资源生命周期；有界探针超时。Windows 显式 selector loop；本地默认 IP 避免 localhost IPv6 连接拖延。
- Alembic 初始迁移真正安装 pgvector；无 create_all。业务表与认证将在 Slice 1 建立。
- Docker Compose 四服务、Nginx 同源代理、依赖健康门槛、数据库/Redis 命名卷、固定基础镜像版本和依赖锁；数据库/Redis 固定 digest。
- 九张参考图逐张阅读，原始文件保留；标准路径副本与原图 SHA-256 一致，manifest 保存尺寸和映射。

## 修改的关键文件

- `apps/api/app/{core,application,infrastructure,api}`：配置、错误、事件循环、资源、健康服务及路由。
- `apps/api/alembic`、`apps/api/tests`、`pyproject.toml`、`uv.lock`：真实迁移、测试和锁定工具链。
- `apps/web/src/{layouts,pages,features,services,stores,styles,types}`：首页基线、真实 API 状态、生成契约。
- `tests/e2e/baseline.spec.ts`、`playwright.config.ts`、`scripts/verify.ps1`：可复现的自动验收。
- `docker-compose.yml`、`infra/docker/*`、`.env.example`、`.gitignore`、`README.md`。
- `PRD.md`、`TECHNICAL.md`、`prompt.md`：同步用户要求的并发 LLM 分析与时间预算；`DESIGN.md` 补充参考文件映射。

## 数据库/API/前端联调结果

本地开发前端以及 Compose Web 都已访问真实 API。容器 Web `/` 返回 200，`/api/v1/health/ready` 返回 200，四项依赖均为 `ok`。API、PostgreSQL、Redis 健康；Web 正常运行。没有私有资源 API，也没有宣称已实现认证或租户隔离。

初始迁移已在开发数据库执行到 `0001_pgvector (head)`。集成测试另外创建随机空库，确认迁移前 readiness=503，升级后 readiness=200，pgvector 运算与 Redis PING 成功，downgrade/base 与再次 upgrade/head 成功；只清理测试创建的数据库。

## 测试命令与真实结果

完整入口 `pwsh -File scripts/verify.ps1` 已执行，退出码 0，最终输出 `All Slice 0 verification commands passed.`

| 命令 | 实际结果 |
|---|---|
| `uv run ruff format --check apps/api scripts` | 21 files already formatted |
| `uv run ruff check apps/api scripts` | All checks passed |
| `uv run mypy` | 12 个源文件，无问题 |
| `uv run pytest -q` | 15 passed，包含真实基础设施集成测试 |
| `npm run format:check` | 所有匹配文件符合 Prettier |
| `npm run lint` | ESLint 退出 0 |
| `npm run typecheck` | TypeScript 退出 0 |
| `npm test` | 1 个测试文件、3 项通过 |
| `npm run build` | Vite 8.3.4 构建成功；JS 489.89 kB（gzip 155.75 kB） |
| `npm run test:e2e` | 本地 Vite + 真实 API：2 passed |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080 npm run test:e2e` | Compose Web + Nginx + API：2 passed（PowerShell 通过 `$env:` 设置） |
| `docker compose --progress plain up -d --build` | Web/API 镜像构建、四服务启动成功 |
| `docker compose config -q` | 退出 0，无配置错误 |
| `uv run alembic -c apps/api/alembic.ini current` | `0001_pgvector (head)` |
| `npm run api:types` | 从真实 OpenAPI 生成并格式化 TS 类型 |

测试过程中真实出现并修复的问题：健康路由/错误契约尚未实现、配置根目录错误、Windows Proactor 与 psycopg 不兼容、错误处理丢失 Allow 响应头、响应头 Mapping 类型不匹配。没有删除测试绕过问题。独立审查发现的 Allow 头问题通过新增测试先复现，再修复，完整验证重新通过。

非失败提示：Playwright 的 NO_COLOR/FORCE_COLOR 冲突、开发模式减少动态效果提示，以及一次 Vite 插件耗时提示；不影响退出码和断言。首轮 ghcr uv 镜像下载缓慢，改用 Python 镜像内安装相同固定版本 uv；锁文件和架构不变。

## 外部 API 真实调用

手动执行 `uv run python scripts/check_providers.py`，四组配置并发执行，全部 HTTP 200 且有有效结果：

| 配置 | 结果 | 当次耗时 |
|---|---|---:|
| Bocha | JSON，1 条带 URL 的真实搜索结果 | 0.46s |
| DeepSeek | `deepseek-v4.1-flash`，SSE，有内容，真实 total_tokens=10 | 8.21s |
| GLM | `glm-5.3-flash`，SSE，有内容，真实 total_tokens=20 | 7.49s |
| DeepSeek2 | `deepseek-v4.1-flash`，SSE，有内容，真实 total_tokens=10 | 3.11s |

原 DeepSeek 模型名 `deepseek-v4-flash` 分别引发 503/404 `model_not_found`；读取供应商模型列表后，实际调用 `deepseek-v4.1-flash` 成功，再只修改本地两处模型名。GLM 首轮因网关返回 SSE 被 JSON 解析拒绝，按 SSE 解码后成功。模型列表的一次请求超时并未被当作模型生成成功；后续真实生成请求已成功。上述仅为简短 API 连通性验证，不是完整调研报告或长期可用性保证。

用户随后新增两组配置，独立并发进行三轮简短流式请求，每轮输入为 `Reply with exactly OK.`、max_tokens=32。六次请求全部 HTTP 200 且有有效正文，未修改这两组配置；首字计时只看正文 content，不读取/展示隐藏推理内容。结果保存在本地 `.artifacts/provider-latency-check.json`：

| 配置 | 正文首 Token 中位时间 | 完整响应中位时间 | 完整响应范围 |
|---|---:|---:|---:|
| DEEPSEEK3 / deepseek-flash | 0.683s | 0.697s | 0.632–0.892s |
| GLM2 / glm-5.3-flash | 2.881s | 2.882s | 2.816–4.230s |

这是三次小样本短响应延迟，不是吞吐量/报告生成性能评测，不可直接外推长报告耗时。

## UI 原图对照与偏差

已对照工作台原图检查 232px 侧栏、62px 顶栏、欢迎/输入区域、浅色技能卡、四模板和底部区域；侧栏没有场景技能。桌面 1672×941、手机 390×844 截图保存在本地忽略目录 `.artifacts/screenshots/`。手机无横向溢出，菜单、焦点输入可用。

此切片仅为视觉基线：无认证用户名，显示访客；六场景只作预览，尚不进行 Registry 配置；近期研究为空态；真实健康状态取代原图未有业务数据可支持的统计卡。首页下方内容仍需滚动，其余八页尚未实现，不宣称视觉整体验收完成。后续在 Slice 1/2/5/6 持续校准。

## 安全、来源与未完成内容

`.env`、虚拟环境、node_modules、运行日志及诊断产物均忽略。真实密钥不进入前端、镜像或提交；`.env.example` 仅为本地开发占位配置。没有虚构评论、价格、项目、趋势、证据数或 Token。公开健康 API 不访问模型，UI 的 provider 配置标记不自动宣称已联网验证。

仍未实现：注册/登录/默认 Tenant/业务表与权限、13 个可执行 Skill、LangGraph 四 Agent 与 Checkpointer、并发研究运行/时间预算、SSE、取消/恢复、证据/报告存储与 PDF。**v0.1 尚未完成，输入到报告的完整链路尚未验收。**

## 下一切片建议

按既定顺序进入 Slice 1：认证、默认个人 Tenant、成员关系及基础业务迁移、真实登录态和视觉 Shell；使用真实 PostgreSQL 进行跨账户隔离测试。Slice 3 必须并发执行独立 LLM 分析，并用真实 Trace 起止时间验证重叠、并发上限与总截止时间。
