# 在跑自动化可靠性 + 日常入口健康 · 启动文档（P13）

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/ops-reliability.md、templates/specialized/ops-reliability/SPEC.md
任务：run-id = ops-reliability-20261014。按 SPEC：R1 三路（qq-bridge/快捷方式/链接门禁），R2 登记 B3-B6。
硬约束：无人值守不提问；不改 P10 正在写的文件；不 push；无版本控制目录留清单。
完成时写 runs/ops-reliability-20261014/DONE。
```

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run ops-reliability-20261014 --template templates/specialized/ops-reliability \
  --goal-file kickoff/ops-reliability-goal.txt --project-root /home/dev/Desktop/deepseek \
  --scope '见 SPEC §1/§2' --tdo 3
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate ops-reliability-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad ops-reliability-20261014 --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3' --timeout 7200 --jobs 3
python3 scripts/wf.py state ops-reliability-20261014 STATUS qa-pending
python3 scripts/wf.py delegate ops-reliability-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate ops-reliability-20261014 --role pmo --timeout 3600
python3 scripts/wf.py new-round ops-reliability-20261014
python3 scripts/wf.py squad ops-reliability-20261014 --agents 'tdo-b1:WS-4' --timeout 7200 --jobs 1
```
