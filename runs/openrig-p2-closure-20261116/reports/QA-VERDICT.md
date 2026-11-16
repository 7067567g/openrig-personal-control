<!-- wf-doc
run: openrig-p2-closure-20261116
round: 1
doc: QA-VERDICT
owner: QA
state: qa-verdict
updated: 2026-11-16
-->

# QA-VERDICT · Round 1 — P2 closure（R13 probe / R14 next / F-3 / F-5）

> 写者：QA（assurance-qa）｜ 独立复跑，不采信 TDO 日志结论
> 结论：**PASS-WITH-WARN**（P1–P4 功能判据 + 负向门 + 零越界全部通过；6 条 WARN 见 §5，无 FAIL）
> 建议返回：`close_round`（**不是** `impl_p2`）
> 进入 close 前须处置 1 条（R-001，S2，见 §7），不阻塞本步判据。

## 0. 复跑范围与证据

| 项 | 值 |
| --- | --- |
| 工作目录 | `/home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group` |
| 证据 | `reports/evidence/04-qa-rerun.txt`（Q1/Q2/Q3/Q5/Q9/verify_render/hash）、`reports/evidence/05-qa-negatives.txt`（QA 自建负向 + 无 live + 无写 + scope + 产品仓） |
| 被测对象 | 7 个文件的 sha256 与 `03-impl-acceptance.txt` 声明**逐一对齐**（`04-qa-rerun.txt` 末段），即我测的字节就是 TDO 交付的字节 |
| 判据来源 | `PROJECT.md §1 G1–G6`、`PROJECT.md §3 M1–M6`、`00-plan.md §4 Q1–Q12`、`TASK.md §1–§5` |
| 上游 | `STATUS-Round-1.md`（WS-1 完成条目 + 已知薄弱点 1–6） |

## 1. 判据对照（PROJECT §1 / §3）

| 判据 | 结果 | 证据 |
| --- | --- | --- |
| G1 R13 只读 probe 识别合法 DAG 与 broken refs，不调 live | **PASS** | 本 run `ok=true terminal=["close_round"] rc=0`；QA 自建 3 个 broken 临时工作流均 `ok=false rc=1`（`05-qa-negatives.txt` 行 dup/nodep/nonext）；爆炸桩证明 subprocess 调用 0 次、模块未 import subprocess |
| G2 R14 `openrig-run next` 输出 canonical 顺序、零执行 | **PASS** | 5 步顺序与 `TASK §2` 逐字一致；`rc=0`；爆炸桩 0 调用；run 目录树 sha256 前后一致；缺/坏 bridge 均 rc=2 |
| G3 F-3 closeout 必须覆盖实际解析 FINAL | **PASS** | QA 自建 7 例：双 FINAL 只 attest 根 → 唯一 `closeout_resolved_final_missing`（无 hash 噪声）；双 entry / 仅根 / 仅 reports 三种正例全 PASS；`resolve_final` 仍优先 `reports/FINAL.md` |
| G4 F-5 tags 三处一致且等于实测，doc_consistency rc=0 | **PASS** | `WORKFLOW-TAGS.md:6` / `:10` / `:23` 三处均 63 = `runs/` 实测 63；`doc_consistency --check` 0 error rc=0；**`scripts/doc_consistency.py` 未被改**（mtime 2026-11-11），即修在文档不在检查器 |
| G5 零越界（产品仓 0 改动、无 commit/push、pre-existing dirty 未被覆盖） | **PASS** | 产品仓 `60-外部仓库/openrig-upstream` status 0 行、HEAD `cd10746` 未变、近 2h 0 个新文件；KB HEAD 仍 `9fa8d27`；近 4h 改动仅白名单 7 文件 + kickoff（§2 Q10） |
| G6 每个新门 ≥1 真负向，QA 独立复跑 | **PASS** | 3 个门各≥1 负向；QA 用自己的 fixture 复跑，不依赖 TDO 测试文件（§3） |
| M1 full pytest | **PASS** | `329 passed rc=0`（基线 310 → +19：12 probe + 4 next + 3 close_lint） |
| M2 doc_consistency | **PASS** | rc=0 |
| M3 probe 正/负 | **PASS** | §3 |
| M4 next 顺序 / 0 subprocess | **PASS** | §3 |
| M5 F-3 双 FINAL 只 attest 根 → ERROR | **PASS** | §3 |
| M6 产品仓 0 新增改动 / HEAD 不变 | **PASS** | 见 G5 |

## 2. QA 独立复跑矩阵（00-plan §4 Q1–Q12）

| # | 检查 | 命令 | rc | 实测 |
| --- | --- | --- | --- | --- |
| Q1 | 全量 pytest | `.venv/bin/python -m pytest tests -q` | 0 | `329 passed in 7.44s` |
| Q2 | doc_consistency | `.venv/bin/python scripts/doc_consistency.py --check` | 0 | `0 error(s), 0 warning(s)` |
| Q3 | probe 对本 run | `... workflow_invariants_probe.py --run-dir runs/openrig-p2-closure-20261116 --json` | 0 | `ok=true`、`steps=[plan, impl_p2, qa_final, close_round]`、`terminal=["close_round"]`、`unreachable=[]`、`problems=[]` |
| Q4 | probe 三个 broken | QA fixture `/tmp/opencode/qa-p2/wf-{dup,nodep,nonext}.yaml`（`--workflow` 覆盖） | 1/1/1 | `duplicateIds=['a']` / `missingDependsOn=['ghost']` / `missingNextHopTargets=['nowhere']` |
| Q5 | next 本 run | `... openrig_run.py next --run-dir runs/openrig-p2-closure-20261116 --json` | 0 | 5 步 = check → start --dry-run → start → verify_render --strict → wf.py archive-gate，`ok=true` |
| Q6 | next 无 live / 无写 | 爆炸桩（subprocess.run/Popen/os.system）+ run 目录树 sha256 前后 | 0 | `live_calls={run:0,popen:0,system:0}`；`NO_CHANGE`；坏 bridge rc=2 时不构造命令 |
| Q7 | F-3 负向 | QA fixture A：双 FINAL 不同内容、只 attest 根 | — | 唯一 finding = `closeout_resolved_final_missing`（无 `closeout_hash_mismatch`） |
| Q8 | F-3 正向 | QA fixture B：双 entry；C：仅根；D：仅 reports | — | 三者 findings 均为 `[]` |
| Q9 | 本 run close_lint（close 前） | `... wf_close_lint.py --run openrig-p2-closure-20261116 --strict` | 1 | 仅 `final_missing` + `closeout_missing`，与 `00-plan §6.4` 一致；F-3 新规则未误报。**不是 FAIL** |
| Q10 | scope diff | 近 4h 文件 mtime 扫描 + 与 `00-baseline.txt` 状态清单 diff | — | 白名单 7 个改动文件（`scripts/openrig_run.py`、`scripts/wf_close_lint.py`、`scripts/workflow_invariants_probe.py`、`tests/test_openrig_run.py`、`tests/test_wf_close_lint.py`、`tests/test_workflow_invariants_probe.py`、`WORKFLOW-TAGS.md`）+ kickoff 记录；0 越界代码改动（但见 W5/W6 两条基线口径问题） |
| Q11 | 产品仓零改动 | `git -C ../../60-外部仓库/openrig-upstream status --porcelain \| wc -l` | 0 | 0 行；HEAD `cd1074651c83…` |
| Q12 | 无 commit/push | `git -C .. log -1` / 分支 / stash | — | HEAD 仍 `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac`；仅 `main` 分支；无 stash |

## 3. 负向矩阵（全部 QA 自建，不复用 TDO 测试）

`workflow_invariants_probe.py --run-dir /tmp/opencode/qa-p2 --workflow <fixture>`：

| fixture | 期望 | 实测 |
| --- | --- | --- |
| `good`（链式 + flow-list + next_hop 回边） | ok / rc0 | `ok=true rc=0`（注：`terminal=[]`，因末端 step 带 `next_hop.failed`，符合 plan 定义，见 §6-R3） |
| `dup` 重复 id | ok=false / rc1 | `duplicateIds=['a'] problems=['duplicate_id:a']` |
| `nodep` 缺依赖目标 | ok=false / rc1 | `missingDependsOn=['ghost']`，`b` 进 `unreachable` |
| `nonext` 缺 next_hop 目标 | ok=false / rc1 | `missingNextHopTargets=['nowhere']` |
| `unreach` 孤儿节点 | ok=true + WARN | `ok=true`，`unreachable=['orphan']` |
| `empty` 无 steps | ok=false / rc1 | `problems=['no_steps']`（契约差异见 §6-R2） |
| `crlf` CRLF 行尾 | 不误判 | `missingDependsOn=['ghost']` 正确 |
| `quoted` 引号 / 变体缩进 | 不误判 | 正确解析 |
| `inline`（`next_hop: {on: {failed: nowhere}}`） | — | **`ok=true`（静默漏检）→ W3** |
| `flowonly`（`- {id: a}`） | — | **`ok=true`，`steps=[{id:null},{id:null}]` → W3** |
| `comment`（`- id: a   # root step`） | — | **`ok=false`，id 把注释吃进去 → W4** |

`rc=2` 路径：probe 缺 run-dir / 缺 workflow 均 rc=2；`next` 缺 bridge / 坏 JSON 均 rc=2。
F-3 单独矩阵见 `05-qa-negatives.txt`（A–G 七例）。
无 live 调用：`subprocess.run=<爆炸桩>` 下 `next`/`probe` 均正常返回，调用计数全 0。

## 4. 独立性与我**未**验证的部分

- 我复跑的是当前磁盘字节（与交付声明 sha256 一致），不是 TDO 的日志。
- `resolve_final` / revision / mtime 逻辑**无法做字节级 before/after 对比**：`scripts/wf_close_lint.py` 属 pre-existing untracked，基线与现状都不在 git 里，TDO 只留了 before-sha256。我用「行为验证 + 代码阅读」代替：A–G 七例、既有 revision/mtime 测试全绿、`final_after_closeout` 的候选集合仍含两个 FINAL 路径。
- 未跑任何 live 步骤（不 `rig up`、不起 daemon、不跑 paved-road 第 2/3/5 步）；R14 的验收范围本来就是"只打印"。
- 未穷举 YAML 写法（W3/W4 已给出已知漏检面）。

## 5. WARN（不阻塞本步判据，须在 close/FINAL 记录）

| ID | 级别 | 内容 | 归属 |
| --- | --- | --- | --- |
| **R-001** | S2 风险 | 本 run `verify_render --strict` 仍 rc=1：4 个 `openrig/*` 文件 bytes 与 `render-manifest.json` 不符且无 `render-specializations.json`。文件 mtime 08:40:13 早于 impl_p2（08:44:45），**非本步改动**；但 next 打印的第 4 步在本 run 会失败。 | **D-004 已裁决本 run 不修**；owner=下一次实例化 |
| **R-002** | S3 风险 | probe 对**未解析**的写法静默 PASS（`- {id: a}` 全 flow-map、inline `next_hop`），可对含缺失引用的 workflow 返回 `ok=true` —— 与"no fake PASS"约束冲突。渲染器当前只产出 block 写法，故对本 run 对象无实际误判。 | TDO（下轮 fail-closed） |
| **P-001** | S4 问题 | probe 不剥离行内 `#` 注释，`- id: a   # root step` 使合法 workflow 假报 `missing_depends_on`。 | TDO（下轮） |
| **C-001** | S3 变更 | kickoff 08:40:22 的 guidance 投影改写了 **KB 仓被跟踪的根 `AGENTS.md`**（+380 行，含本 run P2 guidance 与他 rig 的 `main-approver`/`tdo-b` 块），不在 `PROJECT §0` 写范围。 | 主会话（需拍板） |
| **P-002** | S4 问题 | `00-baseline.txt` 状态清单不可复现：漏了 pre-existing 未跟踪的 `workflow-group/workflow-tags.json`（birth 2026-10-23、ctime 2026-11-11、无脚本引用，**非 impl_p2 引入**）。故 Q10 只能靠清单 diff 证明，`status_sha256` 复算不等。 | 主会话（下次 baseline 用显式可复现命令） |
| **C-002** | S4 变更 | probe 的 `ok=false` 条件比 `TASK §1` 多一条 `no_steps`；QA **裁决保留**（结构门应 fail-closed），需回写契约文本。 | TDO/主会话（文档同步） |

> R-001 的处置以 **D-004** 为准：本 run 不碰 `openrig/**`（`render-specialize` 会写 `openrig/render-specializations.json`，同样越出 `TASK §0`），也不重写 `render-manifest.json`（D-004 选项 C 已拒绝）。FINAL 如实记"paved-road 第 4 步在本 run fail-closed"，修复留给下一次实例化用统一 renderer 重生成 run 包。
> **close_round 动作**：D-004 生效后请以 `issues.py close <xlsx> R-001 --decision D-004` 关闭该行（否则 `wf.py doctor` 会因"未关闭 S1/S2"再报 1 WARN，见 §9）。

## 6. 对三个已声明判断点的裁决

- **R1（F-5 数字 62 vs 63）**：接受 63。TASK 写 62 是 run 目录创建前的旧值；以 `doc_consistency.py` + `runs/` 实测为准，且检查器未改。若硬编码 62，`doc_consistency` 会永久 rc=1。
- **R2（`no_steps` 是否算 ok=false）**：**保留**。结构门对空/坏文件必须 fail-closed；登记 C-002 让契约文本同步，不降级为 WARN。
- **R3（`terminal` 语义）**：实现与 `00-plan §2 P1` 定义一致（无后继**且**自身无 `next_hop.failed`），因此"末端 step 带失败回边"的链会得到 `terminal=[]`。这是"无失败回边"的语义，不是"最后一步"；只进 WARN，不影响 `ok`。无需修，但下轮文档应改名或加注，避免误读。

## 7. 结论与 close_round 前置

P1–P4 四个包都落地且有可复跑的负向；全量 329 passed、doc_consistency rc0、probe/next rc0、F-3 正负例符合预期；产品仓零改动、无 commit/push、scope 无越界代码改动。
**判定 PASS-WITH-WARN，返回 `close_round`。**

进入 close 的硬性前置（按顺序，否则会踩 revision/mtime 或 F-3）：

1. 先写 `reports/FINAL.md`（本 run 不写根级 `FINAL.md` 也可，但 closeout 必须覆盖 `reports/FINAL.md`）；
2. 用 `wf.py evidence-record` 记录证据，确保 `closedAt` **晚于** FINAL.md 写入（否则 `final_after_closeout`）；
3. `reports/evidence/closeout.json` 的 `entries[]` 必须含 `path: "reports/FINAL.md"`（新 F-3 规则；只 attest 根级会 `closeout_resolved_final_missing`）；
4. `wf_close_lint.py --run openrig-p2-closure-20261116 --strict` 必须 rc=0；
5. **R-001 不修**（D-004 生效）：本 run 不碰 `openrig/**`；FINAL 如实写"paved-road 第 4 步 `verify_render --strict` 在本 run fail-closed（rc=1，4 个特化文件）"，owner 为下一次实例化。若要让 doctor 的"未关闭 S1/S2"清零，主会话用 `--decision D-004` 关闭该 ISSUES 行；
6. FINAL 必须如实写：R13 是只读 probe、未改 workflow engine、未加 `invariants.checks[]`；R14 是纯打印、未执行任何 live 命令；本 run 未实现 R09–R12 之外的任何东西。
7. `ISSUES.xlsx` 本轮新增 6 行（R-001/R-002/P-001/P-002/C-001/C-002），close 前不得静默关闭；主会话需对 C-001（AGENTS.md）拍板，其余按 §8 的状态处理。

## 8. 逐项状态（PASS / WARN / FAIL / SKIP）

> 口径：PASS=我独立复跑并且结果符合判据；WARN=符合预期但需具名记录；FAIL=判据不成立；SKIP=明确不在本步范围。

| 项 | 状态 | 命令 | 退出码 / 关键输出 |
| --- | --- | --- | --- |
| Q1 全量 pytest | **PASS** | `.venv/bin/python -m pytest tests -q` | rc=0，`329 passed` |
| Q2 doc_consistency | **PASS** | `.venv/bin/python scripts/doc_consistency.py --check` | rc=0，`0 error(s), 0 warning(s)` |
| Q3 probe 合法 DAG（本 run） | **PASS** | `... workflow_invariants_probe.py --run-dir runs/openrig-p2-closure-20261116 --json` | rc=0，`ok=true`，`terminal=["close_round"]`，`terminal` 之外全空 |
| Q4 probe 三个 broken | **PASS** | 同上 `--workflow /tmp/opencode/qa-p2/wf-{dup,nodep,nonext}.yaml` | rc=1/1/1，分别命中 `duplicateIds` / `missingDependsOn` / `missingNextHopTargets` |
| Q5 next 5 步顺序 | **PASS** | `... openrig_run.py next --run-dir runs/openrig-p2-closure-20261116 --json` | rc=0，5 步与 TASK §2 逐字一致 |
| Q6 next 零 subprocess / 零写 | **PASS** | 爆炸桩 + run 目录树 sha256 前后对比 | `live_calls={run:0,popen:0,system:0}`；目录树 `NO_CHANGE` |
| Q7 F-3 负向（双 FINAL 不同 + 只 attest 根） | **PASS** | QA fixture A（import `wf_close_lint`） | 唯一 finding `closeout_resolved_final_missing` |
| Q8 F-3 正向（双 entry / 仅根 / 仅 reports） | **PASS** | QA fixture B/C/D | 三者 findings 均为 `[]` |
| Q9 本 run `close_lint --strict`（close 前） | **WARN** | `... wf_close_lint.py --run openrig-p2-closure-20261116 --strict` | rc=1，`errors=2`：仅 `final_missing` + `closeout_missing`。**按主会话口径：不当 done 通过、不当缺陷 FAIL**；FINAL/closeout 属 close_round |
| Q10 scope diff（mtime + 清单 diff） | **PASS** | `find … -newermt '-4 hours'` + `diff` 对 `00-baseline.txt` | 7 个白名单文件 + kickoff；0 越界代码改动 |
| Q11 产品仓零改动 | **PASS** | `git -C ../../60-外部仓库/openrig-upstream status --porcelain \| wc -l` | 0；HEAD `cd1074651c83…` |
| Q12 无 commit/push、HEAD 不变 | **PASS** | `git -C .. log -1`、`git branch`、`git stash list` | HEAD `9fa8d27a95db…`；仅 `main`；无 stash |
| verify_render --strict（paved-road 第 4 步） | **WARN** | `... verify_render.py --run-dir runs/openrig-p2-closure-20261116 --strict` | rc=1，`mismatches=4 specialized=0`；由 D-004 裁决本 run 不修（R-001） |
| `wf.py doctor`（本 run） | **WARN** | `.venv/bin/python scripts/wf.py doctor openrig-p2-closure-20261116` | rc=0，`errors=0 warns=2`：`PROJECT.md: owner=MAIN 应为 PMO`（D-005 接受）+ `还有 1 条未关闭的 S1/S2`（即 R-001，D-004 后应 close） |
| 系统 `python3` doctor | **SKIP** | `python3 scripts/wf.py doctor …`（D-006） | rc=1，`required-components: machine.openpyxl` 缺 openpyxl；环境事实，不作门禁 |
| live 起 rig / 跑 paved-road 第 2、3、5 步 | **SKIP** | — | TASK §2 明确 R14 只打印；`rig up`/daemon 起停不在本步范围 |

## 9. 对 D-004 / D-005 的独立裁决（不继承结论）

**D-004（render-manifest 漂移：记录不重修）— 接受，附 1 条具名后果。**
- 事实核对一致：4 文件磁盘 bytes 1168/2421/390/974 vs manifest 2060/3997/653/1199；mtime 均 08:40:13（manifest 08:40:00）；impl_p2 期间未变（我的 4h mtime 扫描里它们只出现在白名单 7 文件之外，属实例化产物）。
- 选项 C（重写 manifest 反向签收）拒绝正确；选项 A（`render_master.py --force`）会写 `openrig/**`，越出 `TASK §0`，也正确拒绝。
- 补充：`render-specialize` 同样写 `openrig/render-specializations.json`，**同样越界**，所以本 run 也不采用 —— 我最初给 R-001 写的修法在本 run 无效，以 D-004 为准。
- 具名后果：R14 printed road 第 4 步在任何"有 run 特化"的 run 上都会 rc=1。这不是本步缺陷，但意味着该 printed road 目前不可原样执行；下一轮应在**实例化阶段**生成 specialization 记录（或在 road 里把该步标成"可选/需先 specialize"）。

**D-005（无 PMO，`PROJECT owner=MAIN` 接受 1 个 doctor WARN）— 接受，附 1 条事实更新。**
- 独立复跑：`.venv/bin/python scripts/wf.py doctor …` → `errors=0`，`warns` 含 `PROJECT.md: owner=MAIN 应为 PMO`，与 D-005 一致。
- 事实更新：**现在是 warns=2**。第二条是`还有 1 条未关闭的 S1/S2`，由本轮新增的 R-001（S2）引入，与 D-005 无关。D-004 生效后应 `issues.py close R-001 --decision D-004`，doctor 才会回到 warns=1。
- 我同意"不改 owner 字段"（字段要与事实一致）；但建议在 SPEC §9 里预先声明"3-seat run 的 PROJECT owner=MAIN 例外"，否则每个同型 run 都要重新解释同一 WARN。

**D-006（验收解释器统一 `.venv/bin/python`）— 接受并已遵守。**
- 独立复跑：系统 `python3 scripts/wf.py doctor …` → rc=1（`machine.openpyxl` 缺依赖）；`.venv/bin/python` → rc=0。本 verdict 与全部证据里的命令均为 `.venv/bin/python`。

**C-001 机制补充（不作为裁决，只界定归属）**：改写 `AGENTS.md` 的时间是 08:40:22，处于实例化（08:40:13）之后、impl_p2（08:44:45）之前，因此不是 TDO 手改。`workflow-group/AGENTS.md` 记载的启动前置是 `openrig_preflight.py --workspace <seat 工作区>` 会把 preflight/guidance 注入工作区 `AGENTS.md`；P0 run 的 QA W2 已记录同一类副作用（并称其为 TASK §5 授权的唯一例外）。本 run 的 `TASK.md` 没有这条授权，`PROJECT §0` 写范围也不含仓根 `AGENTS.md` —— 所以登记为 C-001 由主会话拍板；我不自行恢复（恢复到 git HEAD 会连带删掉他 rig 留下的块，风险更大）。
