<!-- wf-evidence
run: openrig-master-selfopt-20261020
round: 1
doc: SELF-OPT-PLAN
owner: PMO
state: plan-ready
updated: 2026-10-20
-->

# SELF-OPT-PLAN — 母版 v1.0.0 → v1.1.0 自优化计划

> 写者：PMO（`PROJECT.md` §2.1.1 唯一授权产出物）｜ 本文件不含执行状态；执行状态以 OpenRig queue/workflow + `STATUS-Round-1.md` 为准。
> 约束：本文件只描述改动，**不改动** `templates/specialized/openrig-workflow-master/**` 任何文件。

## 0. 结论摘要

v1.0.0 的**结构不需要重写**：双平面权威、唯一 rig/workflow、bridge 单一映射这三条是对的，且已被一次真实 smoke 验证（5/5 ready、validate/instantiate/abort、doctor PASS）。v1.1.0 的收益全部集中在五个"摩擦点"：

1. **接入**：参数错误在写盘后才发现；首次接入要人工抄 6 个 export + 4 条命令。
2. **管理**：`status` 只有原始 JSON，没有可直接判读的就绪/前沿/队列摘要；`doctor` 不检查 bridge 与 spec 是否漂移。
3. **优化**：成本/延迟/队列指标没有落点，收口复盘只能凭记忆。
4. **SAFETY**：只有散文约束，没有可被 agent 读取和校验的契约字段。
5. **自应用**：版本号、模板、bridge、spec 之间没有一处能一次性自检。

**分层交付**：Tier A（I-1…I-7）已随两个 packet 下发，是本轮验收对象；Tier B（I-8…I-12）是同一目标的延续，**需 MAIN 在 `DECISIONS.md` 扩包后才下发**，本轮不静默扩范围。

## 1. 基线（已核阅，非转述）

| 对象 | 观察 | 位置 |
| --- | --- | --- |
| 版本 | `1.0.0` | `VERSION`；`README.md:3` |
| generator | 156 行；无 `--dry-run`/无清单/`--daemon-port` 无范围校验/无自检 | `render_master.py:23-38`、`:57-67`、`:138-151` |
| bridge 工具 | 126 行；`status` 仅 `ps`+`workflow status`；`doctor` 不交叉校验 spec；`capture` 无清单/无脱敏扫描 | `tools/openrig_bridge.py:44-102` |
| 模板 | 4 tpl + guidance；占位符残留由 `render()` 兜底报错 | `render_master.py:47-54` |
| 架构文档 | §3 接入 / §4 管理 / §5 优化 / §7 扩展点，SAFETY 仅 §4.6 散文 | `ARCHITECTURE.md:213-218`、`:311-317` |
| 真实验证 | 5/5 ready、validate/instantiate/abort、`wf new-run` doctor PASS | `validation/README.md` |
| 已知后续 | SAFETY、status/queue 双写审计、多项目 registry、成本遥测 | `CHANGELOG.md` §1.1.0 候选 |
| 引擎限制（外部项 X-1，**上游 Side**） | fan-out handoff 到 ≠1 后继时源 packet 记 `closureReason=no-follow-on`、`closureTarget=null`（单值字段）；successors 投影本身正确，仅闭包字段粒度丢失。按 **D-006** 登记不修，去向=母版 `CHANGELOG.md` 的"已知上游问题"（MAIN 在 S5 落盘），上游 issue 需人工确认，未确认不算完成 | `qitem-20261019202036-e52815ff` transitions#3；OpenRig `packages/daemon/src/domain/workflow-projector.ts:1089-1096`；`DECISIONS.md` D-006 |

## 2. 改动项（逐项：改什么/为什么 → 归属 → 验收 → 风险/回滚 → 不得改动）

### 2.1 接入简化与诊断

#### I-1 写盘前参数校验 + `--dry-run` + `--json`（Tier A / OC-1）

- **改什么**：`render_master.py` 在写任何文件前完成校验；新增 `--dry-run`（只打印计划，不落盘）与 `--json`（stdout 输出 `{ok, outputDir, files[], next[]}`）。
- **为什么**：现在 `--daemon-port 70000`、非法 `--run-id`、输出目录冲突都要等 `mkdir`/写盘后才可能失败或半成品；接入者拿不到机器可读的下一步命令，只能照 README 手抄。
- **归属**：**TDO-OC** 独占 `render_master.py`。
- **验收**：
  ```bash
  cd templates/specialized/openrig-workflow-master
  python3 render_master.py --run-id selfopt-oc-dry --project-root /tmp --output-dir /tmp/o1 --dry-run --json; echo rc=$?   # rc=0，且 /tmp/o1 不存在
  python3 render_master.py --run-id BAD_ID --project-root /tmp --dry-run; echo rc=$?                                       # rc=2，stderr 含 run-id
  python3 render_master.py --run-id ok --project-root /tmp --daemon-port 70000 --dry-run; echo rc=$?                        # rc=2，stderr 含 daemon-port
  python3 render_master.py --run-id ok --project-root /tmp --output-dir /tmp/o1 --json | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["ok"] and d["files"]'
  ```
- **风险/回滚**：风险是 `--json` 改变 stdout 影响现有脚本；回滚只需删除新 flag（默认行为保持人类可读文本）。默认（不带 flag）输出必须逐字兼容 v1.0.0。
- **不得改动**：默认参数值、bundle 文件名与路径、`OPENRIG-BRIDGE.json` 字段集合、`--force` 语义。

#### I-2 `doctor` 交叉校验 bridge ↔ rig.yaml ↔ workflow.yaml（Tier A / DSH-2）

- **改什么**：`tools/openrig_bridge.py doctor` 读取两份 spec，比对 `bridge.rigName`↔`rig.yaml` 名字/`cwd`、`bridge.workflowId`↔`workflow.yaml` id、`seatMap` 的五个角色↔`workflow.yaml` `roles.*.preferred_targets`；校验 `openrigHome` 可创建/可写；不一致输出 `FAIL <字段> bridge=… spec=…` 且 rc=1。
- **为什么**：bridge 是唯一映射，漂移等于两个平面各说各话；现在 doctor 只查字段存在，不查一致性。
- **归属**：**TDO-DSH** 独占 `tools/openrig_bridge.py`。
- **验收**：
  ```bash
  python3 tools/openrig_bridge.py doctor --run-dir runs/openrig-master-selfopt-20261020; echo rc=$?      # PASS, rc=0
  cp -r runs/openrig-master-selfopt-20261020 /tmp/brk && sed -i 's/"rigName": "openrig-master-selfopt"/"rigName": "wrong"/' /tmp/brk/openrig/OPENRIG-BRIDGE.json
  python3 tools/openrig_bridge.py doctor --run-dir /tmp/brk; echo rc=$?                                  # rc=1，FAIL rigName
  ```
- **风险/回滚**：风险是旧 bundle 字段缺失导致误 FAIL；回滚=新增校验全部降级为 `WARN` 且 rc 不变（一行开关）。旧 bridge 必须仍能 PASS。
- **不得改动**：不改 queue/workflow、不写 live bundle、`doctor` 仍然只读、`PASS` 行格式保持可 grep。

#### I-3 渲染清单 `render-manifest.json`（Tier A / OC-2）

- **改什么**：每次渲染写 `render-manifest.json`（`masterVersion`、`renderedAt`、每个产物 `path`+`sha256`，模板文件同样计入）。
- **为什么**：QA 现在无法证明"这个 bundle 就是这版母版渲染的"；也无法区分"重渲染差异"与"人改了生成物"。
- **归属**：**TDO-OC**（`render_master.py` + `templates/**` 若需插注释）。
- **验收**：
  ```bash
  for d in /tmp/m1 /tmp/m2; do python3 render_master.py --run-id mm --project-root /tmp --output-dir $d --json >/dev/null; done
  python3 - <<'PY'
  import json,hashlib,pathlib
  a=json.load(open('/tmp/m1/render-manifest.json')); b=json.load(open('/tmp/m2/render-manifest.json'))
  assert {k:v['sha256'] for k,v in a['files'].items()}=={k:v['sha256'] for k,v in b['files'].items()}
  print("deterministic ok")
  PY
  ```
- **风险/回滚**：风险是 manifest 自身被计入造成自引用；回滚=删除该文件（不参与 bridge，不影响启动）；manifest 必须排除自身。
- **不得改动**：不新增 bundle 中的启动必需文件、不改 `rig.yaml`/`workflow.yaml` 结构、不许把 `renderedAt` 写进 sha256 覆盖范围（时间戳不参与哈希）。

### 2.2 管理 / 状态同步与恢复

#### I-4 `status` 增强：就绪/前沿/队列摘要 + 稳定退出码（Tier A / DSH-1）

- **改什么**：`status` 输出增加 `seats{ready,total,bySeat}`、`workflow{instance,currentStep,frontier[]}`、`queue{pending,inProgress,overdue}`、`generatedAt`；stdout 支持 `--json`；退出码：0 全就绪、2 降级（有 seat 未 ready 或某子命令失败，证据仍落盘）。
- **为什么**：现在 `OPENRIG-STATE.json` 里是原始 CLI 输出，PMO/QA 要自己数 seat；且全部失败也返回 0，无法当门禁用。
- **归属**：**TDO-DSH**。
- **验收**：
  ```bash
  python3 tools/openrig_bridge.py status --run-dir runs/openrig-master-selfopt-20261020 --json | python3 -c 'import json,sys;d=json.load(sys.stdin);assert {"seats","workflow","queue","generatedAt"}<=d.keys();print(d["seats"])'
  python3 tools/openrig_bridge.py status --run-dir runs/openrig-master-selfopt-20261020; echo rc=$?   # 全就绪 rc=0
  python3 tools/openrig_bridge.py status --run-dir /tmp/brk; echo rc=$?                                # 不可达 rc=2，且 OPENRIG-STATE.json 仍生成
  ```
- **风险/回滚**：风险是 `rig ps` JSON 结构变化；回滚=保留原字段名并新增字段（只加不改），队列字段缺失时记 `null` 而非报错。
- **不得改动**：不复制 queue 正文/transcript 文本（只计数与 id）、不改执行面状态、不新增网络调用、`OPENRIG-STATE.json` 原有顶层键不可删。

#### I-5 恢复演练 `recover --plan`（Tier B / DSH-6，需扩包）

- **改什么**：新增只读子命令 `recover --plan`，按 `bridge` 打印四步恢复序列（snapshot 检查 → resume → fresh-primed → 升级 MAIN），并显式标注 `NOT EXECUTED`。
- **为什么**：`ARCHITECTURE.md` §4.4 写了优先级，但恢复时仍靠人回忆；把命令固化可减少"用新 seat 冒充 resume"。
- **归属**：**TDO-DSH**（`tools/openrig_bridge.py` + `ARCHITECTURE.md`）。
- **验收**：`python3 tools/openrig_bridge.py recover --plan --run-dir runs/<run>` 输出含四个有序步骤、每条命令、`NOT EXECUTED` 头；执行后 `git status --porcelain` 无新增、无 daemon 调用（可用 `strace`/包装脚本证明无 `rig` 子进程）。
- **风险/回滚**：风险是有人把打印当执行；回滚=删除子命令。**不得**提供 `--execute`。
- **不得改动**：不改 §4.4 的优先级语义、不自动 resume、不写 snapshot、不删会话。

#### I-6 外部项 X-1（只登记，无母版改动；去向=D-006 → CHANGELOG「已知上游问题」）

fan-out 关闭原因丢粒度（见 §1）。**执行归属：非本 run 角色（不改 OpenRig 源码、不改 queue 历史行）；承载 owner=MAIN（母版 `CHANGELOG.md`"已知上游问题"落盘）+ PMO（本文件 §7 计划侧留痕），出处 D-006。**

### 2.3 优化 / 遥测 / 成本 / 队列调优

#### I-7 队列调优契约进 `ARCHITECTURE.md`（Tier A / DSH-4 的一部分）

- **改什么**：§5.4 写入可执行调优表：packet 粒度上限（一次改动 ≤1 文件面 + ≤3 任务）、`tier`/`priority` 使用规则、`max_hops` 与 depends_on 的分工、fan-out 适用/不适用判据、stale claim 的 watchdog 端口。
- **为什么**：现在 §5.4 是原则句，TDO 拆包时仍会凭感觉；本轮已出现"一个 packet 4 项任务"的偏大风险。
- **归属**：**TDO-DSH**（`ARCHITECTURE.md`）。
- **验收**：文档条目逐条能指到命令或字段名（`rig queue` / `workflow.yaml` 键），无纯形容词；QA 抽查 3 条可对照本轮两个 packet 判定。
- **风险/回滚**：风险是文档与引擎行为不符；回滚=回退该节。**不得改动**：不改已有 §5.1/§5.2 的默认值、不把建议写成硬规则。
- **不得改动**：见左。

#### I-8 遥测脚手架 `--with-telemetry`（Tier B / OC-4，需扩包）

- **改什么**：渲染时可选生成 `telemetry/plan.json`（packet 计划字段：`ws`、`ownerRole`、`estWallMinutes`、`modelCalls`、`tokensIn/out`、`costUsd`，默认 `null`）+ `guidance/telemetry.md`（填写规则）。
- **为什么**：§5.5 要求收口记录成本，但没有任何落点，导致 M 系列只能"待采集"。
- **归属**：**TDO-OC**（`render_master.py` + `templates/**`）。
- **验收**：`--with-telemetry` 渲染后 `telemetry/plan.json` 存在且 `json.loads` 通过、schema 键固定；**不带该 flag 时 bundle 与 v1.0.0 字节一致**（用 I-3 清单比对）；文件内无 key/token（正则扫描 PASS）。
- **风险/回滚**：风险是有人把估算值当实测；回滚=关闭 flag（默认关）。字段语义必须写"估算 vs 实测"。
- **不得改动**：不放任何凭证、不接 provider API、不改变默认 bundle。

#### I-9 `status` 队列深度与陈旧度指标（Tier B / DSH-5，需扩包）

- **改什么**：`status --queues` 增加每 seat `queueDepth`、`oldestActionableAgeSeconds`、`overdueCount`；只取 id/state/时间，不取正文。
- **为什么**：调优闭环（测量→找最贵最慢→缩小范围）缺少第一手数据；现在只能人工跑 `rig queue list`。
- **归属**：**TDO-DSH**（`tools/openrig_bridge.py`）。
- **验收**：对 live run 运行后字段齐全；构造 `/tmp` 假 bridge 指向无 queue 的 home → 字段为 `null` 且 rc=2，不抛栈。
- **风险/回滚**：风险是 `queue list` 输出量大拖慢；回滚=flag 默认关、超时 10s 降级。
- **不得改动**：不落 queue 正文、不写 queue、不改变 I-4 的默认输出。

### 2.4 SAFETY 扩展（高风险 run）

#### I-10 SAFETY 契约进 `ARCHITECTURE.md` §7（Tier A / DSH-4）

- **改什么**：定义可机读契约：动作类别枚举（`delete`/`publish`/`hdrive_write`/`perm_change`）、gate 结果枚举（`gate_pass`/`gate_fail`/`safety_pending`/`safety_reject`/`executed_ok`/`executed_bad`）、前置条件（独立 SAFETY seat ≠ 提出者/执行者/QA/人工批准人）、账本路径（`safety/{actions,gates,reviews,human-approvals,executions}/`）、bridge `policy.safetyMode` 取值（`on-demand`/`always`）。
- **为什么**：§4.6 只有散文；没有契约字段时，agent 无法判断"这次该不该走门控"，QA 也无法核对。
- **归属**：**TDO-DSH**（`ARCHITECTURE.md`；`tools/openrig_bridge.py` 仅在 doctor 里校验 `policy.safetyMode` 枚举）。
- **验收**：文档含上述四个枚举与路径；`doctor` 对 `safetyMode: "off"` 的临时 bridge 报 FAIL（非法枚举）；对 live run（`on-demand`）PASS。
- **风险/回滚**：风险是文档承诺了未实现的执行器；回滚=删除 §7 契约段。文档必须明写"v1.1.0 只定义契约、不实现门控执行器"。
- **不得改动**：不实现 gate、不新增 seat 到默认 rig、不改 `policy.safetyMode` 默认值（`on-demand`）、不触碰 H 盘。
- **口径约束（D-006）**：若 §7 契约涉及 packet 闭包字段（`closureReason`/`closureTarget`），必须标注为**上游 Side 已知行为**（successors 投影正确，仅多后继时字段粒度丢失；复核口径=`closureTarget===null` 时回读 `transitionNote`），**不得写成母版缺陷**，也不得在 v1.1.0 内"修复"。

### 2.4.1 WS-3b（返工包：闭合 P-001/P-002，D-009 + D-011）

- **触发**：QA `QA_FAIL`（`QA-SELF-OPT.md` state=fail）开 P-001（S2，I-7 §5.4 未升级为契约表）与 P-002（S2，I-10 doctor 未校验 `schemaVersion`/`policy.safetyMode`）。
- **定义**：不是新增能力，而是**把已交付 Tier A 的验收缺口补齐**。硬边界（D-009）：仅 `tools/openrig_bridge.py` 的 `_doctor_check` 单点 + `ARCHITECTURE.md` §3.2/§5.4/§7 + DSH 报告差异节 + `evidence/dsh/fix-*`；**禁改** `render_master.py`、`templates/**`、已交付证据、live bundle、版本号。D-011 把 I-7 并入同一包。
- **验收（可复跑）**：① live run `doctor` rc=0；② 临时 bridge `policy.safetyMode=off` → rc=1 且 `FAIL policy.safetyMode`；③ 临时 bridge `schemaVersion=999` → rc=1 且 `FAIL schemaVersion`；④ §5.4 为表格且每行指向真实命令/字段；⑤ §7 含 `safetyMode ∈ {on-demand, always}`，与 `render_master.py:178` 一致；⑥ 报告补「与 §2.4 差异及理由」。
- **与 D-007 的区别（关键，避免被读成扩范围）**：D-007 拒绝的是 **Tier B 新增能力**（遥测脚手架、`--self-check`、`recover --plan`、队列陈旧度指标）；WS-3b 闭合的是 **已交付 Tier A 的验收缺口**，不新增能力、不改 Tier A 判据，故两者不矛盾。
- **执行顺序事实（不美化）**：DSH 在 04:38–04:40 已自行完成修复并产出 `TDO-DSH-FIX-REPORT.md`，**早于**本包创建；即本轮存在一次「先做后立项」的队列谱系缺口。本包按**收尾核实包**处理，不伪装成事前委派；缺口本身记入 `PROJECT.md` §6。
- **归属**：**TDO-DSH**（`tools/openrig_bridge.py`、`ARCHITECTURE.md`、`TDO-DSH-FIX-REPORT.md`、`evidence/dsh/fix-*`）；TDO-OC 只读。

### 2.5 自应用 / 版本 / 校验

#### I-11 `--self-check`（Tier B / OC-5，需扩包）

- **改什么**：`render_master.py --self-check` 校验：`VERSION` 为 semver、`CHANGELOG.md` 存在对应版本小节、四个模板渲染后无残留 `{{...}}`、`READMD.md` 版本行与 `VERSION` 一致、bridge `schemaVersion` 已知；任一不符 rc=2。
- **为什么**：现在版本/文档/模板三者可以各自漂移，没有任何一处会报错；自应用时最危险的就是"拿错版本渲染"。
- **归属**：**TDO-OC**（`render_master.py`）。
- **验收**：`python3 render_master.py --self-check; echo rc=$?` → rc=0；把母版复制到 `/tmp/mc` 并把 `VERSION` 改为 `9.9.9` 后 `--self-check` → rc=2 且报 `VERSION/CHANGELOG mismatch`（证明不改原文件也能测）。
- **风险/回滚**：风险是 CHANGELOG 格式收紧误报；回滚=该项降为 WARN。**不得改动**：不改 `VERSION`/`CHANGELOG` 内容、不自动写文件。

#### I-12 版本化与收口（Tier A / MAIN，`PROJECT.md` §2.1.1）

- **改什么**：`VERSION` 1.0.0 → 1.1.0；`CHANGELOG.md` 增加 1.1.0 小节（逐条对应 I-1…I-11 的实际落地项，未落地项标注"延后"）；`README.md:3` 版本行同步；保留 v1.0.0 bundle 兼容说明（bridge `schemaVersion: 1` 不变）。
- **为什么**：G6 要求；且 v1.0.0 的 smoke 证据必须仍可解释。
- **归属**：**MAIN**（非 TDO）；`QA` 只核对不代写。
- **验收**：`grep -q 1.1.0 VERSION`；`sed -n 3p README.md` 含 1.1.0；`CHANGELOG.md` 有 `## 1.1.0` 且至少 5 条带文件名的条目；`render_master.py --self-check` rc=0。
- **风险/回滚**：风险是版本号先于代码落地；回滚=回退三处版本行。**不得改动**：不改 bridge schema 版本、不改生成物路径、不删 1.0.0 小节。

## 3. 归属矩阵（disjoint 校验）

| 文件 | TDO-OC | TDO-DSH | QA | MAIN |
| --- | --- | --- | --- | --- |
| `render_master.py` | 写（I-1/3/8/11） | 只读 | 只读 | 只读 |
| `templates/**` | 写 | 只读 | 只读 | 只读 |
| `tools/openrig_bridge.py` | 只读 | 写（I-2/4/5/9/10） | 只读 | 只读 |
| `ARCHITECTURE.md` | 只读 | 写（I-5/7/10） | 只读 | 只读 |
| `VERSION`/`CHANGELOG.md`/`README.md` | 只读 | 只读 | 只读 | 写（I-12） |
| `TDO-OC-REPORT.md` / `TDO-DSH-REPORT.md` | 各自 | 各自 | 只读 | 只读 |
| `SELF-OPT-PLAN.md` | 只读 | 只读 | 只读 | 只读（PMO 写） |
| `QA-SELF-OPT.md` / `ISSUES.xlsx` | 只读 | 只读 | 写 | 只读 |
| `STATUS-Round-1.md` | 追加己行 | 追加己行 | 只读 | 按 §3 不读正文 |

交集为空。**共享文件只有 `VERSION/CHANGELOG/README` 三个，全部归 MAIN 收口**，两 TDO 均只读。

## 4. 已下发 / 待扩包

| 项 | ID | 归属 | 状态 |
| --- | --- | --- | --- |
| I-1 / I-3 | OC-1 / OC-2 | TDO-OC | 已下发 `qitem-20261019202230-5b6fef7c` |
| I-2 / I-4 / I-7 / I-10 | DSH-2 / DSH-1 /（DSH-4 文档）/（DSH-4 文档） | TDO-DSH | 已下发 `qitem-20261019202230-6650a1af` |
| I-5 / I-8 / I-9 / I-11 | DSH-6 / OC-4 / DSH-5 / OC-5 | TDO-DSH / TDO-OC | **不扩包（D-007，Q-4=B）**：Tier A 为本轮唯一验收对象；Tier B 去向=母版 `CHANGELOG.md`"v1.2 候选"（MAIN S5 落盘）；例外须新决策+新 packet |
| I-12 | — | MAIN | 收口阶段（WS-5） |
| I-6 / X-1 | — | 执行：非本 run 角色；承载 owner=MAIN（CHANGELOG）+ PMO（计划侧 §7）（D-006） | 只登记 |

> 本轮 dispatch 已发生，故 Tier B 不擅自追加到在途 packet；追加会让已声明验收口径变化，违反"包有界"。

## 5. 证据与命名（两 TDO 共用）

- 路径：`runs/openrig-master-selfopt-20261020/evidence/{oc,dsh}/<id>-<subject>.{txt,json}`。
- **禁止 `*.log`**：被 `.gitignore` 忽略，`append-status --also` 会连带整条进度提交失败（`WORKFLOW.md` §5 已记）。
- 每条进度必须三件套：命令 + 退出码 + 证据路径；缺一不算完成。
- 报告：`TDO-OC-REPORT.md` / `TDO-DSH-REPORT.md` = 改动清单（文件:行）+ 复跑命令 + 逐项 PASS/FAIL/延后（含理由）+ 未决项。
- 证据里禁止出现 key/token/完整 transcript 正文。

## 6. QA 对照表（S3 直接用）

| 判据 | 证据 |
| --- | --- |
| G1 五维覆盖 | 本文件 §2（1–5 节齐全） |
| G2 OC ≥1 项可复跑 | `TDO-OC-REPORT.md` + `evidence/oc/*` + §2 命令退出码 |
| G3 DSH ≥1 项可复跑 | `TDO-DSH-REPORT.md` + `evidence/dsh/*` + §2 命令退出码 |
| G4 新母版可实例化 | 合并后：render → `wf.py new-run` scratch → `doctor` PASS → `workflow validate` PASS |
| G5 无 open S1/S2 | `QA-SELF-OPT.md` + `ISSUES.xlsx` |
| G6 v1.1.0 + 文档 | §2 I-12 四条 grep + `--self-check` |
| M10 无越界 | `git status --porcelain` 仅白名单；`--force` 未用于 live bundle |
| D-006/D-007/D-010 落盘 | `grep -c "已知上游问题" CHANGELOG.md` ≥1；`grep -c "v1.2 候选" CHANGELOG.md` ≥1；「已知限制」节含 D-010 强制措辞（同 output-dir 可比 + 4 产物一致 + 路径相对化列 v1.2）—— **关闭前（S5 后）**硬门；`waiting-main` 只要求 owner/去向已登记（见 `PROJECT.md` §6 两段式口径） |

## 7. 风险与回滚总表

| 风险 | 触发 | 缓解 | 回滚 |
| --- | --- | --- | --- |
| 改动破坏 live bundle | 对 `runs/.../openrig/` 用 `--force` | 明令禁止；QA 查 `git status` | 用 I-3 清单确认后重渲染到 `/tmp` 比对 |
| doctor 误 FAIL 旧 bundle | 新增一致性校验 | 缺失字段降 WARN | 单行开关退回只读字段检查 |
| status 退出码变更打断脚本 | 0/2 语义 | 只在 flag 或文档中宣告；默认输出兼容 | 保留旧子命令输出路径 |
| 遥测被当实测 | 默认值 `null` | 文档写"估算 vs 实测" | 关闭 `--with-telemetry` |
| 版本号先行 | MAIN 提前改 VERSION | `--self-check` 拦截 | 回退三处版本行 |
| 恢复演练被误执行 | `recover --plan` 输出命令 | `NOT EXECUTED` 头 + 无 `--execute` | 删除子命令 |
| 上游 fan-out 闭包粒度丢失（X-1） | 多后继 handoff 时 `closureTarget=null` | **D-006**：不修上游；承载=母版 `CHANGELOG.md`"已知上游问题"（MAIN S5）；复核=Round 2 收轮前，判定口径 `closureTarget===null` 时回读 `transitionNote` | 无（不改上游源码）；若上游修复，仅删 CHANGELOG 条目 |

## 8. 本轮明确不做（反目标）

1. 不重构双平面模型、不改 OpenRig 源码/数据库、不改 queue/workflow 状态。
2. 不实现 SAFETY 执行器/门控（只写契约）；不做 H 盘、删除、发布。
3. 不接 provider API，不采集真实 token 计费（只留字段与填写规则）。
4. 不做多项目 registry、不改 UI、不写一键 bootstrap 脚本。
5. 不覆盖 live bundle、不为"验证"重启 live rig/daemon。
6. 不在本轮追加 Tier B 到在途 packet（**D-007 已定：本轮不扩包**，例外须新决策 + 新 packet）。

## 9. 待拍板（不代拍）

| 事项 | 选项 | 结论 | 时点 |
| --- | --- | --- | --- |
| Q-1 并行/串行 | A 并行（两 seat = 预算上限）／B 串行 | **已定 A（D-004）**：上限 2 活跃 agent；同文件冲突、doctor 连红两次、或需第 3 个活跃 agent 即转串行（OC 优先） | 2026-10-20 04:24 |
| Q-2 SAFETY 是否强制 | A 仅高风险（`on-demand`）／B 全 run（`always`） | **已定 A（D-005）**：本 run 不设 SAFETY 位；v1.1 契约按"高风险触发式"写（I-10） | 2026-10-20 04:24 |
| Q-3 失败后 resume/fresh | A 优先 resume，fresh 需 DECISION／B 一律 fresh | **已定 A（D-008）**：默认 resume；fresh 须立 `D-xxx` 并写明理由，且不得表述为"恢复"；作为 v1.1 模板默认策略 | 2026-10-20 04:28 |
| Q-4 Tier B 是否扩包 | A 本轮扩（OC-4/OC-5/DSH-5/DSH-6）／B 留 v1.2 | **已定 B（D-007）**：不扩包；Tier A 为本轮唯一验收对象；去向=母版 `CHANGELOG.md`"v1.2 候选"（MAIN S5 落盘）；例外只能经新决策+新 packet 开单独子集 | 2026-10-20 04:28 |

> **并行时序澄清（回应 MAIN 04:24 批注）**：`SELF-OPT-PLAN.md` 本版未主张"DSH 依赖 OC-2 清单"。DSH-2 判据只读 `rig.yaml` / `workflow.yaml` / bridge 三处既有字段，不消费 `render-manifest.json`；两包唯一共享物是只读的母版目录，故 D-004 的并行判定成立。若后续 DSH 确需清单字段，属有界返工，不构成前置依赖。

