# 方法论实战验证 + 消费闭环 · 启动文档（P2）

> 前置：P1（kb-debt）已把方法论正文写入 `05-methodology/`。本 run 验证它，并把真实查询日志喂给 #32。

## 1. 粘给新会话的提示词

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/kb-method-action-full-burn.md、templates/specialized/kb-method-action/SPEC.md
任务：run-id = kb-method-action-20261014。按本文件执行：抽取方法论原则→逐条处置→实现一个可运行原型→
     真实查询日志回写 05-methodology/kb-evolution-direction-assessment.md 阶段 2（#32）。
硬约束：无人值守不提问；写权限只限 SPEC §2；不虚构日志/结果；TDO 只改不提交，主会话每轮 wf.py commit；不 push。
完成或确认阻塞时写出 runs/kb-method-action-20261014/DONE（一行结论）。
```

## 2. 参数与命令

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run kb-method-action-20261014 --template templates/specialized/kb-method-action \
  --goal-file kickoff/kb-method-action-goal.txt --project-root /home/dev/Desktop/deepseek/deepseek-知识库 \
  --scope '05-methodology/** 只追加 + runs/**' --tdo 3
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate kb-method-action-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad kb-method-action-20261014 \
  --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3' --timeout 3600 --jobs 3
python3 scripts/wf.py state kb-method-action-20261014 STATUS qa-pending
python3 scripts/wf.py delegate kb-method-action-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate kb-method-action-20261014 --role pmo --timeout 3600
python3 scripts/wf.py new-round kb-method-action-20261014     # R2：回归/自测/收口
```

## 3. 分片

| WS | 写权限 | 产出 |
| --- | --- | --- |
| WS-1 | runs/** | 方法论原则逐条处置表（采用/不适用+理由） |
| WS-2 | runs/** | 可运行原型 + 构建/启动/功能自测证据 |
| WS-3 | runs/** + `05-methodology/kb-evolution-direction-assessment.md` | ≥10 条真实查询日志回写 #32 |

## 4. 坑

- 查询日志只记真实查询；维护性 grep 不计；不补记。
- 原型优先离线单文件（无网络依赖），保证可复跑。
- 回写 #32 前先读其既有口径，冲突记 ISSUES 不自作主张。
