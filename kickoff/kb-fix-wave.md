# KB 按票修订 + 断言门禁化 · 启动文档（P8）

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/kb-fix-wave.md、templates/specialized/kb-fix-wave/SPEC.md
任务：run-id = kb-fix-20261014。按 SPEC：R1 三路修订 16 条票（按域互斥），R2 建 kb-claims.mjs 门禁并接 CI，
     最后复跑 16/16 全绿。票源 runs/kb-claim-verify-20261014/reports/tickets-proposed.md。
硬约束：无人值守不提问；写权限见 SPEC；不改金问题题目/归档本体；不 push。
完成时写 runs/kb-fix-20261014/DONE。
```

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run kb-fix-20261014 --template templates/specialized/kb-fix-wave \
  --goal-file kickoff/kb-fix-wave-goal.txt --project-root /home/dev/Desktop/deepseek/deepseek-知识库 \
  --scope '见 SPEC §1/§2' --tdo 3
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate kb-fix-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad kb-fix-20261014 --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3' --timeout 7200 --jobs 3
python3 scripts/wf.py state kb-fix-20261014 STATUS qa-pending
python3 scripts/wf.py delegate kb-fix-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate kb-fix-20261014 --role pmo --timeout 3600
python3 scripts/wf.py new-round kb-fix-20261014
python3 scripts/wf.py squad kb-fix-20261014 --agents 'tdo-b1:WS-4' --timeout 7200 --jobs 1
```
