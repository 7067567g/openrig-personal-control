<!-- wf-doc
run: openrig-p0-hard-constraints-20261116
round: 1
doc: QA-VERDICT
owner: QA
state: qa-verdict
updated: 2026-11-16
-->

# QA-VERDICT · Round 1 — P0 hard-constraint stack（R01–R07 + R08）

> 写者：QA（assurance-qa）｜ 独立复跑，不采信 TDO 日志结论
> 结论：**PASS-WITH-WARN**（功能硬门全部通过；5 条 WARN 见 §5，无 FAIL）
> 返回：`close_round`（不是 `impl_close_archive_render`）

## 0. 复跑范围与证据

| 项 | 值 |
| --- | --- |
| 工作目录 | `/home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group` |
| 证据根 | `runs/openrig-p0-hard-constraints-20261116/reports/evidence/qa/` |
| 全量 pytest | `.venv/bin/python -m pytest tests -q -p no:cacheprovider` → **rc=0，259 passed**（`qa/full-pytest.txt`） |
| 六入口 | 逐条真实 rc 见 `qa/six-entrypoints.txt` |
| 负向用例 | 14 条，覆盖 R01/R03/R04/R05/R06/R07，见 `qa/negative-cases.txt` |
| scope | `qa/scope-diff.txt`（相对启动快照新增恰好 10 个路径、0 删除、0 状态位变化） |
| 产品仓 | `qa/product-baseline.txt`（HEAD/status/diff/dirty 四值完全一致） |
| 文件完整性 | 17 个实现文件当前 sha256 与 packet `after_sha256` 逐一对齐（`qa/current-sha256.txt`） |

QA 自己的副作用（AGENTS.md managed block、monitor target.json、baseline 快照）已在
`qa/qa-self-side-effects.md` 记录，并全部恢复到操作前状态（含逐字节 `cmp`/sha256 证明）。

## 1. 目标判据（PROJECT §1 G1–G6）

| 判据 | 结果 | 证据 |
| --- | --- | --- |
| G1 R05/R06 preflight + components + issues 降级 + doctor | **PASS** | `preflight-advisory-empty.txt`(ok:false/rc0)、`neg-preflight-no-context.txt`(ok:false/rc1)、`preflight-positive.txt`(ok:true/rc0)、`neg-required-components-empty-root.json`(rc1、8 个 required 失败、8/8 带 install_hint)、`neg-issues-no-openpyxl-jsonl-fallback.txt`(HAS_OPENPYXL=False 仍 import 成功并读 JSONL)、`doctor.txt`(errors=[], required-components ok) |
| G2 R02/R03 baseline/verify-baseline/evidence_run | **PASS** | `verify-baseline-final.txt`(rc1、statusAdded 恰为 4 个 Packet C 文件、statusRemoved=[])、`neg-evidence-run-exit7.txt`(rc=7)、`neg-evidence-run-pipefail.txt`(rc=1)、`baseline-with-project-root.txt`(rc0) |
| G3 R01/R04/R07 archive-gate / close strict / verify-render | **PASS** | `neg-archive-gate-partial.txt`(gate rc2 + missing 透传)、`neg-archive-gate-missing-guard.txt`(rc3)、`fake-archive-gate-complete.txt`(rc0/ok:true)、`neg-close-strict-empty-run.json`、`neg-close-strict-sha-mismatch.txt`、`neg-close-strict-rev-chain.txt`、`pos-close-strict-good-run.txt`(PASS)、`neg-verify-render-*`(rc1/rc0/rc2 三态)、`pos-verify-render-clean.txt`(ok:true) |
| G4 R08 每硬门 ≥1 真负向 | **PASS** | 14 条负向，均断言失败语义；pytest 断言原文见 `tests/test_openrig_preflight.py:62-116`、`tests/test_archive_gate.py:59-98`、`tests/test_wf_close_lint.py:511-570`、`tests/test_verify_render.py:54-98`、`tests/test_wf_baseline.py:59-119` |
| G5 零越界 | **PASS** | `scope-diff.txt`：新增 10 路径（与 MAIN 预期完全一致），0 删除；产品仓四值一致；templates/roles/其它 runs 无改动 |
| G6 证据 | **PASS-WITH-WARN** | 每包 changed-files/命令/真实 rc/负向输出齐全；WARN：Packet C 两个文件缺 before-sha256（§5 W4） |

## 2. 指标（PROJECT §3 M1–M9）

| # | 指标 | 目标 | 实测 | 结果 |
| --- | --- | --- | --- | --- |
| M1 | 全量 pytest | rc=0 | rc=0，259 passed | PASS |
| M2 | 硬门负向覆盖 | 每门 ≥1 | 14 条 / 6 个门 | PASS |
| M3 | preflight 语义 | 无上下文 ok:false/rc1；advisory ok:false/rc0 | 实测一致 | PASS |
| M4 | baseline 自噪声 | 改文件→rc1；run 内新增→rc0 | verify rc1 且只列 4 个计划内文件；QA 在 run 内写入 50+ 证据文件后 statusAdded 仍只有那 4 个 | PASS |
| M5 | evidence_run 真 rc | exit7→7；`false \| tail`→1 | 7 / 1 | PASS |
| M6 | archive-gate | partial→2；missing→3 | 2 / 3 | PASS |
| M7 | close strict | 缺 FINAL/manifest/sha 不符/rev 倒退→ERROR | 4 类 ERROR 全部实测；合法 manifest→PASS | PASS |
| M8 | verify-render | 默认 rc0/ok:false；strict rc1；坏 manifest rc2 | 实测一致（cleanish 副本 ok:true/rc0） | PASS |
| M9 | 越界改动 | 产品仓与模板/其它 runs 零新增 | 产品仓四值一致；scope 新增 10 路径全在计划内 | PASS |

## 3. TASK §5 六条入口（真实 rc）

| # | 命令（缩写） | rc | 说明 |
| --- | --- | --- | --- |
| 1 | `pytest tests -q` | 0 | 259 passed |
| 2 | `openrig_preflight.py --json --advisory` | 0 | `ok:false`（未伪造 ok） |
| 3 | `openrig_preflight.py --json --run-id … --workspace KB --run-dir …` | 0 | `ok:true`，5/5 required 通过；KB `AGENTS.md` sha256 前后不变 |
| 4 | `wf.py baseline <run> --json` | 1 | 缺 `.run-meta.json` → 明确要求 `--project-root`；加该参数后 rc=0（W3） |
| 5 | `wf.py verify-baseline <run> --json` | 1 | 漂移检测正确：恰好 4 个 Packet C 文件；未见 QA 证据文件（run 目录排除生效） |
| 6 | `verify_render.py --run-dir … --json` | 0 | `ok:false` 的 live drift WARN（W5），`--strict` 同输入 rc=1 |

## 4. 独立scope与产品仓核对

- 相对启动快照 `impl_baseline_evidence/00-baseline.startup.txt`：新增 **10** 个路径
  （A：`required_components.py`/`test_required_components.py`/`test_openrig_preflight.py`；
  B：`evidence_run.sh`/`test_wf_baseline.py`/`test_evidence_run.py`；
  C：`verify_render.py`/`test_archive_gate.py`/`test_evidence_record.py`/`test_verify_render.py`），
  删除 **0**，同路径状态位变化 **0**。
- 内容有变化但状态行不变的：`scripts/issues.py`、`scripts/wf.py`、`tests/test_issues.py`、
  `tests/test_wf.py`、根 `AGENTS.md`（TASK §5 授权例外，
  `629742bf… → 53eed071…`），以及启动时已是未跟踪的 `openrig_preflight.py`/`wf_close_lint.py`/
  `test_wf_close_lint.py`。均落在 PROJECT §4 的包边界内。
- 产品仓 `/home/a7067567g/下载/deepseek/deepseek-项目/10-openrig-deepseek`：
  HEAD `e932ae94e4c07b619c39902f29db949464ebb295`、
  status sha256 `3b64cf90…`、diff sha256 `dc564a37…`、dirty 29 —— 与规划基线完全一致。
- 当前 17 个实现/测试文件 sha256 与三份 `changed-files.txt` 的 `after_sha256` 全部一致，
  说明证据记录之后代码没有再被改动。

## 5. WARN（不阻塞功能判据，但必须在 close/FINAL 记录）

- **W1 — FINAL.md 路径约定不一致（close 前必须处理）**
  `wf_close_lint.py:795` 只认 `run_dir/FINAL.md`，而 PROJECT §4.5 要求写 `reports/FINAL.md`；
  仓库现有 5 个 run 全部是 `reports/FINAL.md`，没有一个是根级 `FINAL.md`。
  实测：只放 `reports/FINAL.md` → `final_missing`；补一个根级 `FINAL.md` 但晚于 `closedAt`
  → `final_after_closeout`；按“先写根级 FINAL.md、再 `evidence-record`、最后 lint”顺序 → PASS
  （`qa/evidence-record-e2e-demo.txt`、`qa/pos-close-strict-good-run.txt`）。
  建议：close_round 同时写根级 `FINAL.md`（内容与 `reports/FINAL.md` 一致）并在写入后
  `evidence-record`；不要放宽 strict 检查。
- **W2 — preflight 在“校验失败”时也会先写文件**
  `openrig_preflight.py:257` 先注入、`:261` 才校验。用错误/不存在 run-id 调用 `--workspace`
  会把工作区 AGENTS.md 的 managed block 改写成该 run-id，并改写监控 `target.json`、启动
  `yueyue-monitor.service`；随后才返回 rc=1。门是 fail-closed 的，但失败路径有持久副作用。
  建议后续把注入推迟到 `run_context`/`run_docs` 通过之后（或先写临时文件、校验后再落盘）。
  本次 QA 已恢复被影响的两个文件（见 `qa/qa-self-side-effects.md`）。
- **W3 — TASK §5 的 baseline 命令对本 run 不可直接运行**
  本 run 无 `.run-meta.json`（启动时由模板直接建目录），字面命令 rc=1；加 `--project-root`
  后 rc=0。语义符合 TASK §3.1，但文档命令不完整，close 复跑时须带参数。
- **W4 — Packet C 证据缺 2 个 before-sha256**
  `impl_close_archive_render/changed-files.txt` 中 `scripts/wf_close_lint.py` 与
  `tests/test_wf_close_lint.py` 记为 “n/a (pre-existing untracked, no snapshot)”，不满足
  PROJECT G6 “before/after sha256”。文件本身无异常（after 与当前一致），建议下轮补
  `git hash-object` 或先复制快照的 before 记录。
- **W5 — live render drift（预期 WARN）**
  `verify_render.py` 对 `rig.yaml`、`workflow.yaml`、`guidance/team.md`、`OPENRIG-BRIDGE.json`
  报 bytes mismatch，默认 rc=0/`ok:false`。与 PROJECT §5.3 注 3 一致，属 render 后写入的 run
  特化内容，**不得**为重跑重写 manifest 来“修绿”；FINAL 记 WARN，并把
  “manifest 与 run 特化 guidance 不同源”列为下轮候选。

## 6. 明确不作为问题的事项

- `verify-baseline` rc=1 且 `statusAdded` 恰为 Packet C 的 4 个新文件：这是**正确的漂移检测**，
  因为快照捕获于 Packet C 之前；PROJECT §5.3 已把该判读写死。
- KB 根 `AGENTS.md` 被 preflight 注入改写：TASK §5 明确授权的唯一例外，sha 已记录且此后未再变。
- 监控 `target.json` 在 Packet A 的改写：`openrig_preflight.py` 既有 monitor 注册行为，
  Packet A 证据已声明。

## 7. 结论

R01–R07 六个硬门全部具备可失败、可复跑的机器门，R08 每个门都有真负向测试；全量 259 passed；
产品仓与 scope 无越界。**判定 PASS-WITH-WARN**，可进入 `close_round`。

进入 close 的硬性前置（来自 W1）：

1. 写 `reports/FINAL.md` 与根级 `FINAL.md`（内容一致）；
2. 用 `wf.py evidence-record` 记录证据并确保 `closedAt` 晚于 FINAL.md 写入；
3. `wf_close_lint.py --run openrig-p0-hard-constraints-20261116 --strict` 必须 rc=0；
4. close 后重跑全量 pytest 与 TASK §5（baseline 那条带 `--project-root`）。

不得声称 R09–R14（P1/P2）已实现；本轮未实现。
