# 项目仓冻结声明红 + 隐藏差量 + 契约补测 · 启动文档（P9）

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/project-freeze-facts.md、templates/specialized/project-freeze-facts/SPEC.md
任务：run-id = project-freeze-20261014。对 /home/dev/Desktop/deepseek/deepseek-项目 按 SPEC 执行：
     R1 三路（冻结声明红 / CRLF+anythingxl 登记 / 体素契约补测），R2 事实归属收口。
硬约束：无人值守不提问；只提交不 push；不动归档数据本体；写权限见 SPEC。
完成时写 runs/project-freeze-20261014/DONE。
```

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run project-freeze-20261014 --template templates/specialized/project-freeze-facts \
  --goal-file kickoff/project-freeze-facts-goal.txt \
  --project-root /home/dev/Desktop/deepseek/deepseek-项目 --scope '见 SPEC §1/§2' --tdo 3
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate project-freeze-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad project-freeze-20261014 --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3' --timeout 7200 --jobs 3
python3 scripts/wf.py state project-freeze-20261014 STATUS qa-pending
python3 scripts/wf.py delegate project-freeze-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate project-freeze-20261014 --role pmo --timeout 3600
python3 scripts/wf.py commit --repo /home/dev/Desktop/deepseek/deepseek-项目 \
  --run project-freeze-20261014 --round 1 --message 'R1 冻结声明与差量' -- scripts docs 20-tif2lines 20-tif2lines-org 30-voxel-chinese-arch 30-voxel-jrpg-town 40-anythingxl-prompt-lab
python3 scripts/wf.py new-round project-freeze-20261014
python3 scripts/wf.py squad project-freeze-20261014 --agents 'tdo-b1:WS-4' --timeout 7200 --jobs 1
```
