# workflow-group 引擎测试 + CI · 启动文档（P12）

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/wf-engine-tests.md、templates/specialized/wf-engine-tests/SPEC.md
任务：run-id = wf-engine-tests-20261014。按 SPEC 给 wf.py/issues.py/run_queue.py 补 pytest 与 CI，并落地 S-1/S-2/S-3。
硬约束：无人值守不提问；只动 workflow-group 与 CI 文件；不 push；反例先红后绿。
完成时写 runs/wf-engine-tests-20261014/DONE。
```

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run wf-engine-tests-20261014 --template templates/specialized/wf-engine-tests \
  --goal-file kickoff/wf-engine-tests-goal.txt --project-root /home/dev/Desktop/deepseek/deepseek-知识库 \
  --scope 'workflow-group/**, .github/workflows/wf-validate.yml' --tdo 2
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate wf-engine-tests-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad wf-engine-tests-20261014 --agents 'tdo-a1:WS-1,tdo-a2:WS-2' --timeout 7200 --jobs 2
python3 scripts/wf.py state wf-engine-tests-20261014 STATUS qa-pending
python3 scripts/wf.py delegate wf-engine-tests-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate wf-engine-tests-20261014 --role pmo --timeout 3600
python3 scripts/wf.py new-round wf-engine-tests-20261014
python3 scripts/wf.py squad wf-engine-tests-20261014 --agents 'tdo-b1:WS-3' --timeout 7200 --jobs 1
```
