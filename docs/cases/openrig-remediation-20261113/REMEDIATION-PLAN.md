# 月月bot / wechat-bridge-v2 专项整改方案

> 日期：2026-11-13
> 适用工作区：`<repo>`
> 适用 run：`sctg-app-feel-auto-20261113`
> 文档性质：整改执行合同。交给执行智能体后，按本文顺序执行；不要跳步，不要先跑新一轮。
> 原则：先冻结、再对账、再修驱动、再补验收、最后恢复跑轮。任何“先跑一轮看看”的做法都视为违反本方案。

---

## 0. 一句话结论

当前不是“OpenRig 30 轮自动流程跑得不好”，而是：

> **一个 SCTG task-card + `dsh --profile headless` 单 seat + Python `auto_driver.py` 的 33 轮混合计划，在 R15.5 处停止；它没有使用 OpenRig 的 rig/queue/workflow，`check_round.py` 又大量是 token/file 检查，导致每轮 PASS 后仍要靠人工审计补轮。**

本次整改目标不是“再跑几轮”，而是把**轮次语义、执行驱动、验收门禁、独立 QA、状态权威、telemetry、卫生与发布**一次性收口，使后续 30 轮可重复、可恢复、可审计、可停止。

---

## 1. 当前事实（只读盘点结果）

### 1.1 运行器事实

| 事实 | 证据 |
|---|---|
| 当前 run | `.sctg/runs/sctg-app-feel-auto-20261113/` |
| 驱动使用 DSH 单 seat | `tools/sctg/auto_driver.py` 中 `DEFAULT_SEAT = ["dsh", "--profile", "headless"]` |
| 主 driver 没有 OpenRig | `auto_driver.py` 只调用 SCTG kit 的 `render/start/dispatch/collect/gate` 和 `subprocess.run([dsh, prompt])`，没有 `rig up/send/queue/workflow` |
| OpenRig 只在 R15.5 出现 | `rounds.yaml` R15.5 `host_only: true`、`seat: openrig-dsh` |
| 单 seat 串行 | `docs/AUTO-RUN-PREP-2.md` 自述：“单 seat 串行，尚无 handoff/join” |
| SCTG kit 来源 | `auto_driver.py` `DEFAULT_KIT` 指向 `workflow-group/drafts/sctg/kit` |

### 1.2 轮次事实

`tools/sctg/rounds.yaml` 当前有 **33 个轮位**：

```text
R01–R30
+ R05.5
+ R09.5
+ R15.5
```

其中：

```text
needs_main: R16, R25, R29, R30
external:   R21, R22, R23, R28
host_only:  R15.5
```

`docs/AUTO-RUN-PREP-3.md` 写的是 **32 个轮位**，与当前 `rounds.yaml` 的 33 不一致。

### 1.3 状态事实

`.sctg/runs/sctg-app-feel-auto-20261113/`：

```text
ROUNDS.jsonl 记录了 R03–R15，共 13 条 PASS
R15.5 报告已存在（reports/sctg/R15.5.md），但没有写进 ROUNDS.jsonl
BLOCKED 内容 = R15（12:48）
DONE    内容 = all requested rounds passed（14:59）
```

也就是说：

```text
BLOCKED 与 DONE 同时存在
R15 在 ROUNDS.jsonl 中 PASS，但 BLOCKED 仍保留 R15
R15.5 没有被状态文件登记
DONE 的“all requested rounds passed”与 13 条 PASS 不一致
```

### 1.4 验收事实

- `sctg-kit` 的 `g0–g3` 只检查 schema / scope / evidence / command，不检查业务语义。
- `tools/sctg/check_round.py` 对 R10–R30 主要依赖 `round_checks.py` 的文件存在 + token 检查。
- 例如：
  - R10：`sim/app.js` 含“重连”、报告含“断线”
  - R11：文档含“评测”、报告含“记忆”
  - R12：报告含“修正”、文档含“回退”
  - R13：`sim/app.js` 含“会话”、报告含“切换”
  - R14：`sim/app.js` 含“搜索”、报告含“回忆”
  - R15：`sim/app.js` 含“记忆”、报告含“钉住”
- 这些检查不能证明真实 DOM 行为、交互手感、真机表现、live 链路。
- `tools/sctg/app_smoke.py` 也主要是 token + Node 测试，不是 UI/真机 E2E。

### 1.5 时间事实

`ROUNDS.jsonl`：

```text
R03 08:51:34
R15 12:56:10
```

13 轮约 4 小时 05 分，平均约 19 分钟/轮。  
R10–R15 约 8 分钟/轮。  
按当前粒度，30 轮约 4–9.5 小时，尚未计 R16/R25/R29/R30 人工、R21–R23/R28 外部 Android、反复插入的准备/审计轮。

### 1.6 Git 卫生事实

- 当前分支 `main`，HEAD `54b23dc`。
- 工作区有大量未提交修改和未跟踪文件：
  - 修改：`sim/app.js`、`sim/styles.css`、`lib/*.mjs`、`test/*`、`docs/*`
  - 未跟踪：`tools/sctg/**`、`tools/adb/**`、`reports/sctg/**`、`docs/AUTO-RUN-*`、`test/adb-*` 等
- `.sctg/`、`.openrig/`、`.claude/`、`CLAUDE.md`、`.mcp.json` 被 `.gitignore` 忽略。
- `reports/sctg/adb/R15.5.json` 和 `reports/sctg/R15.5.md` 含真实设备 target `<tailnet-device>:5555`；公开/外发前必须脱敏。

---

## 2. 问题清单（按优先级）

### P0 — 阻断正确性

#### P0-1 执行架构名不副实

- 文档/预期把它当 OpenRig 多 seat 流程；
- 实际是 DSH 单 seat + Python driver；
- 没有 rig/queue/workflow/transcript/resume；
- OpenRig 只在 R15.5 手工出现。

**后果**：对 OpenRig 的期待（多 seat、队列、自动推进、独立 QA、恢复）全部落空；每轮只能靠单 seat 自证。

#### P0-2 轮次语义混合、计数漂移

- 30 产品轮 + 3 准备轮 + 4 人工轮 + 4 外部轮混在同一个 `rounds.yaml`；
- 32 vs 33 轮位不一致；
- R15.5 后加但未登记状态；
- `BLOCKED` / `DONE` 同时存在；
- `DONE` 与 `ROUNDS.jsonl` 不一致。

**后果**：无法判断“当前第几轮”“还差几轮”“是否完成”；每次人工审计都要先修复状态。

#### P0-3 验收门禁过弱

- `check_round.py` 大量 token/file 检查；
- `app_smoke.py` 不是 UI E2E；
- `g0–g3` 不检查业务语义；
- 单 seat 既生产又自证；
- 没有独立 QA seat/角色。

**后果**：gate PASS 不代表功能正确；人工必须逐轮补审计，导致 R05.5/R09.5/R15.5 这类返工轮不断插入。

#### P0-4 工作区未冻结、未提交

- 大量业务/流程文件未提交；
- 自动跑继续写文件会覆盖/混叠；
- 没有 baseline tag；
- 没有可回滚点。

**后果**：整改和继续跑轮互相污染；一旦出错无法区分“整改前/整改后”。

### P1 — 影响可维护性

#### P1-1 状态写入不是原子的

- `auto_driver.py` 直接写 `ROUNDS.jsonl` / `DONE` / `BLOCKED` / `NEED_MAIN`；
- 没有临时文件 + rename；
- 没有 lock；
- 没有 schema/版本号；
- 没有 resume 前的状态一致性校验。

#### P1-2 `--all` 语义不完整

- 遇到 `NEED_MAIN` / `BLOCKED` 就停止；
- 但已写入 `DONE` 会导致后续误判；
- 没有 `--continue-nonblocking`、`--halt-on-need-main` 的明确策略；
- `DONE` 的写入条件不是“所有产品轮 PASS”。

#### P1-3 缺少 round telemetry

没有每轮：
```text
start/end
duration
attempt count
gate/check verdict
changed files
test count
evidence hash
human intervention
issue opened/closed
```

#### P1-4 外部 Android 轮未隔离

- R21/R22/R23/R28 写 `../bridge-app/**`；
- 主仓 driver 不能跨仓写；
- 目前没有独立 run/独立 write scope/独立验收；
- `R15.5` 的 ADB 自动结论也只是 `ADB_PASS_NEED_MAIN`。

#### P1-5 `check_round.py` 与 `round_checks.py` 职责混乱

- `check_round.py` 既有硬编码分支，又有 `ROUND_CHECKS` 注册表；
- R01–R09 与 R10–R30 的检查风格不一致；
- 缺少统一的 `check-manifest` schema；
- 部分轮次仍是 token 占位。

#### P1-6 Git/发布卫生

- 生成物 `reports/sctg/**` 未提交；
- `.sctg/` 被忽略，导致 submission/evidence 不可复现；
- R15.5 含设备 target；
- `tools/adb/`、`tools/sctg/` 未纳入版本控制；
- 没有 baseline tag / 整改分支。

### P2 — 影响体验与效率

- 30 轮粒度过粗：每轮 = 一张卡 + gate + check + report；
- 准备轮/审计轮没有固定位置，靠临时插入；
- 没有独立 QA 节奏；
- 没有按风险分层（UI/真机/live/长稳/外部 Android）；
- 没有统一的“何时停止/何时插入新轮”规则；
- 没有把 OpenRig 用在该用的地方（多 seat/queue/resume），也没有明确声明不用。

---

## 3. 整改目标

### 3.1 总目标

把当前“单 seat + 弱检查 + 状态漂移 + 人工补轮”的流程，整改为：

```text
权威状态
  + 明确轮次分类
  + 原子 driver
  + 行为验收
  + 独立 QA
  + telemetry
  + 可回滚 Git 基线
```

### 3.2 具体目标

1. **一个权威状态源**：`RUN-STATE.json` + `ROUNDS.jsonl` + `rounds.yaml` 三者一致。
2. **30 个产品轮不再混入准备/外部/人工轮**。
3. **每轮有行为级验收**，不再以 token 检查作为唯一证据。
4. **里程碑有独立 QA**，生产者和验收者分离。
5. **driver 可恢复、可停止、可审计**，`DONE` 只在真正完成时出现。
6. **每轮有 telemetry**，能回答“为什么又插了一轮”。
7. **工作区干净、可回滚、无敏感信息**。
8. **明确 OpenRig 边界**：要么真正使用，要么明确不用，不再混称。

---

## 4. 架构决策（必须先拍板）

### 方案 A（推荐，适合当前 30 个产品轮）

```text
SCTG task-card + 单 seat DSH
+ 行为级 check
+ 独立 QA 里程碑
+ telemetry
```

适用理由：

- 当前 `auto_driver.py` 已经是一条可运行的 SCTG 单 seat 路径；
- 30 轮主要是单线 UI/功能改进，不需要多 seat 并发；
- 改造成本最低，能最快恢复跑轮；
- OpenRig 只在需要多 seat/queue/resume/transcript 的阶段使用。

**必须同时做**：文档中明确写“本 run 是 SCTG + DSH 单 seat，不是 OpenRig hybrid”，不要再让 OpenRig 背锅。

### 方案 B（适合需要多 seat/独立 QA/恢复的阶段）

```text
OpenRig rig
+ lead seat
+ independent QA seat
+ queue packet
+ workflow
+ bridge/transcript
```

适用条件：

- 需要独立 QA seat 或多 seat join；
- 需要 queue/claim/blocked/resume/transcript；
- 需要 30 轮跨会话恢复。

**不推荐现在直接切**：当前工作区未冻结、验收弱、状态漂移；直接切 OpenRig 会把这些问题的成本放大。

### 建议

**先按方案 A 完成整改和 30 轮恢复；在 R16/R25/R29/R30 等人工点或长稳阶段，再决定是否引入 OpenRig 独立 QA seat。**

---

## 5. 整改执行顺序（R0–R10）

> 执行智能体必须按顺序做。每一步先写计划/证据，再改文件；每步结束跑验收；不通过不进入下一步。

### R0 — 冻结与基线（P0）

**目标**：把当前工作区变成一个可回滚、可审计的基线。

步骤：

1. 记录：
   ```bash
   git status --short > reports/compare-20261113/BASELINE-git-status.txt
   git diff > reports/compare-20261113/BASELINE-git-diff.patch
   git rev-parse HEAD > reports/compare-20261113/BASELINE-head.txt
   ```
2. 创建整改分支：
   ```bash
   git switch -c remediation/20261113
   ```
3. 提交当前 WIP（不要 `git add -A` 盲加，按目录/文件分组）：
   - `sim/`, `lib/`, `test/`, `docs/`, `tools/sctg/`, `tools/adb/`, `reports/sctg/`（先脱敏 R15.5）
   - `.gitignore` 更新
4. 打 tag：
   ```bash
   git tag baseline-pre-remediation-20261113
   ```
5. 明确规则：R0 完成前不得跑任何产品轮。

**验收**：

```text
git status --short 干净（或只剩明确忽略项）
baseline tag 存在
R15.5 的 target/IP 已脱敏
```

### R1 — 状态对账（P0）

**目标**：消除 `BLOCKED` / `DONE` / `ROUNDS.jsonl` / `rounds.yaml` 的矛盾。

步骤：

1. 备份 `.sctg/runs/sctg-app-feel-auto-20261113/` 到 `reports/compare-20261113/state-backup-20261113/`（只备份文本状态；不要提交 `.sctg` 原始 submission）。
2. 新建权威状态 `reports/sctg/RUN-STATE.json`：
   ```json
   {
     "schema": 2,
     "run_id": "sctg-app-feel-auto-20261113",
     "architecture": "sctg-dsh-single-seat",
     "product_rounds_total": 30,
     "product_rounds_passed": ["R01", "..."],
     "prep_rounds": ["R05.5", "R09.5", "R15.5"],
     "human_checkpoints": ["R16", "R25", "R29", "R30"],
     "external_rounds": ["R21", "R22", "R23", "R28"],
     "active_round": "R15.5",
     "terminal": false,
     "updated_at": "..."
   }
   ```
3. 将 `ROUNDS.jsonl` 改为只记录**产品轮**，并补 schema：
   ```json
   {"schema":1,"round":"R03","kind":"product","verdict":"PASS","at":"..."}
   ```
4. 把 R15.5 从“隐含状态”改为显式：
   - 在 `RUN-STATE.json` 的 `prep_rounds` 里登记；
   - 在 `reports/sctg/R15.5.md` 顶部写 `status: ADB_PASS_NEED_MAIN`；
   - 不把 R15.5 计入 30 个产品轮。
5. 删除或归档冲突标记：
   - `BLOCKED` 保留为历史证据时改名为 `BLOCKED.history`；
   - `DONE` 在未完成 30 产品轮前不得存在；改名 `DONE.invalid-20261113`。
6. 更新 `docs/AUTO-RUN-PREP-3.md`，把 32/33 轮位差异写清。

**验收**：

```text
RUN-STATE.json 可 JSON 解析
product_rounds_total=30
ROUNDS.jsonl 无重复/无未知 round
BLOCKED/DONE 不再同时存在
R15.5 明确登记
python3 tools/sctg/check_round.py R15.5 的 ADB 分支仍可跑
```

### R2 — 轮次分类与 30 轮重排（P0）

**目标**：把 30 产品轮、准备轮、人工检查点、外部 Android 轮分开。

步骤：

1. 重写 `tools/sctg/rounds.yaml` 顶层结构：
   ```yaml
   schema: 2
   run_id: sctg-app-feel-auto-20261113
   product_rounds:
     - R01 ...
     - R30 ...
   prep_rounds:
     - R05.5 ...
     - R09.5 ...
     - R15.5 ...
   human_checkpoints:
     - R16
     - R25
     - R29
     - R30
   external_rounds:
     - R21
     - R22
     - R23
     - R28
   ```
2. 为每个产品轮补：
   ```yaml
   kind: product
   acceptance:
     behavior_tests: [...]
     artifacts: [...]
     evidence: [...]
   ```
3. 把 `needs_main` / `external` 从产品轮计数中移除。
4. 固定准备轮位置：R05.5、R09.5、R15.5 是**仅有的**准备轮；后续不得临时插入，除非走变更单。
5. 写 `reports/sctg/ROUND-MAP.md`：
   ```text
   当前 R01–R15 对应产品轮 1–15
   R15.5 是 ADB 特殊准备轮，不计入 30
   R16–R30 是剩余产品轮 + 人工/外部点
   ```

**验收**：

```text
product_rounds 数量 = 30
prep_rounds = {R05.5, R09.5, R15.5}
human_checkpoints/external_rounds 不混入 product_rounds
rounds.yaml 可 YAML 解析
```

### R3 — Driver 原子化与恢复（P0）

**目标**：让 `auto_driver.py` 可恢复、可停止、不会产生矛盾状态。

必须修改：

1. **权威状态**
   - 只从 `reports/sctg/RUN-STATE.json` 和 `ROUNDS.jsonl` 读取；
   - 启动时校验：
     - 产品轮总数 30；
     - `ROUNDS.jsonl` 无未知/重复；
     - `RUN-STATE.active_round` 与 `ROUNDS.jsonl` 一致。
2. **原子写**
   - `RUN-STATE.json` 用 `tempfile` + `os.replace`；
   - `ROUNDS.jsonl` 追加前加 `fcntl` 文件锁；
   - 写入后 `fsync`。
3. **停止语义**
   - `--all` 默认在第一个 `NEED_MAIN`/`BLOCKED` 停止；
   - 不写 `DONE`，只写 `RUN-STATE.terminal=false`；
   - 增加 `--continue-past-need-main`（显式）和 `--halt-on-need-main`（默认）。
4. **DONE 条件**
   - 只有 30 个产品轮全部 PASS，且 human checkpoints 明确 `accepted`，才允许 `DONE`；
   - `DONE` 内容写 `product_rounds_passed=30/30` 和 tag/commit。
5. **幂等**
   - 同一 round/attempt 重复执行不得重复追加 `ROUNDS.jsonl`；
   - 已 PASS 轮次跳过；
   - 已 `BLOCKED` 轮次默认不重跑，除非 `--retry-blocked`。
6. **超时/取消**
   - seat 子进程超时后杀掉整个进程组；
   - 写 `TIMEOUT` 事件，不写 PASS；
   - 等待 submission 文件使用可取消轮询。
7. **环境固定**
   - `DEFAULT_KIT` 改为相对路径或可配置，不指向 `workflow-group/drafts`；
   - `--seat-command` 必须显式记录到 `RUN-STATE.json`；
   - 记录 `dsh --version`、`node --version`、`python --version`。

**验收**：

```text
python3 tools/sctg/auto_driver.py --dry-run 通过
中断后重跑不重复写 PASS
NEED_MAIN 不产生 DONE
RUN-STATE.json 与 ROUNDS.jsonl 一致
```

### R4 — 行为级验收（P0）

**目标**：把 token/file check 升级为行为/证据 check。

最低要求：

1. 每个产品轮必须有：
   - `behavior_tests`: 实际运行命令（Node test / DOM test / Python test / ADB command）；
   - `artifacts`: 产出文件；
   - `evidence`: 命令 + exit code + 关键输出/hash；
   - `scope_diff`: 只允许 write_scope 内文件变化；
   - `verdict`: PASS/FAIL/NEED_MAIN。
2. 禁止把“报告里出现某个词”作为唯一 PASS 条件。
3. UI 轮次：
   - 需要 DOM/浏览器/ADB 行为验证；
   - 至少 1 个真实交互断言（点击、输入、滚动、面板打开）；
   - 视觉/触控/键盘/安全区标 `NEED_MAIN`。
4. 真机轮次：
   - `R15.5` 保留 ADB 自动 PASS + 4 项 NEED_MAIN；
   - 报告必须写清“自动 PASS 不等于真机体验 PASS”。
5. 每轮固定产物：
   ```text
   reports/sctg/Rxx.md
   reports/sctg/Rxx.json
   reports/sctg/evidence/Rxx/
   ```
6. `check_round.py` 与 `round_checks.py` 统一为一个 `CHECK-MANIFEST` schema；不要两套风格。

**验收**：

```text
每个产品轮至少 1 个 behavior_test
token-only 检查数量 = 0
每个 PASS 有 evidence hash/命令
NEED_MAIN 不被计入 PASS
```

### R5 — 独立 QA 里程碑（P0）

**目标**：生产者与验收者分离，避免单 seat 自证。

规则：

- 产品轮由 lead seat 执行；
- 每 5 个产品轮（R05/R10/R15/R20/R25/R30）插入独立 QA：
  - 独立 agent/seat（可以是另一个 DSH 会话或 OpenRig QA seat）；
  - 只读代码 + 运行测试 + 真机/浏览器检查；
  - 写 `reports/sctg/QA-Rxx.md`；
  - 开 ISSUE，不直接改产品文件。
- QA 发现 S1/S2 时，插入**显式**修复轮；修复轮编号写进 `rounds.yaml`，不得临时改号。
- `QA PASS` 必须有：
  - 测试命令/exit code；
  - 关键行为证据；
  - 与 SCTG gate 结果的交叉引用；
  - `scope_conflicts=0`。

**验收**：

```text
6 个 QA 里程碑文件存在
QA 与 lead seat 不是同一执行身份
QA 发现的问题有 ISSUE ID 和去向
无 QA 自证
```

### R6 — Telemetry 与轮次趋势（P1）

**目标**：用数据回答“为什么又插了一轮”。

每轮追加 `reports/sctg/telemetry.jsonl`：

```json
{
  "round": "R10",
  "kind": "product",
  "start": "...",
  "end": "...",
  "duration_s": 480,
  "attempts": 1,
  "gate": "PASS",
  "check": "PASS",
  "behavior_tests": 3,
  "changed_files": ["sim/app.js"],
  "evidence_hashes": ["sha256:..."],
  "human_intervention": false,
  "issues_opened": 0,
  "issues_closed": 0,
  "rework": false
}
```

生成 `reports/sctg/TELEMETRY.md`：

- 每轮耗时；
- R03–R15 平均 ~19 min/轮（早期），R10–R15 ~8 min/轮；
- issue 新增/关闭；
- 插轮原因；
- 预计剩余时间。

**验收**：

```text
telemetry.jsonl 每轮一行
TELEMETRY.md 能回答：当前第几轮、已用时间、剩余估计、插轮原因
```

### R7 — 外部 Android 与 scope 隔离（P1）

**目标**：不让 `../bridge-app/**` 污染主仓。

规则：

- R21/R22/R23/R28 单独 `android_rounds.yaml` + 独立 run；
- 主仓 `rounds.yaml` 只保留 pointer，不直接写 `../bridge-app/**`；
- 外部轮验收在 `bridge-app` 仓内完成，主仓只引用 commit/hash/报告；
- R15.5 的 ADB 验收只作为主仓 host-only 证据，不替代 R21–R23。

**验收**：

```text
主仓 product_rounds 无 external 写入
android run 有独立 state/evidence
跨仓引用是 commit + hash，不是复制文件
```

### R8 — 安全与脱敏（P0）

**目标**：公开/外发前不泄露真实设备、token、截图、日志。

必须做：

1. R15.5 报告/JSON 中的真实 target `100.x.y.z:5555` 替换为 `<tailnet-device>:5555`；
2. 不提交：
   - 原始截图；
   - UI dump XML；
   - logcat 全文；
   - token/password/secret；
   - 真实聊天正文；
3. 只提交脱敏 JSON/哈希/布尔检查；
4. 加 `scripts/check_sanitization.py`（或项目等价脚本）：
   - `/home/*`、`/Users/*`、`~/.dsh`、`sk-*`、`ghp_*`、`xox*`、`AKIA*`、私钥；
   - 真实设备 IP/序列号；
   - token= 行。
5. `.gitignore` 补：
   ```text
   .sctg/
   .openrig/
   .claude/
   CLAUDE.md
   .mcp.json
   reports/sctg/evidence/raw/
   ```
6. 公开/外发前跑：
   ```bash
   grep -RInE '/home/|/Users/|sk-[A-Za-z0-9]{20,}|ghp_|xox|AKIA|100\.[0-9]+\.[0-9]+\.[0-9]+' .
   ```

**验收**：

```text
sanitization 扫描 0 命中（允许已脱敏占位符）
R15.5 无真实 IP/序列号
无原始截图/UI dump/logcat
```

### R9 — Git / CI / 发布（P0）

**目标**：工作区干净、可回滚、可复现。

步骤：

1. 分支：`remediation/20261113`；
2. 每个整改步骤一个 commit；
3. 更新 `.gitignore`；
4. 提交 `tools/sctg/**`、`tools/adb/**`、`test/**`、`docs/**`、`reports/sctg/**`（脱敏后）；
5. 加 `scripts/check_remediation.py` 或 `make check`：
   - `python3 -m compileall tools/sctg tools/adb`
   - `node --check sim/app.js`
   - `node --test test/app-ui-fixes.test.mjs test/app-commands.test.mjs`
   - `python3 tools/sctg/app_smoke.py`
   - `python3 -m json.tool reports/sctg/RUN-STATE.json`
   - `python3 -m json.tool reports/sctg/telemetry.jsonl`（逐行）
6. 打 tag：`remediation-ready-20261113`；
7. 不自动 push，等 MAIN 明确批准。

**验收**：

```text
git status 干净
tag 存在
check 全绿
```

### R10 — 恢复 30 轮（P1）

**前提**：R0–R9 全绿。

恢复规则：

1. 从 `RUN-STATE.json` 的 `active_round` 恢复；
2. 按 `product_rounds` 顺序跑；
3. 遇到 `NEED_MAIN` 停止并写 `NEED_MAIN`，不写 `DONE`；
4. 遇到外部轮跳过，写入 `external_pending`；
5. 每 5 轮 QA；
6. 每轮写 telemetry；
7. 任何插轮必须：
   - 写 `CHANGE-REQUEST-<id>.md`；
   - 说明原因/证据/影响轮数；
   - MAIN 批准；
   - 更新 `rounds.yaml` + `RUN-STATE.json`。

**验收**：

```text
30/30 产品轮 PASS 或明确 accepted
telemetry 完整
QA 6 个里程碑 PASS
无 open S1/S2
DONE 内容与状态一致
```

---

## 6. 必须修改/新增的文件清单

### 6.1 必改

```text
tools/sctg/auto_driver.py
tools/sctg/rounds.yaml
tools/sctg/check_round.py
tools/sctg/round_checks.py
tools/sctg/app_smoke.py
tools/sctg/normalize_submission.py
.gitignore
docs/AUTO-RUN-PREP-2.md
docs/AUTO-RUN-PREP-3.md
reports/sctg/R15.5.md
reports/sctg/adb/R15.5.json
```

### 6.2 必增

```text
reports/sctg/RUN-STATE.json
reports/sctg/telemetry.jsonl
reports/sctg/TELEMETRY.md
reports/sctg/ROUND-MAP.md
reports/sctg/QA-R05.md
reports/sctg/QA-R10.md
reports/sctg/QA-R15.md
reports/sctg/QA-R20.md
reports/sctg/QA-R25.md
reports/sctg/QA-R30.md
reports/compare-20261113/BASELINE-git-status.txt
reports/compare-20261113/BASELINE-git-diff.patch
reports/compare-20261113/BASELINE-head.txt
scripts/check_remediation.py
```

### 6.3 禁改

- 不在本轮修改 `../bridge-app/**`；
- 不删除旧微信桥；
- 不修改 `workflow-group/templates/**`、`roles/**`、`scripts/**`；
- 不把 `.sctg/` 原始 submission/evidence 直接提交；
- 不把真实设备 IP/token/截图/UI dump/logcat 提交。

---

## 7. 验收命令清单

执行智能体在 R9/R10 结束前必须跑：

```bash
cd <repo>

# 1. Python 语法
python3 -m compileall -q tools/sctg tools/adb

# 2. Node 语法
node --check sim/app.js

# 3. 核心测试
node --test test/app-ui-fixes.test.mjs test/app-commands.test.mjs \
  test/status-card.test.mjs test/sctg-pilot-status-log.test.mjs

# 4. App smoke
python3 tools/sctg/app_smoke.py

# 5. 轮次 check（逐轮）
python3 tools/sctg/check_round.py R01
python3 tools/sctg/check_round.py R02
# ...
python3 tools/sctg/check_round.py R15

# 6. 状态 JSON
python3 -m json.tool reports/sctg/RUN-STATE.json >/dev/null
while IFS= read -r line; do echo "$line" | python3 -m json.tool >/dev/null; done < reports/sctg/telemetry.jsonl

# 7. Driver dry-run
python3 tools/sctg/auto_driver.py --dry-run

# 8. 卫生
git diff --check
git status --short
```

---

## 8. Definition of Done

全部满足才允许说“整改完成”：

- [ ] `RUN-STATE.json` 是唯一权威状态，且与 `ROUNDS.jsonl`、`rounds.yaml` 一致。
- [ ] 30 个产品轮 + 3 个准备轮 + 4 个人工点 + 4 个外部轮，分类清楚，计数不再漂移。
- [ ] R15.5 已登记，`DONE` 不再与 `BLOCKED` 并存。
- [ ] `auto_driver.py` 原子写、可恢复、NEED_MAIN 不写 DONE。
- [ ] R10–R30 不再以 token/file 作为唯一验收。
- [ ] 每 5 轮有独立 QA，生产者和验收者分离。
- [ ] 每轮有 telemetry。
- [ ] 外部 Android 轮独立 run，不写主仓 scope。
- [ ] R15.5 及所有报告已脱敏。
- [ ] Git 工作区干净，整改分支/tag 存在。
- [ ] 验收命令全绿。
- [ ] 没有任何“临时插轮”未走变更单。

---

## 9. 给执行智能体的硬规则

1. **先 R0 冻结，不要先跑轮。**
2. **不要用 `git add -A` 盲提交**；按文件组提交。
3. **不要删除 `.sctg/` 运行产物**；先备份到 `reports/compare-20261113/state-backup-20261113/`。
4. **不要把真实设备 IP/token/截图/UI dump/logcat 写进仓库。**
5. **不要把 `NEED_MAIN` 当 PASS。**
6. **不要把 token 检查当行为验收。**
7. **不要临时插入轮次**；必须走 CHANGE-REQUEST。
8. **每步结束写证据**：命令、exit code、hash、文件路径。
9. **每次状态变更后重新读 `RUN-STATE.json`**，不要凭记忆。
10. **如果发现方案与事实冲突，先停下来写冲突报告，不要自行改目标。**

---

## 10. 建议的最小整改批次

如果一次做完太大，按以下 4 批提交：

```text
批次 1（P0 冻结/对账）
  R0 + R1 + Git baseline

批次 2（P0 驱动/轮次）
  R2 + R3

批次 3（P0 验收/QA）
  R4 + R5 + R8

批次 4（P1 telemetry/外部/Git）
  R6 + R7 + R9

然后 R10 恢复跑轮。
```

每批结束都要：

```text
git status 干净
check 全绿
写 reports/compare-20261113/BATCH-<n>.md
```

---

## 11. 附：当前轮次与文件对照

```text
产品轮（30）:
  R01–R30

准备轮（3，不计入 30）:
  R05.5  自动跑重整
  R09.5  R10–R30 前置清空
  R15.5  ADB 真机验收

人工点（4）:
  R16, R25, R29, R30

外部 Android（4）:
  R21, R22, R23, R28
```

当前实际状态：

```text
ROUNDS.jsonl: R03–R15 = 13 PASS
R15.5: 报告存在，未登记
R16: NEED_MAIN 停点
```

整改后必须变成：

```text
RUN-STATE.json:
  product_rounds_total: 30
  product_rounds_passed: [...]
  prep_rounds: [R05.5, R09.5, R15.5]
  human_checkpoints: [R16, R25, R29, R30]
  external_rounds: [R21, R22, R23, R28]
  active_round: <真实值>
  terminal: false/true
```

---

> 本方案是整改合同，不是建议清单。执行智能体应先完整阅读，再按 R0–R10 顺序执行；任何偏离都要先写 `DEVIATION-<id>.md` 并等待 MAIN 批准。
