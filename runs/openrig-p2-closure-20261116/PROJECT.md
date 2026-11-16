<!-- wf-doc
run: openrig-p2-closure-20261116
round: 1
doc: PROJECT
owner: MAIN
state: closed
updated: 2026-11-16
tags: template/openrig-workflow-master, baseline/two-plane-orchestration
primary_type: composite/two-plane-orchestration
maturity: M3
baseline: composite/two-plane-orchestration@1.0.0
contracts: strategy@1.0.0, research@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0
-->

# PROJECT — P2 closure

> 本 run 无 PMO seat（编制 3：main / tdo-oc / qa）。`plan` step 由 workflow instance 分配给 main，因此 §0-§5 的计划正文由 MAIN 按本 run 实例化契约填写；计划细节的权威副本是 `reports/00-plan.md`。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `openrig-p2-closure-20261116` |
| 目标 | R13 只读 invariants probe；R14 paved-road next；F-3 closeout 实际 FINAL；F-5 WORKFLOW-TAGS 旧计数。 |
| 写范围 | `workflow-group/scripts/**`、`workflow-group/tests/**`、`workflow-group/WORKFLOW-TAGS.md`、本 run `reports/**` |
| 只读 | OpenRig 产品仓、其它 runs、KB 正式域、模板/角色 |
| 编制 | MAIN×1 / TDO-OC×1 / QA×1；无 DSH、无 PMO、无 SAFETY |
| 工作流 | `plan → impl_p2 → qa_final → close_round`（workflow instance `01M7GWRH62K4J8FT9C5ZPX5Y0G`） |
| 终止判据 | 全量 pytest 绿；doc_consistency 绿；F-3/F-5 有负向测试；产品仓零改动；无 commit/push |
| 基线 | HEAD `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac`；pytest 310 passed；doc_consistency rc=1（tags-count 62≠63） |

## 1. 判据

- **G1 R13**：只读 probe 能识别合法 DAG 与 broken refs；不调用 live。
- **G2 R14**：`openrig-run next` 输出 canonical 顺序，零执行。
- **G3 F-3**：closeout 必须覆盖**实际解析**的 FINAL 路径；双 FINAL 不同内容只 attest 根 → ERROR。
- **G4 F-5**：WORKFLOW-TAGS 顶部声明、§0 文中、§1.1 表三处 canonical 计数一致且等于实测；doc_consistency rc0。
- **G5 零越界**：产品仓零改动；无 commit/push；pre-existing dirty 不被覆盖。
- **G6 负向**：每个新门至少 1 条负向测试，且 QA 独立复跑。

## 2. 工作包与范围

| 包 | 动作 | 文件 | 明确不做 |
| --- | --- | --- | --- |
| P1 | R13 只读 invariants probe | 新增 `scripts/workflow_invariants_probe.py`；新增 `tests/test_workflow_invariants_probe.py` | 不改 engine、不加 `invariants.checks[]`、不引入 PyYAML |
| P2 | R14 paved-road `next` | 改 `scripts/openrig_run.py`；追加 `tests/test_openrig_run.py` | 不执行命令、不起 daemon、不写文件 |
| P3 | F-3 closeout 实际 FINAL | 改 `scripts/wf_close_lint.py`；追加 `tests/test_wf_close_lint.py` | 不动 `resolve_final`、revision/mtime 逻辑 |
| P4 | F-5 tags 旧计数 | 改 `WORKFLOW-TAGS.md` 三处 canonical 数字 | 不重排标签矩阵、不改 baseline/specialized 计数 |

P1 接口：`workflow_invariants_probe.py --run-dir runs/openrig-p2-closure-20261116 [--workflow PATH] [--json]`（任意 run 目录同理），输出 `steps/duplicateIds/missingDependsOn/missingNextHopTargets/unreachable/terminal/problems/ok`；rc 0/1/2。
P2 接口：`openrig-run next --run-dir runs/openrig-p2-closure-20261116 [--json]`（任意 run 目录同理），5 步 `check → start --dry-run → start → verify_render --strict → wf.py archive-gate`；缺 bridge rc=2。
P3 接口：新增 ERROR `closeout_resolved_final_missing`；`reports/FINAL.md` 优先解析不变。
P4 接口：`canonical=63`（实测含本 run）；顶部/§0/§1.1 一致。

## 3. 指标

| # | 指标 | 目标 |
| --- | --- | --- |
| M1 | full pytest | rc=0，≥ 310 passed |
| M2 | doc_consistency | rc=0 |
| M3 | invariants probe | 合法 ok；三类 broken refs 均 ok=false |
| M4 | openrig-run next | 5 步顺序精确；subprocess 0 调用 |
| M5 | closeout F-3 | 双 FINAL 不同内容 + 只 attest 根 → ERROR |
| M6 | product scope | 0 新增产品仓改动；HEAD 不变 |

## 4. 结论

计划完成，未改代码。待 impl_p2 落地后由 QA 复跑 `reports/00-plan.md §4` 的 Q1–Q12。

## 5. 证据

| 证据 | 路径 |
| --- | --- |
| 计划全文（包边界/测试/验收命令/QA 矩阵） | `reports/00-plan.md` |
| 改动前基线（HEAD/status/diff hash） | `reports/evidence/00-baseline.txt` |
| 计划时刻复跑（pytest/doc_consistency/文件存在性） | `reports/evidence/01-plan-probe.txt` |

## 6. 残余风险与承接

| 项 | owner | 去向 | 最晚复核轮 |
| --- | --- | --- | --- |
| R-001（S2）`verify_render --strict` rc=1，`next` 第 4 步在本 run 失败（D-008 接受不修） | 下一次实例化入口（统一 renderer） | 下一 run 的 P3 入口用 `render_master.py`/`render-specialize` 统一登记特化；若用户要求本 run step 4 变绿，需先显式扩写范围 | R2 |
| R-002 / P-001（probe 未解析写法静默 PASS、行内注释假报） | 下一轮 TDO | probe 解析器补 flow-map/inline `next_hop` 与行内 `#` 剥离，并加负向 | R2 |
| P-002（baseline 清单不可复现） | 下一轮 MAIN | `wf.py baseline` 用全量 `git status --porcelain` + 未跟踪清单，输出可复算 digest | R2 |
| C-001（kickoff 把 guidance 注入写进根 `AGENTS.md`） | kickoff/preflight 维护者 | 注入只写 seat 工作区副本，不写项目仓被跟踪文件；加一条回归检查 | R2 |
| C-002（probe `no_steps` 契约差异） | 文档维护 | TASK/plan 契约文本补 `no_steps` 为 `ok=false` 条件 | R2 |
| D-006（系统 python3 缺 openpyxl） | 环境维护 | 统一走 `.venv`；若 CI 用系统解释器需先装 requirements-dev | R2 |
| D-005（本 run 无 PMO，PROJECT owner=MAIN） | run 模板 | 3-seat 特化在 SPEC 预声明 owner 例外 | R2 |

