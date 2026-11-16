# 烧额度复盘与工作流回写 · 启动文档（P5）

> 前面几轮烧完后，把实战经验固化进 workflow-group。

## 1. 粘给新会话的提示词

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/burn-postmortem.md、templates/specialized/burn-postmortem/SPEC.md
任务：run-id = burn-postmortem-20261014。复盘 burner/burner.log 与各 run 的 DELEGATIONS/reports（只读），
     统计消耗/轮次/失败模式，把坑变成 WORKFLOW/roles/DESIGN/burner 的改进，产出复盘报告。
硬约束：无人值守不提问；只写 workflow-group/** 与 runs/**；KB 正式域只读；不 push。
完成时写 runs/burn-postmortem-20261014/DONE。
```

## 2. 参数与命令

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run burn-postmortem-20261014 --template templates/specialized/burn-postmortem \
  --goal-file kickoff/burn-postmortem-goal.txt --project-root /home/dev/Desktop/deepseek/deepseek-知识库 \
  --scope 'workflow-group/**（含 burner/）' --tdo 2
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate burn-postmortem-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad burn-postmortem-20261014 \
  --agents 'tdo-a1:WS-1,tdo-a2:WS-2' --timeout 3600 --jobs 2
python3 scripts/wf.py state burn-postmortem-20261014 STATUS qa-pending
python3 scripts/wf.py delegate burn-postmortem-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate burn-postmortem-20261014 --role pmo --timeout 3600
```

## 3. 分片

| WS | 范围 | 产出 |
| --- | --- | --- |
| WS-1 | 数据复盘 | 消耗/轮次/失败模式统计表 |
| WS-2 | 规范与代码回写 | WORKFLOW/roles/DESIGN/burner 改进（每条有依据） |

## 4. 坑

- 只读别的 run 的报告，不要改它们；改进只落在 `workflow-group/**`。
- 改动后跑工作流自检（`wf.py doctor`、模板冒烟），别改坏给下次烧额度用的模板。
