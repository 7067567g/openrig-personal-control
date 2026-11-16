<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: PROJECT
owner: PMO
state: pmo-plan
updated: <DATE>
-->

# PROJECT — <PROJECT-NAME>

> 写者：PMO ｜ 主会话只读 §6（+ 本文件头状态字段）｜ 其他角色只读本文件 + `SPEC.md`
> 特化：本文件已预填 H 盘整理的目标/阶段/安全门控；PMO 只做校验、细化、按盘点结果分区。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | `<GOAL>` |
| 项目根 | `<PROJECT-ROOT>`（本 run 的 H 盘根；必须是用户确认的挂载路径） |
| H 盘根 | `<H-ROOT>`（如 `/mnt/h`；与项目根一致或写明关系） |
| 第一轮范围 | `<H-SCOPE>`（只允许用户明确给出的目录/对象；禁止默认全盘） |
| 隔离区 | `<QUARANTINE>`（必须在 H 盘根内，不能等于根） |
| 写权限白名单 | `<WRITE-SCOPE>`；H 盘状态变化只能经 `hdrive_gate.py run`，run 产物仅写 `runs/<RUN-ID>/**` |
| 只读边界 | `scripts/**`、`roles/**`、`templates/**`、`WORKFLOW.md`、KB 正式域、H 盘系统/回收目录 |
| 主会话 | 人/主会话模型（负责逐条 `human-approve` red 动作） |
| 编制 | PMO×1 / TDO×<TDO-N> / QA×1 / **SAFETY×1** |
| 当前轮次 | Round <ROUND-N> |
| 终止判据 | 达成：§1 全部判据通过、`safety_pending=0`、无 open S1/S2；终止：连续 2 轮无进展、用户叫停或 H 盘根不可用 |

> 安全前置：`DECISIONS.md` 中 H 盘根、第一轮范围、隔离区、保留期、人工批准人五项未拍板前，本 run 不得产生任何写 H 盘的 action。

## 1. 目标与成功判据

- **G1 安全预检通过（只读）**：H 盘根真实存在且是挂载点；第一轮范围明确、不含系统目录；隔离区候选在根内且不等于根。
  - 判据：`findmnt -T <H-ROOT>` 输出、路径检查记录、用户确认的 `D-xxx`；未通过则 state 标阻塞。
- **G2 全量盘点**：范围内每个可枚举对象都有 item 记录与处置候选，不抽样。
  - 判据：`reports/inventory-*.jsonl` 可复算；对象数/大小/排除项/符号链接清单完整；QA 抽 10 项回源一致。
- **G3 处置计划可审计**：每个 item 有 `keep/move/copy/quarantine/needs-human` 结论；所有写动作已转 action。
  - 判据：item→action 映射表 100% 覆盖；`hdrive_gate.py propose` 后每个 action 有唯一 ID 与 digest。
- **G4 安全门控与逐条审核**：所有 FAIL action 由独立 SAFETY 逐条 review；所有 red 有独立人工批准；未审 FAIL=0。
  - 判据：`hdrive_gate.py status --json` 中 `safety_pending==0`；review 数 = FAIL 数；red 的 human-approval 数 = red approve 数；无批量记录。
- **G5 执行不越界**：只有 PASS 或已 approve 的 action 被执行；执行失败即停；无直接 shell 绕过。
  - 判据：execution 账本 `SUCCESS` + 失败项均有记录；审计无“无 gate/无 review/摘要不符”的执行；前后清单差异全部可解释。
- **G6 独立核验与收口**：QA 核对账本与前后清单；审计报告、隔离区清单、保留期、遗留项去向齐全。
  - 判据：`reports/audit-final.md`；ISSUES 无 open S1/S2；`doctor` 无新增 ERROR；关闭收口核对通过。

**反目标（明确不做）**：

- 不做全盘无差别清理，不把“整理”自动解释为删除。
- 不直接永久删除；不使用 `rm -rf`/`del`/`format`/`diskpart`。
- 不改 H 盘系统目录、回收站、挂载/分区/权限/属主。
- 不把 H 盘正文/隐私/凭证复制进 run 报告或 KB 正式域。
- 不让 TDO 自审、不让 SAFETY 执行、不批量审批。

## 2. 范围

### 2.1 范围内

- 用户确认的第一轮 H 盘目录：`<H-SCOPE>`；
- `runs/<RUN-ID>/**`：盘点、action、门控、审核、执行、审计报告；
- 经用户确认、P2 计划中逐项列出的 H 盘对象。

### 2.2 范围外

- H 盘根本身作为单个 action 目标；系统目录、回收站、`$Recycle.Bin`、`System Volume Information`、符号链接/重解析点；
- 未在 P2 处置表出现的对象；
- 任何 H 盘以外路径的写入（run 目录除外）；
- KB 正式域、`scripts/**`、`roles/**`、`templates/**`、`WORKFLOW.md`；
- 永久删除（purge）默认不执行，除非用户书面确认且独立人工批准。

### 2.3 假设与依赖

- 用户能提供 H 盘在 WSL/原生环境中的可访问路径，并确认挂载状态；
- `scripts/hdrive_gate.py` 可运行；`safety/config.json` 已由主会话初始化；
- 指定独立 SAFETY 与人工批准人；
- 磁盘空间足够、隔离区可写；若不足，执行必须暂停并升级。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据来源 | 采集方式 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | 预检通过项 | 0/4 | 4/4 | 待采集 | `reports/preflight.md` | 路径/挂载/权限/用户确认逐项打勾 |
| M2 | 盘点覆盖率 | 0 | 100% | 待采集 | `reports/inventory-*.jsonl` | 对象数复算 + QA 抽检 |
| M3 | item 处置结论率 | 0 | 100% | 待采集 | `reports/disposition-*.md` | item→action 映射 |
| M4 | FAIL 逐条审核完成率 | 0 | 100% | 待采集 | `safety/reviews/` | review 数 = FAIL 数；无批量 |
| M5 | red 人工批准完成率 | 0 | 100% | 待采集 | `safety/human-approvals/` | 审批数 = red approve 数 |
| M6 | 未授权执行数 | 0 | 0 | 待采集 | `safety/executions/` | 对照 gate/review/human/digest |
| M7 | 范围外/未解释变化 | 0 | 0 | 待采集 | 前后清单 + QA 审计 | 差异逐条解释 |
| M8 | 开工/收口门禁 | — | `safety_pending=0` + `doctor` PASS | 待采集 | 命令输出 | 实跑 |

## 4. 分任务（Workstreams）

> H 盘范围在 P1 前未知，因此 WS 先按阶段声明；P4 执行分区必须在 P1 盘点完成后按顶层目录拆分，保证互不重叠。

| WS | 阶段 | 任务 | 产出物（路径） | 验收判据 | 依赖 | 建议执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WS-1 | P0–P1 | 预检 + 全量只读盘点 + 分类 | `reports/preflight.md`、`reports/inventory-*.jsonl`、`reports/classification-*.md` | G1/G2；100% 覆盖；不写 H 盘 | 用户确认范围 | TDO | 待开始 |
| WS-2 | P2 | 逐项处置计划 + actions.jsonl + propose | `reports/disposition-*.md`、`actions.jsonl`、`safety/actions/` | G3；item→action 100% | WS-1 | TDO | 待开始 |
| SAFETY | P3 | 对每个 FAIL action 逐条审核；red 记录待人工批准 | `safety/reviews/ACT-*.json` | 每条 FAIL 恰好一条审核；无批量/自审 | WS-2 + `gate` | SAFETY | 待开始 |
| WS-3a…n | P4 | 按顶层目录分区的执行 | `safety/executions/`、`STATUS-Round-<N>.md` | G5；分区互斥；一次一个 action | P3 放行 | TDO | 待开始 |
| WS-QA | P5 | 账本/清单/范围外独立核验 | `ISSUES.xlsx` 当轮新增行、`reports/qa-verification.md` | G6；无绕过；无未解释差异 | WS-3 | QA | 待开始 |
| WS-4 | P6 | 审计报告 + 隔离区清单 + 保留期 | `reports/audit-final.md`、`reports/quarantine-manifest.md` | G6；DoD 全过 | WS-QA | TDO/PMO | 待开始 |

## 5. 轮次计划与结论

### Round <ROUND-N> 计划（PMO S1）

- 本轮目标：只做 P0–P2 的只读盘点与处置计划，以及门控初始化；不执行任何 H 盘写 action。
- 本轮不做：不 purge、不移动未列入计划的对象、不碰系统目录。
- 预期 R2 才进入 P3/P4；P4 分区数由主会话按盘点和 §2.1 TDO 数量决策表重定。

### Round <ROUND-N> 结论（PMO S4）

- 完成：
- 未完成 / 阻塞：
- 下轮候选：

## 6. PMO 上报区（唯一给主会话的摘要）

> 主会话只读本区。安全门控摘要可由 PMO 在本区引用 `hdrive_gate.py status --json` 的数字，但不贴 action 正文。
> 没有待拍板项就写“无”；有则必须给全四栏。

- **本轮结论**：<一句话>
- **安全门控摘要**：actions=__ / gate_pass=__ / gate_fail=__ / safety_pending=__ / safety_reject=__ / red_pending_human=__ / executed_ok=__ / executed_bad=__
- **待拍板**：

| 编号 | 分歧/选项 | 选项 A | 选项 B | PMO 建议 | 最晚决策时点 |
| --- | --- | --- | --- | --- | --- |
| Q-1 | H 盘根与第一轮范围 | `<H-ROOT + scope>` | `<另一个明确范围>` | 用户确认后再动盘 | 任何写 action 前 |
| Q-2 | 隔离区与保留期 | `<QUARANTINE>` / `<N> 天` | `<另一个位置/期限>` | 在 H 盘根内且可回滚 | P2 前 |
| Q-3 | 是否允许 purge | 本轮不 purge | 逐条双批后 purge | 推荐本轮只隔离 | P3 前 |

- **指标变化**：<M1–M8: 前 → 后>
- **下一轮建议编制**：TDO×<N'>（盘点后按顶层目录拆分；没有互斥分区时 N'=1）
- **风险提示**：<1 条最重要风险 + 对应 ISSUES ID>

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| <DATE> | R<ROUND-N> | 建档 | 主会话 |
