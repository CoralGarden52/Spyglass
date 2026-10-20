# Slice 1 验收记录 — 2026-10-20

## 已实现功能

- 邮箱注册/登录/登出/Me；注册在一个事务内创建 User、默认个人 Tenant、owner 成员关系与会话。邮箱大小写规范化后唯一，重复/并发注册不会创建第二份个人工作空间。
- Argon2id 密码哈希（注册密码 15–128 字符）、随机 256 位持久会话、过期与撤销；数据库只保存 Session/CSRF 摘要。Cookie 为 HttpOnly/SameSite=Lax，CSRF Cookie 可供页面读取；生产配置必须启用 Secure 并使用 HTTPS。
- 所有写操作验证可信 Origin；私有写操作验证与会话绑定的 X-CSRF-Token。Redis Lua 限流登录/注册，429 含 Retry-After；Redis 不可用时返回明确 503，不绕过限流。
- TenantContext 从当前有效会话和成员关系解析，私有仓储查询强制过滤 Tenant，客户端不能指定租户。项目、会话和消息查询的跨账户 UUID 返回 404。
- Project 创建/搜索/分页/读取，Thread 创建/读取/真实消息历史查询；创建要求 Idempotency-Key，相同内容返回原实体，不同内容冲突 409。
- 迁移 `0002_auth_workspace` 建立八张表：users、tenants、tenant_members、sessions、research_projects、threads、runs、messages。角色/状态 CHECK、同租户复合外键、个人 Tenant 唯一索引与活动 Run 部分唯一索引实际生效。
- 登录注册页、路由守卫、刷新恢复、账户设置/登出、真实项目创建/列表/搜索/详情、首页真实近期项目、加载/空态/错误反馈。侧栏显示真实用户，保留七个入口，尚未实现的业务页明确禁用；场景技能仍在输入框下方，侧栏没有场景卡。
- 统一身份边界清理：显式登出、Me 发现身份失效或变更、登录/注册成功均清理旧私有缓存、草稿及模式，避免跨账户界面残留。

## 修改的关键文件

- `apps/api/app/infrastructure/database/{base,accounts,research}.py`、`apps/api/alembic/versions/0002_auth_workspace_accounts_tenant_context_and_research_.py`：实际模型和迁移。
- `apps/api/app/{core/security,core/dependencies,application/auth,infrastructure/auth_repository,infrastructure/rate_limit,api/auth}.py`：密码、会话、TenantContext、CSRF、限流与认证 API。
- `apps/api/app/{application/research,infrastructure/research_repository,api/research}.py`：租户隔离的项目/会话服务。
- `apps/web/src/features/auth/*`、`pages/{AuthPage,AccountSettings,ResearchProjects}.tsx`、`services/{client,auth,research}.ts`：真实前后端交互。
- `apps/web/src/{main,layouts/AppShell,pages/Workbench,stores/workbench}`、生成的 `types/api.generated.ts`：守卫、真实用户/近期项目和身份切换清理。
- `apps/api/tests/{conftest,integration/test_auth,integration/test_auth_security}.py`、`tests/e2e/*`、`scripts/run_e2e.py`：真实隔离数据库验收与回归测试。
- README/TECHNICAL/.env.example、依赖锁与 verify.ps1 同步实际能力和协议。

## 数据库/API/前端联调结果

隔离测试数据库上已实际完成：注册 → 进入首页 → 刷新恢复 → 创建项目 → 搜索/详情/刷新读取 → 登出 → 错误密码反馈 → 正确登录；另一个账户读取同一项目 URL 被拒绝。Thread 消息接口查询真实空会话返回空数组，没有合成消息。

空数据库从 0001 升级至 0002、downgrade 至 base 再完整升级通过；Alembic check 输出 `No new upgrade operations detected.`。原有 0001 开发数据库已升级至 head，没有删除数据或使用 create_all。

Compose 镜像已重建并启动，Web `/login` 返回 200，API readiness 返回 ready，未登录 Me 返回 401；PostgreSQL、Redis、API 均 healthy。页面入口仍为 http://127.0.0.1:8080，刷新会进入登录页，用户可自行注册。没有在业务数据库内预置测试账户；完整认证浏览器联调使用单独的临时数据库和 8001/5174 端口。

## 测试命令与真实结果

最终执行 `pwsh -File scripts/verify.ps1`，退出码 0，输出 `All Spyglass verification commands passed.`：

| 命令 | 实际结果 |
|---|---|
| `uv run ruff format --check apps/api scripts` | 42 files already formatted |
| `uv run ruff check apps/api scripts` | All checks passed |
| `uv run mypy` | 28 个源文件，无问题 |
| `uv run pytest -q` | **36 passed in 34.84s**，真实 PostgreSQL/Redis |
| `uv run alembic -c apps/api/alembic.ini check` | 无新迁移操作 |
| `npm run format:check` | Prettier 通过 |
| `npm run lint` | ESLint 通过 |
| `npm run typecheck` | TypeScript 通过 |
| `npm test` | **2 个测试文件、6 项通过** |
| `npm run build` | Vite 构建成功，JS 506.91kB / gzip 160.39kB |
| `npm run test:e2e` | **5 passed in 11.4s**，包含桌面/手机与账户切换回归 |
| `npm run api:types` | 从运行代码的 OpenAPI 重新生成 TS 契约 |
| `docker compose --progress plain up -d --build` | 两镜像构建、四服务启动成功 |

重点断言：随机伪造/撤销/过期 Session 不获权限；实际密码与 Cookie 摘要存储；inactive 成员拒绝访问；非可信/缺失 Origin、缺失/伪造 CSRF 被拒绝；Redis 不可用返回安全错误；并发同邮箱只创建一组用户/租户/成员；私有创建幂等与冲突；跨租户外键、非法角色、同 Thread 第二个活动 Run 被数据库拒绝；前端缓存/草稿跨账户不残留。

测试数据隔离：pytest 创建随机 `spyglass_test_*` 空库；Playwright runner 创建随机 `spyglass_e2e_*` 空库，并设置独立 Redis 限流命名空间，测试后仅删除本次创建的测试库。测试不访问模型/搜索供应商，不产生 API 费用或伪造报告。

## 审查、故障与视觉对照

真实发现并修复：注册路由尚未存在时首个测试 404；自动生成复合唯一约束的名字碰撞导致迁移失败；异步 Redis 返回值与 SQLAlchemy scalar 类型注解；非标准上游错误体触发前端 TypeError；移动端测试需跟随真实导航链接语义更新。

独立审查发现隐私状态问题：Alice 的会话被其他标签页撤销后，Bob 登录可能看到 Alice 未提交草稿。先增加 E2E，确实在“Bob 草稿应为空”处失败；再统一身份切换清理，5 项浏览器测试全部通过。README 中旧 Slice 0 描述已同步。审查没有其他待修复项。

已检查桌面首页、手机、注册页和项目详情截图，本地文件为 `.artifacts/screenshots/slice-1-*.png`。截图采集前回到页顶并等待注册卡片入场结束，避免把滚动或动画中间态当成视觉偏差。保留白/浅灰/深绿与原图 Shell 结构；登录页按 DESIGN 的同色系表单规范实现。我的调研暂为基础列表/保存页面，五指标卡、活动侧栏与完整业务布局仍属 Slice 5；不使用原图运营数字填充界面。

非失败提示：Vite 单个 JS chunk 超过 500kB（506.91kB），后续可按路由拆分；Playwright NO_COLOR/FORCE_COLOR 和减少动态效果提示。所有验证均退出 0，没有通过抬高阈值或删除测试隐藏问题。

## 仍未实现或待确认内容

可执行 Skill Registry/单选场景配置、LangGraph 四 Agent/Checkpointer、并发 LLM 研究/总预算、Run 执行 API/SSE/取消/恢复、报告/证据/导出、完整竞品/情报/Trace 页面仍未实现。runs/messages 基础表不代表运行流程完成；Thread API 可实际持久化，但当前没有研究会话执行界面。

当前仅个人 Tenant；无团队邀请/角色管理、密码重置、邮箱验证或 MFA。Compose 是本地 HTTP 开发环境，生产需 HTTPS 和 Secure Cookie。未宣称完成尚未存在的文件/向量/SSE 私有资源隔离测试。

## 下一切片建议

Slice 2：实现 Registry/Loader/Resolver/Validator 和 13 个独立版本化 Skill，接通技能中心、六场景单选、四核心强制必选与三个增强配置。继续保留用户确认的 Slice 3 性能要求：独立 LLM 分析并发，具有并发上限、超时和 Run 总预算，并用真实运行记录验收。
