# POST-CLOSE-CLEANUP — openrig-p1-hard-constraints-20261116

- 归档：OpenCode-only（无 DSH seat），严格归档 `sessionSnapshots` 结构性缺失；
  以 `--allow-incomplete` 归档为 PARTIAL，不冒充 COMPLETE。决策记录见
  `deepseek-项目/10-openrig-deepseek/var/openrig-archive/ARCHIVE-DECISIONS.md` 的 `D-P1-01`。
- 执行面：归档后 `rig down`，daemon 停止，端口 `47978` 关闭，临时 home 删除。
- 产品仓：未 commit/push；产品仓 HEAD/status/diff 与规划基线一致。
- 已知残余：P1 `rig up` 在 KB 根 `AGENTS.md` 注入了 `guidance/team.md` managed block；
  R10 审计现在能列出它，但命名空间/归属尚未迁移（Q5 先审计后迁移），本轮不强行回滚。
- dashboard target：未改动（P1 QA 已核对 active 仍为旧 run，且无本 run target）。
