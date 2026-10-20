# Slice 3 验收记录 — 2026-10-20

## 已实现功能

- 真实 LangGraph StateGraph、PostgreSQL Checkpointer、独立专业模型调用与结构化交接：Planner → Resolver → Collector → Normalizer → Analyst → Writer → Reviewer。四核心全部保存有效产物或显式不足；按冻结配置执行增强分析。
- 产品能力、定价、用户评价独立调用并发；SWOT 与无相互依赖的增强分析并发，战略建议等待依赖。共享 LLM 并发上限默认 3，单调用含排队超时 60 秒、Run 总预算 240 秒、本地运行容量 2、最多返工 2 次；超时后最多 15 秒无模型清理。
- 兼容 Chat Completions JSON/SSE Provider；显式流式请求，读取实际正文和 usage，未知用量为 null。Bocha 检索、受限网页获取、去重及租户证据检索实际执行。未配置 embedding 时使用关键词/结构化检索。
- 实际可查询的来源、证据、竞品快照、评论、分析修订、Claim/ClaimEvidence、报告版本、质检和调用记录。事实 Claim 引用本轮有效证据；搜索摘要与网页原文分开标注；未找到不等于明确不支持。
- 评论逐字引用与去重；同页多个评论分别匹配 fingerprint；整体正/负/中/混合中 mixed 计入分母一次，方面分别计数；返工后的统计读取最新分析修订，保留未分类样本数。无合法评论时零样本且显式不足。
- Reviewer 保存问题、target 和真实内容摘要，定向回到 Collector/Analyst/Writer；保留修复前后产物。仅 Claim ID 变化不能被当作修复，仍有问题或无变化进入 needs_review。
- 内部有界 Executor 的提交、取消、状态与退出清理；初始化/清理错误不会在数据库正常时留下假 running。公开 Run API/SSE 尚未开放。
- 认证的报告列表、报告详情与证据读取 API；项目详情可刷新/选择报告、查看真实章节、证据、分析修订、质检及调用耗时/用量，刷新仍可读回。主操作有加载、空态、错误和禁用原因。

## 修改的关键文件

- `apps/api/app/agent/runtime/{contracts,state,context,graph,checkpoint,executor,sentiment}.py`：类型、工作流、并发、状态与持久化执行。
- `apps/api/app/agent/agents/{collection,analysis,reporting}.py`：各专业角色与结构化交接、定向返工。
- `apps/api/app/agent/tools/{registry,fetch}.py`、`infrastructure/providers/chat.py`：工具许可、Bocha、SSRF/robots 防护与模型适配。
- `infrastructure/{research_store,report_repository}.py`、`infrastructure/database/knowledge.py`：租户数据与报告版本；`application/run_preparation.py` 保存实际请求。
- `apps/api/alembic/versions/0004_research_runtime_persist_research_evidence_analysis.py`、`0005_langgraph_checkpoint.py`：业务数据和独立 SDK 检查点迁移。
- `apps/api/app/{api/reports,application/reports,domain/report_schemas}.py`、`apps/web/src/{services/reports,features/reports/ProjectReports,pages/ResearchProjects}` 与生成类型：最小前后端读回。
- `apps/api/tests/{unit/test_runtime_adapters,unit/test_checkpoint_migration,integration/test_research_runtime,integration/test_runtime_review_regressions}.py`、隔离 fixtures、`tests/e2e/reports.spec.ts` 和 `seed_report.py`：真实基础设施与浏览器验收。
- `scripts/check_research.py`：显式付费联网诊断；README、TECHNICAL、技能说明、`.env.example`、计划和依赖锁同步。

## 数据库/API/前端联调结果

开发数据库已在线升级至 `0005_langgraph_checkpoint`，不删除原业务数据。0004 新增 12 张实际业务表，0005 在独立 langgraph schema 使用 SDK 初始化。SDK 含并发索引，只在部署迁移初始化；并发两 Thread 不再执行 setup。0005 明确拒绝离线 `--sql`，在拒绝前不连接数据库；空库迁移、降级/升级及 Alembic check 均实际执行。

只读 API：GET `/api/v1/research/{project_id}/reports`、`/reports/{report_id}`、`/evidence/{evidence_id}`。未登录 401、跨租户猜 UUID 404；Schema 与 OpenAPI 生成 TS 同步。浏览器在独立 `spyglass_e2e_*` 数据库运行真实 Graph 和受控模型/工具，读取四核心报告、打开证据、查看两轮质检及修订、刷新恢复，并通过手机无水平溢出检查。测试数据明确标注 synthetic/fixture，不进入正常业务库。

Compose API/Web 已重建，服务入口为 http://127.0.0.1:8080。最终 PostgreSQL/Redis/API 均 healthy，Web 运行；根页面 HTTP 200、readiness HTTP 200/ready、未登录报告读取 HTTP 401/unauthorized。没有向正常业务数据库预置测试报告。

### 真实联网结果（不是 fixture）

使用 `uv run python scripts/check_research.py`，每次创建、迁移并清理独立 `spyglass_live_*` 数据库。任务为 Cursor、Claude Code、Windsurf 的合法公开竞品调研。共执行三轮，未继续重复请求以追求成功结果：

| 轮次 | 实测                                                            | 结论                                                                                                                                                       |
| ---- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | 46.92 秒；0 条证据、5 节报告、读取 HTTP 200                     | 兼容网关在 stream=false 时只返回 usage SSE 帧。已改显式 stream=true，并补正文/最终 usage 帧回归测试；本轮仍为 needs_review。                               |
| 2    | 240.47 秒；20 条真实证据、5 节报告、2 条质检记录、读取 HTTP 200 | 实际执行模型/搜索/网页与返工；三项核心模型调用同时开始，耗时分别 15.01/16.78/24.48 秒。达到 Run 总预算后保存 needs_review 报告；未找到合法评论保持零样本。 |
| 3    | 60.22 秒；0 条证据、5 节报告、读取 HTTP 200                     | Planner 单调用超时，保存显式不足/needs_review，不继续无意义模型调用。                                                                                      |

以上均未取得质量通过的真实报告，不代表供应商稳定可用。第二轮出现 Reviewer 非法 JSON 及后续可操作问题，后续 Collector 返工被总预算停止；未编造价格或评论来补齐。当前忽略目录 `.artifacts/live-research.json` 只保留最后一轮脱敏结果，早两轮耗时来自本次真实执行输出，未声称保存了全部历史 JSON。后端“有来源或显式不足”符合当前切片门槛；稳定高质量报告和前端输入链路仍需后续验证。

## 测试命令与真实结果

完整 `pwsh -File scripts/verify.ps1` 实际退出码 0，包含：

| 命令                                                         | 实际结果                               |
| ------------------------------------------------------------ | -------------------------------------- |
| `uv run ruff format --check apps/api scripts` / `ruff check` | 格式与 lint 通过                       |
| `uv run mypy`                                                | 65 个源码文件通过                      |
| `uv run pytest -q`                                           | 当时 **83 passed in 97.00s**           |
| `uv run alembic -c apps/api/alembic.ini check`               | No new upgrade operations detected     |
| `npm run format:check` / `lint` / `typecheck`                | 全部退出码 0                           |
| `npm test`                                                   | **3 files / 7 tests passed**           |
| `npm run build`                                              | 成功，主 JS 525.91 kB / gzip 165.18 kB |
| `npm run test:e2e`                                           | **9 passed (17.2s)**                   |
| `npm run api:types`                                          | 成功生成 OpenAPI TypeScript 类型       |

完整检查后增加了 0005 离线保护及回归测试，最终再次执行：

| 命令                                                                                  | 最终实际结果                                  |
| ------------------------------------------------------------------------------------- | --------------------------------------------- |
| `uv run pytest -q`                                                                    | **84 passed in 93.92s**                       |
| `uv run ruff format --check apps/api scripts tests/e2e/seed_report.py` / `ruff check` | 92 files already formatted；All checks passed |
| `uv run mypy apps/api/app`                                                            | 65 个源码文件通过                             |
| `uv run alembic -c apps/api/alembic.ini check` / `current`                            | 无新操作；`0005_langgraph_checkpoint (head)`  |
| `docker compose up -d --build api web`                                                | 最终代码重建并启动成功                        |

另外，文档格式问题已用 Prettier 修复。53 个暂存文件与前端 bundle 扫描未检出 `.env` 中实际 API Key/Secret，`.env` 未跟踪，扫描未输出密钥值。

离线迁移回归另外做了撤回保护 → 测试失败 → 恢复保护 → 测试通过，连接目标固定为本机不可用端口，不接触业务数据库。首次异步运行因修复已进入进程而通过，不作为 RED 证据；后续受控撤回才验证保护确实必需。

测试覆盖真实并发重叠及容量限制、超时停止模型、两个 Thread 状态/检查点隔离、立即取消与初始化取消、初始化/清理失败终态、缺证据/错误 Schema/矛盾信息的真实定向返工、无变化降级、mixed/多方面/去重、同页多条评论、最新修订分母、跨租户报告/证据拒绝，以及空库迁移。开发中曾发现并修复多评论合并、跨字段价格校验缺失、旧情感分类残留、重定向绕过 robots、初始化异常停留 running、取消被覆盖和并发检查点 setup 死锁。没有删除失败测试规避问题。

非失败提示：Vite 主包仍超过 500 kB，路由拆包尚未完成；测试环境颜色及 reduced-motion 提示不影响退出码。

## UI 原图对照与偏差

本轮查看原图 03/09，结合既有九张设计基准，沿用白底、浅灰分隔、深绿与固定侧栏；场景仍在工作台输入框下方。实际检查 `.artifacts/screenshots/slice-3-report.png`：已保存报告、章节、证据入口、结构化折叠和两轮质量记录可见。Playwright 包含桌面与 390px 手机检查。

当前在既有项目详情中加入最小读回，不宣称完成原图 03 的聊天/报告双栏、完整图表或原图 09 的全量 Trace 页面，也未宣称像素级一致；这些分别属于 Slice 4/5。截图为明确标注的隔离 synthetic 报告，不是业务联网结果。

## 安全/来源/数据真实性检查

- 所有私有读写按服务端 TenantContext 过滤，复合外键阻止跨租户/Run 关联；冻结 Skill 版本/校验和/Schema/工具白名单实际参与执行。
- web_fetch 验证协议、域名、所有 DNS 地址和每次重定向目标，固定已验证 IP，保留 Host/TLS SNI；逐跳 robots、类型/大小/超时有限。robots 本身重定向拒绝访问。
- 外部材料作为不可信数据；不允许技能读取环境密钥，不记录隐藏推理。审计记录角色/工具、Prompt 版本、哈希、真实耗时/usage 和脱敏错误。
- Fixture 仅在测试目录/隔离数据库使用；正常生产模块无 fixture 开关。`.env` 不入库、不改写或打印密钥，前端 bundle 与暂存内容提交前扫描。

## 仍未实现或待确认内容

- 尚无公开 Run 创建、SSE、取消/恢复接口与前端输入执行链路；开始分析明确禁用，Slice 4 接入。刷新可读已保存报告，不代表实时事件恢复已实现。
- 当前真实联网仍因供应商超时/输出质量进入 needs_review；不得将其宣布为质量验收通过、稳定完整报告或 v0.1 完成。
- 自动增强选择仍为显式 manifest_rules；真实 Planner 提取竞品和研究范围，未宣称已实现模型智能 Skill 选择。
- 尚无跨进程可靠队列、异常进程退出后的任务重建或分布式恢复；内部检查点读取仅定位 Thread 最新 Run，历史报告由业务版本保留。
- 完整竞品档案/报告/情报/追踪页面、报告编辑/PDF、真实时间序列图、文件上传/向量检索及 v0.1 综合安全验收在后续切片。当前不构造虚假 embedding 或统计。

## 下一切片建议

Slice 4：公开有幂等和租户权限的 Run 创建/查询/取消/恢复与事件持久化/SSE，将既有 LangGraph 节点和调用记录适配为统一事件；接入原图双栏，打通工作台提交 → 并发研究 → 实时报告 → 刷新恢复。重点验证断线不取消、游标去重、跨租户订阅拒绝和当前真实供应商超时反馈。
