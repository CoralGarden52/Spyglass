# Spyglass — Codex 主开发提示词（prompt.md）

> 使用方式：把本文件与 `PRD.md`、`TECHNICAL.md`、`DESIGN.md`、`AGENTS.md` 放入 Spyglass 仓库根目录，把 `assets/references/` 九张图片保留原样。将下方「启动任务」复制给 Codex。后续使用「切片指令」逐项推进；这些是功能顺序和验收门槛，不是开发排期。**请实际修改代码并运行测试，不要只输出设计方案或生成空目录。**

## 一、启动任务（直接复制给 Codex）

你现在是 Spyglass 的全栈工程负责人和 Coding Agent。请从当前仓库实际状态出发，开发一个具有可扩展架构的竞品分析 Agent MVP。

### 必读资料与优先级

1. 阅读仓库根目录 `AGENTS.md`、`PRD.md`、`TECHNICAL.md`、`DESIGN.md`、`prompt.md` 全文，并逐张查看 `assets/references/01-workbench.png` 至 `09-trace-detail.png` 的原图。
2. `PRD.md` 决定范围和用户流程，`TECHNICAL.md` 决定架构/Schema/API，`DESIGN.md` 与图片决定视觉，`AGENTS.md` 决定编码、测试和验收规则。遇到矛盾不要自己删除要求，要明确指出并提议最小一致化修正。
3. 开始之前先检查现有 `git status`、代码/目录、依赖、Docker 及可运行工具链；不得删除/覆盖未读的既有用户代码。

### 必须达成的产品结果

- 用 React 19 + TypeScript + Vite + TailwindCSS + Zustand + React Router，配合 ReactFlow、ECharts（必要时 D3）、Framer Motion 开发完整 Web UI；用 FastAPI + LangGraph Python + PostgreSQL/pgvector + Redis 实现真实后端。
- UI 逐页以九张参考原图为唯一视觉依据：工作台、我的调研、调研会话/实时报告、竞品档案、竞争情报、报告中心、技能中心、运行追踪总览和详情。**删除左侧 Sidebar 底部工作空间上方的「场景技能」块；场景技能仅在初始工作台输入框下方展示**，技能中心另行保留正常 Skill 管理。
- 场景 Skill 恰好六种、单选，默认通用分析；四项基础分析 Skill（产品能力、定价策略、SWOT、用户评价）无论场景/报告模式如何，全部由后端强制执行；增强 Skill MVP 三项（市场格局、商业模式、战略建议）可手动/自动组合，共计 13 个用户可见 Skill。
- 用户评价分析必须包含评论级正向/负向/中性/混合四分类、方面级情感抽取（同一条 mixed 评论可能在不同维度有不同情感）、真实统计/样本/来源及偏差说明；不能合成真实评论。
- 使用 LangGraph 构建真实协作流程：Planner + SkillResolver → Collector → Normalizer → Analyst（产品/定价/用户评价 → SWOT/可选增强）→ Writer → Reviewer；Reviewer 按结构化 issues 真正路由回采集/分析/写作节点并比较返工结果。
- 实现真实用户与默认个人 Tenant、项目、Thread、Run、Evidence、Claim、ReportVersion、Skill Registry、真实模型/工具调用、SSE 实时事件、取消与历史恢复、报告 PDF 导出、基本安全和测试。
- 第一个版本使用模块化单体与 LocalRunExecutor，但预留稳定 RunExecutor/ToolRegistry/ModelProvider/Storage Ports；运行状态不与 SSE 请求生命周期绑定；数据库按 Tenant 隔离、同 Thread 活跃 Run 原子串行、不同 Thread State 独立。此为未来多租户/多 Worker/MCP/Harness 的扩展基础，而非提前搭建空壳微服务。

### 执行原则

- 请**先输出简短的现状检查结论、架构落点、第一项切片计划和验收命令，然后立刻实施第一项切片**。不要停留在无限规划，也不要一口气生成所有页面和所有空后端文件。
- 一个切片必须把其需要的数据层/业务层/API/前端/测试闭环完成。实现后运行格式化、类型检查、相应测试，检查页面与原图一致性。
- 密钥都使用环境变量，生成 `.env.example` 占位符；缺少真实 API Key 时，允许隔离测试 fixtures，但正常 UI 必须明确显示「未配置/真实采集不可用」，不可伪造真实调研结果。
- 若现有仓库尚无任何代码，第一切片从初始化应用、数据库迁移、认证、统一 UI Shell 与首页视觉骨架开始；后续遵守下方切片顺序。
- 每个切片结束输出已改文件、实际功能、运行/测试命令及结果、已知限制，说明下个切片如何继续；测试未运行不得写“通过”。

## 二、开发切片指令（依次执行，通过验收后再进入下一项）

以下文本也可作为独立后续 Codex 指令使用。每次只执行当前切片，不把未实现能力宣称完成。

### Slice 0 — 工程初始化与基线检查

建立根目录与 `apps/web`、`apps/api`、`extensions/skills`、`infra`、`tests` 的必需结构；完成 React/FastAPI 的可运行入口、配置管理、lint/typecheck、pytest/Vitest/Playwright 基础、Docker Compose（web/api/postgres+pgvector/redis）、`.env.example` 和迁移机制。使用可维护的锁定依赖；健康检查和统一 API 错误响应可测试。检查原图文件能在项目中读取。

**通过门槛**：Web/API 启动、PostgreSQL/Redis 连通、迁移可从空库执行、测试命令可运行；README 写明可复现的启动方式，没有真实密钥被提交。

### Slice 1 — 认证、数据库业务骨架与视觉 Shell

实现注册/登录/登出/Me、默认个人 Tenant、`tenant_members` 和 TenantContext；项目/Thread/Run 等基础迁移；搭建 Sidebar/Topbar/路由守卫、空态和错误态。参考 `DESIGN.md` 与原图还原 Sidebar 和工作台的主要结构，删除 SideBar 场景技能，工作台输入框下方显示六个场景卡。

**通过门槛**：不同账户数据不能互读；桌面参考视口的 Sidebar/首页结构符合设计；真实表单验证和登录态可用；不使用静态伪造数据。

### Slice 2 — 可配置 Skill 系统

实现 Registry/Loader/Resolver/Validator、Skill Manifest 与 SKILL.md，注册六场景、四 core、三 advanced；支持 `GET /skills` 和配置 API；Skill Center 用真实 Registry 展示分类、版本、启用/必选及详情。工作台场景单选、四 core 只读必选、三 advanced 手动或自动配置；Run 保存 Skill 版本快照，后端阻止绕过 core 必选规则。

**通过门槛**：13 个 Skill 独立加载并被 Schema 校验；六场景单选；直接调用 API 删除 core 被拒绝或自动补回；Skill 版本与工具许可可追踪。

### Slice 3 — LangGraph 核心研究闭环

在 `agent/runtime` 实现 typed State、Graph、Checkpoint、Executor；Provider 封装 DeepSeek，ToolRegistry 封装 DeepSeek Search/web_fetch/去重/证据检索（2026-10-20 用户指定替换 Bocha；搜索内容使用 summary，保留原生评分和 date）；实现 Planner/Collector/Normalizer/Analyst/Writer/Reviewer，先从产品能力/价格/用户评价的结构化产物生成有来源的 SWOT；按配置调用增强 Skills。Reporter 生成结构化 Sections 和 Evidence/Claim 映射。

为 Reviewer 实现结构化 issues、按 `target` 定向返工、返工计数限制及 `needs_review` 降级；准备真实可复现的缺失证据/错误 Schema fixture。用户评价测试包括评论级四分类、方面级不同情绪、去重与真实分母。根据用户 2026-10-20 补充要求，产品能力/定价/用户评价 LLM 调用必须并发，配置并发上限、单调用超时和 Run 总预算；测试真实重叠和截止时间，不用串行执行独立分析来生成报告。

**通过门槛**：后端能从合法任务生成真实报告或显式数据不足；四 core 全部产生有效状态；Reviewer 能真实打回并观察产物变化；Graph 可持久化/检索 checkpoint；无无限循环或无来源的事实断言。

### Slice 4 — Run API、SSE 与调研双栏联调

实现 `POST /threads/{id}/runs` + 幂等键、查询状态/事件/取消/恢复、持久化 RunEvent/Step/ToolCall/Message；LangGraph 内部事件适配为统一 SSE。实现前端调研会话原图的左侧消息/阶段进度/事件卡，右侧报告结构化实时预览。支持断开重连按游标获取已保存事件；同 Thread 同时只允许一个活动 Run；不同 Thread 可独立运行。

**通过门槛**：真实前端从提交到报告更新无 Mock；刷新可恢复最终消息、状态及报告；SSE 断开不取消 Run；工具失败有可读状态；取消 API 与显示一致；不同租户不能订阅别人的 Run。

### Slice 5 — 竞品知识、报告、竞争情报与运行追踪

实现 CompetitorProfile、Source/Evidence/Claim/ReviewSample、AnalysisArtifact 和 ReportVersion 的实际查询与关联；逐页接入我的调研、竞品档案、竞争情报、报告中心、技能中心、Run 列表与详情。报告支持基础编辑、版本冲突处理、当前版本 PDF 导出。图片里的统计使用真实聚合；历史不足时图表采用空态。

**通过门槛**：同一次调研在项目、报告、竞品、情报及 Trace 页面数据一致；Claim 可回溯到 Source；Token/耗时/工具调用可复核；PDF 真实生成，未实现导出格式清晰禁用。

### Slice 6 — 业务边界、安全、评测及整体验收

完成跨租户/文件/向量/SSE 越权测试、注册与登录安全、web_fetch SSRF 防护、上传校验、Prompt Injection 防线、工具幂等、并发、状态恢复、报告编辑冲突、真实评论方面情感、质量返工等测试。对照原图完成桌面截图及响应式/键盘导航验收；文档与 OpenAPI 更新到实际实现状态。

**通过门槛**：`PRD.md`、`TECHNICAL.md`、`DESIGN.md`、`AGENTS.md` 的 MVP 验收项逐条有证据；不存在无响应按钮、虚构运营数据和未注明的替代实现；README 的能力列表与代码一致。

## 三、集成测试专用研究任务

可替换以下占位产品名贯穿前后端测试（**价格、评价、结论必须实际检索或清晰标注未知**）。生产代码、系统提示词和默认输入不得写死某家产品、厂商、域名或结论；产品身份来自用户输入，场景只提供通用维度与消歧规则。固定产品测试样例只允许存在于隔离测试或历史验收记录。

```text
研究 [产品名称 A]、[产品名称 B] 的产品定位、核心功能、
定价策略和公开用户评价，基于可核验来源分析正向/负向/中性/混合评价，
按评价方面区分功能、性能、价格、易用性等观点，
给出每家产品的 SWOT，最后生成带来源的结构化竞品报告。
场景：按输入选择，默认通用；模式：标准调研；增强：市场格局分析。
```

准备仅用于**测试环境**的受控 Source/Evidence/Review fixtures，覆盖价格缺失、矛盾来源、mixed 评论、Reviewer 返工、用户中途变更任务、SSE 重连和跨租户访问。测试数据界面必须显式标注，不混入正常业务报表。

## 四、完成汇报格式（每一切片都遵守）

```markdown
### 本切片结果

- 已实现：……
- 修改的关键文件：……
- API / 数据迁移 / 前端联动：……
- 测试命令与**实际输出结果**：……
- UI 原图对照与偏差：……
- 安全/来源/数据真实性检查：……
- 未完成项或已知限制：……
- 下一切片及其前置依赖：……
```

**不要跳过验收；不要报告未运行的测试已经通过；不要根据设计图硬编码产品信息或统计；不要把规划中的多租户 Worker/Harness 冒充当前已具备的生产能力。**
