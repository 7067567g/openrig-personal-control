<!-- wf-doc
run: openrig-p0-hard-constraints-20261116
round: 1
doc: STATUS
owner: TDO
state: closed
updated: 2026-11-16
-->

# STATUS · Round 1 — openrig-p0-hard-constraints-20261116

> 写者：TDO（持锁者，轮值）｜ 主会话按流程不读本文件正文 ｜ QA 在 S3 读
> **锁协议**：写入前 `python3 scripts/wf.py lock openrig-p0-hard-constraints-20261116 --agent 你的名字`；一次只追加一条；提交后 `unlock`。
> 推荐直接用 `append-status`（自动完成加锁→追加→提交→解锁）。
> **游离项指针**：发现无 WS 归属/无 owner/无去向的已知事项，在「交接给 QA」区写一句话 + 证据路径（不复制正文），由 PMO 在 S4 按收口规则处理。
> 本文件由 close_round 汇总本轮各步骤后收口；细节以 `reports/` 与 OpenRig queue/transcript 为准。

## 进度条目

<!-- wf:progress:start -->
| 时间 | 执行体 | WS | 动作 | 产出/证据 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 2026-11-16 | MAIN | WS-1 | 写 PROJECT §0–§5 与执行计划，冻结包边界/命令/无产品变更规则 | reports/00-plan.md | 完成 |
| 2026-11-16 | TDO-OC | WS-2 | R05/R06：preflight 真检查、required_components、issues 降级、doctor | reports/evidence/impl_preflight_components/ | 完成 |
| 2026-11-16 | TDO-OC | WS-3 | R02/R03：run-meta、baseline/verify-baseline、evidence_run.sh | reports/evidence/impl_baseline_evidence/ | 完成 |
| 2026-11-16 | TDO-OC | WS-4 | R01/R04/R07/R08：archive-gate、close strict、verify-render | reports/evidence/impl_close_archive_render/ | 完成 |
| 2026-11-16 | QA | WS-5 | 独立复跑全量 + 14 条负向 + 六入口 + scope/product | reports/QA-VERDICT.md | 完成 |
| 2026-11-16 | MAIN | WS-6 | 终检、FINAL、closeout manifest、strict lint、DECISIONS/PROJECT 收口 | reports/FINAL.md、reports/evidence/closeout.json | 完成 |
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
  - **WS-1（Packet A）**：R05 真检查与 R06 组件/降级完成；定向 pytest 绿，preflight 负向 rc 语义符合。
  - **WS-2（Packet B）**：baseline/verify-baseline 排除本 run；evidence_run 保留真实 rc 与 pipefail；负向用例绿。
  - **WS-3（Packet C）**：archive-gate partial→rc2 / missing→rc3；close strict 四类 ERROR；verify-render default WARN/strict ERROR。
<!-- wf:handoff-ws:end -->
- **自检命令与结果**：全量 `.venv/bin/python -m pytest tests -q` → rc=0，259 passed；TASK §5 六入口真实 rc 见 `reports/evidence/qa/six-entrypoints.txt` 与 `reports/evidence/closeout/`。
- **已知薄弱点 / 未验证项**：W2（preflight 失败路径副作用）、W3（baseline 字面命令缺 `.run-meta.json`）、W4（2 个 pre-existing untracked 文件缺 before-sha）、W5（live render drift 预期 WARN）；均已登记承接，见 PROJECT §8 与 DECISIONS D-006。

<!-- wf:handoff:start -->
<!-- wf:handoff:end -->
