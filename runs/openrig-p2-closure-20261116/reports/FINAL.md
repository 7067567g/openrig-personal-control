# FINAL — P2 closure（R13 / R14 / F-3 / F-5）

> run：`openrig-p2-closure-20261116`｜轮次：R1｜状态：**PASS-WITH-WARN（已接受）**｜关闭判据：G1–G6 达成
> 写者：MAIN（close_round）｜QA 结论：`reports/QA-VERDICT.md` = PASS-WITH-WARN
> HEAD 未变：`9fa8d27a95dba40c9f324f91497bc6754aa4b9ac`（无 commit、无 push）

## 1. 交付内容

| 包 | 交付 | 位置 |
| --- | --- | --- |
| P1 / R13 | 只读 invariants probe（标准库文本解析，无 PyYAML、无 subprocess） | `scripts/workflow_invariants_probe.py`；`tests/test_workflow_invariants_probe.py`（12 tests） |
| P2 / R14 | `openrig-run next`：打印 canonical 5 步 + local-only/hybrid 提示，零执行 | `scripts/openrig_run.py`；`tests/test_openrig_run.py`（+5 tests） |
| P3 / F-3 | closeout 必须覆盖 `resolve_final()` 实际路径，新增 ERROR `closeout_resolved_final_missing` | `scripts/wf_close_lint.py`；`tests/test_wf_close_lint.py`（+3 tests） |
| P4 / F-5 | `WORKFLOW-TAGS.md` 三处 canonical 计数 62 → **63**（实测含本 run） | `WORKFLOW-TAGS.md:6`、`:10`、`:23` |

**明确未做**：未改 workflow engine；未新增 `invariants.checks[]` 字段；未执行任何 live 命令（无 `rig up`、无 daemon、无 `workflow instantiate`）；未改 OpenRig 产品代码；未 `commit`/`push`。

## 2. 验收结果（`.venv/bin/python` 口径，D-006）

| 检查 | 结果 |
| --- | --- |
| 全量 pytest | **329 passed**（基线 310，+19） |
| `doc_consistency.py --check` | **0 error rc=0**（`checks` 未改，修在文档） |
| probe 本 run | `ok=true`、`steps=[plan, impl_p2, qa_final, close_round]`、`terminal=["close_round"]`、`problems=[]`、rc=0 |
| probe 负向 | 重复 id / 缺 `depends_on` / 缺 `next_hop.failed` → 均 `ok=false` rc=1（QA 自建 fixture 复跑） |
| `openrig-run next` | 5 步顺序精确一致、rc=0；subprocess 爆炸桩 0 调用、run 目录 sha256 前后一致；缺/坏 bridge rc=2 |
| F-3 负向 | 双 FINAL 内容不同 + 只 attest 根 → 唯一 finding `closeout_resolved_final_missing` |
| F-3 正向 | 双 entry / 仅根 / 仅 reports 三例 `findings=[]` |
| `wf_close_lint --strict` | **rc=0**（见 §6 closeout） |
| 产品仓 | `60-外部仓库/openrig-upstream` status 0 行、HEAD `cd10746` 未变；`60-外部仓库/openrig` 0 新文件 |
| scope | 代码/测试改动仅 6 文件 + `WORKFLOW-TAGS.md`，全部在 TASK §0 白名单 |

## 3. 与原任务的显式偏差（均为有意，已记录）

1. **F-5 数字用 63 而非 TASK 写的 62**：62 是 run 目录创建前的旧值；本 run 目录存在后 `runs/` 实测 63。硬编码 62 会让 `doc_consistency` 永久 rc=1。QA 裁决（QA-VERDICT §6-R1）接受 63。
2. **probe 的 `ok=false` 多一条 `no_steps`**：TASK §1 未列。结构门对空/坏文件必须 fail-closed；QA 裁决保留（§6-R2），并要求契约文本同步（C-002）。
3. **`terminal` 语义**：`terminal` = 无后继**且**自身无 `next_hop.failed`，不是"最后一步"。末端带失败回边的链会得到 `terminal=[]`；只进 WARN（QA §6-R3）。
4. **F-3 比 TASK 更严**：内容相同的双 FINAL 也要求"解析路径必须有 entry"。

## 4. 接受的风险（FINAL 如实记录，不掩盖）

| ID | 内容 | 处置 |
| --- | --- | --- |
| **R-001 (S2)** | 本 run `verify_render --strict` rc=1：`rig.yaml` 1168/2060、`workflow.yaml` 2421/3997、`guidance/team.md` 390/653、`OPENRIG-BRIDGE.json` 974/1199 字节与 `render-manifest.json` 不符；manifest 是母版通用渲染口径，磁盘是本 run 的 4 步 3-seat 特化 | **D-008：接受、不修**。TASK §0 写范围不含 `runs/<run>/openrig/**`；不重写 manifest（P0 W5 先例）。**后果：`openrig-run next` 第 4 步在本 run 会失败，这是 fail-closed 的正确表现，不是本 run 的 PASS 项。** owner：下一次实例化统一 renderer |
| **D-005** | `PROJECT.md owner=MAIN 应为 PMO`（doctor warns=1） | 本 run 无 PMO（SPEC §9 = 3 seats），如实保留 |
| **D-006** | 系统 `python3` 缺 `openpyxl`，`wf.py doctor` 在系统解释器下 FAIL | 验收统一 `.venv/bin/python`；不改机器环境 |
| **D-011** | 收口初判"并发外部写入"经复核为误判：`scripts/wf.py`/`wf-validate.yml` 的 mtime 分别为 00:59 / 00:54，**早于本 run（08:40）**，属 pre-existing dirty | 已在 D-011 更正；不追查、不回滚、不 commit |
| **P-002** | `00-baseline.txt` 状态清单不可完全复现（漏 pre-existing 未跟踪 `workflow-tags.json`） | 下一轮 baseline 用显式可复现命令 |

**R13/R14 的边界必须被准确理解**：R13 是只读探测，不是引擎不变量实现；R14 是打印铺好的路，不执行。二者都不证明任何运行中的 rig 行为正确。

## 5. 越界事件与恢复

- **C-001**：kickoff `08:40:22` 的 guidance 投影向**被跟踪的**根 `AGENTS.md` 追加 380 行（0 删除），且含另一 rig 的 `main-approver`/`tdo-b` 块。按 **D-007** 恢复 HEAD：
  - 改前 sha256 `77fe8aa9…a60a5e`（备份在 `reports/evidence/agts/AGENTS.md.pre-revert`）；
  - 改后 sha256 `45960c4b…7bf4` = HEAD blob，`git status --porcelain AGENTS.md` 为空；
  - 恢复后 `git diff` 的 `M` 集合 = 基线集合 − `AGENTS.md`，无新增越界路径。
- 缺陷根因在 kickoff/preflight 的 guidance 注入路径（把 seat guidance 写进了项目仓根 `AGENTS.md`），不在本 run 产出；owner 已登记（D-009 C-001）。

## 6. 收口证据

- `reports/evidence/closeout.json`：`entries[]` 覆盖 `reports/FINAL.md`（F-3 新规则要求的解析路径）及关键证据文件，自动记录 bytes/sha256/rc。
- `reports/evidence/00-baseline.txt`、`01-plan-probe.txt`、`02-main-rerun.txt`（MAIN）、`03-impl-acceptance.txt`（TDO）、`04-qa-rerun.txt`、`05-qa-negatives.txt`（QA）。
- `wf_close_lint.py --run openrig-p2-closure-20261116 --strict` → rc=0；`wf.py doctor` → PASS（errors=0，warns=1 = D-005）。

## 7. ISSUES 处置（6 行，全部有 owner + 去向）

R-001 已决议（D-008 接受不修）；C-001 已处置（D-007 恢复）；C-002 保留 fail-closed 语义并同步契约文本；R-002 / P-001 / P-002 延期，owner 与轮次见 D-009。授权 QA 按 D-010 更新行状态与关联决策 ID。

## 8. 结论

P2 收尾达成：R13 只读 probe、R14 paved-road next、F-3 实际 FINAL 覆盖、F-5 tags 计数一致，均有独立可复跑的负向测试；产品仓零改动、无 commit/push。剩余项全部具名、有 owner、有去向，其中 R-001 是**接受**而非**修复**——本 run 的 `openrig-run next` 第 4 步会如实失败。
