# SPEC — Advisor Report Fusion（多报告筛选、合并与处置）

## 0. 分层声明

baseline: composite/postmortem-meta-governance@1.0.0
contracts: audit@1.0.0, strategy@1.0.0, optimize@1.0.0, verify@1.0.0

> 本 SPEC 只写本领域特有规则；通用四件套、单一写者、锁协议与状态迁移仍服从 `WORKFLOW.md` / `roles/`。

## 1. 任务

把同主题的多份顾问/审计报告转成一个**可追溯、去重、已裁决、可执行**的问题台账，并处理本轮获准处理的低风险项：

1. 保留原始报告作为只读证据，不从报告正文创建第二事实源；
2. 逐条抽取 claim、问题、风险、建议与反例；
3. 按底层机制合并重复项，保留来源并集和冲突；
4. 对每个问题簇给出唯一处置：`accept_now` / `accept_next` / `park` / `reject` / `already_done`；
5. 只对 `accept_now` 项落代码/文档改动并附验收证据；
6. 独立核验来源覆盖、处置完整性与测试结果。

## 2. 输入与读取纪律

- 输入是用户指定的报告文件、版本/时间/哈希，以及仓库当前代码树。
- 每份报告必须先记录：绝对路径、字节数、行数、sha256、生成者/模型、生成时间、是否只读、读取范围。
- 报告中的结论优先级：`直接代码/文件事实` > `可复跑命令` > `报告事实引用` > `报告推断` > `报告建议`。
- 不得用报告里的“事实”标签替代仓库复核；报告引用可能对应旧快照、旧提交或另一副本。
- 不读取报告未声明的目录外材料；不修改报告原文。

## 3. 机器可读台账

`reports/claim-register.jsonl` 每行一个 claim，至少包含：

```json
{"id":"AFC-001","title":"...","claim_type":"fact|inference|recommendation|risk","sources":["OC:P0-1"],"evidence_status":"verified|partial|stale|unverified","disposition":"accept_now|accept_next|park|reject|already_done","wave":"W0|W1|W2|W3|none","owner":"TDO|PMO|MAIN|QA","action":"...","acceptance":"...","notes":"..."}
```

- `sources` 使用稳定前缀：`OC:`（OpenCode 顾问报告）、`DSH:`（纯 DSH 报告）、`CMP:`（质量比较报告）；章节/行动号必须可回查。
- 一个 JSONL 行是**去重后的问题簇**，不是逐段摘抄；合并前的逐条抽取放在 `reports/claim-register.raw.jsonl` 或报告表中。
- `accept_now` 必须同时有 `owner`、`action`、`acceptance`、`wave`；`reject` 必须有 `reject_reason`；`park` 必须有 `trigger`。
- `already_done` 必须给出代码位置或命令证据。

## 4. 阶段与门禁

### A0 来源盘点（只读）
- 记录报告元信息与哈希；建立源章节清单。
- 输出 `reports/00-source-inventory.md`。
- 门禁：每份输入都有哈希与读取边界；缺一不得继续。

### A1 原始 claim 抽取（只读）
- 按报告章节/行动项逐条编号，保留原文位置、类型、严重度与建议。
- 不提前去重；不得丢弃“与另一报告重复”的条目。
- 输出 `claim-register.raw.jsonl` 或等价表格。
- 门禁：源章节清单每一项都至少映射到一个原始 claim，或说明无 claim。

### A2 合并为 canonical 问题簇
- 合并规则：同一底层机制/同一修复点 → 一个簇；仅措辞相似但修复点不同 → 不合并。
- 每个簇记录：全部来源、最高证据等级、冲突点、合并理由、反例/限制。
- 冲突裁决：证据优先、保守升级、不强制统一成熟度；无法裁决时 `park` 并写触发条件。
- 输出 `reports/01-fusion-matrix.md` 与去重后的 `reports/claim-register.jsonl`。
- 门禁：无重复 `id`；每个原始 claim 都能映射到簇；每个簇至少有 1 个来源。

### A3 处置与优先级
- 固定处置枚举：`accept_now` / `accept_next` / `park` / `reject` / `already_done`。
- `accept_now` 仅限本 run 写权限内、低/中风险、可在本轮机械验收的项。
- 高风险的删除、发布、外部 push、权限变更、生产 live 操作不得进入 `accept_now`；必须走 SAFETY/人工批准。
- 成熟度、模板数量、文档行数等指标不得作为硬目标倒逼证据；只能作为观察值。
- 输出 `reports/02-disposition.md` 与 `reports/03-source-coverage.md`。

### A4 本轮执行（仅 accept_now）
- 每项改动先记录基线/复现证据，再改，再复跑。
- 不碰与本项无关的文件；不顺手重写文档；不 `git add -A`。
- 输出 `reports/04-implementation.md` 与证据文件。

### A5 独立核验
- QA/独立执行体复跑验收命令，检查反例或负向测试。
- 逐项核对：报告章节覆盖、问题簇来源并集、处置字段、未验证项、写权限边界。
- 输出 `reports/05-verification.md`。
- 不得把“测试通过”外推成未测试的行为通过；缺环境时写 `SKIP` + 原因。

### A6 收口
- 输出 `reports/06-summary.md`：已处理、待处理、拒绝、阻塞、下一步 owner。
- 未处理项必须有 owner + 去向 + 最晚复核点；没有具体去向的“后续 run/人工”不算有效去向。
- 不得在存在未解释 S1/S2 时关闭。

## 5. 筛选规则

1. **先保留、后筛选**：先去重，再做处置；禁止在抽取阶段按个人偏好丢弃。
2. **不把情绪/重复申明当问题**：纯文档措辞若没有可验证后果，归入文档复杂度簇并降级。
3. **不把建议当事实**：报告建议的目标值（如“M2 清零”“砍 25%”“≤15 个”）必须标为建议/推断，不可直接作为验收判据。
4. **不把旧快照当现状**：代码/版本/路径类断言必须回查当前树；无法回查则标 `stale` 或 `unverified`。
5. **不做无验收动作的 accept_now**：没有可复跑判据的项最多进入 `accept_next` 或 `park`。

## 6. 合并规则

- 仅在“同一底层机制 + 同一修复点”时合并；共享一个上游症状不等于同一问题。
- 合并后保留所有来源编号；不得只保留“主报告”来源。
- 证据等级取最强，但冲突和反证必须同时保留。
- 对冲突处置默认保守：
  - 保留已有安全默认与成熟度标签，直到有真实闭环证据；
  - 先抽通用 modifier/plane 能力，再评估是否合并模板；
  - 不强制在期限内容量清零或升级。

## 7. OpenRig 专项核验

- 归档：必须有 `MANIFEST.json` / `ARCHIVE-MANIFEST.json` 中 `archiveStatus=COMPLETE`，并检查 run snapshot、session、transcript、OpenRig state、home snapshot 五类；历史 `PARTIAL` 只能作缺口证据，不能作通过样本。
- teardown：必须有可执行前置守卫与拒绝路径的测试/日志；仅文档声明不算落地。
- bridge：当前新样本期望 `schemaVersion: 2`；路径字段遵守相对/绝对语义；v1 legacy 不得冒充新样本。
- SAFETY：只有真实调用 `digest + gate + review + human-approve` 的执行器与负例才算实现；纯契约/账本格式不算。
- 真实运行必须使用隔离 `OPENRIG_HOME` 与独立端口；不得复用或杀掉用户既有 daemon/rig；不得直接写 queue/workflow DB。
- 无 rig/daemon 环境时，OpenRig 动态项一律标 `SKIP`/`park`，不得用静态搜索冒充 E2E。

## 8. 证据格式

```text
[PASS] <检查项> | cmd: <命令> | exit: <码> | evidence: <路径>
[FAIL] <检查项> | cmd: <命令> | exit: <码> | blocker: <阻塞面> | evidence: <路径>
[SKIP] <检查项> | why: <原因> | 后续: <触发条件/环境>
```

所有验收必须能回答：命令、退出码、证据路径、比对基线、是否负向测试。

## 9. 完成定义（DoD）

- 报告元信息与源章节覆盖表齐全；
- 原始 claim 完整，合并后无丢失；每个问题簇有来源、证据等级与唯一处置；
- `accept_now` 全部有实现与复跑证据；`accept_next`/`park`/`reject` 全部有 owner/触发条件/理由；
- 无 open S1/S2，或已明确列出阻塞与最晚决策点；
- `python3 templates/specialized/advisor-report-fusion/check_fusion.py --register <jsonl> --require-disposition` 返回 `rc=0`；
- `python3 -m pytest -q` 与 `python3 scripts/contract_lock.py check` 按实际范围复跑并如实记录；
- 不修改本 run 之外的报告原文，不把报告建议写成权威规则。

## 10. 反目标

- 不做“报告摘要生成器”；必须产出可处置的问题簇。
- 不做第二事实源、第二数据库或双向票仓同步。
- 不因合并就删除安全默认、历史证据或冲突意见。
- 不新增常设角色/第 8 个原子轮型来“解决”流程问题。
- 不把本模板的特定输入报告写死为通用规则。
