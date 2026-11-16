# SPEC — 物探正确性回归与格式契约（P11）

## 0. 分层声明

baseline: composite/fix-wave@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

> 特化规则，优先于通用手册。仓库：`/home/dev/Desktop/deepseek/deepseek-项目`（只提交不 push）。
> 依据：E 侦察（2026-10-14）。票仓纪律见 `docs/testing.md` / `testing-r27-draft.md`（R26 四行声明）。

## 1. R1（3 路并行，仓库内文件互斥）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-1 | `10-signaldeck/tests/**`、`10-signaldeck/src/tools/stdtrack/**`、`tests/gate-steps.json` | E1：stdtrack A/B fixture 化（去 Windows 快照/7z 依赖，Linux 可跑）+ P-050/P-052/去重三条边界回归 + 接门禁。**验收：新脚本 Linux exit 0；变异「Target 列 20→19」「cut<首点静默」对应用例红；`bash tests/run-linux.sh --step=<新步骤>` PASS；按 R26 写 FOCUS/ORACLE/LEVEL/非目标** |
| WS-2 | `20-fault-stick-depth-conversion/tests/**`、`20-fault-stick-depth-conversion/scripts/**` | E2：42 个深度域产物不变量矩阵（行数/表头/X·Y·sign/fault token/T 列有限性 + 中值面/保守/斜率重算分支专属不变量），豁免项回指真实 nodeid。**验收：`uv run pytest` 全绿；改任一产物某行 → 对应用例红** |
| WS-3 | `docs/smi-dat-dialects.md`、`20-tif2lines/tests/**`、`20-zhongjiang-horizon-calibration/tests/**`、`20-wellhead-section-lines/tests/**`、`20-belt-boundary-polygon/tests/**` | E3：D1–D10 方言覆盖矩阵（表头逐字/编码/CRLF/列义/往返 + nodeid），文档常量与代码常量一致性断言；tif2lines D4 单一读入点或冻结样例契约。**验收：矩阵每格真实 nodeid 或显式 gap；改表头常量/列序 → 红；D4 往返逐值一致** |

## 2. R2（2 路）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-4 | `10-signaldeck/tests/verification/**`、`10-signaldeck/tests/gate-steps.json`、`10-signaldeck/tests/fixtures/**` | E7：`verify-well-ab-review.mjs` 接进 24 步门禁 + fixtures 全量数值 diff + `toFloat` 宽松边界断言。**验收：门禁出现该步骤且 PASS；变异 `(a2-a1+π)%2π` 取模 → 红** |
| WS-5 | `20-flc-horizon-tracking/tests/**` | E8：flc 脚本/产物可跑性矩阵逐行断言 + 11 个不可再生 `.dat` 只读不变量（格式/行列/CRLF/编码）。**验收：每个脚本/产物有判定；误运行归档脚本必须硬失败** |

## 3. 全内容与证据

- 每条按 R26 写 FOCUS/ORACLE/LEVEL/非目标；变异抽证给"改哪行→哪个用例红"；
- 不得为凑矩阵写形式测试；豁免必须给 source 与真实 nodeid。

## 4. 禁止

- 不 push；不改产物数据本体（只读校验）；不删除文件；TDO 只改不提交，主会话每轮 `wf.py commit` 明确路径；白名单外只读。

## 5. DoD

- 新 fixture/门禁在 Linux 全绿；三条变异抽证红；矩阵无空壳；
- `reports/final.md`；ISSUES 无 open S1/S2；父仓提交只含白名单路径。
