# DESIGN — 设计取舍与可调参数

> **非规范**：本文只记录设计取舍与理由；规则以 `WORKFLOW.md` 为准。
> 要改流程：`WORKFLOW.md` 是 canonical。先改 `WORKFLOW.md`，再同步角色/模板/脚本，最后回写本文记录理由。

## 1. 核心约束推导

需求四条约束：① 主会话纯委派；② 三类角色分工固定；③ 流程固定为 PMO→TDO→QA→PMO→主会话；④ 细节自定。由此推出三个硬设计：

- **文档即接口**：主会话"不看 TDO/QA 正文"意味着文档必须自带状态与摘要；因此每份文档都有 `wf-doc` 元信息块 + 固定章节，且 PMO 的 `PROJECT.md` §6 是唯一"上行通道"。
- **单一写者**：三类角色分别只写一份文档，天然避免并发写冲突；唯一多写者文档是 STATUS（多个 TDO），所以只有它需要锁。
- **状态机显式化**：把"谁在什么时候读什么"写成状态值（`pmo-plan`/`plan-ready`/`tdo-in-progress`/`qa-pending`/`qa-done`/`waiting-main`/`closed`），这样体检脚本能自动判断流程卡在哪一步。

## 2. 关键取舍

| 取舍点 | 选择 | 放弃的方案 | 理由 |
| --- | --- | --- | --- |
| 交互媒介 | Markdown + 一个 xlsx | 全部 Markdown（含 ISSUES.md） | 表格类状态（问题/风险/变更）用 xlsx 便于人查、筛选、下拉约束；md 仍作主流程载体 |
| ISSUES 写入 | 脚本 `issues.py` 统一分配 ID | 智能体手编 xlsx | 手编 xlsx 易破坏格式/公式/校验；脚本保证列结构与 ID 单调 |
| STATUS 并发 | 目录锁 + 逐条追加 + 逐条提交 | 无锁/每轮一次大提交 | 满足"锁定写入、进度逐个提交"；锁用 `mkdir` 原子性，零依赖 |
| 锁超时 | TTL 900s + `--steal` 留痕 | 永久锁 | 智能体会话可能中断；接管必须留痕，避免静默丢进度 |
| 主会话行权 | 只写 DECISIONS + 动状态字段 | 主会话逐轮读全部文档 | 保住"纯委派"边界；项目问题由 PMO 压缩成选项后上报 |
| 编制决策 | 每轮重定，启发式表 | 开局定死 | 返工多就降并发、流程变独立就升并发 |
| 严重度 | S1–S4（S1 必须当轮上报） | 只有"高/中/低" | S1 需要机械可判定：凡 S1 行 `需主会话决策` 必须为"是"，体检脚本可查 |
| 终止判据 | 达成 / 连续 2 轮无进展 / ROI 不足 / 叫停 | 只在"做完"时结束 | 防止无限烧额度；终止必须是显式决策条目 |

## 3. 可调参数

| 参数 | 默认 | 在哪改 | 说明 |
| --- | --- | --- | --- |
| TDO 数量上限 | 5 | `WORKFLOW.md` §2.1 | 超上限合并工作流 |
| 锁 TTL | 900s | `scripts/wf.py` `LOCK_TTL` | 长任务可调大 |
| 锁重试 | 3 次指数退避 | `scripts/wf.py` `LOCK_RETRY` | 并发高时调大 |
| STATUS 提交 | 默认开启（`--no-commit` 可关） | 命令行 | 逐条提交是默认契约 |
| ISSUES 严重度/状态枚举 | S1–S4 / 6 状态 | `templates/ISSUES.xlsx` 的"说明"页 + `issues.py` | 改动需同步 `roles/QA.md` |
| 终止"无进展"轮数 | 2 | `WORKFLOW.md` §7 | 值越大越能容忍探索性停顿 |

## 4. 本次不做（YAGNI）

- 不做 Web UI / 看板：文档 + 脚本已足够，且避免第二个事实源。
- 不做自动调度（主会话手动发委派）：调度逻辑靠状态机，本阶段人/主会话更便宜。
- 不做多仓库同步：run 目录自包含，产出物路径写绝对/相对路径均可。
- 不做语义检索：与 KB 演进方向无关，本工作流只管理过程文档，不建索引。
- 不做 ISSUES 自动汇总图：`汇总` sheet 用 COUNTIF 公式已够。

## 5. 已知边界

- `issues.py` 依赖 `openpyxl`（本机 3.1.5 已装）；未装时给出安装提示，不会静默写坏文件。
- 同一 xlsx 不能被两个进程同时写；约定只有 QA 新增、PMO 收轮改状态，实际冲突概率极低；如冲突，脚本报错重试。
- STATUS 锁只保护文件写入与提交，不保护产出物文件；产出物互斥由工作流拆分（§2.1）保证。
- `runs/` 默认入 git（进度逐条提交是设计的一部分）；`.locks/` 已被忽略。

## 6. opencode 直连的取舍（2026-10-12 接入，仅 opencode 1.x）

| 取舍点 | 选择 | 放弃的方案 | 理由 |
| --- | --- | --- | --- |
| 对接通道 | opencode **1.x** serve 的 v1 同步 HTTP API（v2 已移除该端点，`serve_start` 在拼 `--pure` 前守卫并 rc=1） | v2 `/api/session/{id}/prompt`、ACP、`opencode run` 子进程 | v2 无头下只受理不执行（503）且 v1 端点 405；ACP 两端都是 server；`opencode run` 每次冷启动且难拿 session 级成本数据。本机 v2.0.32 的实际委派需 `opencode run`（本仓未内置 adapter；插件线 `opencode_delegate.py` 为外部封装） |
| 默认模型 | `opencode-go/deepseek-v4.1-flash` | 默认 pro | 委派量大、任务结构化，flash 够用且便宜；要强模型用 `--model` |
| 默认 opencode agent | `minimal` | 默认 primary agent | primary 带编排注入，24 个自定义 agent 上下文更重；minimal 工具够用、token 省 |
| 工作目录 | server cwd = `workflow-group/` | 每个 run 起一个 server | 相对路径 `runs/<id>/...` 统一、一个常驻服务管全部 run；项目隔离靠 run 目录而非 opencode project |
| 记账 | 自动写 `DELEGATIONS.md` + `delegations/*.md` | 只在会话里看 | 主会话不看正文的原则要靠文件留痕；成本数据轮末可汇总进 DECISIONS |
| 状态迁移 | 委派消息里要求角色自己跑 `wf.py state`；delegate 只做前置守卫 | 主会话代跑 | 保持"唯一写者"：写者文档的状态由写者推进，主会话只做收轮后的下一轮创建 |
| 会话清理 | 不自动删 | 自动删 | 审计与复跑需要；确认无用再手工删 |

## 7. 真实项目 / 烧额度场景的扩展（2026-10-13）

| 缺口 | 补法 | 理由 |
| --- | --- | --- |
| delegate 同步串行，多 TDO 会白等 | `wf.py squad`：ThreadPool 并发发 N 个 session，各自绑定唯一 WS | 一天窗口要把墙钟压在并行度上，而不是排队上 |
| 没有写权限概念 | PROJECT §0 增加「项目根 / 写权限白名单」，契约与 TDO/PMO 手册同步 | 真实项目仓常混有他人改动，越界成本高 |
| 项目仓提交策略缺失 | `wf.py commit --repo ... -- <paths>`，只 add 明确路径、不 push | 并发提交会抢 index；`git add -A` 会裹入他人改动 |
| 烧了多少不知道 | `wf.py ledger` 按角色汇总 cost/tokens/耗时 | 额度有期限时，需要按小时评估产出率 |
| PMO 缺项目上下文 | `new-run --project-root/--scope/--goal-file` | PMO 需要知道"能改哪、项目在哪"才能拆片 |

## 8. 按目录特化（2026-10-13）

- **问题**：通用模板适合"从零立项"，但真实烧额度场景往往是"一个目录范围 + 一个明确任务"，PMO 从白纸规划太慢、边界也容易出错。
- **做法**：引入 `SPEC.md` + `--template`。SPEC 固定四件事：写权限分区表（一 WS 一目录/一文件边界）、全内容覆盖要求（逐文件处置，不许抽样）、证据格式、禁止项与 DoD。委派消息自动要求先读 SPEC；冲突时 SPEC 优先，但四条约束不可覆盖（文档即接口、单一写者、锁、分歧不落地）。
- **模板库**：`templates/specialized/<name>/`；当前有 `kb-debt-burn`（KB 欠账清理）。新场景复制一份改写 SPEC §2 分区表即可。
- **为什么不让 PMO 全自动拆**：PMO 看不到用户意图的优先级；SPEC 把"写哪里、覆盖到什么程度"固定下来，PMO 只做细化与编制，避免跑偏。

## 9. 烧额度实战后的加固（2026-10-14，burn-postmortem）

> 依据：`burner/burner.log`、各 run 的 `DELEGATIONS.md`/STATUS；完整观察→改动映射见 `runs/burn-postmortem-20261014/reports/ws2-changes.md`。

| 缺口 | 补法 | 理由（观察出处） |
| --- | --- | --- |
| 队列会重复拉起已完成的 run | `run_queue.py` 启动 pack 前查 `runs/<id>/DONE`（或 `BLOCKED`），命中即 `SKIP`；需重跑先删 DONE | kb-debt-20261013 已于 10-13 23:14 closed，10-14 01:16 仍被重跑，花 63664 tokens、委派新增 0 行，仅换来写 DONE（`burner.log` L10-11；`git log` d9a3e65 vs 8736241） |
| 单条 send 长时间无可见性 | `send` 放线程，主线程按 `heartbeat_sec`（默认 300s）记 `HEARTBEAT`；`send_timeout_sec` 43200→7200 | 实测单条 send 68/42/98 分钟且期间零日志，无法区分"在跑"与"卡死"（`burner.log` L15/L20/L25） |
| `--also` 指向被忽略文件会让提交整条失败 | 文档层约定 `--also` 只给 git 跟踪路径；日志类产物只留盘 + 报告内联 | `runs/signaldeck-runtime-20261014/STATUS-Round-1.md` WS-2 薄弱点 3（`git add --` 失败连带整条提交失败） |
| cost 字段让人严重低估烧额 | 逐 pack 记官方余额差（`PACK <id> 结束 余额 ¥a → ¥b（Δ¥c）`）；预算以余额差为准 | P1–P4 session cost 合计≈$0.0034，而余额 ¥32.18→¥27.29（Δ¥4.89），差约两个数量级（`burner.log` L6/L27；各 run `DELEGATIONS.md`） |

## 10. 母版采纳：规则优先、MAIN 建模与用字规范（2026-10-15）

> 依据：本 run（`master-adoption-20261015`）主会话拍板 `D-001~D-008`；前序 run `so-necessity-research-20261015`（D-006/D-008）与 `role-boundary-audit-20261015`。
> 本节只记录“为什么这样改”。条文一律以 `WORKFLOW.md`（§1/§2/§3/§3.1/§4.0/§4/§6/§7/§10/§11）与 `roles/**` 为准；本节与 §1–§9 历史表述冲突的，以 WORKFLOW/roles 为准，由新表述取代。

### 10.1 证据结论：不引入“SO”实体（该术语已退役）

- **结论**：不设该角色、不建默认 `TERMINAL` 载体、不加状态值、不做每轮必收台账（见 `WORKFLOW §11`）。
- **证据**：`so-necessity-research-20261015` D-006/D-008 —— 16/16 closed run 均在无该角色下完成；真实缺口是“关闭时无承接”（实证 141/187 开放项关闭时无去向），而非缺少领域角色。
- **取舍**：完整方案（角色 + 载体 + 工具 + 记账）复杂度未被收益覆盖，违反“缺席容忍”；改为规则优先 + 零新增常设角色。

### 10.2 状态迁移权矩阵（唯一执行者）

- **缺口**：`wf.py state` 不校验身份，“PMO 或主会话可关”口径二义（前序 run FP-1）。
- **决策**：新增 `WORKFLOW §4.0` 把“谁能迁”写死；**内容写权与状态迁移权分离**，状态字段是流程推进操作，不算“写别人文档”。
- **矩阵全文**见 `WORKFLOW.md §4.0`（10 条迁移，覆盖立项 → 各阶段 → `closed`）。

### 10.3 ISSUES 所有权（四处口径一致）

- **决策**：QA 只**新增行**；`update/close` 仅由 `DECISIONS.md` 明确授权的 PMO 使用，授权范围仅「状态」「关联决策ID」两列，不改其他列、不删行；关闭/挂起必须有可追溯证据落点（`PROJECT §6` 或 `DECISIONS D-xxx`）。
- **取代关系**：`WORKFLOW §4` 契约表原表述（PMO 可在收轮时更新状态列）与隐式允许 QA 自行 `update/close` 的旧写法，均被本条取代；`roles/QA.md`、`roles/PMO.md`、`templates/README.md`、`roles/delegation-briefs.md` 同步。

### 10.4 主会话（MAIN）建模补全

- **缺口**：只新增 `roles/MAIN.md` 会与 `WORKFLOW §1/§2` 矛盾（前序 run RT-3），形成第二套角色定义。
- **决策**：一次落地——新增 `roles/MAIN.md`，同步改 `WORKFLOW §1/§2`（角色表新增 MAIN 行、去掉与事实不符的“只做三件事”）；`templates/PROJECT.md` 增“主会话提交范围”字段。

### 10.5 用字规范与两条收口规则

- **术语**：采用 `WORKFLOW §11` 术语表为唯一规范；`SO`、`Specialist Office`、`Specialist Officer`、`执行专员`、`领域专员`、`L1/L2/L3` 作为规范术语退役，历史材料保留原文。
- **关闭收口规则**：run `closed` 前，所有已知游离项必须有 owner + 去向，或由主会话在 `DECISIONS.md` 显式接受；否则不得关闭。写入 `WORKFLOW §7`。
- **跨轮承接规则**：跨轮/跨 run 承接必须写 owner + 去向 + 最晚复核轮；未立项的“下一 run”不算有效去向。写入 `WORKFLOW §6`。
- **命名**：规则用中文“关闭收口规则”“跨轮承接规则”；规范正文避免 `R1/R4` 代号（易与 `R-xxx` 风险 ID 混淆）。

### 10.6 阶段 2（本轮不做，仅登记）

不改 `scripts/**`、`templates/ISSUES.xlsx`、状态值与文档枚举；以下留待有真实样本与试点后再评估：

1. `doctor` 关闭门禁机检（关闭时检查游离项去向）；
2. STATUS 分节重复 / 执行体-WS 绑定检查；
3. `TERMINAL` 默认载体、游离角色/枚举/工具/记账；
4. S1 计划可验证性轻量检查；
5. 任何 `scripts/**` / `templates/ISSUES.xlsx` / 状态值改动；
6. 历史材料中退役术语的正文改写（历史 runs / 旧报告保持原样）。

## 11. H 盘安全门控与独立 SAFETY（2026-10-18）

> 需求来源：H 盘专项整理必须带安全门控，且每条未通过门控的指令由单独安全员审核。
> 规则落点：`WORKFLOW.md §2/§3/§4/§6/§11`、`roles/SAFETY.md`、`templates/specialized/h-drive-cleanup/`、`scripts/hdrive_gate.py`。

### 11.1 为什么不是又加一个常设角色

- 既有结论仍是“不设常设 SO/领域专员”；H 盘 run 的 SAFETY 是**任务级独立复核位**，只在 SPEC 明示启用门控时由主会话单独委派，随 run 关闭而结束。
- 角色边界刻意做窄：不计划、不执行、不写四件套，只对 `gate.status=FAIL` 的 action 通过脚本逐条写 review。
- 这样既满足“单独安全员逐条审核”的用户要求，也不把 SAFETY 扩张成第二个 PMO/领域专家。

### 11.2 为什么门控必须绑定 action digest

- 只审“命令大意”会在 action 参数被替换后失效；审核/人工批准均绑定 action canonical JSON 的 sha256。
- action 落盘后不提供 update 接口；“改完再审”必须提交新 action、新 ID、新 digest。
- 执行器在执行前再次校验 digest、gate、review、human approval 和文件系统前置条件，防止审核后状态漂移。

### 11.3 为什么默认隔离而不是删除

- H 盘是用户真实数据，删除不可逆；门控默认允许 `move/quarantine/copy/mkdir` 等可回滚动作。
- `purge` 只能作用于配置的隔离区，且固定为 red：必须 SAFETY approve + 独立人工 approve；本轮默认禁止 purge。
- `exec` 是受控例外，不是通用 shell 后门；解释器/破坏性程序永久不可执行，且必须有 dry-run 证据和 rollback。

### 11.4 为什么失败即停

- 一次执行多个 action 会让失败原因与现场变化难以归因；执行器一次只执行一个，首个非 `SUCCESS`/`EFFECT_MISMATCH` 即停。
- 失败动作不能“重试看看”，必须提交新 action 重新走门控；避免绕过审核或重复副作用。

### 11.5 已知边界

- 这是**工作流门控**，不是 OS 沙箱。若执行体直接 shell 写 H 盘，脚本无法从内核层面阻止；只能通过 SPEC 禁止 + QA 审计 + S1 停工追责。要在 OS 层强制，需另做只读挂载/专用执行账户/沙箱。
- 双执行后端已落地：POSIX 用 `scripts/hdrive_gate.py`（挂载路径），Windows 用 `scripts/windows/hgate.py`（原生 `H:\`，仅 mkdir/move）；两端语义相同，但路径/op 集合不同，run 必须在 DECISIONS 固定后端。
- `exec` 的静态路径检查是保守启发式，不能替代 SAFETY 逐条人工判断和 dry-run 证据。
- 隔离区保留期与最终 purge 由用户业务决策，不由门控自动决定。


## 12. 模板三层：冻结原子轮型 + 基准模板 + 领域特化（2026-10-23）

> 来源：`WORKFLOW-TAGS.md` 首轮标签化结论；用户要求“在基础母版上冻结原子轮型，并把复合类型登记为基准模板（特化重点参考）”。
> 规则落点：`WORKFLOW.md §4.1–§4.3`、`templates/contracts/`、`templates/baseline/`、`templates/specialized/README.md`。

### 12.1 为什么分三层

- **原子轮型**只回答“这一轮最小要产出什么、过哪些强制门、如何交接”，跨域稳定；适合冻结。
- **基准模板**只回答“复合类型通常由哪些原子轮型按什么顺序组合、重点证据是什么、哪些领域模板可参考”，是选型/特化入口。
- **领域特化**回答具体项目“写哪些路径、用什么命令、哪些风险修饰、DoD 是什么”，可以随项目变化，但不能改原子契约的最小集。
- 若把三者混成一个 `SPEC.md`，每次新增项目都会复制一遍门禁/交接，最终产生同名不同版和模板漂移；分层后只允许“加严 + adapter”，不允许重抄/删减母版接口。

### 12.2 冻结协议

- 冻结对象：`templates/contracts/**` + 基础母版文件；`LOCK.json` 记录 sha256，`python3 scripts/contract_lock.py check` rc=1 即漂移。
- 只增不改：变更必须升 `templates/contracts/VERSION`、写迁移影响、重新生成 `LOCK.json`；旧版本不原地覆盖。
- `wf.py new-run` 拒绝直接使用 `templates/baseline/*` 或 `templates/contracts/*`；基准模板不是 run 模板。

### 12.3 基准模板的定位

- `templates/baseline/REGISTRY.json` 是机器注册表；`REGISTRY.md` 是人读索引；每个 `BASELINE.md` 固定写主攻方向、特点、默认管线、强制证据、重点参考与成熟度。
- 领域 `SPEC.md §0` 用 `baseline:` + `contracts:` 双引用；没有匹配 baseline 时必须写 `baseline: none + 理由`，避免“无类型”特化悄悄扩散。
- baseline 的 M2/M3 只是成熟度，不是可直接运行承诺；只有具体领域 `templates/specialized/<name>` 才是 run 入口。

### 12.4 取舍与边界

- 代价是多了一层文档与一次 freeze 核验；收益是模板选型、证据和风险修饰不再靠记忆，也避免复制导致的门禁漂移。
- 不引入新角色/新状态值/新台账；原子契约仍跑在既有四件套与 STATUS/ISSUES/DECISIONS 中。
- 本轮只冻结接口和注册表；run 级 `tags/primary_type/maturity` 自动注入与插件面板读取仍属于后续实现。
