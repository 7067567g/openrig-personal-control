# Problems — P0/P1/P2

## P0-1 执行架构名不副实

- 预期：OpenRig 多 seat / queue / workflow / transcript。
- 实际：`auto_driver.py` + `dsh --profile headless` 单 seat。
- 证据：`artifacts/auto_driver.py` `DEFAULT_SEAT = ["dsh", "--profile", "headless"]`；无 `rig up/send/queue/workflow`。
- 影响：多 seat 自动推进、独立 QA、resume、transcript 全部没有；每轮靠单 seat 自证。

## P0-2 轮次语义混合、状态漂移

- 33 个轮位：R01–R30 + R05.5 + R09.5 + R15.5。
- `PREP3` 写 32；`rounds.yaml` 33。
- `R15.5` 未进 `ROUNDS.jsonl`。
- 历史 `BLOCKED=R15` 与 `DONE=all requested rounds passed` 并存（现已改名为 `.history` / `.invalid-20261113`）。
- 影响：无法判断真实进度；每次审计先修状态。

## P0-3 验收门禁过弱

- `g0–g3` 只查 schema/scope/evidence/command。
- `round_checks.py` R10–R30 大量 token/file 检查。
- 例：R10 “重连/断线”、R11 “评测/记忆”、R13 “会话/切换”。
- 单 seat 生产 + 自证，没有独立 QA。
- 影响：PASS 不代表行为正确；人工反复插轮。

## P0-4 工作区未冻结

- `git status` 大量修改/未跟踪文件。
- `tools/sctg/**`、`tools/adb/**`、`reports/sctg/**` 未提交。
- 没有 baseline tag/整改分支。
- 影响：整改与继续跑轮互相污染，不可回滚。

## P1-1 Driver 状态非原子

- 直接写 `ROUNDS.jsonl` / `DONE` / `BLOCKED` / `NEED_MAIN`。
- 无临时文件 + rename、无锁、无 schema 校验。
- `DONE` 写入条件不是“30 产品轮全部 PASS”。

## P1-2 NEED_MAIN/外部轮没有统一停止语义

- `--all` 遇 NEED_MAIN 停止，但仍可能留下 DONE。
- R21/R22/R23/R28 写 `../bridge-app/**`，主 driver 不能跨仓写。
- R16/R25/R29/R30 需要 MAIN。

## P1-3 无 telemetry

没有每轮耗时、attempt、gate/check、changed files、evidence hash、人工干预、issue 趋势。

## P1-4 检查职责混乱

`check_round.py` 既有硬编码分支又有 `ROUND_CHECKS` 注册表；R01–R09 与 R10–R30 风格不一致。

## P1-5 Git/发布卫生

`.sctg/` 被忽略；`reports/sctg/**` 未提交；R15.5 含真实 tailnet target（已在本案例副本脱敏）。

## P2 体验与效率

- 每轮 = 一张卡 + gate + check + report，粒度过粗。
- 准备轮/审计轮临时插入，没有固定节奏。
- 没有独立 QA 里程碑。
- 30 轮体感时间约 4–9.5 小时（按 R10–R15 8 min/轮、早期 19 min/轮估算），尚未计人工/外部轮。
