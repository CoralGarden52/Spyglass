# 技能加载 409 修复记录

## 已实现功能

修复工作台与技能中心加载失败。实际 API 日志为认证身份读取成功、`GET /api/v1/skills` 返回 409，而非模型或数据库连接失败。只读比对确认正常业务库中 13 个 0.1.0 Skill 的旧哈希均对应 CRLF 原始文件；当前 LF 文件与旧 Schema/指导内容相同，仅换行不同。

新 Loader 用 LF 计算统一校验和，并计算同一 Manifest/指导/Schema 的有限 LF/CRLF 旧哈希变体。仓储接受这些确切变体，历史记录保持不可变；API 和 Resolver 使用实际保存的校验和，Run 执行仍从原版本读取。真正改动内容仍返回 409。前端现在展示服务端错误原因，不再仅有笼统的失败/重试。

## 修改的关键文件

- `apps/api/app/agent/skills/{loader,resolver}.py`
- `apps/api/app/{infrastructure/skill_repository,application/skills}.py`
- `apps/web/src/{features/skills/WorkbenchSkills,pages/SkillCenter}.tsx`
- 技能 Registry 单元测试、快照集成测试与 `tests/e2e/skills.spec.ts`
- README、TECHNICAL 与本记录；无新 API、Schema、依赖或数据库迁移。

## 数据库/API/前端联调结果

回归使用真实迁移后的隔离库：先注册旧算法 CRLF 版本，再切换 LF 清单，验证列表成功且返回历史哈希；准备实际 Run 后，读取冻结定义成功。13 行旧内容/哈希未改写，版本不可变测试及实际内容冲突测试保留。

正常业务数据库通过只读事务确认 13/13 旧哈希符合兼容规则，不创建测试账户/报告，不删除或更新旧技能。浏览器回归覆盖工作台和技能中心展示同一 409 服务端原因。

## 测试命令与真实结果

- RED：换行一致性与旧目录/API/Run 回归各失败一次，分别表现为校验和不等、列表 409；浏览器错误提示回归失败，实际只显示“技能加载失败 重试”。
- GREEN：针对性后端测试 **23 passed in 25.49s**；新增浏览器用例 **1 passed (11.4s)**；mypy 65 文件通过。
- `pwsh -File scripts/verify.ps1`：Ruff 91 文件、mypy 65 源码、后端 **86 passed in 97.55s**、Alembic check 无变化、Prettier/ESLint/TypeScript、前端 **7 passed** 和构建均通过；脚本在浏览器测试阶段退出 1，10 个 worker 下 9 项通过，1 项 Chromium 启动失败（尚未进入页面，DevTools pipe 中断）。随后以 3 个 worker 重跑全部浏览器用例。
- `docker compose up -d --build api web`：成功重建；容器内只读检查 13/13 旧版本兼容，readiness HTTP 200/ready。无需清库或迁移。
- `npm run test:e2e -- --workers=3`：**10 passed (20.3s)**；全部断言保留，原启动失败的项目权限用例也通过。测试的浏览器并发限制没有改变研究 LLM 的并发配置。
- 独立代码审查未发现重要问题，确认真实内容冲突仍被拒绝、历史内容/哈希与新 Run 引用一致。
- 人工查看真实隔离 API 的工作台截图，六场景与四必选项正常显示；没有改动视觉结构。未替代用户登录正常业务账户。

## 仍未实现或待确认内容

本修复只处理技能清单加载；不处理模型 JSON 输出问题，不提前开放 Slice 4 的运行/SSE。浏览器当前位于登录页，需正常登录后访问工作台；没有代替用户创建或使用业务账户。

## 下一切片建议

继续 Slice 4 的真实 Run API/SSE/调研双栏；模型结构化输出兼容问题需单独定位，不和本次换行修复混在一起。
