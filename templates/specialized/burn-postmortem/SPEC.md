# SPEC — 烧额度复盘与工作流回写（P5）

## 0. 分层声明

baseline: composite/postmortem-meta-governance@1.0.0
contracts: audit@1.0.0, strategy@1.0.0, optimize@1.0.0, verify@1.0.0

> 特化规则，优先于通用手册。目标：把本次"拉主会话烧额度"的实战经验固化进工作流组。

## 1. 任务

1. 复盘：读取 `burner/burner.log`、各 run 的 `DELEGATIONS.md`/`reports/*`（只读），统计额度消耗、轮次、失败模式、锁/权限/超时问题；
2. 回写：更新 `WORKFLOW.md`/`roles/*`/`DESIGN.md`/`burner/*`，把踩到的坑变成规则或代码；
3. 报告：`runs/<RUN-ID>/reports/postmortem.md`，含数据表与改进清单。

## 2. 写权限

| 路径 | 用途 |
| --- | --- |
| `workflow-group/**` | 规范/角色/burner/模板更新 |
| `runs/<RUN-ID>/**` | 复盘报告 |

KB 正式域只读。

## 3. 证据

- 每条改进必须对应一条观察（日志/记录/错误信息）；
- 性能/额度结论给数字（cost、tokens、轮次、失败率）。

## 4. 禁止

- 不改 KB 正式域、不动项目仓、不 push；
- 不为了"有产出"而堆无依据的规则。

## 5. DoD

- 复盘报告（数据 + 失败模式 + 改进清单）；
- `WORKFLOW.md`/`roles/*`/`burner/*` 至少 3 处有依据的改进；
- 工作流自检通过（`wf.py doctor` 语法/模板冒烟）。
