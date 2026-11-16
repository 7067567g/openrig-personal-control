# KB 消费接口与检索增强 · 启动文档（P7）

> 依据：`runs/kb-claim-verify-20261014/reports/`、F 侦察（kb-recall-eval 现状 hit@1/2/3=47/51/53，#32 手工表，router 无门禁）。

## 1. 粘给新会话的提示词

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/kb-consume-interface.md、templates/specialized/kb-consume-interface/SPEC.md
任务：run-id = kb-consume-20261014。按 SPEC §1 三路并行实现 KB 消费接口（kb-ask/日志、router-sync 门禁、消费引用计数），
     R2 做别名扩展与证据复跑；全程测试约束见 SPEC；主会话不读正文。
硬约束：无人值守不提问；写权限精确到 SPEC 文件清单；不改金问题题目；不 push。
完成或确认阻塞时写 runs/kb-consume-20261014/DONE。
```

## 2. 命令

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run kb-consume-20261014 --template templates/specialized/kb-consume-interface \
  --goal-file kickoff/kb-consume-interface-goal.txt --project-root /home/dev/Desktop/deepseek/deepseek-知识库 \
  --scope '见 SPEC §1/§2 文件清单' --tdo 3
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate kb-consume-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad kb-consume-20261014 \
  --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3' --timeout 7200 --jobs 3
python3 scripts/wf.py state kb-consume-20261014 STATUS qa-pending
python3 scripts/wf.py delegate kb-consume-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate kb-consume-20261014 --role pmo --timeout 3600
python3 scripts/wf.py commit --repo /home/dev/Desktop/deepseek/deepseek-知识库 \
  --run kb-consume-20261014 --round 1 --message 'R1 消费接口' -- scripts tests 00-overview
python3 scripts/wf.py new-round kb-consume-20261014
python3 scripts/wf.py squad kb-consume-20261014 --agents 'tdo-b1:WS-4,tdo-b2:WS-5' --timeout 7200 --jobs 2
```

## 3. 坑

- 热文件互斥：R1 里 `kb-validate.mjs` / `kb-generate-views.mjs` / `kb-ask.mjs` 互不重叠；R2 才动 `kb-recall-eval.mjs` 与 `terminology.yaml`。
- `kb-generate-views.mjs` 有单测基线（`tests/kb-generate-views.test.mjs`）：改了要同步测试与快照，否则 `--check` 红。
- 12 条真实查询在 `runs/kb-method-action-20261014/reports/WS4-query-log.md` 与 `05-methodology/kb-evolution-direction-assessment.md` 阶段 2；复跑判定要逐条写清。
