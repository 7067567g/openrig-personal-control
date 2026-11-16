# SPEC — KB 消费接口与检索增强（P7）

## 0. 分层声明

baseline: composite/knowledge-pipeline@1.0.0
contracts: research@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0

> 特化规则，优先于通用手册。依据：`runs/kb-claim-verify-20261014`、F 侦察报告（2026-10-14）。
> 目标：把 KB 从"文档库"推进到"可验证的消费接口"，并直接喂方向 C 判据（#32）。

## 1. 任务与分片（R1 三路并行，热文件互斥）

| WS | 任务 | 写权限（精确到文件） | 验收判据 |
| --- | --- | --- | --- |
| WS-1 | `F2` 任意问题消费接口：`kb-ask.mjs`（BM25 rank/top-k + canonical 判定 + `--json`/`--log`）+ JSONL 查询日志（append-only）+ 周汇总 | `scripts/kb-ask.mjs`、`tests/kb-ask.test.mjs` | 对 #32 的 12 条真实查询复跑命中 ≥11/12；无网络、确定性；日志只追加 |
| WS-2 | `F8` router↔frontmatter 投影一致性门禁：`kb-validate router-sync` 双向比对 router 行 × 文档 `applies-to-task`/`not-for` | `scripts/kb-validate.mjs`（仅新增子命令）、`tests/router-sync.test.mjs` | 现有投影全一致；反例夹具（router 有行/文档无投影 等）必须 FAIL；`validate all` 不回归 |
| WS-3 | `F6` 消费引用计数：在生成视图里分列「结构入边(see-also)」与「消费命中(kb-ask 日志)」+ 0 引用候选表 | `scripts/kb-generate-views.mjs`、`tests/kb-generate-views.test.mjs` | 与 backlink-index 一致性检查通过；`genviews --check` OK；用 12 条日志复算可核对 |

## 2. R2（R1 后，热文件释放）

| WS | 任务 | 写权限 | 验收判据 |
| --- | --- | --- | --- |
| WS-4 | `F4` 检索别名/同义扩展：修 4 条已知未命中（GQ-010/020/053/071），别名源=terminology aliases + router 术语（**`terminology.yaml` 只读，由 P8 独占写**） | `scripts/kb-recall-eval.mjs`、`tests/kb-recall-eval.test.mjs` | hit@3 目标 57/57；其余题 rank 快照不回归；禁止改期望文档/删题 |
| WS-5 | `F7` 证据到期复跑：EV-001~006 逐条复跑、更新 `verified-at/expires` | `00-overview/evidence.yaml`、（失败项）run 报告 | `hygiene` 0 expired；复跑命令可执行；`validate all` 全绿 |

## 3. 全内容与证据

- 每片报告逐项列"改了什么/为什么/怎么验证"，证据给命令+输出摘要；
- 新增脚本必须有单测与反例夹具；
- 12 条真实查询复跑要逐条给命中/未命中与 rank。

## 4. 禁止

- 不改 `00-overview/golden-questions.md` 的题目与期望文档（防作弊）；不删题；
- 不引入 LLM/网络依赖；不伪造通过；
- 白名单外只读；TDO 只改不提交，主会话每轮 `wf.py commit` 明确路径；不 push。

## 5. DoD

- `validate all` 0 FAIL/0 WARN、`genviews --check` OK、`node --test` 全绿、`hygiene` 0 expired；
- `kb-ask` 对 12 条真实查询 ≥11/12；hit@3 目标达成且无回归；
- `reports/final.md`（含指标前后对比）；ISSUES 无 open S1/S2。
