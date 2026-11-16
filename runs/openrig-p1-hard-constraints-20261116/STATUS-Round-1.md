<!-- wf-doc
run: openrig-p1-hard-constraints-20261116
round: 1
doc: STATUS
owner: TDO
state: qa-pending
updated: 2026-11-16
-->

# STATUS · Round 1 — openrig-p1-hard-constraints-20261116

> 写者：TDO（持锁者，轮值）｜ 主会话按流程不读本文件正文 ｜ QA 在 S3 读
> **锁协议**：写入前 `python3 scripts/wf.py lock openrig-p1-hard-constraints-20261116 --agent 你的名字`；一次只追加一条；提交后 `unlock`。
> 推荐直接用 `append-status`（自动完成加锁→追加→提交→解锁）。
> **游离项指针**：发现无 WS 归属/无 owner/无去向的已知事项，在「交接给 QA」区写一句话 + 证据路径（不复制正文），由 PMO 在 S4 按收口规则处理。

## 进度条目

<!-- wf:progress:start -->
| 时间 | 执行体 | WS | 动作 | 产出/证据 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 2026-11-16 01:05 | MAIN | plan | 写 PROJECT §0–§5 与 reports/00-plan.md；定义 A–D 包边界、测试矩阵、无产品变更规则与停止条件 | reports/00-plan.md; reports/evidence/00-baseline.txt | 完成 |
| 2026-11-16 01:05 | TDO-OC | A | W2/W3/W4：preflight 无副作用失败路径 + wf.py meta-set + snapshot_files.py 及负向测试 | reports/evidence/A/SUMMARY.md | 完成 |
| 2026-11-16 01:05 | TDO-OC | B | R09/R10：canonical 55→62、CI 接入 doc_consistency、audit_managed_blocks 只读审计 | reports/evidence/B/SUMMARY.md | 完成 |
| 2026-11-16 01:05 | TDO-OC | C | R11/R12：openrig_run check/start fail-closed + fake-rig 测试、复制/生成边界写清 | reports/evidence/C/SUMMARY.md | 完成 |
| 2026-11-16 01:05 | TDO-OC | D | W5/R04b：render specialization 记录与校验、close-lint 双 FINAL 路径 | reports/evidence/D/SUMMARY.md | 完成 |
| 2026-11-16 01:05 | QA | qa_final | 独立复跑：310 pytest、doc rc0、20 条负向、六入口、产品仓/AGENTS/target 零副作用；r2 判 PASS（0 FAIL；5 发现 = 1 S2 + 3 S3 + 1 S4；另 2 条已裁决 WARN + 1 条 SKIP），F-1 由 D-008 关闭 | reports/QA-VERDICT.md; reports/evidence/qa/ | 完成 |
<!-- wf:progress:end -->

## 阻塞

<!-- wf:blockers:start -->
| ID | 描述 | 阻塞谁 | 需要什么 | 提出时间 | 状态 |
| --- | --- | --- | --- | --- | --- |
<!-- wf:blockers:end -->

## 交接给 QA

> TDO 在全部完成后填写（否则 QA 无法起手）。
> 并发提醒：每名 TDO 只写自己 WS 的小节（`- **WS-n（执行体）**：`），不覆盖他人段。

- **完成定义对照**（对照 PROJECT §4 验收判据逐条）：
<!-- wf:handoff-ws:start -->
  - **WS-1（A/B/C/D + QA）**：G1–G6 全 PASS —— G1 `reports/evidence/A/`；G2 `reports/evidence/B/`；G3 `reports/evidence/C/`；G4 `reports/evidence/D/`；G5 `reports/evidence/qa/product-baseline.txt` + `scope-diff.txt`；G6 `reports/QA-VERDICT.md` §1/§8。
<!-- wf:handoff-ws:end -->
- **自检命令与结果**：`pytest tests -q` → 310 passed rc0；`doc_consistency.py --check` → rc0；`verify_render.py --json` → rc0/`ok:false`（4 处 manifest 漂移，收轮登记特化前）；`wf_close_lint --strict` → rc1（`final_missing`+`closeout_missing`，收轮前预期）。逐条见 `reports/evidence/qa/entrypoints.txt`。
- **已知薄弱点 / 未验证项**：A/B 的 before-hash 未采集（untracked，D-006）；live run 4 处 render 漂移收轮登记为特化（D-004）；CI 仅静态核对未实跑；`openrig_run start` 非 dry-run 全链路未在真实 daemon 上执行。

## 收轮

- **QA 判定**：PASS（r2 定稿：0 FAIL；5 条发现 = 1 S2 + 3 S3 + 1 S4，S2 已由本收轮关闭；另有 2 条已裁决 WARN + 1 条声明限制 SKIP），见 `reports/QA-VERDICT.md`（sha `df7588116c45…`）。
- **MAIN 收轮**：`reports/FINAL.md`、根 `FINAL.md`、`reports/evidence/closeout.json`（24 条）、`wf_close_lint --strict` rc=0。
- **状态位说明**：本文件 state 停在 `qa-pending`。`qa-done` 只能由 QA 角色签（`wf.py state … STATUS qa-done --by QA`），MAIN 不代签；QA 的 PASS 事实以上方判定与 `QA-VERDICT.md` 为准。

<!-- wf:handoff:start -->
<!-- wf:handoff:end -->
