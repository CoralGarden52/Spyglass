# Spyglass — Codex 项目开发规则（AGENTS.md）

> 这是项目根目录 Codex/AI Coding Agent 必须遵守的约束。产品事实以 `PRD.md` 为准，协议以 `TECHNICAL.md` 为准，视觉以 `DESIGN.md` 和 `assets/references/` 为准，任务入口见 `prompt.md`。这些文档若有矛盾，应指出冲突、建议最小修正并在修改后保持同步，不得静默自行替换核心要求。

## 1. 总体任务与不可更改要求

实现 Spyglass：具有真实前后端、可用 Skills 和 LangGraph 多 Agent 协作的竞品分析 MVP，为未来多租户、多并发和完整 Harness 保留稳定边界。

**锁定技术选型**：React 19、TypeScript、Vite、TailwindCSS、Zustand、React Router、ReactFlow、ECharts（按需 D3）、Framer Motion；FastAPI、Pydantic、LangGraph Python；PostgreSQL + pgvector + Redis。依赖选用相互兼容的维护版本，生成锁文件；不得未经确认改成 Next.js/NestJS/AgentScope/CrewAI 或额外引入第二套 Agent 编排核心。模型和搜索通过 Provider 接入，当前为 DeepSeek 模型与 DeepSeek Search（2026-10-20 按用户要求移除 Bocha，搜索固定使用 DEEPSEEK3_API_KEY）。

**视觉锁定**：九张 `assets/references/*.png` 是设计基准；不能替换为任意模板/自创风格。删除全局 Sidebar 的「场景技能」卡片区域，放在工作台输入框正下方；技能中心仍保留 Skill 管理。

**Skill 锁定**：6 场景单选（默认通用）；4 核心分析全部必选（产品能力、定价、用户评价、SWOT）；3 增强分析可选（市场格局、商业模式、战略建议）。每项是独立可注册、可版本化 Skill，不能只以 if/else 给几段不同文案。用户评价必须支持整体正/负/中/混合和方面级情感，mixed 评论仅计入整体分母一次。

**Agent 锁定**：Collector/Analyst/Writer/Reviewer 四个专业 Agent，加 Planner/Resolver/Normalizer 等职责明确的工作流节点。真实结构化交接，质检可打回并能观察修复前后区别；不可只画箭头或由单一 Prompt 假扮所有 Agent。

## 2. 工作方式

1. 开始任何实现前阅读全部五份文档及相关 UI 原图，先检查现有代码/依赖/目录；**不得盲目覆盖用户已有修改**。
2. 先给出当前任务的范围、拟修改文件、验收方式、存在风险；每次处理一个可闭环的纵向切片：数据库/后端/API/前端/测试实际联通。
3. 完成切片后运行相关命令，报告实际执行的命令、结果、未完成项；不以“代码看起来正确”代替测试。
4. 每个新增 API 至少有请求/响应 Schema、Tenant 权限、错误响应和针对性测试；文档变更同步 OpenAPI/TypeScript 类型。
5. 每个 UI 主操作必须接入真实状态或明确禁用并告知原因，不允许无响应按钮、静态假进度和所有指标硬编码。
6. 如果外部 API 密钥/服务不可用，使用单元/集成测试 fixture 验证接口，同时在正常 UI 明确提示未配置或降级；Fixture 必须显著隔离，不得伪装为已完成真实联网调研。
7. 每次提交遵循格式化、lint、静态类型检查、相关测试和数据库迁移检查；遇到失败应定位修复，不通过删除测试绕过。
8. 逐步扩展架构，不提前生产大量空类/空目录/TODO facade；不能把长期计划中的模块宣布为 MVP 已实现。
9. 所有实现要兼顾可读性、独立职责、类型、必要注释和最低依赖原则；不能为了抽象而抽象，也不能全部写在 `main.py` / 一个 Graph 文件。
10. 提交说明和 README 要反映实际功能和限制，状态应可复现。

## 3. 代码结构与边界

- React 页面只调用 `services`/生成的类型与事件适配层，不直接拼接数据库或 LangGraph 的内部结构。
- Zustand 管界面态；服务端缓存交由 TanStack Query；SSE 客户端按事件 ID/序号去重、断线重放、Run 生命周期独立。
- FastAPI Router 只做认证/验证/调用 Application Service；禁止路由函数直接构建完整 Agent Graph 或执行复杂多轮 LLM 调用。
- Application Service 管事务与用户操作；Graph 管流程与 State；业务仓储隐藏 ORM；Storage/Tool/Model 使用可替换适配接口。
- 业务数据库与 LangGraph Checkpointer 分开；State 存关键引用，不把整篇网页或大二进制存到 checkpoint。
- Skills 采用 Registry/Resolver/Loader/Validator，与 Agent/Tool 解耦；不允许 Skill 读取环境密钥或自行突破工具白名单。
- Run 具有独立 `run_id`，每 Thread 同时一个活动 Run 的并发不变量由数据库/事务强制；未来 Worker 通过 RunExecutor Port 接入。
- 对接口/Manifest/事件定义声明 `schema_version` 或版本策略；既有报告固定 Skill 版本和历史证据。

## 4. 数据正确性与来源约束

- Source、Evidence、Claim、ClaimEvidence、CompetitorProfile、ReviewSample、ReportVersion 必须是实际可查询数据模型，事实性结论关联来源和定位；没有来源应明确标记 insufficient_evidence。
- 功能状态区分已支持/部分支持/未发现来源/明确不支持/待验证；不得把搜索不到等同于明确不支持。
- 不编造官网、价格、用户评论、样本数、声称“市场份额”或日趋势；截图里的运营数字是视觉素材，不是种子数据。
- 用户评价至少整体四分类和方面级抽取；报告保留分母、样本量、去重、源平台、来源偏差说明；置信度不等于评论真实性。
- 价格含币种、计费单位、采集/发布日期；趋势图有真实时间序列方可显示。
- 未真正运行的模型/工具不填假 Token；未知 usage 显示 `null`/「—」。Trace 提供公开可解释的步骤、Prompt 版本/脱敏输入摘要、真实工具信息，不伪造模型隐藏推理链。
- 上传问卷/访谈仅分析具有使用权限的数据，脱敏个人信息；禁止合成假受访者或将测试 Fixture 当业务数据。

## 5. 认证与安全底线

- 所有租户私有资源必须通过已认证用户和成员关系解析 Tenant，仓储/查询/向量/缓存/文件/SSE 均强制校验归属；不得信任未经验证的浏览器 `tenant_id`。
- 密钥只能从环境变量读取，不能写入源码、前端 bundle、测试快照或日志；`.env.example` 必须只含占位符。
- 安全密码哈希、Cookie 安全属性、CSRF 防护（若 Cookie 会话）、CORS 白名单、登录限流、文件类型/大小验证、用户输入 Schema 验证均不可遗漏。
- `web_fetch` 做协议/域名/IP/重定向与响应大小限制，防 SSRF；遵守网站可访问策略、robots 与授权约束；检索内容不获得 System/Developer 指令权限。
- 对写操作和 LangGraph 恢复使用幂等键；不得用无限重试掩盖 API 限流或产生重复写入。
- Trace/日志对用户私密材料、凭证和工具参数做脱敏；不将敏感数据送入其他 Tenant 的 Memory。

## 6. 必要测试矩阵

### Backend / DB
- Auth 注册、登录、登出、失败/限流、默认个人 Tenant；所有受保护路由未授权返回正确错误。
- 不同 Tenant 的 Project、Thread、Report、Evidence、Asset、Run Events、Vector 搜索相互隔离；直接猜 UUID 也无法越权。
- 相同幂等键不会创建第二个 Run；同 Thread 活动 Run 并发冲突受事务保护，不同 Thread 可隔离运行。
- Alembic 可从空数据库迁移，外键、索引、唯一约束和角色约束可验证。

### Agent / Skill / Evidence
- 6 个场景被正确加载且只能一个主场景；4 核心全部入计划及结果（或显式 insufficient_evidence）；3 增强按配置匹配。
- 版本快照与执行记录相符；Skill 声明工具超出白名单时拒绝执行。
- 用户评价包含 mixed 和多方面不同情感 fixture，聚合比例与分母正确；重复评价不会重复计数。
- Reviewer 使用固定缺证据/错误 Schema/矛盾信息 fixture 触发指定方向的真实返工；修复后产物确有差异，失败上限进入 needs_review。
- 每条事实 Claim 的 Evidence ID 可查询和打开；来源缺失时不自动通过。
- Tool 失败、供应商超时、配置未提供等都按已定义策略处理；重试安全。

### API / Events / Frontend
- Run 创建返回真实 ID；SSE 事件顺序稳定，重连/游标回放不导致最后一条消息重复。
- 取消是独立 API，断开 SSE 不取消 Run；刷新可读取消息与已保存报告。
- 主路由加载/空态/失败状态正确，UI 主要操作可自动化测试。
- 图片参考桌面视口进行 Playwright 截图对照；保留响应式和键盘可访问。
- PDF 导出真实完成并正确读取报告当前版本；不支持格式有明确反馈。

## 7. 验收停止条件

出现以下任一情况，不得报告该功能已经完成：

- 只有占位代码、`pass`、`TODO`、静态 JSON 充当后端实现；UI 按钮不触发真实服务或不明确禁用。
- 质检没有真实打回路由，或返工结果与返工前完全无变化却报告成功。
- 模拟 Token、证据数、真实产品价格、评价占比、情报趋势混入正常业务模式。
- 前端对原图有明显非授权重设计、Sidebar 场景技能未删除。
- 没有租户权限、无法恢复消息/运行结果、DB 未迁移、缺少基本异常/取消处理。
- 测试未运行却宣称通过，或存在未解释的失败。

结束每个切片时输出：`已实现功能`、`修改的关键文件`、`数据库/API/前端联调结果`、`测试命令与真实结果`、`仍未实现或待确认内容`、`下一切片建议`。不在文档或工作总结里给出未经验证的能力承诺。

## 8. 演进方向（仅规划边界）

V0.1：真实 MVP；V0.5：Context/Memory/HITL/Hooks/Evaluation；V0.8：正式多用户协作/租户配额/Worker/可靠队列/并发调度；V1.0：Gateway/MCP/动态 Subagents/Sandbox/CLI/Extension System/完整 Harness。保留扩展接口，不提前实现空壳服务；是否新增依赖要有实际功能需求、测试及文档依据。
