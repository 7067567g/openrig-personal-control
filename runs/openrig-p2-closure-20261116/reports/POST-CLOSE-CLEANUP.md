# POST-CLOSE-CLEANUP — openrig-p2-closure-20261116

- 归档：OpenCode-only（无 DSH seat），严格归档 `sessionSnapshots` 结构性缺失；
  以 `--allow-incomplete` 归档为 PARTIAL，不冒充 COMPLETE。决策记录见
  `deepseek-项目/10-openrig-deepseek/var/openrig-archive/ARCHIVE-DECISIONS.md` 的 `D-P2-01`。
- 执行面：归档后 `rig down`，daemon 停止，端口 `47979` 关闭，临时 home 删除。
- 产品仓：未 commit/push；产品仓 HEAD/status/diff 与规划基线一致。
- 工作区 managed block：当前 KB 根 `AGENTS.md` 已无 `OpenRig MANAGED BLOCK`（P2 C-001 由主会话处置后清零）；
  `audit_managed_blocks.py` 对本文件应返回 0 块。
- dashboard target：未新增本 run target；active 仍为旧 run。
