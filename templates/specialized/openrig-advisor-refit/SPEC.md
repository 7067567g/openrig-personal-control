# SPEC — OpenRig Advisor Refit（报告驱动的 workflow 内容优化）

## 0. 分层声明

baseline: composite/two-plane-orchestration@1.0.0
contracts: strategy@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0

> 本文件是一次报告驱动工作流优化的特化规则，优先于通用 `WORKFLOW.md` / `roles/*` 中冲突的部分。
> 不覆盖：文档即接口、单一写者、锁协议、状态迁移唯一执行者、分歧不落地。

## 1. 任务

把三份 2026-10-23 顾问报告中的高置信、已裁决项落成**当前工作流内容的最小可验证优化**，并由 OpenRig 真实双平面执行面跑通一条可归档的工作流：

1. 以三份报告为只读输入，以现有 `advisor-report-fusion-20261023` 融合台账为已裁决依据；不重新做 93→25 的全量抽取。
2. 只执行本轮写权限内、可机械验收的内容优化；报告建议不是规范，旧快照不是现状。
3. 本轮内容优化限定两类：
   - **文档降噪**：退役术语只在 `WORKFLOW.md` 术语表保留一处；角色手册不再重复复述历史禁令，但保留“不建游离台账、无主项进 ISSUES/STATUS 指针”的操作语义；增加机检防止回潮。
   - **模板层收敛（保守 pilot）**：把 canonical 零引用的 `issue-sync` 从 `templates/baseline/` 降级为 `templates/specialized/issue-sync/` adapter；保留 `safe-cleanup` M3、不强制 M2 清零、不按报告百分比硬砍文档。
4. 本 run 自身必须用 OpenRig 的 rig / queue / workflow / transcript 执行并产出一个严格 `archiveStatus=COMPLETE` 的归档样本，再经 teardown 守卫收口。
5. 任何动态失败如实记 `FAIL`/`SKIP`，不得用静态搜索或本地模拟冒充 OpenRig E2E。

## 2. 输入与证据优先级

- 只读输入：
  - `ADVISOR-GEMINI4ARGON-20261023.md`
  - `ADVISOR-GEMINI4ARGON-DSH-20261023.md`
  - `ADVISOR-QUALITY-COMPARISON-20261023.md`
  - `runs/advisor-report-fusion-20261023/reports/claim-register.jsonl`（已裁决簇；辅助索引，不替代当前代码事实）
- 优先级：`当前代码/命令事实` > `可复跑测试/运行证据` > `已裁决融合台账` > `报告事实引用` > `报告推断` > `报告建议`。
- 报告原文只读：记录路径、sha256、读取范围；不修改、不复制正文建第二事实源。

## 3. 写权限

| 路径 | 权限 | 用途 |
| --- | --- | --- |
| `runs/openrig-advisor-refit-20261023/**` | 可写 | 本 run 四件套、报告、证据、OpenRig bundle |
| `templates/specialized/openrig-advisor-refit/**` | 可写 | 本轮复用模板 |
| `roles/*.md`、`AGENTS.md`、`WORKFLOW.md` | 可写（本轮降噪） | 删除重复退役术语；保留操作语义 |
| `tests/test_doc_noise.py`、`tests/test_template_layers.py` | 可写 | 机检与模板迁移回归 |
| `templates/baseline/**`、`templates/specialized/**`、`templates/contracts/**` | 可写（仅本轮批准项） | issue-sync 降级、注册表/版本/锁更新 |
| `scripts/contract_lock.py` | 可写（仅版本字面量） | `workflow-group-base` 升 `1.1.0` 并重签 LOCK |
| 三份报告原文、`runs/advisor-report-fusion-20261023/**`、OpenRig 源码 | **只读** | 事实输入/对照 |
| `/tmp/openrig-workflow-openrig-advisor-refit-20261023/**` | 可写（隔离） | OpenRig HOME |

## 4. 强制门禁

- **G-DOC**：`roles/*.md` 与 `AGENTS.md` 中 `SO` / `TERMINAL` / `L1`–`L3` 退役术语出现次数为 0；操作语义仍有：不建游离台账、无主项进 ISSUES/STATUS、去向必须闭合。
- **G-TPL**：`templates/baseline/` 不再包含 `issue-sync`；`templates/specialized/issue-sync/` 为唯一 canonical adapter；`REGISTRY.{md,json}`、`VERSION`、`BASELINE-MAP.md` 同步；`test_template_layers.py` 通过。
- **G-LOCK**：`python3 scripts/contract_lock.py check` rc=0；基础母版升 `workflow-group-base@1.1.0`，LOCK 重新生成，未授权的 contract-set 不变。
- **G-TEST**：全量 `python3 -m pytest tests -q` 通过；新增降噪回归覆盖“角色手册无退役术语”与“术语表单一来源”。
- **G-DUAL**：OpenRig 隔离 home + 独立端口；4/4 seats ready；workflow validate rc=0；workflow instantiate 产生 entry packet；queue 至少完成 plan/docs/templates/verify 四类 packet；transcript 可采集。
- **G-ARCHIVE**：run 归档 `MANIFEST.json.archiveStatus == "COMPLETE"`，五类 required 全 true；teardown wrapper 在 COMPLETE 后执行；不得先拆 live home。
- **G-QA**：QA 对每项给 PASS/WARN/FAIL/SKIP 与证据；无 open S1/S2 才能关闭。

## 5. 证据格式

```text
[PASS] <检查项> | cmd: <命令> | exit: <码> | evidence: <路径>
[FAIL] <检查项> | cmd: <命令> | exit: <码> | blocker: <阻塞面> | evidence: <路径>
[SKIP] <检查项> | why: <原因> | 后续: <触发条件>
```

所有动态证据必须包含：OpenRig home、port、rig name、workflow instance id、qitem id、seat session、transcript 路径或 archive manifest 路径。

## 6. 完成定义

- 两类内容优化完成，G-DOC/G-TPL/G-LOCK/G-TEST 全绿。
- OpenRig 4 seats ready、workflow 走完 plan→docs→templates→verify→main close，且有 queue/workflow/transcript 证据。
- COMPLETE 归档先于 teardown；无残留 daemon/tmux/runner。
- `PROJECT.md` §6 报告结论、指标变化、残余风险；`DECISIONS.md` 有对应 D-xxx。
- 明确列出未做项与原因，不把报告中的未来建议写成已完成。

## 7. 反目标

- 不重做三份报告的全文抽取；不把融合台账当规范。
- 不强制 M2 清零、不降级 `safe-cleanup`、不按 25% 硬指标压缩文档。
- 不新增常设角色、不新增第 8 原子轮型、不建游离台账。
- 不修改 OpenRig 源码、queue/workflow DB、三份报告原文。
- 不使用用户既有 daemon/rig，不泄露凭据，不把 local-only/静态检查写成 E2E。
