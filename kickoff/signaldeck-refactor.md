# SignalDeck 完全体重构 — R7–R11 续跑 kickoff

> 用途：burner / 无人值守主会话拉起 `signaldeck-refactor-20261025` 的剩余轮次。
> 事实源：`runs/signaldeck-refactor-20261025/PROJECT.md` + `DECISIONS.md` + `reports/VERDICT.md`。

## 当前状态（2026-11-04）

- 已完成 R1–R6：清点 306/306、基线 8+306、映射 35→72、4/4 runner 可重建、tool-lib 2 工具接入。
- 当前 `VERDICT: ADJUST`，`PROJECT: waiting-main`，`open S1/S2 = 0`。
- 预算：`max_rounds=12`，已用 6。

## 剩余轮次

| 轮 | 目标 | 关键门禁 |
| --- | --- | --- |
| R7 | gate 上锁：`verify-tool-build` + 3 个治理 verifier 进两包 `gate-steps` | `verify-windows-gate-parity`、全量 gate |
| R8 | rule-chain 单一语义 + geo 单一实现 | `verify-rule-engine`、oracle/随机差分、A/B |
| R9 | Host 拆分：runtime 五模块 + HTTP 路由表 + 单测 | `build:host`、`verify-host-build`、`_smoke_host` |
| R10 | 前端 domain/platform + widgets lazy + `ctx.lib.apiVersion` / 结果版本戳 / `/api/health` | 前端 check/build、smoke |
| R11 | 最终验收：全量门禁、A/B 全量、删重复、更新台账、`VERDICT: STOP` | 全量 gate、0 open S1/S2、0 未登记重复 |

## 无人值守硬规则

1. 全程不要向用户提问；需要拍板的事记入 `PROJECT §6` / `DECISIONS.md`，继续其它可做项。
2. 每轮按 S1 PMO → S2 TDO → S3 QA → S4 PMO → S5 MAIN 走完；不要交完一波就停。
3. 写权限以 `SPEC.md` 为准；白名单外只读；TDO 只改不提交，主会话每轮用明确 pathspec 提交；永不 push。
4. 完成 DoD 或确认阻塞时，写 `runs/signaldeck-refactor-20261025/DONE`（一行结论），写完才结束。
5. 长命令优先后台：`nohup ... > runs/<id>/logs/<step>.log 2>&1 &`，轮询日志尾部/DELEGATIONS/doctor。
6. 不新开票；残余只进 `ISSUES.xlsx` / `PROJECT §6` / `DECISIONS.md`。
