# POST-CLOSE-CLEANUP — openrig-p0-hard-constraints-20261116

- 归档：本 run 为 OpenCode-only（无 DSH seat），严格归档的 `sessionSnapshots` 结构性缺失；
  以 `--allow-incomplete` 归档为 PARTIAL，不冒充 COMPLETE。决策记录见
  `deepseek-项目/10-openrig-deepseek/var/openrig-archive/ARCHIVE-DECISIONS.md` 的 `D-P0-01`。
- 副作用回滚：
  - KB 根 `AGENTS.md` 的 preflight managed block 已移除，sha256 恢复为 `629742bf…`（启动前）。
  - dashboard `target.json` 的本次 target 已移除、`active` 恢复为 `openrig-docs-governance-20261115`，
    sha256 恢复为 `62ee9d57…`（启动前）。
- 执行面：归档完成后 `rig down`，daemon systemd unit 停止，端口 `47977` 关闭，临时 home 删除。
- 产品仓：未 commit/push；产品仓 HEAD/status/diff 仍与规划基线一致。
