<!-- wf-doc
run: openrig-p0-hard-constraints-20261116
round: 1
doc: PROJECT
owner: PMO
state: closed
updated: 2026-11-16
tags: template/openrig-workflow-master, baseline/two-plane-orchestration
primary_type: composite/two-plane-orchestration
maturity: M3
baseline: composite/two-plane-orchestration@1.0.0
contracts: strategy@1.0.0, research@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0
-->

# PROJECT — P0 hard constraints

> 写者：PMO ｜ 本轮 3 seats 无独立 PMO，`plan` 包由 MAIN 按 WORKFLOW 代行，写完后本文件只读 ｜ 主会话运行期只读 §6。
> 控制面权威：本文件 + `SPEC.md` + `DECISIONS.md`；执行面权威：OpenRig queue/workflow/transcript。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `openrig-p0-hard-constraints-20261116` |
| 一句话目标 | 实施 P0 hard-constraint stack R01–R07，并为每个硬门补 R08 负向测试；只改 workflow-group scripts/tests 与本 run reports。 |
| 项目根 | `/home/a7067567g/下载/deepseek/deepseek-知识库` |
| 只读产品仓 | `/home/a7067567g/下载/deepseek/deepseek-项目/10-openrig-deepseek`（HEAD `e932ae94e4c07b619c39902f29db949464ebb295`；规划时已有 29 条 pre-existing dirty，不得覆盖/回滚） |
| 写权限白名单 | `workflow-group/scripts/**`、`workflow-group/tests/**`、`workflow-group/runs/openrig-p0-hard-constraints-20261116/reports/**` |
| 主会话提交范围 | 无：本轮不 commit、不 push、不打 tag |
| 编制 | MAIN×1 / TDO-OC×1 / QA×1（无 PMO、无 DSH、无 SAFETY） |
| 当前轮次 | Round 1 |
| 工作流 | `plan → impl_preflight_components → impl_baseline_evidence → impl_close_archive_render → qa_final → close_round` |
| 终止判据 | 全量 pytest rc=0；TASK §5 六条入口可复跑；每个硬门至少 1 个负向用例；产品仓相对规划基线零新增改动；无 commit/push；QA 独立复跑 PASS 或 PASS-WITH-WARN。 |

## 1. 目标与成功判据

- **G1 R05/R06（Packet A）**：`openrig_preflight.py` 的 `ok` 仅由全部 `required` checks 决定，缺 workspace/run-id/managed block/run docs 均 fail-closed；`required_components.py` 对缺失依赖给出可执行安装命令；`issues.py` 在无 `openpyxl` 时 import 不崩且 `read_rows()` 走 JSONL 降级；`wf.py doctor` 顶部报告 required-components 而不是抛 `NoneType`。
  - 判据：目标测试文件全绿；无上下文跑出 `ok:false`/rc=1，`--advisory` 同样 `ok:false` 但 rc=0；`HAS_OPENPYXL=False` 的模拟导入成功。
- **G2 R02/R03（Packet B）**：`baseline` 捕获 HEAD/status/diff 的 sha256 并排除本 run 目录；`verify-baseline` 用同一 projectRoot/excludePaths 重算，任一变化 rc=1 且打印结构化 diff；`evidence_run.sh` 保留真实 rc、启用 pipefail、记录 stdout/stderr sha256。
  - 判据：临时 git 仓库中改文件 → verify rc=1；本 run 目录内新增文件 → verify rc=0；`printf x; exit 7` → rc=7 且文件含 `rc=7`；`false | tail` → rc=1。
- **G3 R01/R04/R07（Packet C）**：`archive-gate` 只 dry-run 复用 guard 的 strict COMPLETE 语义；`wf_close_lint.py --strict` 要求 FINAL.md + closeout manifest + 逐条重算 sha256 + revision 链不倒退；`verify_render.py` 默认 WARN、`--strict` 才 ERROR，manifest 缺失/坏 JSON 返回 rc=2。
  - 判据：guard complete→rc=0/ok:true，partial→rc=2/ok:false，guard missing→rc=3；strict 缺 FINAL/缺 manifest/sha 不符/rev 倒退全部 ERROR；verify-render 改一字节默认 rc=0/ok:false，`--strict` rc=1。
- **G4 R08 负向覆盖**：每个硬门至少 1 个故意失败的用例，且测试里断言的是失败语义而非“打印了就算”。
- **G5 零越界**：默认只改 G1–G3 列出的文件；OpenRig 产品仓、模板正文、其它 runs、KB 正式域零新增改动；不覆盖 pre-existing dirty。
- **G6 证据**：每个 packet 在 `reports/evidence/PACKET/` 留下 changed-files、before/after sha256、命令、真实 rc、负向输出；QA 独立复跑全量 pytest + 至少 5 个负向用例 + scope/product 对比。

**反目标（明确不做）**：

- 不实现 P1/P2（R09–R14：CI、block audit、wrapper、lockfile、workflow engine invariants 等）。
- 不改 OpenRig 产品代码、产品 guard、模板正文、其它 run 目录。
- 不为了 `ok:true` 删除/放宽检查；不伪造 GateResult；不把 WARN 写成 PASS。
- 不 `git add -A`、不 commit、不 push、不设金额预算。
- 不删除任何既有文件或 pre-existing dirty 内容；不直改 OpenRig SQLite/queue 表。

## 2. 范围

### 2.1 范围内

- Packet A（R05/R06）、Packet B（R02/R03）、Packet C（R01/R04/R07）的实现与测试；R08 随三个包分布。
- 每个 packet 的 `reports/evidence/PACKET/` 证据。
- QA 的 `reports/QA-VERDICT.md` 与 close 的 `reports/FINAL.md`、`DECISIONS.md`/`STATUS-Round-1.md` 收口更新。

### 2.2 范围外

- R09–R14 与任何 P1/P2 能力。
- 产品仓 `/home/a7067567g/下载/deepseek/deepseek-项目/10-openrig-deepseek` 的任何写入；只允许只读调用其 `scripts/openrig-teardown.py` 作为 archive guard。
- `workflow-group/templates/**`、`roles/**`、`WORKFLOW.md` 正文、其它 `runs/**`。
- KB 正式知识区（`00-overview/` 等 8 个目录）。
- commit/push/tag、金额预算、永久删除。

### 2.3 假设与依赖

- 运行时：`workflow-group/.venv/bin/python` = Python 3.12.15；pytest 9.0.2；openpyxl 3.1.5 已安装（缺 openpyxl 的路径用 monkeypatch 模拟，不卸载环境）。
- `rig` CLI 与 `node` 可解析；`git` 可用；临时测试自建 git 仓库。
- archive guard 默认路径 `../deepseek-项目/10-openrig-deepseek/scripts/openrig-teardown.py`（相对 KB 仓库根），可用 `OPENRIG_TEARDOWN_GUARD` 覆盖；guard 只 dry-run。
- 仓库与产品仓在规划时均已 dirty：基线以 sha256 为准，不要求工作树干净，只要求“相对基线未新增预期外改动”。
- 本 run 的 `reports/evidence/00-baseline.txt` 已由启动阶段捕获：KB HEAD `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac`、status sha256 `eefbb03b…b7d4e5`、diff sha256 `1d81f1c0…3c6f9a0`。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据来源 | 采集方式 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | 全量 pytest | 未采集 | rc=0 | 待采集 | `reports/evidence/qa/full-pytest.txt` | `.venv/bin/python -m pytest tests -q` |
| M2 | 硬门负向覆盖 | 0 | 每个硬门 ≥1 负向用例 | 待采集 | 各 packet 负向日志 + QA 复跑 | pytest 选择器 + 手工命令 |
| M3 | preflight 语义 | `ok` 恒 true | 无上下文→ok:false/rc1；`--advisory`→ok:false/rc0 | 待采集 | `reports/evidence/impl_preflight_components/` | 三条 preflight 命令 |
| M4 | baseline 自噪声 | 无入口 | 改文件→rc1；run 内新增→rc0 | 待采集 | `reports/evidence/impl_baseline_evidence/` | 临时 git 仓库测试 |
| M5 | evidence_run 真 rc | 无入口 | exit 7→rc7；`false \| tail`→rc1 | 待采集 | `reports/evidence/impl_baseline_evidence/` | shell 负向用例 |
| M6 | archive-gate | 无入口 | partial→rc2；missing guard→rc3 | 待采集 | `reports/evidence/impl_close_archive_render/` | fake guard 测试 |
| M7 | close strict | 默认宽松 | 缺 FINAL/manifest/sha 不符/rev 倒退→ERROR | 待采集 | `reports/evidence/impl_close_archive_render/` | `--strict` 测试 |
| M8 | verify-render | 无入口 | 改字节→默认 rc0/ok:false；`--strict`→rc1；坏 manifest→rc2 | 待采集 | `reports/evidence/impl_close_archive_render/` | manifest 篡改测试 |
| M9 | 越界改动 | 产品仓 29 条 dirty | 产品仓与模板/其它 runs 零新增；本 run 外的新增改动为空 | 待采集 | `reports/evidence/qa/scope-diff.txt` | `git status`/sha256 对比规划基线 |

## 4. 分任务（Workstreams / Packet 边界）

> 硬规则：每个包只允许改下表列出的文件；不得顺手改“看着相关”的文件。`scripts/wf.py` 被 A/B/C 三包共用，因此 A→B→C 必须**串行单写者**，后一包开始前确认前一包已退出且未留半成品。

### 4.1 Packet A — R05/R06（执行体 TDO-OC）

| 动作 | 文件 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 新建 | `scripts/required_components.py` | 不存在 | `check_components(root)` 返回 `{id, group, required, ok, detail, install_hint}`；组 machine/control/openrig/runtime |
| 修改 | `scripts/openrig_preflight.py` | 193 行，`ok` 恒 true | 加 `--advisory`；输出 `ok/checks/reasons`；五项必查；注入后重读块 |
| 修改 | `scripts/issues.py` | import 后无条件构造 Side/Border/Alignment | 用 `if HAS_OPENPYXL` 保护或惰性函数；JSONL 降级保持 |
| 修改 | `scripts/wf.py` | doctor 无组件检查 | doctor 顶部接入 `check_components`；缺 openpyxl 不得 NoneType |
| 新建 | `tests/test_required_components.py` | 不存在 | 正常全 ok / 临时 root 缺模板 / monkeypatch 缺 openpyxl |
| 新建 | `tests/test_openrig_preflight.py` | 不存在 | 无上下文、advisory、无 block、注入后 ok、缺 docs |
| 修改 | `tests/test_issues.py` | 397 行 | 增加 `HAS_OPENPYXL=False` 导入 + `read_rows` JSONL |
| 修改 | `tests/test_wf.py` | 662 行 | 只加 doctor required-components 用例 |

- 禁止：触碰 `scripts/wf_close_lint.py`、`scripts/verify_render.py`、`scripts/evidence_run.sh` 及 Packet B/C 测试。
- 定向验收：`.venv/bin/python -m pytest tests/test_required_components.py tests/test_openrig_preflight.py tests/test_issues.py tests/test_wf.py -q`
- 证据目录：`reports/evidence/impl_preflight_components/`（changed-files、before/after sha256、targeted pytest 日志、负向命令输出）。

### 4.2 Packet B — R02/R03（执行体 TDO-OC）

| 动作 | 文件 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 修改 | `scripts/wf.py` | `new-run` 无 `.run-meta.json`；无 baseline 子命令 | 写 `.run-meta.json`；新增 `baseline` / `verify-baseline`；排除本 run 目录 |
| 新建 | `scripts/evidence_run.sh` | 不存在 | `pipefail`、真实 rc、`command/cwd/started_at/finished_at/rc/stdout_sha256/stderr_sha256`、stdout/stderr 原文；`chmod +x` |
| 新建 | `tests/test_wf_baseline.py` | 不存在 | 临时 git 仓库 + 临时 run；baseline→verify=0；改文件→1；run 内新增→0 |
| 新建 | `tests/test_evidence_run.py` | 不存在 | `exit 7`→rc7；`false \| tail`→rc1；hash 字段存在 |

- 禁止：触碰 Packet A 的 `required_components.py`/preflight/`issues.py` 逻辑，或 Packet C 的 close/archive/render 文件。
- 定向验收：`.venv/bin/python -m pytest tests/test_wf_baseline.py tests/test_evidence_run.py -q`
- 证据目录：`reports/evidence/impl_baseline_evidence/`。

### 4.3 Packet C — R01/R04/R07/R08（执行体 TDO-OC）

| 动作 | 文件 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 修改 | `scripts/wf.py` | 无 archive-gate / evidence-record | 新增两子命令；archive-gate 只 dry-run；evidence-record 写 closeout.json |
| 修改 | `scripts/wf_close_lint.py` | 884 行，无 `--strict` | 保留默认；新增 strict 四条检查 + revision 链 + REV 记录 |
| 新建 | `scripts/verify_render.py` | 不存在 | 读 `openrig/render-manifest.json`，重算 bytes/sha256；默认 WARN，`--strict` ERROR，坏 manifest rc=2 |
| 新建 | `tests/test_archive_gate.py` | 不存在 | fake guard complete/partial/missing；不得执行 marker 命令 |
| 修改 | `tests/test_wf_close_lint.py` | 460 行 | 增加 strict 缺 FINAL/manifest/sha/rev 用例；合法 manifest PASS |
| 新建 | `tests/test_verify_render.py` | 不存在 | 未改/改字节/strict/坏 manifest |
| 新建 | `tests/test_evidence_record.py` | 不存在 | 算 sha；二次 revision 保留 `replacesSha256` |

- archive-gate 判定表（补 TASK 未列的 guard rc=1）：guard rc=0→`ok:true`；guard rc=2→`ok:false` 且透传 `archiveStatus/missing`，gate rc=2；guard rc=1（manifest not found）→`ok:false` 透传 error，gate rc=2；guard 文件不存在→gate rc=3 且明确 guard missing。不得把 1 或 3 当通过。
- 禁止：触碰 Packet A/B 的 preflight/components/baseline/evidence_run 逻辑；不得执行 teardown。
- 定向验收：`.venv/bin/python -m pytest tests/test_archive_gate.py tests/test_wf_close_lint.py tests/test_verify_render.py tests/test_evidence_record.py -q`
- 证据目录：`reports/evidence/impl_close_archive_render/`。

### 4.4 QA（执行体 QA，独立复跑）

- 全量 `.venv/bin/python -m pytest tests -q`，记录 rc 与完整日志。
- 至少 5 个负向用例独立复跑（不得只读 TDO 日志）：preflight 无上下文、advisory、`false | tail`、archive partial、close strict 缺 FINAL、verify-render `--strict` 中任选 ≥5，覆盖 ≥4 个硬门。
- TASK §5 六条入口逐条跑，记录真实 rc；任何“预期 rc”与实际不符即为 FAIL。
- scope diff：`git status --porcelain` 相对 `00-baseline` 只允许出现本计划 §4 文件 + 本 run reports；产品仓 status/diff sha256 必须与规划基线一致。
- 产出：`reports/QA-VERDICT.md`（每条判据 PASS/WARN/FAIL/SKIP + 证据路径 + 命令 + rc）。FAIL 退回 `impl_close_archive_render`。

### 4.5 close_round（执行体 MAIN）

- 复核 QA 与证据；再跑全量 pytest 与 TASK §5 六条入口。
- 写 `reports/FINAL.md`、`reports/evidence/closeout.json`；更新 `DECISIONS.md`/`STATUS-Round-1.md`。
- 仅在 QA=PASS 或 PASS-WITH-WARN 且无假门时 exit done；不得声称 P1/P2 已实现。

## 5. 轮次计划与结论

### Round 1 计划

1. `plan`：本文件 + `reports/00-plan.md`，冻结包边界、命令、无产品变更规则。
2. `impl_preflight_components`：只做 Packet A，跑定向 pytest + 三条 preflight 命令，落证据，handoff。
3. `impl_baseline_evidence`：只做 Packet B，先确认 Packet A 已退出；跑定向 pytest + 两条 evidence_run 负向，落证据，handoff。
4. `impl_close_archive_render`：只做 Packet C，先确认 Packet B 已退出；跑定向 pytest + archive/close/render 负向，落证据，handoff。
5. `qa_final`：独立复跑全量 + ≥5 负向 + 六入口 + scope/product 对比，写 QA-VERDICT。
6. `close_round`：终检、FINAL、closeout manifest、DECISIONS/STATUS 收口。

本轮不做：P1/P2、产品改动、模板改动、其它 run 改动、commit/push。

### 验收命令（TASK §5，逐条记录真实 rc）

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/openrig_preflight.py --json --advisory
.venv/bin/python scripts/openrig_preflight.py --json --run-id openrig-p0-hard-constraints-20261116 \
  --workspace /home/a7067567g/下载/deepseek/deepseek-知识库 \
  --run-dir runs/openrig-p0-hard-constraints-20261116
.venv/bin/python scripts/wf.py baseline openrig-p0-hard-constraints-20261116 --json
.venv/bin/python scripts/wf.py verify-baseline openrig-p0-hard-constraints-20261116 --json
.venv/bin/python scripts/verify_render.py --run-dir runs/openrig-p0-hard-constraints-20261116 --json
```

补充定向命令：

```bash
.venv/bin/python -m pytest tests/test_required_components.py tests/test_openrig_preflight.py tests/test_issues.py tests/test_wf.py -q
.venv/bin/python -m pytest tests/test_wf_baseline.py tests/test_evidence_run.py -q
.venv/bin/python -m pytest tests/test_archive_gate.py tests/test_wf_close_lint.py tests/test_verify_render.py tests/test_evidence_record.py -q
.venv/bin/python scripts/wf.py doctor openrig-p0-hard-constraints-20261116 --json
.venv/bin/python scripts/wf_close_lint.py --run openrig-p0-hard-constraints-20261116 --strict --json
```

preflight 正例注入说明：TASK §5 要求用 `--workspace` 注入后再跑。KB 根 `AGENTS.md` 规划时尚无 `OPENRIG-PREFLIGHT` managed block；首次正例注入会改写 `AGENTS.md`，这是**唯一被 TASK §5 授权、但不在 §0 写白名单内的写入**。执行要求：
- 注入前记录 `AGENTS.md` sha256；只允许脚本写入 managed block，禁止手改其它内容；注入后记录新 sha256 并把该文件列入 QA scope 例外（仅此一处）。实际已发生：`629742bfb3306dae03805f868599f14afcd39311a12039a7d97b9810cc61a2a1` → `53eed071626762756e480913c1f1f3eb141f6fb0c96142b4b0950012353c8763`。
- 测试内的正例一律用 `tmp_path` 工作区，避免每个用例污染仓库。
- 若选择不注入仓库根，如实接受 `workspace_context` fail（rc=1），不得伪造 `ok:true`；QA 用临时工作区等价验证正例。

### 无产品变更规则（G5，硬门）

1. 只读对象：`/home/a7067567g/下载/deepseek/deepseek-项目/10-openrig-deepseek`（产品仓）、`workflow-group/templates/**`、`workflow-group/roles/**`、其它 `workflow-group/runs/**`。
2. 规划基线（本文件写定时采集）：产品仓 HEAD `e932ae94e4c07b619c39902f29db949464ebb295`、`status --porcelain` sha256 `3b64cf901a0c232fbbae7e5937111671a01be558c910ae09132756fe54b7e269`、`git diff` sha256 `dc564a37b301c610e7b451bf8eb401cea3baddb3b838bc8a7cc9c292d50e8172`、dirty 条目 29。
3. 每个 packet 结束与 QA/close 时重算三值；任一不同即 STOP：先定位新改动，只撤销“本次新增”的部分，绝不回滚 pre-existing dirty，然后在证据中记 `product-change-detected`。
4. 产品仓已有 29 条 dirty 属于用户既有工作，不算本轮违规；但本轮不得新增、不得覆盖、不得 `git checkout`/`restore`/`stash` 产品仓。
5. KB 侧以**启动基线** `reports/evidence/impl_baseline_evidence/00-baseline.startup.txt`（status `eefbb03b…` / diff `1d81f1c0…`）为“无越界”判据；`reports/evidence/00-baseline.{json,txt}` 是 Packet B 验收时重新捕获的点时刻快照（16:28:24Z，status `44cde8e4…` / diff `a11a6c1c…`），用途是 verify 的即时对照，不是启动基线。允许新增/修改仅限 §4 列出的 scripts/tests 文件、本 run reports，以及 §5.1 注明的 `AGENTS.md` managed-block 例外；其它新增改动一律视为越界。
6. `verify-baseline` 必须在**不重跑 `baseline`** 的前提下执行；详见 §5.3。不得把 rc=1 本身当失败，也不得把“rc=1 但没看 diff”当通过。

### 执行期事实与 QA 口径（MAIN，qa_final 前追加）

TDO 已按 A→B→C 完成实现并 handoff QA；以下事实影响判读，但不改变任何判据：

1. **baseline 是点时刻快照**：启动捕获（16:19:47Z）原样保存在 `reports/evidence/impl_baseline_evidence/00-baseline.startup.txt`；Packet B 验收时 `wf.py baseline` 重新捕获了 `reports/evidence/00-baseline.{json,txt}`（16:28:24Z）。这是命令既定语义，不是覆盖事故；两份都保留。
2. **QA verify-baseline 口径**：不得在 verify 前再次运行 `baseline`（那会重置快照，verify 必然 rc=0，等于自证）。用当前 post-B 快照直接跑 `verify-baseline`，预期 rc=1，`statusAdded` 恰为 Packet C 的 4 个新文件：`scripts/verify_render.py`、`tests/test_archive_gate.py`、`tests/test_evidence_record.py`、`tests/test_verify_render.py`；若出现其它路径即 FAIL。已 dirty/未跟踪文件的修改只体现在 `diffSha256`/`diffStat`，不会新增 status 行。“无越界”另用 `00-baseline.startup.txt` + 当前 `git status` 对照 §4 文件集合复核：相对启动快照，预期新增 10 个路径（A：`required_components.py`、`test_required_components.py`、`test_openrig_preflight.py`；B：`evidence_run.sh`、`test_wf_baseline.py`、`test_evidence_run.py`；C：上述 4 个），预期修改 `scripts/issues.py`、`scripts/wf.py`、`tests/test_issues.py`、`tests/test_wf.py`、`AGENTS.md`，以及 `scripts/openrig_preflight.py`、`scripts/wf_close_lint.py`、`tests/test_wf_close_lint.py` 的内容变化（这三个在启动快照中已是未跟踪文件，故不新增 status 行）。
3. **R07 live render drift = 预期 WARN**：`verify_render.py --run-dir runs/openrig-p0-hard-constraints-20261116` 对 `rig.yaml`、`workflow.yaml`、`guidance/team.md`、`OPENRIG-BRIDGE.json` 报 bytes mismatch，默认 rc=0/`ok:false`。语义核对：workflow 六步/依赖/loop_guards/closure 完整，rig 三 pod/seat/model 完整，bridge seatMap/runtimeEnv/policy 完整；`guidance/team.md` 是 run 特化文案（非模板原文），属 render 后写入。不得重渲染或重写 manifest 来“修绿”；FINAL 记 WARN，并把“manifest 与 run 特化 guidance 不同源”列为下轮候选（S3）。
4. **AGENTS.md 唯一例外已发生**：根 `AGENTS.md` 的 `OPENRIG-PREFLIGHT` managed block 已注入，sha256 `629742bf…` → `53eed071…`，符合 §5.1；QA scope 检查将其列为唯一例外，不得再有其它 `AGENTS.md` 改动。
5. **实现规模**：TDO 报告全量 pytest 259 passed；产品仓三值仍为 `e932ae94…`/`3b64cf90…`/`dc564a37…`、29 dirty。QA 必须独立复跑，不得直接采信。

### 证据目录

```text
runs/openrig-p0-hard-constraints-20261116/reports/
  00-plan.md
  evidence/
    00-baseline.txt                 # 启动阶段已捕获
    impl_preflight_components/      # changed-files.txt, sha256-before-after.txt, targeted-pytest.txt, negative-*.txt
    impl_baseline_evidence/
    impl_close_archive_render/
    qa/                             # full-pytest.txt, negative-cases.txt, six-entrypoints.txt, scope-diff.txt, product-baseline.txt
    closeout.json                   # close_round 的 closeout manifest
  QA-VERDICT.md
  FINAL.md
```

### Round 1 结论（close_round 填）

- 完成：R01–R07 六个硬门全部实现并由 QA 独立复跑；R08 每门 ≥1 真负向；全量 pytest 259 passed；六入口真实 rc 已记录；产品仓/scope 零新增越界。
- 未完成 / 阻塞：无阻塞。P1/P2（R09–R14）明确未实现；W2/W4 转下一轮 P1，W5 转下一轮 S3。
- 下轮候选：R04b（FINAL 路径统一）、W2（preflight 失败路径副作用）、W3（baseline 元数据）、W4（before-sha 取证）、W5（render manifest 同源）；P1 收口前不进入 P2。

## 6. PMO 上报区

- **本轮结论**：P0 交付完成，QA 判定 PASS-WITH-WARN，close_round 已复跑并收口；`reports/FINAL.md` 与根 `FINAL.md` 一致。
- **待拍板**：无。
- **指标变化**：M1 259 passed；M2 14 条负向/6 门；M3–M8 全部按预期 rc；M9 产品仓四值不变、scope 新增恰好 10 路径。
- **下一轮建议编制**：TDO×1 + QA×1（先做 P1 小包，不并行）。
- **风险提示**：W2 失败路径副作用虽 fail-closed 但会写文件；W5 live render drift 属预期 WARN，不得重写 manifest 修绿。

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| 2026-11-16 | R1 | 建档（启动渲染） | 主会话 |
| 2026-11-16 | R1 | 完成 §0–§5 计划：冻结包边界、验收命令、无产品变更规则 | MAIN（plan 包） |
| 2026-11-16 | R1 | TDO 完成 A/B/C；QA 判定 PASS-WITH-WARN（5 WARN）；MAIN 收口，PROJECT 置 closed | MAIN（close_round） |

## 8. 残余风险 / 承接

| 项 | 风险/承接内容 | owner | 去向 | 最晚复核轮 |
| --- | --- | --- | --- | --- |
| W2 | preflight 校验失败路径仍会注入 block/写 monitor | TDO | 下一轮 P1 实现：先校验后落盘 | R2 |
| W3 | 本 run 无 `.run-meta.json`，`baseline` 字面命令 rc=1 | TDO | 下一轮 P1：new-run 元数据回填或命令文档补参数 | R2 |
| W4 | Packet C 两个 pre-existing untracked 文件缺 before-sha256 | TDO | 下一轮 P1：`git hash-object`/快照取证 | R2 |
| W5 | render manifest 与 run 特化 guidance 不同源，live verify 恒 WARN | TDO | 下一轮 S3：manifest 同源化 | R2 |
| R04b | FINAL 路径双写（根 + reports） | MAIN | 下一轮统一约定，减少双写 | R2 |
