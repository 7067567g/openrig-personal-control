<!-- wf-doc
run: openrig-p1-hard-constraints-20261116
round: 1
doc: PROJECT
owner: MAIN
state: pmo-plan
updated: 2026-11-16
tags: template/openrig-workflow-master, baseline/two-plane-orchestration
primary_type: composite/two-plane-orchestration
maturity: M3
baseline: composite/two-plane-orchestration@1.0.0
contracts: strategy@1.0.0, research@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0
-->

# PROJECT — P1 hard constraints

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `openrig-p1-hard-constraints-20261116` |
| 目标 | 实施 W2/W3/W4/W5/R04b + R09/R10/R11/R12：副作用修复、meta/snapshot、CI docs 门、block 审计、openrig-run wrapper、render 特化、FINAL 路径兼容。 |
| 写范围 | workflow-group scripts/tests/docs/CI + 本 run reports |
| 只读 | OpenRig 产品仓、其它 runs |
| 编制 | MAIN×1 / TDO-OC×1 / QA×1；无 DSH |
| 工作流 | `plan → impl_preflight_evidence → impl_ci_blocks → impl_wrapper_boundary → impl_close_render → qa_final → close_round` |
| 终止判据 | 全量 pytest 绿；doc_consistency 绿；每个 gate 有负向测试；产品仓零改动；无 commit/push |

## 1. 判据

- **G1 W2/W3/W4**：失败 preflight 无副作用；meta-set 可回填；untracked 文件可快照。
- **G2 R09/R10**：docs 计数修正且 CI 接入；managed block 只读审计可输出/orphan strict。
- **G3 R11/R12**：openrig-run check 失败语义正确；dry-run 不执行；复制/生成边界写清。
- **G4 W5/R04b**：render 特化可记录/校验；close strict 兼容根与 reports FINAL。
- **G5 零越界**：产品仓零改动；AGENTS/target 副作用可恢复。
- **G6 证据**：每包命令/rc/hash 齐全；QA 独立复跑。

## 2. 范围

只做 P1；R13/R14（workflow engine invariants、paved-road prompt）不在本轮。

## 3. 指标

| # | 指标 | 目标 |
| --- | --- | --- |
| M1 | full pytest | rc=0 |
| M2 | doc_consistency | rc=0 |
| M3 | preflight invalid run | AGENTS/target 字节不变 |
| M4 | meta/snapshot | 旧 run 可回填；untracked before/after 可记录 |
| M5 | block audit | 2 blocks 可枚举；strict orphan rc1 |
| M6 | openrig-run check | ready→0；incomplete→1；daemon down→1 除非 allow |
| M7 | render specialization | exact→ok; stale→mismatch; strict exact→0 |
| M8 | close strict | reports/FINAL.md 与根 FINAL.md 均可 PASS |
| M9 | product scope | 产品仓 0 新增越界 |

## 4. 结论

待采集。

## 5. 分包与交接

严格线性单写者：`plan → A → B → C → D → qa_final → close_round`；任一时刻只有一名写者持有 `workflow-group` 文件。

| 包 | 步骤 / 执行体 | 交付 | 退出证据 |
| --- | --- | --- | --- |
| 计划 | `plan` / MAIN | `PROJECT.md` §0–§5、`reports/00-plan.md` | 本文件 + `00-plan.md` |
| A | `impl_preflight_evidence` / TDO-OC | W2 无副作用失败路径、W3 `meta-set`、W4 `snapshot_files.py` + 负向测试 | `reports/evidence/A/**` |
| B | `impl_ci_blocks` / TDO-OC | R09 canonical 计数 + CI 接线、R10 `audit_managed_blocks.py` + 测试 | `reports/evidence/B/**` |
| C | `impl_wrapper_boundary` / TDO-OC | R11 `openrig_run.py` check/start + fake-rig 测试、R12 复制/生成边界 | `reports/evidence/C/**` |
| D | `impl_close_render` / TDO-OC | W5 render specialization、R04b FINAL 双路径 + 测试 | `reports/evidence/D/**` |
| 验收 | `qa_final` / QA | 独立复跑 + `reports/QA-VERDICT.md` | QA 证据目录 |
| 收轮 | `close_round` / MAIN | `reports/FINAL.md`、closeout、DECISIONS/STATUS | closeout 证据 |

硬约束（全包一致）：

1. 只写 TASK §0 白名单；`workflow-group/README.md` **不在**白名单，R12 文案落 `templates/specialized/openrig-workflow-master/ENTRYPOINTS.md`。
2. `scripts/wf.py` 由 A、D 共用，必须串行；后包起手前确认前包已 handoff 且无半成品。
3. 不 commit/push/tag；不设金额预算；pre-existing dirty 只读。
4. 每个 gate 至少 1 个负向测试；失败路径不得留持久副作用（AGENTS.md、`target.json`、systemd 服务）。
5. 全量 pytest 基线 = 259 passed（rc=0，2026-11-15T16:49Z 实测）；收轮不得低于该数且必须 rc=0。

详细文件级边界、测试矩阵、证据清单与停止条件见 [`reports/00-plan.md`](reports/00-plan.md)。
