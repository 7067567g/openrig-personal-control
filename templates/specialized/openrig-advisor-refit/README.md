# openrig-advisor-refit — 报告驱动的 workflow 内容优化

适用：已有一组顾问/审计报告和融合台账，需要把已裁决项落成当前工作流内容优化，并**真实经过 OpenRig 双平面**执行、验证、归档、teardown。

本模板是薄特化：

- 不复制 `openrig-workflow-master` 的全部实现；复用其 `render_master.py`。
- 只提供本场景的 4-seat OpenRig 模板与一个 `specialize_bundle.py` 薄适配器，把 master 生成的 5-role bridge 收窄为与 4-seat workflow 一致。
- 不新增 baseline 复合类型；使用 `composite/two-plane-orchestration@1.0.0` 作为执行面底座。

## 快速开始

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group

python3 scripts/wf.py new-run openrig-advisor-refit-20261023 \
  --template templates/specialized/openrig-advisor-refit \
  --goal-file kickoff/openrig-advisor-refit-goal.txt \
  --project-root /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group \
  --scope 'runs/openrig-advisor-refit-20261023/**; templates/specialized/openrig-advisor-refit/**; roles/*.md; WORKFLOW.md; AGENTS.md; tests/*.py; templates/baseline/**; templates/specialized/**; templates/contracts/**; scripts/contract_lock.py' \
  --tdo 1

# 渲染 master bundle，再用薄适配器收窄为 4 seats / 4 roles
python3 templates/specialized/openrig-workflow-master/render_master.py \
  --run-id openrig-advisor-refit-20261023 \
  --project-root /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group \
  --output-dir runs/openrig-advisor-refit-20261023/openrig \
  --openrig-cli 'node /home/dev/Desktop/deepseek/deepseek-项目/10-openrig-deepseek/packages/cli/dist/bin-wrapper.js' \
  --openrig-home /tmp/openrig-workflow-openrig-advisor-refit-20261023 \
  --daemon-port 47899 \
  --template-dir templates/specialized/openrig-advisor-refit/templates \
  --force --json

python3 templates/specialized/openrig-advisor-refit/specialize_bundle.py \
  --bundle runs/openrig-advisor-refit-20261023/openrig
```

## 约束

- 先归档后 teardown：`MANIFEST.json.archiveStatus=COMPLETE` 且 `required.*` 全 true。
- 不复用/杀掉用户既有 daemon/rig；不写 OpenRig queue/workflow DB。
- DSH live 不可用时标 SKIP，不用 OpenCode 结果冒充 DSH。
- 文档降噪不得丢“无主项进 ISSUES/STATUS、去向闭合”的操作语义。
