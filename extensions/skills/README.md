# Spyglass Skills

Slice 2 已注册 13 个独立版本化 Skill：6 scenario、4 core、3 advanced。每个目录包含 `manifest.yaml` 和 `SKILL.md`。输入、输出和配置 Schema 的名称映射在 `apps/api/app/agent/skills/contracts.py`，加载时检查版本、目录边界、工具白名单、Schema 与依赖环。

目录文件与三个 Schema 一起计算 SHA-256。数据库按 `(id, version)` 保存定义，禁止更新或删除已注册版本；修改说明、Manifest 或 Schema 后应提升受影响技能的版本。业务运行保存已解析的版本、校验和、参数、工具许可、选择来源及原因，后续配置变化不改写既有快照。

场景每次单选；四项基础不可关闭；增强项支持手选和清单规则选择。`recommended_advanced` 目前按场景和 quick/standard/deep 选择，没有调用 LLM Planner。租户配置更换版本后须在技能中心确认保存，才能参与新的计划；旧配置不兼容时界面明确展示待确认的新默认值，不自动覆盖数据库。

Slice 3 已在真实 LangGraph 中读取并校验 Run 冻结的数据库版本，注入选中指导与 Schema，按工具白名单执行。分析产物和修订实际落库，Reviewer 有 Collector/Analyst/Writer 返工边；产品、价格、用户评价并发，汇合后按依赖执行 SWOT/增强项。自动增强选择当前仍标明 manifest_rules，Planner 负责研究范围，不宣称其已实现智能技能匹配。公共 Run/SSE 入口与完整前端执行链路留在 Slice 4。
