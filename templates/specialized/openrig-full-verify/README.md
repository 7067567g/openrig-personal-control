# openrig-full-verify 特化模板

## 用途

对已完成 OpenCode + DSH 特化的 OpenRig 自有副本做只读全量检查：静态、四包测试、真实 5-seat E2E、跨重启 resume、workflow/spec、卫生与报告。

## 实例化

```bash
cd workflow-group
python3 scripts/wf.py new-run <run-id> \
  --template templates/specialized/openrig-full-verify \
  --goal-file kickoff/openrig-full-verify-goal.txt \
  --project-root /home/dev/Desktop/deepseek/deepseek-项目/10-openrig-deepseek \
  --scope 'workflow-group/runs/<run-id>/**；openrig-full-verify 模板/kickoff；/tmp/openrig-full-verify-*' \
  --tdo 1
```

## 推荐执行顺序

1. `git status` / upstream clean / commits；
2. `npm run build --workspaces`；`npm run lint`；
3. `npm run test:repo`；
4. daemon 全量（后台、等终态）；
5. cli / tui / ui 全量；
6. feature targeted tests；
7. 隔离真实 rig E2E；
8. rig down/up --existing resume；
9. workflow validate/instantiate；
10. 卫生清理 + `reports/FULL-CHECK.md`。

## 注意

- 不修改源码；
- 不要把定向测试写成“全量”；
- 重测试串行，不用并行 rig 干扰；
- 真实 E2E 必须隔离 `OPENRIG_HOME`；
- 结束前清理 daemon/tmux/runner 和仓库里的 AGENTS.md。
