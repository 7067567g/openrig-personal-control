# SPEC — KB 按票修订 + 断言门禁化（P8）

## 0. 分层声明

baseline: composite/fix-wave@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

> 特化规则，优先于通用手册。票源：`runs/kb-claim-verify-20261014/reports/tickets-proposed.md`（16 条 / 15 篇）。
> 用户口径：**按票测试的约束和推广，根据测试内容的重做和修订**——每条票必须"验证命令 → 修订 → 复跑 → 门禁化"。

## 1. R1 修订波（3 路并行，域互斥）

| WS | 域（写权限） | 内容 |
| --- | --- | --- |
| WS-1 | `01-project-tools/**`、`04-ai-automation/**`、仓根 `README.md` | 票内 01/04/根 条目逐条修订（插件数、`tree_checksum` 措辞、相对链接、opencode 路径等），每条给"验证命令前后对比" |
| WS-2 | `02-geophysics/**`、`06-data-assets/**` | 票内 02/06 条目 + 归档 ARC 台账断言复核（只读 `归档/**`，改文档不改数据），`data-assets-overview` 与 `backup-archive-data-index` 的"不存在"断言逐条给 `ls/du/find` 证据 |
| WS-3 | `03-web-game/**`、`00-overview/terminology.yaml`、`00-overview/terminology-ledger.md`、`00-overview/kb-foundation.md`、`05-methodology/kb-evolution-direction-assessment.md`、`content-review-queue.md` | 票内 03 条目 + 术语缺口（gray-test 独立 term + do-not-use-for）+ 过期规模/数字刷新（108 篇、9 项未闭环、样本数等），保持时点标注 |

## 2. R2 门禁化（1 路）

| WS | 写权限 | 内容 |
| --- | --- | --- |
| WS-4 | `scripts/kb-claims.mjs`、`tests/kb-claims.test.mjs`、`.github/workflows/kb-validate.yml` | 把 16 条票抽成机器可跑断言（数值/路径/命令），支持 `--json` 与夹具；对已修订文档应 0 命中；CI 加一步（外部依赖沿用 `KB_SKIP_EXTERNAL_CHECKS` 降级）；再复跑 16/16 全绿 |

## 3. 全内容与证据

- 每条修订：票 ID + 原断言 + 验证命令 + 实际 + 修订后 diff（≤5 行）+ 复跑结果；
- 不许"改声明凑绿"；归档数据只读；数字类必须与当前实测一致或标注时点。

## 4. 禁止

- 不改 `golden-questions.md` 的题目/期望文档；不改 LICENSE/归档本体；
- 不做无票依据的顺手改；白名单外只读；TDO 只改不提交、主会话每轮 `wf.py commit`；不 push。

## 5. DoD

- 16/16 票有"验证→修订→复跑"闭环；`validate all` 0 FAIL/0 WARN、`genviews --check`、`hygiene` 全绿；
- `kb-claims.mjs` 可对票源复跑并输出 0 命中；CI 通过；
- `reports/final.md`；ISSUES 无 open S1/S2。
