# Slice 2 验收记录 — 2026-10-20

## 已实现功能

- 独立 Loader / Validator / Registry / Resolver；13 份 `manifest.yaml` 与 `SKILL.md`，固定六场景、四基础、三增强。各场景包含不同的维度、来源优先级和评论方面；各分析有实际 Pydantic 输入/输出/配置 Schema。
- 校验 ID、SemVer、文件范围/大小、YAML alias、工具白名单、Schema 名称、配置类型、依赖存在性和环；禁止环境读取工具。SHA-256 覆盖清单、指导及三个 Schema。
- 全局只读版本目录和租户配置分离；数据库禁止修改/删除已注册版本，同版本异内容返回 409。历史版本详情可查询，返回当时定义及默认配置，历史运行参数由 Run 快照保存。
- 认证的技能列表/详情/历史版本、配置 PATCH 和计划预览 API；配置有 Schema 验证、CSRF、可信 Origin、幂等键和修订号。租户间启用状态和参数隔离，客户端不能删除四基础，也不能停用基础或场景。
- 显式配置迁移：技能升版保留旧配置版本/修订号，显示 migration_required；不兼容配置展示待确认的新默认值，阻止选中技能参与新计划，确认保存后恢复。旧定义仍保留。
- 内部 RunPreparation 在真实事务内校验会话归属、锁定 Thread、检查幂等及活动冲突，保存 pending Run、Skill 快照和用户消息。幂等重放返回原 Run，不受后续配置影响；同 Thread 串行、不同 Thread 独立。
- 技能中心展示真实 13 项、分类/搜索/状态/版本、独立详情、工具/依赖/校验和/Schema、配置表单及真实保存。工作台六场景单选、四基础只读必选、三增强手选或规则自动选择、服务端计划预览。包含加载/错误/空结果/待迁移反馈、交互动画、手机布局和键盘输入。
- 注销/身份失效/换账户清除旧草稿、模式和技能选择。已选增强技能停用后仍允许取消该勾选，解除无效计划。

## 修改的关键文件

- `apps/api/app/agent/skills/{contracts,models,loader,validator,registry,resolver}.py` 与 `extensions/skills/*/`：实际定义和校验/解析。
- `apps/api/app/{api/skills,application/skills,infrastructure/skill_repository}.py`、`infrastructure/database/skills.py`：租户配置和版本目录。
- `apps/api/app/application/run_preparation.py`、`infrastructure/run_repository.py`：原子 Run 与消息/快照准备，不执行研究。
- `apps/api/alembic/versions/0003_skill_registry_versioned_skill_catalogue_and_tenant_.py`：三张新表、Run 请求指纹及版本不可变触发器；Dockerfile 纳入技能文件。
- `apps/web/src/{pages/SkillCenter,features/skills/*,services/skills,stores/workbench,layouts/AppShell,main}`、生成的 TypeScript 类型及样式：前后端闭环。
- `apps/api/tests/{unit/test_skill_registry,integration/test_skills,integration/test_skill_snapshots}.py`、`apps/web/src/stores/workbench.test.ts`、`tests/e2e/{skills,auth}.spec.ts`：新增验收及身份边界回归。
- README、TECHNICAL、技能 README、计划和依赖锁同步实际实现。

## 数据库/API/前端联调结果

临时空数据库实际完成注册 → 加载 13 个技能 → 切换场景/增强 → 后端解析预览 → 查看详情 → 保存参数 → 刷新读取 → 停用增强 → 工作台报错并允许取消 → 自动选择排除停用项。另一个账户仍使用自己的默认配置。

真实数据库测试覆盖同键重放、不同键活动冲突、并发准备、跨 Tenant Thread 拒绝、既有快照在配置修改后不变、旧版本保留、同版本冲突及不兼容配置升版后的显式修复。数据库触发器真实拒绝 skills UPDATE/DELETE。

`0003_skill_registry` 已迁移至开发数据库，未删除业务数据。空库 upgrade → downgrade base → upgrade head 的测试通过；Alembic check 无差异。Compose API/Web 已重建，PostgreSQL/Redis/API healthy；Web `/skills` HTTP 200，readiness 200/ready 且四依赖 ok，未认证技能 API 401/unauthorized。未在业务数据库预置测试账户或报告。

## 测试命令与真实结果

最终 `pwsh -File scripts/verify.ps1` 退出码 **0**，输出 `All Spyglass verification commands passed.`：

| 命令 | 实际结果 |
|---|---|
| `uv run ruff format --check apps/api scripts` | 60 files already formatted |
| `uv run ruff check apps/api scripts` | All checks passed |
| `uv run mypy` | Success，42 source files |
| `uv run pytest -q` | **57 passed in 55.63s**，含真实 PostgreSQL/Redis、迁移 roundtrip |
| `uv run alembic -c apps/api/alembic.ini check` | No new upgrade operations detected |
| `npm run format:check` | 全部符合 Prettier |
| `npm run lint` / `npm run typecheck` | 退出码 0 |
| `npm test` | **3 files / 7 tests passed** |
| `npm run build` | 成功；JS 519.39 kB / gzip 163.61 kB |
| `npm run test:e2e` | **8 passed (16.4s)**；临时隔离数据库与 API8001/Web5174 |
| `npm run api:types` | OpenAPI 导出并生成 TypeScript 类型成功 |
| `docker compose up -d --build api web` | 镜像构建、迁移及启动成功 |
| `git diff --check` | 无空白错误 |

开发中先观察到技能路由 404；随后测试真实推动实现。独立审查发现并修复 JSON 键顺序破坏幂等、旧版本配置不可修复、停用增强不可取消，以及升版后表单未重新初始化。JSON 重试回归曾实际失败 409，修复后通过。浏览器回归中整页 goto 重置内存选择导致一项失败，改为通过真实 SPA 导航验证选中 → 停用 → 返回 → 取消，保留原断言，最终八项通过。中间格式检查失败均已修复。

非失败提示：Vite 主包超过 500 kB；尚未做路由拆包优化。测试环境有 NO_COLOR/FORCE_COLOR 和 reduced-motion 提示，不影响结果。

## UI 原图对照与偏差

人工查看 01、07 原图及自动化截图；沿用白底、浅灰线、深绿、固定 232px 侧栏、概览/分类/卡片结构，场景只在工作台输入框下方。实际目录按 6/4/3 分类，未复制原图中的虚构使用量、自动装载开关或额外行业技能。为显示版本、ID、维度及真实配置入口，技能卡纵向内容较原图更多；未宣称像素级一致。详情没有专门原图，沿用既有视觉 Token。

截图位于忽略目录 `.artifacts/screenshots/`：`slice-2-workbench.png`、`slice-2-skills.png`、`slice-2-skill-detail.png`、`slice-2-skills-mobile.png`。1672×941 桌面及 390×844 手机用例通过，手机无水平溢出。

## 仍未实现或待确认内容

- 本切片不生成报告，不调用模型或搜索，不产生伪造分析产物、Token、来源或评论。开始分析仍明确禁用。
- 自动选择目前是带来源说明的 Manifest 场景/模式规则；真实 LLM Planner、工具执行时许可检查、LangGraph、Checkpoint、证据与分析执行属于 Slice 3。
- Slice 2 要求保存 Run 版本，而公共 Run 创建 API 位于 Slice 4；已明确同步到 TECHNICAL，采用内部真实 pending Run 准备事务满足当前持久化验收，不提前暴露无法执行的入口。
- Run/SSE/取消/公开历史查询、报告双栏和导出未实现；自定义技能编辑/市场/热加载/团队管理未实现，相关 UI 明确禁用或未展示。
- 当前配置修订迁移需显式确认；没有发布动态外部技能的接口。

## 下一切片建议

Slice 3：实现真实 LangGraph 研究闭环，接入 Bocha 和模型 Provider、受限 web_fetch、证据标准化、四核心/增强产物、Writer 与 Reviewer 定向返工。产品能力/定价/用户评价必须并发执行，加入并发上限、单调用超时、Run 总预算及真实重叠/截止时间测试；按版本快照读取 Skill，不能重新使用可变目录替代历史定义。随后 Slice 4 才开放前端输入 → Run/SSE → 报告的真实完整链路。
