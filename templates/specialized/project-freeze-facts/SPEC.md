# SPEC — 项目仓冻结声明红 + 隐藏差量 + 契约补测（P9）

## 0. 分层声明

baseline: composite/fix-wave@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

> 特化规则，优先于通用手册。仓库：`/home/dev/Desktop/deepseek/deepseek-项目`（父仓，独立 git；不 push）。
> 依据：B 侦察（2026-10-14）实测 `python3 scripts/repo-facts.py --check` **EXIT=1**（共享声明 2 处违规）。

## 1. R1（3 路并行，文件互斥）

| WS | 写权限（父仓相对路径） | 任务与验收 |
| --- | --- | --- |
| WS-1 | `scripts/shared-declarations.json`、`20-tif2lines/**`、`20-tif2lines-org/**` | 冻结声明红：定性谁改了冻结侧（重放 `git diff 0faeba6 -- 20-tif2lines-org`），逐文件 sha256 对账，归位快照或按新锚重下并把关系改为「有意分叉+理由」。**验收：`python3 scripts/repo-facts.py --check` EXIT=0，且不许只改声明凑绿** |
| WS-2 | `docs/repo-facts.json`、`scripts/repo-facts.py`、`10-v3-tools-platform/plugins/module.well_ab_review/sub/_service.py`、`10-signaldeck/src/desktop/package-lock.json`、`40-anythingxl-prompt-lab/**` | 隐藏差量：CRLF/LF 判定（`git diff --numstat --ignore-cr-at-eol` 为空即纯行尾），产出「该提/该回滚/该删」三选一结论+命令；anythingxl（13 docs + 2 data）登记入 `repo-facts` 并原子提交。**验收：登记后 `repo-facts --check` 不新增 FAIL；每条差量有结论与证据** |
| WS-3 | `30-voxel-chinese-arch/**`、`30-voxel-jrpg-town/**`（含 tests 与其源码） | 契约补测：2738 行源码 vs 131 行测试，按 R27 方向矩阵补边界/错误路径/跨模块契约/幂等四类。**验收：`uv run pytest` 全绿且用例数上升；≥3 条 mutation 抽证（改坏一处必红）** |

## 2. R2（1 路）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-4 | `docs/repo-facts.json`、`docs/local-data-manifest.json`、`docs/asset-exceptions.json` | 事实/归属收口：孤儿资产（45 条无维护者）逐条给 owner 或转 `_archive` 登记（**只登记不移数据**）；票仓 terminal items 清点（不新开票）；`repo-facts --report` 快照落 run 报告。验收：只剩 WS-1 之前的问题或全绿；不改资产本体字节 |

## 3. 全内容与证据

- 每条结论给命令 + 输出摘要；对账表给 sha256；mutation 给"改哪行→哪个用例红"；
- 只读部分（`.ticket-store`、`归档`）不得写入。

## 4. 禁止

- 不 push；不动 `归档/` 数据本体；不删除任何文件；TDO 只改不提交，主会话每轮 `wf.py commit` 明确路径；白名单外只读。

## 5. DoD

- `repo-facts.py --check` EXIT=0；CRLF/anythingxl 有结论并已提交；voxel 用例增加且全绿；
- `reports/final.md`；ISSUES 无 open S1/S2；父仓提交只含白名单路径。
