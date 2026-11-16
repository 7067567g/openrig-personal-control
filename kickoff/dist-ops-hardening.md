# 分发/同步/运维加固 · 启动文档（P10）

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/dist-ops-hardening.md、templates/specialized/dist-ops-hardening/SPEC.md
任务：run-id = dist-ops-20261014。按 SPEC：R1 三路（镜像/日志治理、多仓灾备、运行时 frozen），
     R2 重建分发包与发布门禁，R3 时间允许再做三查门禁与快捷方式校验。
硬约束：无人值守不提问；不 push；不动归档既有内容/venv；写权限见 SPEC。
完成时写 runs/dist-ops-20261014/DONE。
```

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run dist-ops-20261014 --template templates/specialized/dist-ops-hardening \
  --goal-file kickoff/dist-ops-hardening-goal.txt --project-root /home/dev/Desktop/deepseek \
  --scope '见 SPEC §1/§2/§3' --tdo 3
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate dist-ops-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad dist-ops-20261014 --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3' --timeout 7200 --jobs 3
python3 scripts/wf.py state dist-ops-20261014 STATUS qa-pending
python3 scripts/wf.py delegate dist-ops-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate dist-ops-20261014 --role pmo --timeout 3600
python3 scripts/wf.py new-round dist-ops-20261014
python3 scripts/wf.py squad dist-ops-20261014 --agents 'tdo-b1:WS-4' --timeout 7200 --jobs 1
```
