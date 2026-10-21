# Slice 4 验收记录 — 2026-10-21

## 已实现功能

- 公开 Run 创建/查询/历史/SSE/取消接口，与真实有界 LocalRunExecutor 和 LangGraph 联通；幂等重放、同 Thread 活动互斥、Tenant 归属、CSRF 和错误协议实际生效。
- 0006 迁移持久化事件、节点步骤、工具调用。Run 行锁分配 seq，终态、最终消息与 terminal 事件同事务；订阅撤销登录后停止，断流不取消运行，重连按 Run 游标去重。当前 Graph 无人工中断，resume 明确 409，界面没有伪恢复功能。
- 工作台提交真实 Project/Thread/Run，双栏会话展示消息、真实阶段/事件、结构化报告和来源；刷新恢复。取消需确认，失败保留状态及错误；未配置或容量满在创建前拒绝，重启遗留运行明确失败。
- 通用检索和报告提示词，不绑定产品、厂商、域名；工作台模板使用待替换占位符，未替换前明确禁用提交。搜索逐产品覆盖产品/价格/评价，最多一次低相关/空结果改写，不因供应商错误无限重复收费请求。六场景任意动态产品名覆盖有单元测试。
- LLM 使用 summary 内容；前端显示 title、snippet、完整 URL、UTC date、site_name/site_icon（失败/缺失有默认图标）、rerank_score、authority 和自定义来源指数。原始摘要保留；模型上下文按产品/类别轮转并标记超长前缀截取。
- 角色预算、截断识别、显式模型选择和可选 thinking 参数；产品/价格/评价仍并发。Writer 生成独立结构化 outline，服务器无损映射已保存 Claim；Reviewer 输入去除重复大字段，质检不降门槛。提示词 v5 补强价格类型、币种单位、产品/版本与引用一致性。

用户要求停止子代理后，所有后续开发、修复、联调和最终代码审查由主代理直接完成。没有重新启动子代理。

## 修改的关键文件

- `apps/api/alembic/versions/0006_run_events.py`、`app/infrastructure/database/events.py`：迁移、外键、唯一约束和状态约束。
- `app/{api/runs,application/runs,application/run_events,domain/run_schemas}.py`、`infrastructure/{event_store,run_read_repository,research_store}.py`：公开协议、权限、顺序与生命周期。
- `app/agent/agents/{prompts,queries,collection,analysis,reporting}.py`、`runtime/{context,evidence_context,graph,executor,contracts}.py`、`infrastructure/providers/chat.py`：通用提示词、上下文、并发观测及真实调用错误。
- `apps/web/src/pages/{Workbench,ResearchSession,ResearchProjects}.tsx`、`features/runs/`、`features/reports/ProjectReports.tsx`、`services/{runs,launch}.ts`、`styles/index.css`：真实入口、双栏、SSE、来源显示和响应式。
- 生成的 `types/api.generated.ts`、后端集成/单元测试、`tests/e2e/slice4-session.spec.ts`、隔离 `tests/e2e_app.py`、诊断脚本与 README/TECHNICAL/prompt。

## 数据库/API/前端联调结果

开发 Compose 已迁移至 `0006_run_events`，保留既有账户和报告。最终 readiness HTTP 200，PostgreSQL/Redis/pgvector/migrations 均 ok，research_available=true。配置存在不代表外部供应商稳定可用。当前服务 http://127.0.0.1:8080。

普通浏览器测试使用新建 `spyglass_e2e_*` 数据库、真实 API/Graph 和显式受控 Provider；生产 app 不导入 fixture。新增两项浏览器测试验证提交到四核心报告、消息/事件/报告刷新恢复与无重复、手机无横向溢出，以及取消确认/持久终态。已有报告、鉴权、Skill 和租户隔离浏览器测试继续保留。

正常业务账户另用公开 API 进行了四轮付费联网运行，结果可在该账户读取，均不是测试 fixture：

| 轮次                    | 耗时      | 实际结果                                                                                                                     |
| ----------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------- |
| 1：原兼容网关           | 93.65 秒  | 5 章节、67 条 Claim，needs_review；结构化整理/Writer/Reviewer 有错误，作为真实历史保留。                                     |
| 2：原兼容网关           | 16.39 秒  | Planner 传输错误、0 Claim；当时按旧语义保存 needs_review，后续已回归修正“采集前失败”为 failed，不篡改历史。                  |
| 3：DeepSeek3 默认思考   | 241.82 秒 | 多次 6000 Token 输出截断、最终 Run 总预算，0 Claim，needs_review。未把截断 JSON 拼补为成功。                                 |
| 4：DeepSeek3 显式非思考 | 125.51 秒 | 5 章节、63 条 Claim、145 个来源候选、347 条持久化事件；未再截断，但定价 Schema 和跨产品引用等质检仍失败，最终 needs_review。 |

第四轮三个基础分析调用实际开始于 02:06:36.66–36.68 UTC，分别于 42.50、45.09、46.40 结束，存在真实并发重叠。全程 28 次已知模型调用，供应商返回 total_tokens 合计 779398，不推断费用或缓存折扣。最多两次真实返工；质检问题没有被清空以强行通过。

真实报告：Run `3b5c81b5-0189-4ae6-b806-d0528076f8bd`，Report `48a30c10-b9ce-54ff-b93f-1bd564c069a0`，Thread `d0a8fc87-f32e-4364-a9a1-f38763dba3a5`。正常账户浏览器已打开该报告，验证 5 章节、两条消息、145 个来源候选、刷新恢复、站点/URL/UTC 字段和手机无横向溢出，pageerror=[]。

第四轮为 v4 Prompt；其后依据实际错误补强到 v5，自动测试通过，但**没有再执行付费联网验证 v5 的报告质量**。不承诺修改提示词即可保证任意产品都命中足够网页或质量通过。

检索另测 9 查询/45 候选约 3.60 秒，产品/定价首条多为官方文档，评价来源仍参差；组合限定站点的实验曾全部空结果，未将这些限制写入生产。低于 1.5 的候选保留可查但不进入分析。

## 测试命令与真实结果

| 命令                                                                                 | 真实结果                                                             |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| `uv run ruff format --check apps/api scripts` / `uv run ruff check apps/api scripts` | 格式及 lint 通过；114 个文件。                                       |
| `uv run mypy`                                                                        | 76 个源码文件通过。                                                  |
| `uv run pytest -q`（完整验证脚本内执行）                                             | **143 passed in 168.43s**。                                          |
| `uv run alembic -c apps/api/alembic.ini check`                                       | No new upgrade operations detected；完整测试包含空库升级/降级/升级。 |
| `npm run api:types`                                                                  | OpenAPI 导出并生成 TypeScript 成功。                                 |
| `npm run format:check` / `npm run lint` / `npm run typecheck`                        | 均通过。                                                             |
| `npm test`                                                                           | **6 files / 15 tests passed**。                                      |
| `npm run build`                                                                      | 成功；JS 555.25 kB / gzip 173.13 kB，有 >500 kB 非失败警告。         |
| `npm run test:e2e`（Docker 恢复后重跑）                                              | **12 passed (37.5s)**，退出码 0。                                    |
| 忽略目录的真实账户 Playwright 读回脚本                                               | 退出码 0；桌面/来源/手机截图，真实报告仍为 needs_review。            |

早期全量后端曾为 142 pass / 1 fail：0.15 秒计时窗口在新增真实 DB 事件写入后过早到期，尚未进入慢分析节点。测试改为 1 秒并增加三个分析实际进入的断言，定向测试通过，随后完整 143 通过；未删除测试或放宽生产截止时间。

完整 `scripts/verify.ps1` 本轮最终因浏览器阶段基础设施故障退出 1：12 个注册请求均因 Redis 不响应返回 503，PostgreSQL 清理连接也超时，Docker 查询同时挂起。恢复 Docker Desktop/Compose 后 readiness 200，单独重跑全部 E2E 为 12/12 通过。不能将第一次验证脚本声称为整体退出 0；各项最终实际结果如上。

## UI 原图、安全和数据真实性

对照原图 03 保留白/浅灰/深绿、左消息与真实步骤、右报告 Tabs、底部输入及移动面板；Sidebar 无场景卡。动态效果为真实状态和报告保存后的展示，未伪造逐 Token 文本或固定百分比。截图在忽略目录 `.artifacts/screenshots/slice4-live-{desktop,sources,mobile}.png`；抓取手机截图等待侧栏 CSS 动画结束，避免过渡帧造成假裁切。

权限测试覆盖未登录、跨 Tenant/同 Tenant 不同 Run 的游标、猜 UUID、SSE 会话撤销、CSRF、幂等、并发和取消。真实模型错误仅留安全代码/Schema 路径，未保留错误字段原始值、密钥或隐藏推理。来源指数不是事实真实性概率，未知日期/用量不补值。既有报告固定 Skill 版本与历史证据，不因新 Prompt 改写。

## 仍未实现或待确认内容

- 真实联网报告质量尚未通过；v5 对定价格式及跨产品引用的改善仍需下一轮有针对性的联网验证。
- PDF、编辑/版本冲突、完整竞品档案/竞争情报/报告/Trace 中心、真实时间序列图和上传待 Slice 5–6；界面明确禁用，不宣布 v0.1 完成。
- 无人工审批/恢复节点，无跨进程可靠恢复/队列/Worker，SSE 为单进程数据库轮询。暂未拆分 >500 kB 前端主包。

## 下一切片建议

按 prompt.md 进入 Slice 5 前，先用通用 Schema 与引用边界回归验证定价及产品对应关系，再做有针对性的真实质量验收；保留 needs_review。随后接入真实报告中心/编辑版本与 PDF、竞品/来源查询和运行追踪，复用现有租户实体与事件协议。
