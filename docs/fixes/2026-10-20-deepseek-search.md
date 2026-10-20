# DeepSeek Search 切换与原生来源元数据验收

## 已实现功能

2026-10-20 按用户明确要求移除 Bocha 搜索适配及配置读取，搜索固定调用 `https://api.deepseek.com/v1/tools/search`，使用环境变量 `DEEPSEEK3_API_KEY`，无 Bocha 回退。LLM 仍使用既有聊天模型配置，产品/价格/用户评价的三路并发 LangGraph 分析保持不变。

- 模型证据 excerpt 只来自 summary（每条上下文最多 6000 字符），snippet 专供来源列表展示，content 不作为默认替代内容。原始字段保存在 Evidence 的 JSONB 定位元数据中，不把整段内容放入 checkpoint。
- 保存 title/url/snippet/summary/content/rerank_score/authority/date/site_name/site_icon，日期统一 UTC，发布时间仅使用 date，未知不推断。有日期的有效证据从近到远进入分析，未知日期后置。Collector 有查询长度限制、产品消歧、官方域名优先及近期查询操作符指导，Analyst 区分发布时间和采集时间。
- 来源指数采用 `round(0.7 * rerank_score / 3 + 0.3 * authority / 4, 4)`，命名为 `deepseek-native-weighted-v1`。分数未知则指数为 null。项目指数不是事实为真的概率，不为旧来源伪造评分。
- 相关性低于 1.5/未知或 summary 缺失的候选保存为 rejected，供审查但不作为正常分析/Claim 引用证据。仅权威度较低不会自动排除用户评论。
- 6 场景 Skill 升版 0.1.1，其他 7 个版本不变；历史 0.1.0 的工具许可名兼容映射到 DeepSeek，不实现 Bocha 请求、不改写冻结快照。
- Report/Evidence 只读 API、生成的 TypeScript、既有报告来源面板同步支持上述字段；历史报告缺少字段时显示未知。API 错误只暴露稳定错误码。
- 搜索共享并发上限 3，启动间隔至少 0.21 秒，单调用请求/排队预算 30 秒，无自动重试。此为单 API 进程节奏控制，不声称实现多进程账户级限流。

## 修改的关键文件

- `apps/api/app/agent/tools/registry.py`：真实搜索工具、权限、速率和错误边界。
- `apps/api/app/domain/search.py`：原生字段及来源指数。
- `apps/api/app/agent/agents/collection.py`、`analysis.py`：Collector/Analyst 时效提示与 summary 路径。
- `apps/api/app/infrastructure/research_store.py`：候选入库、过滤、原生日期排序及模型上下文精简。
- `apps/api/app/domain/report_schemas.py`、`infrastructure/report_repository.py`：租户隔离的来源读回。
- `apps/web/src/features/reports/ProjectReports.tsx`、`types/api.generated.ts`：来源列表和证据面板。
- `.env.example`、健康服务、6 场景 manifests、诊断脚本和根目录技术文档同步修改。

## 数据库/API/前端联调结果

真实 PostgreSQL 临时库从空库迁移至 `0005_langgraph_checkpoint`；测试候选幂等入库、日期排序、拒绝原因、API 原始数值及其他租户 UUID 访问 404 均通过。正常模型上下文不含 UI snippet/content，低相关性候选不能成为 Claim 支持证据。

浏览器测试使用隔离合成报告，不写入正常业务库。来源面板显示 2.4/3、4/4、86.0/100 和原生发布时间；截图 `.artifacts/screenshots/deepseek-source-metadata.png` 已实际打开检查，无明显溢出。前端主操作、刷新、报告修订和移动视口检查通过。

`docker compose up -d --build api web` 成功。部署后 Web HTTP 200，`/api/v1/health/ready` HTTP 200，PostgreSQL/Redis/pgvector/migrations 均 ok，DeepSeek 模型与搜索配置均 configured（配置状态本身不等于长期连通保证）。未认证 `/skills` 仍正确返回 401。现有数据库目录只读校验：13 个当前定义、6 个待首次正常目录读取注册的新版本、0 个同版本冲突；现有旧场景租户配置数为 0，无需迁移用户配置。

## 测试命令与真实结果

| 命令 | 实际结果 |
| --- | --- |
| `uv run pytest apps/api/tests/unit/test_deepseek_search.py -q` | 首轮旧实现 RED：6 failed；实现后首轮 6 passed；补齐权限/格式/并发案例后 11 passed |
| `uv run pytest apps/api/tests/integration/test_search_evidence.py apps/api/tests/integration/test_research_runtime.py -q` | 8 passed，20.24 秒 |
| `uv run pytest -q` | 最终 98 passed，104.94 秒；含真实数据库迁移、租户、并行图和返工测试 |
| `uv run ruff check apps/api scripts/check_search.py scripts/check_providers.py scripts/check_research.py` | All checks passed |
| `uv run ruff format --check apps/api scripts/check_search.py scripts/check_providers.py scripts/check_research.py` | 93 files already formatted |
| `uv run mypy` | 66 source files 无错误 |
| `npm run api:types` | OpenAPI 与 TypeScript 生成成功 |
| `npm run lint`、`npm run format:check` | 均成功 |
| `npm run test` | 3 files，7 tests passed |
| `npm run build` | 成功；主包 527.34 kB，有大于 500 kB 的非阻断构建警告 |
| `npm run test:e2e -- --workers=3` | 10 passed，22.0 秒 |
| `npm run test:e2e -- --workers=3 tests/e2e/reports.spec.ts` | 来源面板截图复验 1 passed，15.9 秒 |
| `uv run alembic -c apps/api/alembic.ini check` | No new upgrade operations detected |

中间静态检查曾发现 Pydantic computed property 的 mypy 限制，以及 API 默认数组在生成类型中为可选字段；已分别添加限定类型说明和前端空数组兼容，最终类型检查与构建成功。独立 reviewer 检查租户/密钥/历史版本/summary 路径，未发现阻断交付的重要缺陷；其结论不替代主任务执行的测试。

## 真实联网结果

首先使用用户提供的端点与密钥实际返回 HTTP 200，5 条原生结果，1.138 秒，脱敏公开结果保存在 `.artifacts/deepseek-search-preflight-20261020T135610Z.json`。

随后 `uv run python scripts/check_search.py` 使用已实现的正式 ToolRegistry 并发查询三组官方来源：

| 查询 | 条数 | 含 summary | 相关性达到 1.5 | 已知 date | 耗时（含共享排队） |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cursor AI code editor pricing site:cursor.com | 5 | 5 | 5 | 1 | 0.719 秒 |
| Claude Code pricing site:claude.com | 5 | 5 | 5 | 5 | 1.064 秒 |
| Windsurf AI code editor pricing site:windsurf.com | 5 | 5 | 5 | 5 | 1.150 秒 |

本轮总耗时 1.151 秒，15 条结果；4 条未知日期保持 null。原始公开结果和指数保存于 `.artifacts/deepseek-search-adapter-20261020T141332Z.json`。没有进行额外模型报告调用，没有把联网搜索成功当作完整报告成功。

接口字段和查询语法以 [DeepSeek 官方搜索文档](https://api-docs.deepseek.com/zh-cn/api/search/) 为依据；评分阈值仅作检索筛选，不能保证来源事实为真。

## 仍未实现或待确认内容

此前真实报告运行的 3000 Token 输出截断问题没有在本次搜索切换中修复；尚未获得完整真实报告质量验收通过的结果。公共 Run/SSE 和前端输入到执行链路仍为 Slice 4，开始分析继续明确禁用。PDF/完整报告中心等仍待后续切片。多进程共享搜索配额仍需后续调度，不提前宣称完成。

## 下一切片建议

先单独修复模型输出预算/截断诊断与结构化响应稳定性，在新搜索证据下进行一轮真实报告质量验收；之后继续 Slice 4 的公开 Run、取消、SSE 与前端实际执行链路。保留并发 LLM 与 Run 总预算，不以无限重试掩盖失败。
