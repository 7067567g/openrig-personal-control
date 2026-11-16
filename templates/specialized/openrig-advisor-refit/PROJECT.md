<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: PROJECT
owner: PMO
state: pmo-plan
updated: <DATE>
contract_mode: strict
-->

# PROJECT — OpenRig Advisor Refit：工作流内容优化

> 写者：PMO ｜ 主会话只读 §6 ｜ 报告/融合台账是只读输入；当前代码树是事实来源。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | 按三份顾问报告与已裁决融合台账，用 OpenRig 特化并执行一条工作流：完成文档降噪与模板层的保守收敛，产出可复跑证据和严格 COMPLETE 归档样本。 |
| 项目根 | `<PROJECT-ROOT>` |
| 写权限白名单 | `<WRITE-SCOPE>` |
| 报告输入 | `ADVISOR-GEMINI4ARGON-20261023.md`；`ADVISOR-GEMINI4ARGON-DSH-20261023.md`；`ADVISOR-QUALITY-COMPARISON-20261023.md` |
| 已裁决输入 | `runs/advisor-report-fusion-20261023/reports/claim-register.jsonl`（辅助，非规范） |
| OpenRig 工作目录 | `runs/<RUN-ID>/openrig/` |
| 隔离 home / port | `/tmp/openrig-workflow-<RUN-ID>`；独立端口（以 bridge 为准） |
| 编制 | MAIN×1 / PMO×1 / TDO×1 / QA×1（OpenRig 4 seats；运行时使用本机可用 backend） |
| 当前轮次 | Round <ROUND-N> |
| 终止判据 | G-DOC/G-TPL/G-LOCK/G-TEST/G-DUAL/G-ARCHIVE/G-QA 均有结论；无 open S1/S2，或有明确 blocker 与去向 |

## 1. 目标与成功判据

- **G1 来源边界**：三份报告与融合台账只读；报告 sha256/行数/读取范围入 `reports/00-sources.md`。
  - 判据：源文件哈希前后一致；未读目录外材料。
- **G2 文档降噪（机检）**：退役术语只在 `WORKFLOW.md §11` 规范术语表保留；`roles/*.md` 与 `AGENTS.md` 不再重复；操作语义不丢。
  - 判据：`tests/test_doc_noise.py` 通过；`contract_lock.py check` rc=0。
- **G3 模板收敛（保守 pilot）**：`issue-sync` 从 baseline 降级为 specialized adapter；不降级 safe-cleanup，不强制成熟度。
  - 判据：baseline 注册表/目录/`BASELINE-MAP.md` 一致；`test_template_layers.py` 通过。
- **G4 基础母版锁**：文档降噪触发的基础母版变更升 `workflow-group-base@1.1.0` 并重签 LOCK。
  - 判据：`contract_lock.py check` 输出 1.1.0 且 rc=0。
- **G5 OpenRig 双平面执行**：隔离 4 seats ready；workflow validate/instantiate；plan → implement_docs → qa_docs → implement_templates → qa_templates → close_round 有 queue/workflow/transcript 证据。
  - 判据：`OPENRIG-STATE.json`、`reports/openrig-run.md`、evidence 目录。
- **G6 严格归档先于 teardown**：`MANIFEST.json.archiveStatus=COMPLETE`，required 五项 true；之后才 teardown。
  - 判据：archive manifest、teardown 输出、hygiene 检查。
- **G7 独立 QA**：QA 对 G1–G6 逐项 PASS/WARN/FAIL/SKIP 并附证据；无 open S1/S2。
  - 判据：`reports/05-verification.md`。

**反目标**：不重做 93→25 抽取；不把报告建议当规范；不强制 M2 清零；不降级 safe-cleanup；不按 25% 硬指标砍文档；不新增角色/原子轮型/游离台账；不修改 OpenRig 源码/DB/报告原文。

## 2. 范围

### 2.1 范围内

- 三份报告与融合台账的读取边界、哈希、已裁决项映射；
- `roles/*.md`、`AGENTS.md`、`WORKFLOW.md` 的退役术语降噪与操作语义保留；
- `tests/test_doc_noise.py` 新机检；
- `issue-sync` baseline → specialized adapter 的保守迁移；
- baseline 注册表/版本、`BASELINE-MAP.md`、模板层测试同步；
- 基础母版版本与 LOCK 重签；
- 本 run 的 OpenRig bundle、4-seat rig、工作流实例、queue/transcript 证据、COMPLETE 归档与 teardown。

### 2.2 范围外

- `safe-cleanup` 降级/合并、M2 清零、plane/modifier 全量迁移；
- 文档 25% 硬压缩、历史 run 批量关闭/续跑；
- OpenRig 源码/DB 变更、上游 push、生产 live 变更；
- DSH live 调用（本机 provider credential 缺失时明确 SKIP，不伪造）。

### 2.3 假设与依赖

- 当前工作树已包含 `advisor-report-fusion-20261023` 的实现（adapter、doctor、投影、evidence-pack 等）；本轮不重复其完成项。
- OpenRig CLI/daemon 可执行；隔离 home 与端口可用；OpenCode backend 已认证。
- 若 DSH backend 不可用，4-seat rig 的运行时选择可退化为 OpenCode，但必须在报告中记录“DSH live SKIP”。
- 共享母版文件受 LOCK 冻结：任何文档降噪必须同步升版并重签 LOCK。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据 |
| --- | --- | --- | --- | --- | --- |
| M1 | 角色手册退役术语出现 | 11 个文件重复 | `roles/*.md` + `AGENTS.md` = 0；仅 WORKFLOW §11 保留 | 待采集 | `test_doc_noise.py` |
| M2 | baseline 数量 / issue-sync 位置 | 10 / baseline | 9 / specialized adapter | 待采集 | `REGISTRY.json`、`BASELINE-MAP.md` |
| M3 | 基础母版锁 | 1.0.0 | 1.1.0，LOCK 一致 | 待采集 | `contract_lock.py check` |
| M4 | 全量测试 | 182 passed / 2 skipped | 全绿，新增测试通过 | 待采集 | pytest 日志 |
| M5 | OpenRig seats | 未启动 | 4/4 ready | 待采集 | `rig ps` 证据 |
| M6 | workflow 步数 | 未实例化 | 6 步走完（允许有界返工） | 待采集 | `workflow show/trace` |
| M7 | 归档 | 无本轮样本 | `COMPLETE` + required 全 true | 待采集 | `MANIFEST.json` |
| M8 | 收口残余 | 未检查 | 0 daemon/tmux/runner | 待采集 | hygiene 证据 |

## 4. 分任务（Workstreams）

| WS | 任务 | 产出物 | 验收判据 | 依赖 | 执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| WS-0 | 计划、通读输入、确认边界与命令 | `reports/00-sources.md`、`ROUND-PLAN.md` | 哈希/边界齐全；写权限明确；不改代码 | — | PMO | 待开始 |
| WS-1 | 文档降噪 + 机检 + 基础母版升版/重签 | `roles/*.md`、`AGENTS.md`、`WORKFLOW.md`、`tests/test_doc_noise.py`、`LOCK.json` | G-DOC/G-LOCK；测试通过 | WS-0 | TDO | 待开始 |
| WS-2 | issue-sync baseline→specialized + 注册表/映射/测试 | `templates/baseline/**`、`templates/specialized/issue-sync/**`、`BASELINE-MAP.md`、registry | G-TPL；测试通过 | WS-1 | TDO | 待开始 |
| WS-3 | OpenRig 启动、workflow 执行、状态与证据采集 | `reports/openrig-run.md`、`reports/evidence/openrig/**` | 4/4 ready；6 步有 packet/trace；transcript 可采集 | WS-0 | MAIN/TDO | 待开始 |
| WS-4 | 独立核验 + 归档前检查 | `reports/05-verification.md` | G1–G6 逐项结论；无 open S1/S2 | WS-1/2/3 | QA | 待开始 |
| WS-5 | COMPLETE 归档、teardown、hygiene、控制面收口 | `reports/06-summary.md`、archive manifest、DECISIONS | archive COMPLETE；teardown 后无残留 | WS-4 | MAIN | 待开始 |

## 5. 轮次计划与结论

### Round <ROUND-N> 计划

- 先 PMO 只读盘点，写 `ROUND-PLAN.md` 与 `reports/00-sources.md`；不改任何受管文件。
- TDO 先做文档降噪并重签 LOCK，再做 issue-sync 迁移；每一步立即跑对应测试。
- OpenRig 4 seats 与 workflow 实例由主会话启动；TDO/QA 只按 packet 回执，不自行 start/stop daemon。
- QA 全量复跑后，MAIN 才执行 archive → teardown → hygiene → DECISIONS/PROJECT 收口。
- 不把“报告建议”“seat ready”“workflow instantiate”冒充业务完成。

### Round <ROUND-N> 结论

- 待采集。

### 单轮契约（wf.py 投影到 ROUND-PLAN.md）

<!-- wf:round-plan
contract: optimize@1.0.0
produces: reports/00-sources.md; reports/04-implementation.md; reports/openrig-run.md; reports/05-verification.md
gate: python3 -m pytest tests -q
budget: targets=2; tdo=1; minutes=180
NOT-DOING: no-m2-zeroing; no-safe-cleanup-downgrade; no-hard-25pct-shrink; no-openrig-source-change; no-external-push
-->

## 6. PMO 上报区

- **本轮结论**：待采集。
- **待拍板**：待采集。
- **指标变化**：待采集。
- **下一轮建议编制**：待采集。
- **风险提示**：待采集。

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| <DATE> | R<ROUND-N> | 从 openrig-advisor-refit 模板建立报告驱动优化 run | 主会话 |
