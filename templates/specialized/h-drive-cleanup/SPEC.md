# SPEC — H 盘专项整理（安全门控 + 独立安全审核员）

## 0. 分层声明

baseline: composite/safe-cleanup@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

> 本文件是本 run 的**特化规则**，与通用 `WORKFLOW.md` / `roles/*` 冲突时以本文件为准。
> 不可覆盖的四条通用约束仍然有效：文档即接口、单一写者、STATUS 加锁逐条提交、分歧不落地。
> 本 run 额外启用双人控制：**门控自动判定 + 独立 SAFETY 逐条复审 + red 动作人工批准**。
> 实际 run 若选择 Windows 后端，`WINDOWS-RUN.md` 是该 run 的 Windows 事实源（路径/门控/两轮计划）；模板本身不预置真实路径。后端选择和命令映射见 §4.0 与 §10。

## 1. 任务与边界

对用户指定的 H 盘范围做专项整理：

1. 先只读盘点，建立范围内**全量清单**与逐项处置依据；
2. 只做“保留 / 移动 / 复制 / 隔离（quarantine）”等可回滚动作；
3. 永久删除（`purge`）默认不在本轮执行；确需执行时，必须逐条安全审核 + 独立人工批准，并保留证据；
4. 每一条会改变 H 盘状态的指令都必须先经过本 run 选定的门控执行器（POSIX `scripts/hdrive_gate.py` / Windows `scripts/windows/hgate.py`）；门控 FAIL 的指令必须由独立安全审核员**一条一条**审核；
5. 任何未通过门控、未审核、被拒绝或摘要已变化的指令，都不得执行。

**反目标**：

- 不做全盘“无差别清理”；范围、保留规则、隔离区位置未由用户确认前不得改 H 盘。
- 不格式化、不分区、不改盘符/挂载、不改文件系统、不碰系统/回收目录。
- 不通过 `rm -rf`、`del`、`rd`、`format`、`diskpart` 等命令直接删除；删除只能通过隔离区 + 独立审批的 `purge`。
- 不把 H 盘内容复制进 KB 正式域；KB 只保存索引、证据和脱敏报告。
- 不让提出指令的 TDO 自己审自己，不让安全审核员执行指令，不让执行者既当安全审核员又当人工批准人。

## 2. 角色与独立性

| 角色 | 数量 | 本 run 职责 | 禁止 |
| --- | --- | --- | --- |
| 主会话（MAIN） | 1 | 立项、确定 H 盘根/范围、委派、逐条人工批准 red 动作、关闭 run | 不直接执行 H 盘命令 |
| PMO | 1 | 计划、范围拆分、收轮、把安全/QA 结果压成 §6 选项 | 不执行 H 盘命令、不代签安全审核 |
| TDO | N（按分区） | 只读盘点、提交 action、经门控执行已放行动作、写 STATUS | 不审核自己的 action、不绕过执行器 |
| **SAFETY（独立安全审核员）** | 1 | 对**每条**门控 FAIL 的 action 逐条 `approve/reject`，写安全审核账本 | 不提出/不修改/不执行 action；不批量审；不代替人工批准 |
| QA | 1 | 独立核查范围覆盖、证据、门控/审核/执行账本一致性 | 不修产出物、不执行 H 盘命令 |

- SAFETY 是**本特化 run 的任务级独立复核角色**，不是通用工作流的常设角色，也不是已退役的 SO/领域专员结构。
- SAFETY 必须由主会话用**独立会话**委派（`wf.py brief/delegate --role safety`）；不得在 TDO/QA 会话里换名字“角色扮演”，也不得与提出者/执行者共用同一会话。
- SAFETY 只能通过本 run 选定的门控执行器 `review` 命令写 `safety/reviews/ACT-*.json`，不得手改 JSON。
- red 风险动作还需要 `human-approve`；人工批准人由用户/主会话在 `safety/config.json` 中指定，且必须与 SAFETY、提出者、执行者分离。

## 3. 四个安全不变量（违反任一 = S1，停止 run）

1. **默认拒绝**：未被门控判定为 PASS，或 FAIL 未获 SAFETY approve，或 red 未获人工批准，执行器一律拒绝。
2. **摘要绑定**：审核和批准都绑定 action 的 `digest`；action 原文任何改动都会使旧审核失效。
3. **逐条审核**：一条审核记录只对应一个 action；不允许“整批通过”“这一批都差不多”。
4. **禁止绕过**：所有 H 盘状态变化只能由本 run 选定的门控执行器 `run` 执行；TDO 不得直接运行 `mv/cp/rm/robocopy/...` 修改 H 盘。发现绕过立即停工并按 S1 记录。

## 4. 阶段流程

```text
P0 预检（只读）
  检查 H 盘挂载点、用户给定范围、隔离区候选、磁盘空间、读写权限
  ↓ 任一项不满足 = BLOCKED，不初始化写操作
P1 全量盘点（只读）
  按用户范围列出每个顶层对象 + 递归统计 + 重复/大文件/疑似临时文件候选
  产出完整 inventory（不许抽样）；每个对象有唯一 item id
  ↓ 主会话确认盘点范围与保留规则
P2 处置计划（只写 run 目录）
  每个 item 给出：keep / move / copy / quarantine / needs-human
  生成 actions.jsonl；每条 action 带 intent、before 证据、回滚/去向
  ↓ 主会话确认计划；此阶段不得改 H 盘
P3 门控与逐条安全审核
  所选后端门控执行器 propose → gate
  PASS：可进入执行队列
  FAIL：SAFETY 逐条 review；reject 即退出队列
  red：SAFETY approve 后仍需人工 human-approve
  ↓ 未审 FAIL = 0；未批准 red = 0
P4 分批执行（一次一个 action）
  只运行已放行 action；每个 action 独立执行、独立记录
  首个非 SUCCESS / EFFECT_MISMATCH 即停，后续全部暂停
  ↓
P5 独立核验（QA）
  对照执行账本、前后清单、隔离区清单、异常清单、范围外变更
  未通过的 action 必须回到 P2 重新提交新 action
  ↓
P6 收口（只写 run 目录）
  生成审计报告；隔离区保留期与后续处置交给用户决策
  purge 不在本轮默认执行
```

### 4.0 执行后端选择（P0 第一个决策）

本模板支持两个执行后端。实际 run 必须在 `DECISIONS.md` 固定一个，并在运行副本的 `SPEC.md` 记录；不得在同一个 run 混用。

| 后端 | 根路径 | 执行器 | 支持 op | 命令形态 |
| --- | --- | --- | --- | --- |
| `posix` | 真实挂载点（如 `/mnt/h`） | `python3 scripts/hdrive_gate.py` | mkdir/copy/move/quarantine/purge/exec（默认仅建议 mkdir/move） | `--run <run-id>` |
| `windows` | Windows 原生 `H:\` | `python3 scripts/windows/hgate.py` | 仅 mkdir/move | `--run-root <Windows run 目录>` |

- 后端选择写入 `DECISIONS.md`，没有选择 = BLOCKED，不初始化门控。
- 后端选择一旦固定，action 路径、run-root、op 集合和保护清单均按该后端校验。
- Windows 后端不能执行 purge/exec/copy；删除候选只能 move 到待确认区。
- 两后端共享同一安全不变量：默认拒绝、digest 绑定、逐条 SAFETY、red 人工批准、失败即停。

### 4.1 预检（P0）

必须在 H 盘根运行前完成。

**POSIX 后端（示例）：**

```bash
test -d /mnt/h && findmnt -T /mnt/h
python3 scripts/hdrive_gate.py --help
```

**Windows 后端（示例）：**

```bash
python3 scripts/windows/hgate.py --help
# H:\ 的真实盘点由 PowerShell 执行；路径与 run-root 见 §10
```

- 根路径必须与 §4.0 选择的后端一致：POSIX 后端必须是真实挂载点（如 `/mnt/h`）；Windows 后端使用用户确认的 `H:\` 原生盘符，由 `scripts/windows/hgate.py` 包装 PowerShell 校验。两后端都不能猜路径。
- `/mnt/h` 或其他挂载路径只能由用户确认，不得猜。
- 范围必须是 H 盘根下的一个或多个明确目录；**禁止以整个 `H:\` 根作为第一轮执行范围**，除非用户书面确认且盘点/门控计划已拆分。
- 隔离区必须是 H 盘根内的独立目录（建议 `H:\_整理隔离区`），不能等于根，不能位于系统/回收目录。
- 盘未挂载、范围不明、隔离区未定、用户未确认处置口径：写 `STATUS` 阻塞并回执，禁止初始化门控或执行任何写操作。

### 4.2 只读盘点（P1）

- 每个范围内对象必须有 `item_id`、路径、类型、大小、修改时间、hash（文件/可选）、归属处置候选、证据路径。
- 必须覆盖范围内 **100% 可枚举对象**；只读命令可以不经门控，但必须把命令、时间、结果摘要写进证据。
- 符号链接/重解析点只登记，不跟随、不修改；系统目录/回收站直接标记排除并记录原因。
- 盘点报告写到 `runs/<run-id>/reports/inventory-*.md|jsonl`，不得写进 H 盘。

### 4.3 处置计划与 action（P2）

`actions.jsonl` 每行一个 JSON action，由所选后端的门控执行器 `propose` 登记。下面示例是 POSIX 路径格式；Windows 只接受 `mkdir/move` 且路径使用 `H:\` 原生格式（见 §10）。

```jsonl
{"op":"mkdir","intent":"创建隔离区根目录","dst":"/mnt/h/_整理隔离区"}
{"op":"quarantine","intent":"将候选临时文件移入隔离区，保留可回滚路径","src":"/mnt/h/某目录/a.tmp","dst":"/mnt/h/_整理隔离区/2026-10-18/某目录-a.tmp"}
```

- 一个 action 只表达一个原子动作、一个明确目标；禁止通配符、递归目录批量、多个源/目标塞一条。
- `move/quarantine` 的 `dst` 必须在执行前不存在，且父目录已存在；`quarantine` 的 `dst` 必须在隔离区内。
- 所有 action 必须带 `intent`；`exec/purge` 额外必须带 `dry_run_evidence`，`exec` 还要带 `rollback`。
- 写入 H 盘的动作必须是 `mkdir/copy/move/quarantine/purge/exec` 之一；未识别 op 会被门控标为 `executable=false`，即使 SAFETY approve 也不能执行。

### 4.4 门控与审核（P3）

POSIX 示例（Windows 使用 `scripts/windows/hgate.py` 的等价命令，参数映射见 §10）：

```bash
# 1) 初始化：根、隔离区、安全审核员、人工批准人
python3 scripts/hdrive_gate.py init --run <run-id> \
  --root /mnt/h --quarantine-root /mnt/h/_整理隔离区 \
  --safety-reviewer safety-a1 --human-approver user

# 2) 登记 action 并跑门控
python3 scripts/hdrive_gate.py propose --run <run-id> --file actions.jsonl --agent tdo-a1
python3 scripts/hdrive_gate.py gate --run <run-id>

# 3) SAFETY 逐条审核每个 FAIL（一次一个 action；digest 从 gate 输出复制）
python3 scripts/hdrive_gate.py review --run <run-id> --action ACT-0001 \
  --reviewer safety-a1 --verdict approve|reject --digest <digest> \
  --reason "..." --evidence "reports/...."

# 4) red 动作再由独立人工批准（一次一个 action）
python3 scripts/hdrive_gate.py human-approve --run <run-id> --action ACT-0001 \
  --approver user --digest <digest> --reason "..."

# 5) 查看门控状态
python3 scripts/hdrive_gate.py status --run <run-id>
```

- `PASS`：自动放行，不需要 SAFETY 审核，但仍受批次/用户计划确认约束。
- `FAIL`：进入待审队列；SAFETY 必须逐条审。`reject` 的 action 永久退出本轮执行队列。
- `red`：SAFETY approve 后仍需人工批准；未批不得执行。
- 任何 action 原文改动都会触发 `action digest` 不一致；必须重新 propose，旧审核不得复用。
- 批量通过、代签、补签、空泛理由、无证据 approve：一律按 S1 安全事件处理。

### 4.5 执行（P4）

POSIX 示例；Windows 使用 `scripts/windows/hgate.py run --run-root ...`（见 §10）：

```bash
# 一次只执行一个；执行器会重新检查路径、摘要、审核和前置条件
python3 scripts/hdrive_gate.py run --run <run-id> --action ACT-0001 --agent tdo-a1
```

- 执行器不使用 shell；`argv` 为固定数组，`shell=False`。
- 每次执行前重新检查：H 盘仍挂载、action digest 未变、审核/批准存在、源/目标前置条件仍成立。
- 任一失败：执行器写 `BLOCKED_PRECHECK` 或 `FAILED/EFFECT_MISMATCH`，本轮立即停；不得“重试一下看看”。
- 失败后如需继续，提出者必须提交新 action（新 ID、新 digest），重新门控/审核。
- 执行后不得手工补写执行结果；以 `safety/executions/ACT-*.json` 为准。

### 4.6 保护路径与两轮整理（用户特定规则）

当用户给出 protected manifest 时，门控必须把其中的路径和内容视为不可变：

- **固定驻留**：专业软件工区、路径依赖目录、根目录 Excel/PPT 等，只能标记 `KEEP`，不得生成 `move` action；
- 根目录 Excel/PPT 的“原位”包括不改名、不改内容、不移动；
- 每轮开始前先写 `reports/protected-manifest.md`，列出 `KEEP_TOP` / `KEEP_ROOT` / `APP_MANAGED` / `HOLD`；
- 任何 action 命中 protected 路径 = 门控 FAIL + S1，不能靠 SAFETY approve 绕过，必须改计划；
- 非 protected 的工作资料允许结构性“破坏性整理”（拍扁、按树聚合），但每个文件必须写入 `move-ledger.csv`：旧路径、新路径、大小、时间、批次、状态；
- 非工作冷备份/媒体可以拍扁/浅树聚合；目标命名冲突时使用稳定 hash/来源前缀，不得覆盖；
- 计划按 **R1 冻结 + 整目录归位**、**R2 文件级拍扁/聚合 + 混合区收尾** 两轮推进；R2 可拆多个执行批次，但保持同一工作流轮次；
- 用户未明确允许永久删除时，move-only 门控不得包含 delete/purge 分支；结构破坏 ≠ 数据删除。

### 4.7 核验与收口（P5–P6）

QA 必须独立核对：

1. 盘点清单 vs 执行账本：范围内每个对象是否都有处置去向；
2. gate 账本 vs review 账本：每个 FAIL 是否恰好有一条审核记录；每个 red 是否有人工批准；
3. execution 账本：是否存在未 PASS/未审核/未批准/摘要不符却执行的动作；
4. 前后清单：目标是否变化、未预期覆盖/删除是否存在、隔离区清单是否完整；
5. 范围外：是否出现 H 盘之外写入或系统目录变更；
6. 备份/回滚：隔离区路径、保留期、恢复说明是否可执行。

收口报告必须包含：范围、对象总数、处置统计、门控 PASS/FAIL、FAIL 审核通过/拒绝、red 人工批准数、执行成功/失败、异常清单、隔离区保留到期日、遗留项 owner/去向。

## 5. 权限边界

| 路径 | 权限 |
| --- | --- |
| 用户指定的 H 盘范围 | TDO 只读盘点；改状态只能经所选后端的门控 `run`（POSIX `hdrive_gate.py` / Windows `scripts/windows/hgate.py`） |
| 隔离区 | 仅在 SPEC/config 允许时写入；仅 `quarantine` 和经双批的 `purge` 可操作 |
| `runs/<run-id>/**` | TDO 写产出物/STATUS；SAFETY 写 review 账本；QA 写 ISSUES；主会话写 DECISIONS |
| `scripts/`、`roles/`、`templates/`、`WORKFLOW.md` | 只读，不在本 run 修改 |
| H 盘系统/回收目录 | 绝对禁止 |
| KB 正式域 | 不写入；只允许脱敏指针/证据 |

TDO 只改 `PROJECT.md` §0 白名单内的 run 产物，不改其他项目、不改 KB 正式域；H 盘写入只走执行器。

## 6. 安全门控数据与证据

每次行动必须在 run 目录留下：

- `safety/actions/ACT-xxxx.json`：action 原文 + 提出者 + digest；
- `safety/gates/ACT-xxxx.json`：PASS/FAIL、风险、原因码；
- `safety/reviews/ACT-xxxx.json`：SAFETY 逐条终审（FAIL 才有）；
- `safety/human-approvals/ACT-xxxx.json`：red 动作的独立人工批准；
- `safety/executions/ACT-xxxx.json`：命令 argv、cwd、返回码、输出 hash/摘要、效果检查；
- `reports/inventory-*.jsonl`：范围全量清单；
- `reports/audit-final.md`：P6 审计报告。

证据优先级：可复现命令 + 结果摘要 > 文件路径 + 行号/章节 > 文件 hash > 数字对比。禁止“应该没问题”。

> **隐私边界**：`safety/executions/` 与 action 账本会记录 H 盘路径、命令 argv 和输出摘要，可能含个人信息。
> run 目录默认在 git 工作树内；提交或 push 前必须脱敏，含隐私/凭证/敏感路径的 run 应保持本地，不得进入共享仓库。

## 7. 完成定义（DoD）

- P0：H 盘根、用户范围、隔离区、保留规则、人工批准人全部在 `DECISIONS.md` 有明确决定；
- P1：范围内对象清单可复算，100% 有 item 记录；系统目录/符号链接已排除并留证；
- P2：每个 item 有处置结论；所有写动作已转成 action；
- P3：每个 FAIL action 恰好一条 SAFETY 审核；每个 red action 有独立人工批准；未审 FAIL = 0；被拒 action 未执行；
- P4：执行成功数 + 失败数 + 未执行数 = action 总数；无 `SUCCESS` 之外的动作被静默忽略；
- P5：QA 无 S1/S2；无绕过门控执行；无范围外写入；无未知或未解释的对象变化；protected manifest 命中 0 次移动；
- 每个被移动文件在 `move-ledger.csv` 有且只有一条旧→新映射；冲突/未决项进入 `90_待确认` 清单；
- P6：审计报告、隔离区清单、保留到期日、遗留项 owner/去向齐全；
- 所选后端执行器的 `status --json` 中 `safety_pending == 0`（POSIX：`scripts/hdrive_gate.py --run`；Windows：`scripts/windows/hgate.py --run-root`）；
- 结束时 `python3 scripts/wf.py doctor <run-id>` 无 ERROR。

## 8. 禁止清单（硬）

- 禁止 `rm -rf` / `del /s` / `rd /s` / `format` / `diskpart` / `dd` / `mkfs` 直接操作 H 盘；
- 禁止移动 protected manifest 中的路径；禁止点通配符、根目录、系统目录、回收站、符号链接/重解析点作为 action 目标；
- 禁止 TDO 自己 review、SAFETY 自己 approve 自己提出/执行的 action、任何人代签；
- 禁止批量审核、先执行后补审、改 action 后沿用旧 digest；
- 禁止把 `exec` 当作绕过门控的通用后门；解释器和破坏性程序在 exec 中永久不可执行；
- 禁止把 H 盘源文件内容、个人隐私/密钥/凭证写入共享报告或 KB；路径/输出摘要入 git 前必须脱敏；敏感 run 保持本地且不 push；
- 禁止未经用户确认执行 `purge`；purge 必须独立人工批准，并遵守保留期；
- 禁止 push、改分支/tag、改工作流母版（`WORKFLOW.md`、`roles/**`、`templates/**`、`scripts/**`）。

## 9. 启动检查单（主会话）

1. 已选择 `posix` 或 `windows` 后端，H 盘根/run-root 已由用户确认；
2. 用户给出第一轮范围（至少一个明确目录），并确认不包含系统目录；
3. 隔离区路径、保留期、是否允许永久删除已记录到 `DECISIONS.md`；
4. 指定独立 SAFETY（不得与 TDO/QA/人工批准人同身份）；
5. 指定人工批准人（用于 red 动作）；
6. 初始化所选后端的门控执行器（POSIX `hdrive_gate.py` / Windows `scripts/windows/hgate.py`），先跑 P1 只读盘点；
7. 在 P1 完成并经用户确认前，不创建任何写 action。

## 10. Windows 后端命令对照（`windows` 选型时使用）

当 `DECISIONS.md` 选择 `windows` 后端时，H 盘通过 Windows PowerShell 访问，不要求挂载到 WSL。执行入口与 POSIX 示例等价，但 op 仅 mkdir/move、参数用 `--run-root`：

```bash
cd workflow-group
# 所有命令都通过 WSL 包装器调用 Windows PowerShell；路径参数可写 WSL 或 Windows 路径
python3 scripts/windows/hgate.py status --run-root /mnt/c/Users/Administrator/h-cleanup/<run-id> --json
```

Windows 执行器只支持 `mkdir` 和 `move`，没有 `delete/copy/exec`。删除候选一律生成 `move` action，目标写到：

`H:\_整理收纳\90_待确认\...`

- protected manifest：`kickoff/h-drive-windows-protected.json`；
- Windows run 状态目录：`C:\Users\Administrator\h-cleanup\<run-id>\safety\`（敏感原始账本，先留本地）；
- 根目录 Excel/PPT 由 protected 扩展名规则强制保持原位；
- FAIL action 必须由独立 SAFETY 会话逐条审核：
  `python3 scripts/windows/hgate.py review --run-root ... --action ACT-xxxx --reviewer safety-a1 --verdict approve|reject --digest <digest> --reason "..." --evidence "..."`；
- 执行一条：
  `python3 scripts/windows/hgate.py run --run-root ... --action ACT-xxxx --agent tdo-a1`；
- 每批结束后 `status --json`，`safety_pending` 必须为 0 才能进入下一批。
