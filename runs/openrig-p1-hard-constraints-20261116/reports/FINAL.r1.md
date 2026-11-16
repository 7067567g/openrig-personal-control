# FINAL — P1 hard constraints（W2/W3/W4/W5/R04b + R09/R10/R11/R12）

> run: `openrig-p1-hard-constraints-20261116` ｜ 轮次：1 ｜ 收轮：MAIN（`close_round`）
> 权威：`TASK.md` > `SPEC.md` > `PROJECT.md`；QA 独立判定见 `reports/QA-VERDICT.md`。
> 结论：**PASS**（QA PASS + 4 条 S3 WARN + 1 条 S2 已由本收轮处置）。P2（R13/R14）**未实施**。

## 1. 交付结论

P1 六个工作包全部落地，每个硬门都有可失败路径与负向证据：

| 包 | 交付 | 判定 | 证据 |
| --- | --- | --- | --- |
| A | W2 preflight 失败路径零副作用；W3 `wf.py meta-set`；W4 `scripts/snapshot_files.py` | PASS | `reports/evidence/A/` |
| B | R09 `WORKFLOW-TAGS.md` canonical 55→62 + CI 接入；R10 `scripts/audit_managed_blocks.py` | PASS | `reports/evidence/B/` |
| C | R11 `scripts/openrig_run.py check/start` fail-closed；R12 复制/生成边界 | PASS | `reports/evidence/C/` |
| D | W5 render specialization 记录/校验；R04b close-lint 双 FINAL 路径 | PASS | `reports/evidence/D/` |
| QA | 独立复跑 + 20 条自建负向 + 六入口 + 零副作用核验 | PASS | `reports/QA-VERDICT.md` |

## 2. 验收判据（PROJECT §1）

| 判据 | 结果 | 证据 |
| --- | --- | --- |
| G1 W2/W3/W4 | PASS | `evidence/A/SUMMARY.md`、`negative-preflight-invalid-run.txt`、`negative-wf-baseline-legacy.txt` |
| G2 R09/R10 | PASS | `evidence/B/SUMMARY.md`、`negative-doc-count-55.txt`、`evidence/qa/negative-audit-strict.txt` |
| G3 R11/R12 | PASS | `evidence/C/SUMMARY.md`、`evidence/qa/negative-openrig-run.txt` |
| G4 W5/R04b | PASS | `evidence/D/SUMMARY.md`、`evidence/qa/negative-render-specialization.txt`、`negative-close-lint-dual-final.txt` |
| G5 零越界 | PASS | `evidence/qa/product-baseline.txt`、`evidence/qa/scope-diff.txt`、`evidence/qa/AGENTS-target-sideeffects.txt` |
| G6 证据 | PASS | `evidence/A|B|C|D/SUMMARY.md`、`evidence/qa/entrypoints.txt` |

## 3. 指标（PROJECT §3）

| # | 指标 | 实测 |
| --- | --- | --- |
| M1 | full pytest | **310 passed，rc=0**（规划基线 259，+51） |
| M2 | doc_consistency | rc=0，0 error / 0 warning（此前 rc=1） |
| M3 | preflight invalid run | rc=1；workspace `AGENTS.md` 字节不变；monitor `target.json` 未写；`systemctl` 调用 0 |
| M4 | meta/snapshot | legacy run 报错含 `meta-set` 与 `--project-root`；`meta-set` 后 baseline rc=0；untracked before/after 可区分 |
| M5 | block audit | 真实 `AGENTS.md` 7 块可枚举；无块 `summary=0`；orphan `--strict` rc=1 |
| M6 | openrig-run check | ready→0；incomplete→1；missing seat→1；daemon down→1；`--allow-daemon-down`→0；bridge 坏→2 |
| M7 | render specialization | exact→`ok:true`+`specialized:true`；stale→mismatch；`--strict`+exact→rc=0 |
| M8 | close strict | `reports/FINAL.md`、根 `FINAL.md`、两者并存均可 PASS；两者皆缺 ERROR；sha/revision 仍严格 |
| M9 | product scope | 产品仓 HEAD `e932ae9…`、status `3b64cf9…`、diff `2cbcef6…`，29 条 pre-existing dirty 未动 |

## 4. 环境陈述（SPEC §7 要求）

`.venv/bin/python 3.12.15`、`pytest 9.0.2`、`rig openrig-local 0.1.4 (1ee477a3)`、`node v24.22.1` 均可解析。
"全绿"仅指 pytest 310 rc=0 与 doc_consistency rc=0，不含未执行的 GitHub Actions 实跑。

## 5. live run 的 render 漂移与收轮处置（D-004）

`verify_render.py` 对 4 个文件报 mismatch：`rig.yaml`、`workflow.yaml`、`guidance/team.md`、`OPENRIG-BRIDGE.json`。
MAIN 复核确认：同参重渲染可逐字节复现 `render-manifest.json`，说明 manifest 未损坏；4 个文件在渲染后 26 秒
（00:47:58）被整体替换为 3-seat 线性形态（去 pmo/dsh、`maxActiveAgents` 2→1、`maxHops` 10→12），与 `SPEC.md` §9 一致；
p0 与 token-r1 两个历史 run 呈同构漂移。

处置：不重渲染（会改在跑 seat 图）；`close_round` 用 `wf.py render-specialize` 登记 4 条 exact 特化，
reason 明写"launch path 渲染后特化、close 补记、非渲染事件"；随后 `verify_render --strict` → **rc=0**，
四项 `specialized:true`（`reports/evidence/close/verify-render-strict.json`）。
因此本 run 的 render 绿灯是**已登记特化**的结果，不是 manifest 未漂移的证明。

## 6. 已知限制与未验证项

1. **A/B 无 before-hash**（D-006）：`workflow-group/scripts/**` 与多数 `tests/**` 在 KB 仓 untracked，A 起手前无副本；
   `00-baseline.txt` 是 A 编辑之后采集的**前向参考**，不得当作 A 的哈希级证明。A 的 scope 由 path-set 比较 +
   mtime 白名单扫描 + 逐文件 after sha 支撑；B 的 CI 文件有真实 before（HEAD blob `d84743bb…`）。
2. **CI 未实跑**：仅静态核对 YAML 步骤与依赖；本轮禁止 commit/push，也无远端授权。
3. **`openrig_run start` 非 dry-run 全链路未执行**：会起进程、改 live 状态，超出 QA 只读边界；只验证 dry-run 计划与 fake-rig 语义。
4. **`openrig_run check` 的 render 项为 WARN 而非 PASS**：live run 漂移按设计走 WARN，不阻塞。

## 7. QA 发现处置（`QA-VERDICT.md` §6）

| ID | 级别 | 处置 |
| --- | --- | --- |
| F-1 | S2 | **已关闭**：`STATUS-Round-1.md` 已补 6 条包级进度与交接段；`ISSUES.xlsx` 保持为空（本轮无开放缺陷工单），QA 发现以 `QA-VERDICT.md` + 证据目录留痕，见 D-008 |
| F-2 | S3 | 接受为限制，D-006 已记录；下一 round 起用 `snapshot_files.py` 取 before |
| F-3 | S3 | 记录不改：closeout 只按 entry 自身 `path` 校验；双 FINAL 内容不同时可能只 attest 根文件。属 R04b 后续收紧项 |
| F-4 | S3 | 记录：`--strict` 的 `ownerRig` 只认 `rig:<id>` 前缀，真实渲染块 7/7 orphan；默认关闭，接线前需先定命名空间 |
| F-5 | S4 | 记录：`WORKFLOW-TAGS.md` §1.1 表仍写 canonical=37，与顶部 62 不一致（validator 只校顶部）；下轮改表头指向 |
| F-6 | S4 | **已覆盖**：D-004 已在 `DECISIONS.md` 记录漂移处置，不只存在于 queue packet |

## 8. 后续票（不在本轮实施）

1. **launch path 应调用 `render-specialize`**：当前渲染后替换为 3-seat 形态却不登记，导致每个 run 永久 render mismatch。
2. **同 seat 后继步的 `closure_target`**：应写 successor qitem id 而非 session，避免 watchdog 观感歧义（watch-only，未复现误唤醒）。
3. **`templates/specialized/openrig-workflow-master/BASELINE-post.sha256` 陈旧**：`README.md`、`SPEC.md`（2026-10-23）与
   `ENTRYPOINTS.md`（R12）共 3 项 FAILED；刷新属版本升版，超出 TASK §0。
4. **`audit_managed_blocks.py --strict` 命名空间**：接线前先定 `ownerRig` 映射或前缀约定。
5. **R13/R14**：workflow engine invariants、paved-road prompt，本轮明确未做。

## 9. 证据索引

- 计划：`reports/00-plan.md`、`reports/CLOSE-CHECKLIST.md`
- 包证据：`reports/evidence/{A,B,C,D}/`
- QA：`reports/QA-VERDICT.md`、`reports/evidence/qa/`
- 收轮复跑：`reports/evidence/close/`（pytest、doc、preflight、audit、check、dry-run、verify-render pre/strict）
- MAIN 独立复核：`reports/evidence/main-verify-decisions.txt`、`reports/evidence/watchdog-false-positive-check.txt`
- 决策：`DECISIONS.md` D-001–D-009

## 10. 诚实声明

- 本轮**没有**实现 P2 / R13 / R14；**没有**修改 OpenRig 产品仓；**没有** commit/push/tag。
- A/B 的改动**不是**内容哈希级证明；其依据是路径集合、mtime 扫描与 after 哈希（D-006）。
- render 绿灯是**已登记特化**，不等于 manifest 与 live 文件一致。
- CI 接入**未被实跑验证**，只有静态核对与本地等价命令。
