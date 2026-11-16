# SPEC — 在跑自动化可靠性 + 日常入口健康（P13）

## 0. 分层声明

baseline: composite/ops-hardening@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

> 特化规则，优先于通用手册。依据：C/D 侦察（2026-10-14）。
> 注意：`月月bot/`、根脚本、`50-记录与维护/` 大多**不在 git 版本控制内**——改动必须留文件清单+diff 摘要到 run 报告；有 git 的仓库（`快捷方式/`）只提交明确路径、不 push。

## 1. R1（3 路并行）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-1 | `月月bot/qq-bridge/**`、`~/.config/systemd/user/qq-bridge*`（如存在） | qq-bridge 加固：测试 runner（现有 5 脚本一键）+ **B1 `seen_messages` 去重持久化 / B2 `catchup_max_age`** 回归（先 FAIL 后 PASS）；`bridge.log` 轮转；修正 hardstop unit 的 WorkingDirectory 真值。**验收：runner 全绿；B1/B2 用例先红后绿；日志轮转后有截断/归档证据** |
| WS-2 | `快捷方式/**` | 启动器健康：`apps.json` 校验器（目标存在/相对化/无机器绝对路径 反例 FAIL）；`relink-deliverables.py` 干跑报告；收口 6 个未提交文件（`git status --porcelain` 空）。**验收：反例 FAIL、51 条输出真值、提交后工作树干净** |
| WS-3 | `链接核查.sh`、新增 `运维核查.sh` | 链接核查误报修复（URL 解码、反引号代码块剔除）+ 聚合门禁 `运维核查.sh`（链接+镜像+KB，统一退出码）。**验收：含 `%20` 与代码块链接的夹具 0 误报；`--fail-on=broken-link` rc 可断言；不改 `镜像维护.sh`（P10 在写）** |

## 2. R2（1 路）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-4 | `月月bot/qq-bridge/docs/**` | 把 B3–B6（掉线监控/outbox 文件上传等）**只登记**为 RECOVERY_GAPS 状态表 + 触发条件，不开工实现；输出"在跑自动化可靠性清单"给 run 报告。验收：每条 gap 有证据与触发条件 |

## 3. 禁止

- 不 push；不改 `镜像维护.sh`/`镜像日志`（P10）；不动归档；无版本控制目录的改动必须留清单；TDO 只改不提交，主会话对能提交的仓库提交明确路径。

## 4. DoD

- qq-bridge runner 全绿（B1/B2 先红后绿）；快捷方式校验器与收口完成；链接夹具 0 误报 + 聚合退出码可断言；
- `reports/final.md`；ISSUES 无 open S1/S2。
