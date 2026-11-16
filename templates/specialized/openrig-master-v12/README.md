# openrig-master-v12 特化模板

用于把 `templates/specialized/openrig-workflow-master` 从 v1.1.0 更新到 v1.2.0。

本模板只服务一个 bounded run，不是 v1.2 母版本身。运行目标、版图、非目标与验收见：
- `workflow-group/kickoff/openrig-master-v12-audit.md`
- `workflow-group/kickoff/openrig-master-v12-goal.txt`

实例化：

```bash
cd workflow-group
python3 scripts/wf.py new-run openrig-master-v12-20261020 \
  --template templates/specialized/openrig-master-v12 \
  --goal-file kickoff/openrig-master-v12-goal.txt \
  --project-root /home/dev/Desktop/deepseek/deepseek-知识库 \
  --scope 'workflow-group/runs/openrig-master-v12-20261020/**;workflow-group/templates/specialized/openrig-workflow-master/**;workflow-group/templates/specialized/openrig-master-v12/**;workflow-group/tests/test_render_master_portability.py;workflow-group/tests/test_openrig_bridge_doctor.py;workflow-group/tests/test_workflow_rework.py;workflow-group/tests/test_master_release.py;workflow-group/kickoff/openrig-master-v12*' \
  --tdo 2
```

母版 v1.2 发布文档由 MAIN 在 WS-A/WS-B 落定后统一写入，避免 TDO 并发改同一文件。
