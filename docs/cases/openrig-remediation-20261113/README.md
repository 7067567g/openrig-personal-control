# Case — OpenRig / SCTG 自动跑整改（2026-11-13）

> 状态：案例记录 + 整改方案已落盘；源工作区整改尚未由本记录执行。
> 源工作区：`/home/a7067567g/下载/deepseek/月月bot/wechat-bridge-v2`
> 源 run：`sctg-app-feel-auto-20261113`
> 整改合同：`REMEDIATION-PLAN.md`

## 一句话

一个原本期望“30 轮自动跑”的月月bot App 体验优化项目，实际由 `SCTG task-card + dsh --profile headless 单 seat + auto_driver.py` 驱动；跑到 R15.5 后因状态漂移、弱 token 检查、NEED_MAIN/外部 Android 轮和一次全局内存事故而停止，需要专项整改后才能继续。

## 关键事实

- `tools/sctg/rounds.yaml`：**33 个轮位**（R01–R30 + R05.5 + R09.5 + R15.5）。
- `ROUNDS.jsonl`：当前快照 **R01–R15 共 15 条 PASS**（含 R01/R02 两个独立 source_run）。
- `R15.5`：ADB 真机验收报告存在，但**未写入 ROUNDS.jsonl**。
- `R16/R25/R29/R30`：`NEED_MAIN`。
- `R21/R22/R23/R28`：外部 `../bridge-app` Android 轮。
- 运行器：`auto_driver.py` 默认 `dsh --profile headless`，**不是 OpenRig rig/queue/workflow**。
- 结论：这不是 OpenRig 30 轮自动流程，而是 SCTG + DSH 单 seat 的 33 轮混合计划；当前只完成约 15.5/30 个产品轮。

## 文件地图

```text
README.md                 本案例总览
TIMELINE.md               从 R01 到内存事故的时间线
PROBLEMS.md               P0/P1/P2 问题清单
EVIDENCE.md               证据、命令、计数、文件路径
MEMORY-INCIDENT.md        2026-11-13 内存事故根因分析
MEMORY-LIMITS.md          cgroup 限制语义、5G/6G/1G 决策与实现
REMEDIATION-PLAN.md       完整整改合同（R0–R10）
NEXT-STEP.md              交给执行智能体的第一动作
artifacts/
  ROUNDS.jsonl            当前轮次状态快照
  rounds.yaml             33 轮位配置
  auto_driver.py          当前 driver
  round_checks.py         当前 R10–R30 check 注册表
  R15.5.md / R15.5.json   已脱敏的 ADB 报告
  BLOCKED.history.txt     历史 BLOCKED=R15
  DONE.invalid-20261113.txt 历史无效 DONE
  memory-snapshot.txt     事故后内存/cgroup 快照
  oom-evidence.txt        OOM 日志摘录
  git-status.txt          源工作区 git 状态
```

## 结论

- **不是 OpenRig 能力不足**，是当前 run 根本没用 OpenRig 执行面。
- **不是“30 轮没跑完”**，是 30 产品轮 + 3 准备轮 + 4 人工点 + 4 外部轮混在一起，且 R16 就会 NEED_MAIN 停止。
- **反复插轮审计的根因**：`check_round.py` 大量 token/file 检查、单 seat 自证、状态非原子、缺少独立 QA 和 telemetry。
- **内存事故根因**：多个 `dsh-terminal` cgroup 峰值 4.6G / 7G / 11.1G，叠加 GNOME/ComfyUI/localsearch/Chrome/WeChat，14GB 机器触发全局 OOM；被 OOM 杀死的是 Chrome/WeChat/GNOME，不是真正占内存的 dsh terminal cgroup。
