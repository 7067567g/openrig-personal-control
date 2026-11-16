# 00-plan — P2 closure（R13 / R14 / F-3 / F-5）

> 写者：MAIN（step `plan`）｜权威：`TASK.md` + `SPEC.md §9` + 本文件
> 本计划只定义包边界、接口与验收命令，不实现代码。`scripts/**`、`tests/**` 在 impl_p2 由 TDO 修改。

## 0. 目标与不做什么

| 项 | 内容 |
| --- | --- |
| 交付 | R13 只读 invariants probe；R14 `openrig-run next`；F-3 closeout 覆盖实际 FINAL；F-5 WORKFLOW-TAGS 旧计数 |
| 写范围 | `workflow-group/scripts/**`、`workflow-group/tests/**`、`workflow-group/WORKFLOW-TAGS.md`、本 run `reports/**` |
| 不写 | OpenRig 产品仓（`60-外部仓库/**`、`10-运行时/**`）、其它 run、KB 正式域、模板/角色 |
| 不做 | 不改 workflow engine、不加 `invariants.checks[]` 字段、不 `commit`/`push`、不启动/停止 daemon、不跑 live `rig up` |
| 硬门 | 全量 pytest 绿；`doc_consistency --check` rc=0；每个新门至少 1 条负向测试；产品仓零改动 |

## 1. 基线事实（plan 时刻实测）

| 事实 | 证据 |
| --- | --- |
| HEAD `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac`；大量 pre-existing dirty（含 `scripts/wf.py`、`tests/*`） | `reports/evidence/00-baseline.txt` |
| 全量 pytest：`310 passed in 7.82s` | 本次 `pytest tests -q` |
| `doc_consistency.py --check`：**rc=1**，`tags-count` 声明 canonical=62 ≠ 实测 63 | 本次复跑；`runs/` 下 63 个目录（含本 run） |
| `WORKFLOW-TAGS.md:6` 顶部声明 62；`WORKFLOW-TAGS.md:23` §1.1 表写 37；`:10` 文中也写 62 | `grep -n` |
| 不存在 `scripts/workflow_invariants_probe.py`；`openrig_run.py` 只有 `check`/`start` 两个子命令 | `ls scripts/`、`openrig_run.py:503-520` |
| `openrig_run.py` 已有 `_load_bridge()` / `BRIDGE_REL`，可复用于 `next` | `scripts/openrig_run.py:59-90` |
| `wf_close_lint.py` 已按 `reports/FINAL.md` 优先解析（`resolve_final`），但 closeout 只校验"条目自身路径"，不要求覆盖解析结果 | `scripts/wf_close_lint.py:781-790`、`:834-890` |
| 现有测试已覆盖：close lint `reports/` 优先、`next` 不存在 | `tests/test_wf_close_lint.py:584-608` |

**F-5 口径修正**：TASK 写"62"，但本 run 目录创建后实测为 **63**。F-5 采用"与实测一致"为准（顶部声明与 §1.1 表都写 63），并保留"以 `doc_consistency.py` 为准"的免责句。以硬编码 62 收口会让 `doc_consistency` 永久 rc=1。

## 2. Packet 边界与接口

### P1 — R13 只读 invariants probe（新文件）

**新增** `scripts/workflow_invariants_probe.py`（仅标准库；不 import `subprocess`）。

```
workflow_invariants_probe.py --run-dir <run-dir> [--workflow <path>] [--json]
```

- 默认路径 `<run-dir>/openrig/workflow.yaml`；`--workflow` 覆盖。
- 只读文本解析（无 PyYAML）。支持子集：
  - `steps:` 列表项 `- id: <name>`（引号可有）；
  - `depends_on:` 块列表（`- x`）或流式列表（`[a, b]`）；
  - `next_hop:` → `'on':`（或 `on:`）→ `failed: <target>`；
  - 空行、`#` 注释、`steps` 之外字段忽略。
- 输出 JSON：`{schemaVersion, runDir, workflow, ok, steps[], duplicateIds[], missingDependsOn[], missingNextHopTargets[], unreachable[], terminal[], problems[]}`。
  - `steps[] = {id, dependsOn[], nextHopFailed|null}`（保持文件顺序）。
- `ok=false`：重复 id；`depends_on` 指向不存在 id；`next_hop.failed` 指向不存在 id；**外加**解析不到任何 step（`problems:["no_steps"]`，理由见下）。
- `unreachable`、`terminal` 只进 WARN，不影响 `ok`。
- 可达性：以"无 `depends_on` 的 step"为根，沿 `depends_on` 反向边 + `next_hop.failed` 边 BFS；不可达者入 `unreachable`。
- `terminal`：无后继（无 step 依赖它，且自身无 `next_hop.failed`）。本 run 期望 `terminal=["close_round"]`。
- rc：`ok` → 0；`ok=false` → 1；run-dir/workflow 缺失或不可读 → 2。
- 不改 engine、不加 `invariants.checks[]`。

**测试** `tests/test_workflow_invariants_probe.py`（新增）：
1. 合法 DAG → `ok is True`、`terminal == ["close_round"]`、`unreachable == []`；
2. 重复 id → rc/ok false，`duplicateIds` 非空；
3. `depends_on` 指向不存在 step → `missingDependsOn` 非空；
4. `next_hop.failed` 指向不存在 step → `missingNextHopTargets` 非空；
5. unreachable step → 进 `unreachable` 但 `ok is True`；
6. 默认路径缺失 → rc=2；`--workflow` 覆盖生效；
7. **无 live 调用**：`monkeypatch` `subprocess.run`/`subprocess.Popen` 为爆炸桩，probe 全程不触发（断言调用计数 0）。

### P2 — R14 paved-road `next`（改 `scripts/openrig_run.py`）

新增子命令 `next`，只读、零执行：

```
openrig-run next --run-dir <run-dir> [--json]
```

- 读 `openrig/OPENRIG-BRIDGE.json`（复用 `_load_bridge`）；缺失/坏 JSON → rc=2，不构造命令、不 subprocess。
- 输出 canonical 5 步（字符串命令，按此顺序）：
  1. `openrig-run check --run-dir <run-dir>`
  2. `openrig-run start --run-dir <run-dir> --dry-run`
  3. `openrig-run start --run-dir <run-dir>`
  4. `verify_render.py --run-dir <run-dir> --strict`
  5. `wf.py archive-gate <runId>`（`runId` 取 bridge）
- JSON：`{schemaVersion, mode:"next", runDir, ok, steps[{order,id,command}], modeHints[], note}`；`modeHints` 打印 local-only vs hybrid 选择提示，不阻断。
- 非 JSON：编号行 + 提示。
- 不修改任何文件；不调用 daemon/`rig`。`ok` 恒为 `true`（有 bridge 即真），rc=0。

**测试**（追加到 `tests/test_openrig_run.py`）：
1. bridge 齐全 → 5 步顺序精确匹配、`ok is True`；
2. `monkeypatch subprocess.run` 桩 → `next` 不触发（含 `--json`）；
3. 缺 bridge → rc=2，输出无 steps；
4. `next` 不写任何文件（比对 run 目录文件清单/内容 hash 前后一致）。

### P3 — F-3 closeout 必须覆盖**实际解析**的 FINAL（改 `scripts/wf_close_lint.py`）

- `resolve_final()` 保持不变（`reports/FINAL.md` 优先）。
- `strict_findings` 中，解析出 `final` 后计算 `final_rel = final.relative_to(run_dir)`，要求 `entries[*].path` 中存在 `== final_rel` 的条目；否则新增 `ERROR closeout_resolved_final_missing`，message 指明"closeout 必须覆盖实际解析路径 `<final_rel>`"。
- 该规则对"两份 FINAL 同时存在但内容不同、只 attest 根文件"必然报错（`TASK §3` 的必测场景）；对"只有根 FINAL 且根即解析结果"和"reports 条目齐全"保持通过。
- 判定为更简更严的单一规则：**同一内容的两份 FINAL 也只认解析路径**（已在 QA 检查项里显式说明，避免被当隐性行为）。
- 其余逻辑（entry 字段、revision 链、hash/bytes、`closedAt`/mtime、revision 记录）不动；`final_after_closeout` 的 revision 覆盖集合仍含两个候选路径（TASK 要求"保持不变"）。

**测试**（追加到 `tests/test_wf_close_lint.py`）：
1. 双 FINAL 内容不同、closeout 只有根 entry → `closeout_resolved_final_missing`；
2. 双 FINAL 内容不同、closeout 含 `reports/FINAL.md` + 根 entry（P1 双 entry）→ 无 finding（PASS）；
3. 只有 `reports/FINAL.md` 且 entry 齐全 → PASS（回归既有）；
4. 只有根 `FINAL.md` 且 entry 为根 → PASS（回归既有）。

### P4 — F-5 WORKFLOW-TAGS 旧计数（改 `WORKFLOW-TAGS.md`）

- `:6` 顶部声明 `canonical=62` → `canonical=63`。
- `:10` 文中"2026-11-16 实测 62"→ 63（保留 31/37/55 历史）。
- `:23` §1.1 表 `37` → `63`，说明列补"2026-11-16 实测 63（含 openrig-p2-closure run）"。
- 只改与 canonical 计数相关数字，不重排标签矩阵；`baseline=9`、`specialized=26` 不动（实测已一致）。
- 验收：`doc_consistency.py --check` rc=0。

## 3. 顺序、所有权与锁

| 顺序 | seat | 动作 |
| --- | --- | --- |
| 1 | main | 本计划 + `PROJECT §0-§5`；不碰代码 |
| 2 | tdo-oc | 按 P1→P2→P3→P4 实现 + 全部测试；跑 §5 验收；写 STATUS 证据指针 |
| 3 | qa | 独立复跑 §5 + §4 负向矩阵；写 `reports/QA-VERDICT.md` |
| 4 | main | 对照 TASK 与 QA 裁决；写 FINAL/closeout；`workflow project --exit` |

- 单写者：同一时刻只有 impl_p2 的 TDO 写 `scripts/**`/`tests/**`；QA 只写自己的 verdict/issue。
- pre-existing dirty 不覆盖：TDO 只在目标文件做最小 diff，禁止 `git add -A`、禁止 `git checkout`/`restore` 别人改动。

## 4. QA 独立复跑矩阵（必须逐项给命令 + 退出码）

| # | 检查 | 期望 |
| --- | --- | --- |
| Q1 | `.venv/bin/python -m pytest tests -q` | rc=0，passed ≥ 310+新增 |
| Q2 | `.venv/bin/python scripts/doc_consistency.py --check` | rc=0 |
| Q3 | probe 对本 run | `ok=true`，`terminal=["close_round"]`，rc=0 |
| Q4 | probe 三个 broken 临时工作流（重复 id / 缺 dep / 缺 next_hop） | 每个 `ok=false`，rc=1 |
| Q5 | `openrig-run next --run-dir runs/openrig-p2-closure-20261116 --json` | 5 步顺序精确一致，rc=0 |
| Q6 | next 无 live：`subprocess` 桩测试 + 复跑后无 daemon 新进程/无 queue 变动 | 0 次调用 |
| Q7 | F-3 负向：双 FINAL 不同内容 + 只 attest 根 → ERROR | 出现 `closeout_resolved_final_missing` |
| Q8 | F-3 正向：双 entry → PASS | 无 finding |
| Q9 | `wf_close_lint.py --run openrig-p2-closure-20261116 --strict` | 在 FINAL/closeout 就位后 rc=0；就位前允许 `final_missing`/`closeout_missing`（如实记录） |
| Q10 | scope diff：`git status --porcelain` 新增改动仅落在 TASK §0 白名单 | 0 越界路径 |
| Q11 | 产品仓零改动：`git -C <OpenRig 产品仓> status --porcelain` 与基线一致 | 0 新增 |
| Q12 | 无 `commit`/`push`：`git log -1` 仍为基线 HEAD | 未变 |

## 5. 验收命令（TDO 与 QA 同一套）

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/doc_consistency.py --check
.venv/bin/python scripts/workflow_invariants_probe.py --run-dir runs/openrig-p2-closure-20261116 --json
.venv/bin/python scripts/openrig_run.py next --run-dir runs/openrig-p2-closure-20261116 --json
.venv/bin/python scripts/wf_close_lint.py --run openrig-p2-closure-20261116 --strict
```

## 6. 风险 / 已知判断

1. **F-5 数字**：TASK 写 62，实测 63。采用实测；若 QA 认为应保留 62，需要新增一个"排除本 run"的示例或改 `doc_consistency` 口径 —— 那是超范围，本轮不做。
2. **probe 的 `no_steps`**：TASK 的 `ok=false` 三项未列此项。计划加入为"结构性拒收"，防止空/坏文件被当合法；QA 可否决，否决则降级为 WARN + `problems`。
3. **F-3 更严**：内容相同的双 FINAL 也要求解析路径 entry；这是 TASK 语义的自然加强，已在上文写明，不是隐性行为。
4. **`wf_close_lint --strict` 在本轮 close 前必然非 0**（尚无 FINAL/closeout）。QA 阶段如实记录 `final_missing`，不作为 FAIL；close_round 补齐后再复跑。
5. **pre-existing dirty 面很大**（>150 文件）。scope 证明用"改动前基线 + 目标文件 diff"而不是"工作树干净"。

## 7. 完成定义

- P1–P4 全部落地且有对应负向测试；
- §5 五条命令在 close 后全 rc=0（pytest/doc_consistency/probe/next/close_lint）；
- QA verdict 为 PASS 或 PASS-WITH-WARN，warn 已具名；
- 产品仓零新增改动、无 commit/push；
- `reports/FINAL.md` + `reports/evidence/closeout.json` 覆盖实际 FINAL 路径。

## 8. 退出

计划完成，交 `impl_p2`（TDO-OC）。本步未改 `scripts/**`、`tests/**`。
