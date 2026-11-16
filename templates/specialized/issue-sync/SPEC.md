# SPEC — Issue 同步 adapter（从 composite/issue-sync 降级）

## 0. 分层声明

baseline: none — 原 composite/issue-sync 已降级为本 adapter，语义由本 SPEC 承载
contracts: research@1.0.0, verify@1.0.0, audit@1.0.0

> 本文件是 `templates/specialized/issue-sync/` 的 canonical adapter；`templates/baseline/` 不再提供 `issue-sync` 复合类型（2026-10-23 保守收敛，见 `../BASELINE-MAP.md`）。
> 降级理由：canonical 领域特化对其零引用；保留为 specialized 后仍可直接 `--template` 实例化，只是不再占 baseline 名额。
> 成熟度沿用原标记 **M2**（本轮不升不降）。

## 1. 任务

把既有审计 findings 对上游最新版本重核，排除已修复/已跟踪/重复项，只提交仍成立、可复现、非重复的 issue。

1. 每条 finding 重新锚定到目标仓**当前版本**（commit/tag/版本号）；
2. 复跑失败路径，确认仍可复现；
3. 查重（issue / PR / 讨论 / 内部 tracking），决定 submit 或 no-submit；
4. 只读分析轮与写提交轮分离，提交动作单独记录。

## 2. 写权限

| 路径               | 权限                       | 用途                                         |
| ------------------ | -------------------------- | -------------------------------------------- |
| `runs/<RUN-ID>/**` | 可写                       | 重核台账、复跑证据、提交记录、报告           |
| 目标上游仓库       | 按 SPEC/授权只读或提 issue | 仓库代码只读；提交 issue/PR 必须逐条记录 URL |
| 其他项目/正式域    | **只读**                   | 发现的问题只登记，不代改                     |

## 3. 默认管线（原子轮型组合）

1. **research**：issue 口径、困境、候选 findings 清点；
2. **verify**：对最新版本重核与复现，淘汰已被修复/已跟踪项；
3. **audit**：查重、去重、提交决策与记录（含 no-submit 原因）。

每轮只执行一个原子契约，交 `templates/contracts/_shared/VERDICT.md`。

## 4. 强制证据与 DoD

- 每条 finding 的版本锚 + `path:line` 或复跑命令；
- 查重结果（issue/PR/tracking 链接或检索记录）与 no-submit 原因；
- 提交记录（URL/编号）或明确的“不提交”结论；
- 台账覆盖全部候选 findings，不抽样。

## 5. 禁止

- 不把旧版本结论直接提交；不在未复现的情况下开 issue；
- 不重复提交已被跟踪项；不匿名/不夹带无关内容；
- 不改目标仓代码、不 push、不批量刷 issue。

## 6. 收口

- 提交清单 + no-submit 清单 + 台账三件齐备才算完成；
- 未提交项必须写原因与后续触发条件（谁在什么条件下重开）；
- 本 adapter 自身变更不需升 baseline `VERSION`，但必须同步 `REGISTRY.md` 与 `BASELINE-MAP.md`。

## 7. 来源

- 原 `templates/baseline/issue-sync/BASELINE.md`（v1.0.0，M2）正文语义完整迁移；
- 历史参考：`60-外部仓库:issue-framing`、`60-外部仓库:issue-sync`、`runs/lingshu-issue-framing-20261016`、`runs/lingshu-issue-sync-20261016`。
