# 物探正确性回归与格式契约 · 启动文档（P11）

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/geophysics-correctness.md、templates/specialized/geophysics-correctness/SPEC.md
任务：run-id = geophysics-correctness-20261014。对 deepseek-项目 按 SPEC 执行：
     R1 三路（stdtrack 回归/42 产物不变量/SMI 方言矩阵），R2 well_ab 进门禁 + flc 可跑性矩阵。
硬约束：无人值守不提问；只提交不 push；不改数据本体；R26 四行声明。
完成时写 runs/geophysics-correctness-20261014/DONE。
```

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run geophysics-correctness-20261014 --template templates/specialized/geophysics-correctness \
  --goal-file kickoff/geophysics-correctness-goal.txt \
  --project-root /home/dev/Desktop/deepseek/deepseek-项目 --scope '见 SPEC §1/§2' --tdo 3
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate geophysics-correctness-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad geophysics-correctness-20261014 --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3' --timeout 7200 --jobs 3
python3 scripts/wf.py state geophysics-correctness-20261014 STATUS qa-pending
python3 scripts/wf.py delegate geophysics-correctness-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate geophysics-correctness-20261014 --role pmo --timeout 3600
python3 scripts/wf.py new-round geophysics-correctness-20261014
python3 scripts/wf.py squad geophysics-correctness-20261014 --agents 'tdo-b1:WS-4,tdo-b2:WS-5' --timeout 7200 --jobs 2
```
