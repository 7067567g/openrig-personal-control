<!-- wf-evidence
run: openrig-master-selfopt-20261020
round: 1
doc: QA-SELF-OPT
owner: QA
state: pass
updated: 2026-10-20
-->

# QA-SELF-OPT — v1.1 候选独立核查

> 初检快照：`2026-10-19T20:34:50Z`（发现 P-001/P-002）。最终复核快照：`2026-10-19T20:43:41Z`（WS-3b + MAIN S5 后）。
> 核查对象：`templates/specialized/openrig-workflow-master/**` 当前工作树（未重新渲染 live bundle）。
> 写权限遵守：本文件、`evidence/qa/**`、`ISSUES.xlsx`；未改母版任何源码/模板/spec，未覆盖 live bundle，未启停 daemon/rig。
> **最终结论：QA_PASS**。检查 1–7 全部 PASS；无 open S1/S2。P-001/P-002 已由 D-011/WS-3b 修复并在 ISSUES 关闭。保留 WARN：TDO-OC 报告行号略旧、`status` queue 键名与计划正文有 schema 漂移（均不影响验收）。
> 阅读顺序：§1–§11 是 20:34Z 初检过程；§12 是 WS-3b + S5 后的最终增量复核，**最终判定以 §12 为准**。

## 0. 判定摘要

| # | 检查 | 判定 | 摘要 |
| --- | --- | --- | --- |
| 1 | render `--help` / `--dry-run --json` / 非法参数 | **PASS** | 最终代码复跑：help rc0；dry-run rc0 且输出目录不存在；4 类非法参数均 rc2 且 stderr 指名字段 |
| 2 | 双 bundle 渲染 / 模板产物哈希 / manifest | **PASS** | 最终代码复跑：两份渲染 rc0；4 份模板产物哈希完全一致；manifest 5 条、`files` 为 dict、含 `renderedAt`/`templates`、可复算、排除自身；D-010 确认跨目录**仅** bridge 不同 |
| 3 | doctor / status / capture（live + 非沙箱） | **PASS** | live doctor rc0；status --json 可解析（5/5 ready）；capture rc0、5 文件 42984 B、scan.ok=true、`source.kind=transcripts-dir`；WS-3b 后 doctor 临时 bridge 两例 rc1 |
| 4 | scratch run 实例化 + doctor + 清理 | **PASS** | 最终母版复跑：`wf.py new-run` rc0；`wf.py doctor` rc0 PASS（errors=0 warns=1）；scratch 已删除 |
| 5 | `rig workflow validate` | **PASS**（有 warning） | 最终渲染 workflow rc0 ok=true；仅 `declared_not_enforced_v1`（测试 bundle 另有预期 role_not_live）warning |
| 6 | 版本/文档候选 + 报告自洽 | **PASS**（WARN） | `VERSION`/README=1.1.0；CHANGELOG 有 `## 1.1.0` 与 ≥5 条带文件名条目；D-006/D-007/D-010 均有落点。TDO-OC 行号略旧，DSH 报告在 QA 结果前保持 PARTIAL（已条件化） |
| 7 | S1/S2 issue 登记 | **PASS** | P-001/P-002 均 `已关闭`（D-011）；`ISSUES.xlsx` open S1/S2 = 0 |

**最终候选哈希**（详见 `evidence/qa/qa9-ws3b-snapshot.txt`；初检哈希保留在 `qa0-snapshot.txt`）：

```text
render_master.py       4f0e32e6e215c0004e2859bbfeac30719163af5f7f078844234552e812bafcee
openrig_bridge.py      8c449235efdeed37b482976f80bd3ee320f0c44982eceef5771d047edf521c92
ARCHITECTURE.md        9fd734a33956ed23b63d1544fc8b639e349876cb87416ef49e0d56ebf0b51b97
VERSION                1575e1af4a95f12f70b4ee6a6adce8160953d93ea17dc2611b90883ccc3ad3b8
CHANGELOG.md           2d0deaf30a0ebc90322b27d6c72cdc2543bfc038eb27085d63a562fcb993404c
README.md              8dc0858e86e86f0f6e51d0641e339627114e1e852e7b84900bada94bd289c880
TDO-OC-REPORT.md       9da84aa44fa4b2253f8f3f74715ca99a6f54fe3a114cb3177bbef1befb24f637
TDO-DSH-REPORT.md      8b224d080138796c74c5ebca21566008d188af3848e6714574c6df4ce717de75
TDO-DSH-FIX-REPORT.md  415d60c4cf34a010e4cad9001af3745d939fb9835c2c220e224e5a0291bb3eb1
ISSUES.xlsx            1afa7c07c3fcf6ce241c62595d1f9c83e34bdd89de6e76ee518afc942ef161a0
```

> 注：本 run 为活动 run，`TDO-DSH-REPORT.md` / `DECISIONS.md` 在 QA 期间仍被其他 seat 更新。以上为最终复核快照哈希；结论按该快照成立。

---

## 1. 检查 1 — generator 参数契约

工作目录：`templates/specialized/openrig-workflow-master/`

| 命令 | rc | 结果 |
| --- | --- | --- |
| `python3 render_master.py --help` | 0 | 打印 usage 与退出码契约（0/2/3） |
| `python3 render_master.py --run-id qa-selfopt-dry --project-root /tmp --output-dir /tmp/qa-selfopt-dry-1792441808 --dry-run --json` | 0 | `ok=true`、`dryRun=true`、`files=5`、`nextCommands=9`；命令前后目标目录均不存在（`test -e` rc=1） |
| `python3 render_master.py --run-id BAD_ID --project-root /tmp --dry-run` | 2 | stderr 指名 `--run-id` |
| `python3 render_master.py --run-id qa-ok --project-root /tmp --daemon-port 70000 --dry-run` | 2 | stderr 指名 `--daemon-port`（1..65535） |
| `python3 render_master.py --run-id qa-ok --project-root /tmp/nope-qa --dry-run` | 2 | stderr 指名 `--project-root` |
| `python3 render_master.py --run-id qa-ok --project-root /tmp --output-dir "  " --dry-run` | 2 | stderr 指名 `--output-dir` |

判定：**PASS**。参数错误全部发生在写盘前，dry-run 零落盘。

证据：
- `evidence/qa/qa1-help.txt`
- `evidence/qa/qa1-dryrun.json`
- `evidence/qa/qa1-dryrun.err`
- `evidence/qa/qa1-invalid-args.txt`

---

## 2. 检查 2 — 双 bundle 渲染、模板产物哈希、manifest

命令（工作目录同上）：

```bash
python3 render_master.py --run-id qa-selfopt-mm --project-root /tmp --output-dir /tmp/qa-selfopt-mm-a --json   # rc=0
python3 render_master.py --run-id qa-selfopt-mm --project-root /tmp --output-dir /tmp/qa-selfopt-mm-b --json   # rc=0
diff -r /tmp/qa-selfopt-mm-a /tmp/qa-selfopt-mm-b
```

结果：

- 两份 bundle 均 rc=0，各 6 个文件（4 模板产物 + bridge + manifest）。
- 4 份模板产物（`rig.yaml` / `workflow.yaml` / `agents/worker/agent.yaml` / `guidance/team.md`）的 `sha256` **完全一致**。
- `OPENRIG-BRIDGE.json` 与 manifest 中该文件哈希不同：bridge 的 `bundleDir` / `rigSpec` / `workflowSpec` 记录绝对输出路径；这是 v1.0.0 既有契约，TDO-OC 报告 §5-1 已披露，未在本轮修。
- `render-manifest.json`（初检时）：`schemaVersion=1`、`masterVersion=1.0.0`、5 条 `path/template/bytes/sha256`；未包含自身；5/5 哈希独立复算一致。**最终 S5 后 `masterVersion=1.1.0`，并含 `renderedAt`/`templates`/dict 结构，见 §12.5。**
- 额外回归：用 live bridge 参数渲染到 `/tmp`，4 份模板产物与 live bundle 逐字节 `IDENTICAL`；bridge 仅因输出路径不同而不同。
- 计划 I-3 的示例脚本把 `manifest["files"]` 当 dict 使用，实际实现为 **list**；这是计划文本与实现的 schema 漂移（见 W-2），不影响 manifest 的可复算性。

判定：**PASS**。按 D-010（Q-OC-1=A），manifest 只承诺同一 `output-dir` 内可比；跨目录时**仅** `OPENRIG-BRIDGE.json` 的哈希不同（`bundleDir`/`rigSpec`/`workflowSpec` 绝对路径），其余 4 个模板产物全等。复跑 `/tmp/qa-d010-a` vs `/tmp/qa-d010-b` 已验证该声明，不判为缺陷。

证据：
- `evidence/qa/qa2-render-a.json` / `qa2-render-b.json`
- `evidence/qa/qa2-render-a.err` / `qa2-render-b.err`
- `evidence/qa/qa2-manifest-compare.txt`
- `evidence/qa/qa2-livecheck.json` / `qa2-livecheck-compare.txt`

---

## 3. 检查 3 — bridge doctor/status/capture（live + 非沙箱 seat）

### 3.1 doctor（直接对 live run）

```bash
python3 tools/openrig_bridge.py doctor --run-dir runs/openrig-master-selfopt-20261020
# rc=0
# PASS bridge runId=openrig-master-selfopt-20261020 rig=openrig-master-selfopt workflow=openrig-workflow-master-selfopt
#   home=/tmp/openrig-master-selfopt-home exists writable
```

判定：**PASS**。live bundle 的 bridge ↔ `rig.yaml` ↔ `workflow.yaml` ↔ `openrigHome` 一致。

### 3.2 status --json

为避免改写 live run 的 `OPENRIG-STATE.json`（QA 写权限仅本文件 + evidence），把 run 目录的 bridge 复制到 `/tmp/qa-live-status-736661/openrig/` 后执行；执行面仍是 live daemon/rig：

```bash
python3 tools/openrig_bridge.py status --run-dir /tmp/qa-live-status-736661 --json
# rc=0
```

解析结果：顶层键 `degraded/errors/generatedAt/queue/rigName/runId/schemaVersion/seats/sources/workflow`；`seats.total=5, ready=5`；`workflow.instance=01M5AX5EJXRYW48BY577HX8X4X`、`status=active`、`step=qa`、`owner=assurance-qa@openrig-master-selfopt`；`queue={total:1,pending:1,"in-progress":0,blocked:0}`；`degraded=false`。

降级分支：把临时 bridge 的 `openrigCli` 改为 `/bin/false` 后，`status --json` **rc=2**，仍写出 `OPENRIG-STATE.json`，`errors=4`，三个 source 的 rc=1。

判定：**PASS**。字段可解析，0/2 退出码符合计划。

### 3.3 capture（非沙箱 seat）

```bash
python3 tools/openrig_bridge.py capture \
  --run-dir runs/openrig-master-selfopt-20261020 \
  --out runs/openrig-master-selfopt-20261020/evidence/qa/qa3-transcripts
# rc=0
# wrote .../capture-manifest.json (5 files, 42984 bytes)
```

结果：

- `source.kind=transcripts-dir`，`source.dir=/tmp/openrig-master-selfopt-home/transcripts/openrig-master-selfopt`，证明本 QA seat **不是** DSH 的 `/tmp` 沙箱：DSH 报告 §3 的“live 目录分支待 QA 复核”项已复核通过。
- 5 个 transcript 文件，`capture-manifest.json` 记录 `path/bytes/sha256`；独立复算 5/5 一致。
- `scan.ok=true`、`hits=[]`；独立 `grep -RInE` 对同一组模式扫描返回 rc=1（无命中）。
- 附加 rc1 分支：临时 bridge（`openrigCli=/bin/false`）+ 不存在的 `--source` → rc=1，仍写 `capture-manifest.json`，`ok=false`、`files=0`、`source.kind=cli-fallback`。

判定：**PASS**（含 DSH 报告列出的唯一 live 分支待复核项）。

### 3.4 初检暴露的 S2（P-002；WS-3b 后已关闭，见 §12）

对临时 bridge 把 `policy.safetyMode` 改为 `"off"`：

```bash
python3 tools/openrig_bridge.py doctor --run-dir /tmp/qa-selfopt-brk-safety
# rc=0，PASS（未报 FAIL）
```

对临时 bridge 把 `schemaVersion` 改为 `999`：

```bash
python3 tools/openrig_bridge.py doctor --run-dir /tmp/qa-selfopt-brk-schema
# rc=0，PASS（未报 FAIL）
```

计划 I-10 要求 `safetyMode: "off"` 报 FAIL；D-009 验收②进一步要求 `schemaVersion=999` 报 FAIL。**初检时**两者均未实现 → P-002；**WS-3b 后两者均 rc1 并指名字段，P-002 已关闭（§12）**。

> **WS-3b 增量口径（MAIN 20:34Z）**：§7 的 `safetyMode` 行与 `_doctor_check` 的 `schemaVersion`/`safetyMode` 枚举校验是 D-009 的极小增量。**WS-3b 已落地并按 §12 重跑：live PASS、两例非法 bridge rc1，P-002 已关闭。**

证据：
- `evidence/qa/qa3-doctor.txt`
- `evidence/qa/qa3-status.json` / `qa3-status.err`
- `evidence/qa/qa3-status-degraded.txt` / `.json` / `.err`
- `evidence/qa/qa3-capture.out` / `.err`
- `evidence/qa/qa3-capture-verify.txt`
- `evidence/qa/qa3-transcripts/capture-manifest.json` + 5 份 transcript
- `evidence/qa/qa3-capture-rc1.txt`
- `evidence/qa/qa7-precheck-gaps.txt`
- `evidence/qa/qa7-doctor-invalid.txt`
- `evidence/qa/qa7-schema-version.txt`

---

## 4. 检查 4 — scratch run 实例化

```bash
python3 scripts/wf.py new-run qa-scratch-1792441861 \
  --template templates/specialized/openrig-workflow-master \
  --goal "QA scratch instantiation of v1.1 candidate" \
  --project-root /tmp \
  --scope "runs/qa-scratch-1792441861/**" \
  --tdo 2
# rc=0
python3 scripts/wf.py doctor qa-scratch-1792441861
# rc=0；PASS (errors=0, warns=1)
# [WARN] STATUS-Round-1.md: 还没有进度条目
rm -r runs/qa-scratch-1792441861
# rc=0；exists_rc=1（已删除）
```

判定：**PASS**。scratch run 从母版成功实例化，doctor 仅因新 run 尚无 STATUS 进度而 WARN；验证后删除，无残留。

证据：`evidence/qa/qa4-scratch.txt`

---

## 5. 检查 5 — `rig workflow validate`

```bash
rig workflow validate /tmp/qa-selfopt-mm-a/workflow.yaml --json
# rc=0；ok=true；stepCount=5
rig workflow validate runs/openrig-master-selfopt-20261020/openrig/workflow.yaml --json
# rc=0；ok=true；stepCount=5
```

warning：

- 两份都有的 5 条 `declared_not_enforced_v1`：`invariants.continuation_required`、`invariants.preserve_lineage`、`invariants.closure_required`、`closure`、`loop_guards.spawn_budget`。这是 OpenRig v1 的“已声明未执行”提示，不是本次渲染错误。
- `/tmp` 测试 bundle 额外有 5 条 `role_no_live_preferred_target`：因为 `openrig-qa-selfopt-mm` rig 本就不存在，属预期；live workflow 无此 warning，`exceptionReadiness` 的 `unmapped_failed` / `stuck_overdue` 两条路由均为 `ready`（`control-main@openrig-master-selfopt` 是 declared-member）。

判定：**PASS**（有上述 warning；无 error）。

证据：`evidence/qa/qa5-workflow-validate.txt`

---

## 6. 检查 6 — 版本/文档候选与报告自洽

### 6.1 版本/文档（最终快照）

| 项 | 实际 | 判定 |
| --- | --- | --- |
| `VERSION` | `1.1.0` | PASS |
| `README.md` 第 3 行 | `版本：1.1.0` | PASS |
| `CHANGELOG.md` | 有 `## 1.1.0`（8 条改动/新增，含文件名）与 `## 1.0.0`；`## 1.2 候选` | PASS |
| D-006 上游闭包问题 | CHANGELOG `Known limitations` 写明多 successor 时 `closureReason/closureTarget` 可能为 null，`transitionNote` 保留数量 | PASS |
| D-007 Tier B / D-010 路径相对化 | CHANGELOG `## 1.2 候选` 含 bridge 路径相对化、Tier B self-check 等 | PASS |
| D-010 manifest 口径 | CHANGELOG 明确“sha256 只在同一 output-dir 内可比”；README 同步 1.1.0 | PASS |
| `render_master.py --self-check` | 未实现（I-11 为 Tier B，D-007 不扩包） | 不在本轮验收范围 |

结论：**G6/M9 已由 MAIN S5 完成**；版本、README、CHANGELOG 三处一致，D-006/D-007/D-010 均有落点。

### 6.2 报告自洽（最终快照）

| 报告 | 声明 | 独立核对 | 判定 |
| --- | --- | --- | --- |
| TDO-OC | OC-1/2/3 全 PASS；manifest `files` dict 5 项 + `renderedAt` + `templates` 4 项；4 模板与 live 一致 | 最终代码复跑：manifest 结构与报告一致；4 产物与 live `IDENTICAL`；行号区间已更新 | **PASS** |
| TDO-DSH | 结论改为 **PARTIAL（QA 复核前）**；DSH-4 的 P-001/P-002 由 WS-3b 自验补齐，待 QA 转 PASS | QA §12 已重跑 doctor/§5.4；`gate_result` 4 值与单 JSONL 差异节保留并条件化 | **PASS**（PARTIAL 是诚实的中间态，非虚假 PASS） |
| TDO-DSH 哈希 | 报告末尾 `openrig_bridge.py=8c4492…`、`ARCHITECTURE.md=9fd734…` | 与实际最终文件一致 | PASS |
| TDO-OC / TDO-DSH-FIX 证据 | `TDO-DSH-FIX-REPORT.md` 的 P-001/P-002 自验表 | 与 QA §12 的 rc/字段逐项一致 | PASS |

结论：**PASS**。保留 WARN：TDO-OC 个别行号仍是近似值；不影响功能/验收。

证据：
- `evidence/qa/qa6-consistency.txt`
- `evidence/qa/qa9-ws3b-recheck.txt`
- `evidence/qa/qa9-ws3b-snapshot.txt`
- `evidence/qa/qa10-*`

---

## 7. 检查 7 — ISSUE 登记与 S1/S2（最终）

使用 `python3 scripts/issues.py` 写入 `ISSUES.xlsx`（未手工改表）：

```bash
python3 scripts/issues.py list runs/openrig-master-selfopt-20261020/ISSUES.xlsx
# P-001  1  问题  S2  已关闭  否  I-7 §5.4 队列调优契约未落地
# P-002  1  问题  S2  已关闭  是  I-10 SAFETY 契约与 doctor safetyMode/schemaVersion 校验未按计划落地
```

> 关联决策：P-001/P-002 均由 D-011（WS-3b）收口；`issues.py list` 的“决策”列显示的是 need-decision 标志，不是决策 ID。**open S1/S2 = 0。**

### P-001（S2，已关闭 / D-011）I-7 §5.4 队列调优契约未落地

- 初检事实：§5.4 只有 5 条原则句，无 `tier`/`priority`、无 packet 粒度上限、无 `rig queue` 命令/字段；DSH packet 本身 4 项任务，超过 I-7 的 ≤3 任务约束。
- WS-3b 修复：§5.4 改为 7 行契约表（粒度、tier、priority、max_hops↔depends_on、fan-out、stale claim、写入面），每行有“落点/命令”。
- QA 抽查 3 条：`rig queue create --body-file/--tier/--priority` 均存在；`rig queue list --state`、`rig queue unclaim --reason` 存在；`workflow.yaml` 的 `depends_on`、`loop_guards.max_hops` 与 queue 的 `closureRequiredAt` 字段真实存在。
- 已关闭（D-011）。

### P-002（S2，已关闭 / D-009+D-011）I-10 SAFETY 契约与 doctor safetyMode/schemaVersion 校验

- 初检事实：ARCH §7 缺 `safetyMode` 行；`doctor` 对 `safetyMode=off`、`schemaVersion=999` 均 rc0 PASS。
- WS-3b 修复：`_doctor_check` 增加 `schemaVersion==1` 与 `policy.safetyMode ∈ {on-demand, always}` 校验；ARCH §3.2/§7 补载体契约行。
- QA 重跑：live `doctor` rc0 PASS；`safetyMode=off` → `FAIL policy.safetyMode bridge=off spec=on-demand|always` rc1；`schemaVersion=999` → `FAIL schemaVersion bridge=999 spec=1` rc1；`status --json` rc0 可 `json.loads`。
- `gate_result` 4 值与单 JSONL 的差异保留，DSH 报告 §7.1 已登记（D-009 接受），不是缺陷。
- 已关闭（D-011）。

**S1：无。** 本轮未执行删除/发布/权限/H 盘动作；live `safetyMode=on-demand`，SAFETY 执行器按计划未实现。

---

## 8. WARN / 已知限制（未升级为 S1/S2）

| ID | 内容 | 影响 | 证据 |
| --- | --- | --- | --- |
| W-1 | ~~VERSION/README 仍 1.0.0~~ **已解除**：S5 后 `VERSION`/README=1.1.0，CHANGELOG 有 `## 1.1.0` | 无 | `qa10-final-docs.txt`、`qa9-ws3b-snapshot.txt` |
| W-2 | ~~manifest 无 `renderedAt` / `files` 为 list~~ **已解除**：最终 `files` 为 dict、含 `renderedAt`/`templates`；跨目录差异按 D-010 接受 | 无（跨目录仅 bridge 不同，D-010） | `qa10-render-a.json`、`qa2-d010-recheck.txt` |
| W-3 | `status` 实际 `seats{total,ready,nodes}` / `workflow{instance,status,step,owner,frontier}` / `queue{total,pending,in-progress,blocked}`，计划正文写 `seats{ready,total,bySeat}` / `workflow{instance,currentStep,frontier}` / `queue{pending,inProgress,overdue}` | 字段名/缺 `overdue` 属 schema 漂移；当前无消费方依赖；不影响验收 | `qa9-status.json`、`qa3-status.json` |
| W-4 | TDO-OC 报告个别行号为近似值；TDO-DSH 报告在 QA 结果前保持 PARTIAL（已条件化） | 不影响功能结论；最终快照哈希见 §0 | `qa6-consistency.txt`、`qa9-ws3b-snapshot.txt` |
| W-5 | ~~`doctor` 不校验 `bridge.schemaVersion`~~ **已解除**：WS-3b 后 `schemaVersion=999` → rc1 | 无 | `qa9-ws3b-recheck.txt` |

---

## 9. 证据索引

```text
runs/openrig-master-selfopt-20261020/evidence/qa/
├── qa0-snapshot.txt                 # 快照时间、版本、候选哈希、mtimes、live ps、issue 列表
├── qa1-help.txt                     # render --help rc0
├── qa1-dryrun.json / .err           # dry-run --json rc0 + 零落盘
├── qa1-invalid-args.txt             # 4 类非法参数 rc2
├── qa2-render-a.json / .err         # 第一次渲染 rc0
├── qa2-render-b.json / .err         # 第二次渲染 rc0
├── qa2-manifest-compare.txt         # 模板产物哈希一致、manifest 5 条、复算 0 差异
├── qa2-d010-recheck.txt             # D-010 复跑：跨目录仅 bridge 不同，4 产物全等
├── qa2-livecheck.json / -compare    # 与 live bundle 的 4 产物逐字节一致
├── qa3-doctor.txt                   # live doctor rc0 PASS
├── qa3-status.json / .err           # status --json rc0，5/5 ready
├── qa3-status-degraded.txt/.json/.err # openrigCli=/bin/false → rc2 仍落盘
├── qa3-capture.out / .err           # capture rc0
├── qa3-capture-verify.txt           # 5/5 sha256 复算 + 独立 grep 无密钥
├── qa3-transcripts/                 # capture-manifest.json + 5 份 transcript
├── qa3-capture-rc1.txt              # 来源不可用 rc1 仍写 manifest
├── qa4-scratch.txt                  # new-run rc0 / doctor rc0 / 删除
├── qa5-workflow-validate.txt        # 两份 workflow validate rc0 + warnings
├── qa6-consistency.txt              # 版本、文件哈希、报告声称值、§5.4/safetyMode grep
├── qa7-precheck-gaps.txt            # I-7 §5.4 原文 + safetyMode=off doctor rc0 + 枚举差异
├── qa7-doctor-invalid.txt           # 固定路径复跑：safetyMode=off / schemaVersion=999 均 rc0
├── qa7-schema-version.txt           # schemaVersion=999 doctor rc0（早期临时路径）
├── qa8-workflow-handoff.txt         # QA packet 已 claim/close，handoff 到 close_round
├── qa9-ws3b-recheck.txt             # WS-3b：live PASS + safetyMode=off/schemaVersion=999 rc1 + status
├── qa9-status.json / .err           # WS-3b 后 status --json rc0
├── qa9-capture-final.out / .err     # WS-3b 后 capture rc0，5 文件 / scan clean
├── qa9-transcripts-final/           # 最终 capture manifest + 5 transcript
├── qa9-ws3b-p001-commands.txt       # §5.4 抽查：rig queue 命令 / workflow.yaml 键 / closureRequiredAt
├── qa9-ws3b-snapshot.txt            # WS-3b 后最终候选哈希、ISSUES 状态
├── qa10-help-final.txt              # S5 后 render --help rc0
├── qa10-args-final.txt              # S5 后 dry-run / 4 类非法参数 rc2
├── qa10-dry.json                    # S5 后 dry-run --json rc0
├── qa10-render-a.json / -b.json     # S5 后双渲染 rc0
├── qa10-livecheck.json / -compare   # S5 后与 live bundle 4 产物一致
├── qa10-workflow-validate.json      # 最终 workflow validate rc0
├── qa10-scratch-final.txt           # 最终 scratch new-run/doctor/删除
├── qa10-final-docs.txt              # VERSION/README/CHANGELOG + D-006/D-007/D-010
├── qa11-help-final2.txt             # 20:44 render 更新后 help rc0
├── qa11-dry.json / .err             # 20:44 后 dry-run rc0 + 零落盘
├── qa11-args-final2.txt             # 20:44 后 4 类非法参数 rc2
├── qa11-a.json / qa11-b.json        # 20:44 后双渲染 rc0
├── qa11-livecheck.json / -compare   # 20:44 后 4 产物与 live 一致
├── qa11-workflow-validate.json      # 20:44 后 workflow validate rc0
└── qa11-final2-snapshot.txt         # 20:49 最终哈希快照
```

---

## 10. 复查路径（给 MAIN / TDO-DSH）

1. **P-002 / WS-3b（D-009）**：在 `_doctor_check` 增加 `policy.safetyMode ∈ {on-demand, always}` 与已知 `schemaVersion` 集合校验；ARCH §7 补 `safetyMode` 行；报告补差异节。复跑：
   ```bash
   python3 tools/openrig_bridge.py doctor --run-dir runs/openrig-master-selfopt-20261020   # rc0
   # 临时 bridge safetyMode=off → rc1；schemaVersion=999 → rc1
   ```
2. **P-001 / I-7**：补齐 `ARCHITECTURE.md` §5.4 可执行调优表，逐条指向 `rig queue` / queue 字段 / `workflow.yaml` 键；QA 抽 3 条对照本轮 OC/DSH packet。
3. 两项关闭后，重跑本报告检查 1/3/5/6 的最小集；届时才可把 `QA-SELF-OPT` 判定改为 PASS。**该增量复核已完成，见 §12；当前最终判定为 QA_PASS。**

---

## 11. 执行面交接

- claim：`rig queue claim qitem-20261019202950-df7e70a5 --json` rc=0（20:37:35Z，QA packet 进入 in-progress）。
- 关闭/投影：`rig workflow project --instance 01M5AX5EJXRYW48BY577HX8X4X --current-packet qitem-20261019202950-df7e70a5 --exit handoff --actor-session assurance-qa@openrig-master-selfopt --result-note "QA_FAIL: ..." --evidence-ref runs/openrig-master-selfopt-20261020/QA-SELF-OPT.md --json` rc=0。
- 结果：QA packet `state=handed-off`、`closureReason=handed_off_to`、`closureTarget=control-main@openrig-master-selfopt`；workflow 前进到 `close_round`，next packet `qitem-20261019203740-dc5e28f1`，owner `control-main@openrig-master-selfopt`。
- 已 `rig send exec-tdo-oc@openrig-master-selfopt` 回执 QA_FAIL 摘要（rc=0；relay 提示无 activity hook，属 advisory）。
- 20:41Z 收到针对同一 qitem 的 watchdog parked-owner wake；核查时该行已是 `state=handed-off`（terminal），wake 时间 20:36:35Z 早于 claim 20:37:35Z 与 handoff 20:37:40Z。未重开/未改状态，仅 `rig queue update --note` 追加 transition 24 说明，避免重复 wake。
- workflow 实例随后由 control-main 在 `close_round` 以 `exit=failed` 关闭（20:40:09Z），failureReason 明确引用 QA_FAIL 的两个 open S2；异常义务 `qitem-20261019204009-d27e0dcf` 归 control-main。该关闭是 MAIN 对**上一实例**的收口动作；WS-3b 后 §12 已重新复核为 **QA_PASS**。

证据：`evidence/qa/qa8-workflow-handoff.txt`。

---

## 12. WS-3b + MAIN S5 最终增量复核（决定判定）

> 复核时间：`2026-10-19T20:43:41Z`；最终候选哈希见 §0。WS-3b 由 D-009/D-011 授权（bridge `_doctor_check` + ARCH §3.2/§5.4/§7 + DSH 报告差异节），MAIN S5 同步版本/文档。以下为**一次做完**的增量复核。

### 12.1 P-002 — doctor 载体校验

| 用例 | 命令 | rc | 实际输出 |
| --- | --- | --- | --- |
| live run（合法） | `python3 tools/openrig_bridge.py doctor --run-dir runs/openrig-master-selfopt-20261020` | **0** | `PASS bridge runId=… rig=openrig-master-selfopt workflow=…`；`home=/tmp/openrig-master-selfopt-home exists writable` |
| `policy.safetyMode="off"` | `python3 tools/openrig_bridge.py doctor --run-dir /tmp/qa-selfopt-brk-safety` | **1** | `FAIL policy.safetyMode bridge=off spec=on-demand\|always` |
| `schemaVersion=999` | `python3 tools/openrig_bridge.py doctor --run-dir /tmp/qa-selfopt-brk-schema` | **1** | `FAIL schemaVersion bridge=999 spec=1` |

结论：P-002 的 two FAIL 用例均按 D-009 验收①/②返回 rc1 且指名字段；live 仍 PASS。**P-002 关闭（D-011）**。

### 12.2 status — JSON 可解析

```bash
python3 tools/openrig_bridge.py status --run-dir /tmp/qa-ws3b-status --json
# rc=0
```

`json.loads` 通过；顶层键 `degraded/errors/generatedAt/queue/rigName/runId/schemaVersion/seats/sources/workflow`；`seats.ready=5/5`；`queue={total:0,pending:0,"in-progress":0,blocked:0}`；`degraded=false`。workflow 实例 `01M5AX5EJXRYW48BY577HX8X4X` 为 `failed`（D-012 的 close_round 退出，不是 run 终止），`status` 仍能读出该实例，未抛栈。

> 为保护 live run 的 `OPENRIG-STATE.json`（QA 写权限仅本文件 + evidence），status 使用 `/tmp` 的 bridge 副本；执行面仍为 live daemon/rig。doctor 则直接对 live run。

### 12.3 P-001 — §5.4 可执行契约抽查

`ARCHITECTURE.md` §5.4 现为 7 行表（292–307），抽查 3 行：

| 抽查 | 契约内容 | 可复跑证据 |
| --- | --- | --- |
| packet 粒度 | ≤1 文件面 + ≤3 任务；超限拆包；跨文件用 `depends_on` 串行 | `rig queue create --body-file` 存在；`workflow.yaml` 有 `depends_on` |
| `tier` / `priority` | `fast/routine/deep/critical`；`priority` routine/urgent/critical，urgent 需写明阻塞点 | `rig queue create --tier` / `--priority` 均存在（`rig queue create --help`） |
| stale claim | `rig queue list --state in-progress --json` + `rig queue show` 看 claim/age；`rig queue unclaim --reason stale`；watchdog `queue-stuck-sweep`/`parked-owner-consumer` | `rig queue list --state`、`rig queue unclaim --reason` 均存在；queue row 有 `tier/priority/closureRequiredAt` 字段 |

另核对 `max_hops` ↔ `depends_on`、fan-out、写入面（禁止直接写 sqlite/手改 bridge）均有真实命令或 `workflow.yaml` 键；无纯形容词行。**P-001 关闭（D-011）**。

### 12.4 DSH 报告差异节

`TDO-DSH-REPORT.md` §7.1 已保留：
- `gate_result` 交付 4 值：`PASS` / `FAIL` / `NEEDS-HUMAN` / `EXPIRED`；
- 账本为单文件 `runs/<run-id>/safety/gate-ledger.jsonl`；
- 与计划 6 值 / 五目录的差异及理由（D-009 接受），不是未披露的偏差。

`TDO-DSH-FIX-REPORT.md` 的 P-001/P-002 自验表与 QA 实测 rc/字段一致。

### 12.5 generator / 实例化 / validate（S5 后最终代码）

```bash
python3 render_master.py --help                                             # rc=0
python3 render_master.py --run-id qa-final-dry --project-root /tmp \
  --output-dir /tmp/qa-final-dry --dry-run --json                           # rc=0；目录不存在
# 4 类非法参数（run-id/daemon-port/project-root/output-dir）                # rc=2
python3 render_master.py --run-id qa-final --project-root /tmp \
  --output-dir /tmp/qa-final-a --json                                       # rc=0
python3 render_master.py --run-id qa-final --project-root /tmp \
  --output-dir /tmp/qa-final-b --json                                       # rc=0
```

- 4 份模板产物 A/B 哈希完全一致；跨目录**仅** `OPENRIG-BRIDGE.json` 不同（D-010）。
- `render-manifest.json`：`files` 为 dict（5 项：path→template/bytes/sha256）、`renderedAt` 存在、`templates` 4 项原始模板哈希、`masterVersion=1.1.0`；5/5 输出哈希复算一致，清单不含自身。
- 与 live 参数渲染：`rig.yaml` / `workflow.yaml` / `agents/worker/agent.yaml` / `guidance/team.md` 与 live bundle 逐字节 `IDENTICAL`。
- `rig workflow validate /tmp/qa-final-a/workflow.yaml --json` rc0 ok=true；仅 5 条 `declared_not_enforced_v1`（测试 bundle 另有 5 条预期 `role_no_live_preferred_target`）。
- 最终 scratch：`wf.py new-run qa-final-scratch-1792442741` rc0；`wf.py doctor` rc0 PASS（errors=0 warns=1）；已 `rm -r`，无残留。
- **20:44Z 追加更新**：MAIN 对 `render_master.py` 又做了一次非行为性改动（最终哈希 `4f0e32e6…`）。QA 用 `qa11-*` 复跑：help rc0、dry-run rc0 且零落盘、4 类非法参数 rc2、双渲染 rc0、4 产物与 live `IDENTICAL`、`rig workflow validate` rc0 ok=true；manifest 仍为 `1.1.0`/dict/`renderedAt`/`templates`，结论不变。

- `VERSION=1.1.0`；README 第 3 行=1.1.0；CHANGELOG 有 `## 1.1.0`（8 条，含文件名）与 `## 1.0.0`、`## 1.2 候选`。
- D-006（多 successor 闭包字段）、D-007（Tier B/1.2 候选）、D-010（manifest 同目录可比）在 CHANGELOG/README 均有落点。
- `ISSUES.xlsx`：P-001 `已关闭`、P-002 `已关闭`；**open S1/S2 = 0**。

**最终判定：QA_PASS。** 检查 1–7 全部 PASS；无 open S1/S2。保留的非阻断 WARN 仅：`status` 的 queue 键名与计划正文有 schema 漂移（W-3）、TDO-OC 个别行号近似（W-4）。D-012 的 workflow `failed` 是上一实例的 close_round 收口方式，rework 已由 WS-3b 独立 packet + 本次 QA 增量复核闭合，不代表 run 终止。

证据：
- `evidence/qa/qa9-ws3b-recheck.txt`
- `evidence/qa/qa9-status.json` / `.err`
- `evidence/qa/qa9-ws3b-p001-commands.txt`
- `evidence/qa/qa9-ws3b-snapshot.txt`
- `evidence/qa/qa10-help-final.txt`
- `evidence/qa/qa10-args-final.txt`
- `evidence/qa/qa10-dry.json`
- `evidence/qa/qa10-render-a.json` / `qa10-render-b.json`
- `evidence/qa/qa10-livecheck.json` / `qa10-livecheck-compare.txt`
- `evidence/qa/qa10-workflow-validate.json`
- `evidence/qa/qa10-scratch-final.txt`
- `evidence/qa/qa10-final-docs.txt`
