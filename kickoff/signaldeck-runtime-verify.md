# SignalDeck 实跑验证 · 启动文档（P3）

> SignalDeck 已全检过，但"还没试"。本 run 只回答：**它真的能跑吗？**

## 1. 粘给新会话的提示词

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/signaldeck-runtime-verify.md、templates/specialized/signaldeck-runtime-verify/SPEC.md
任务：run-id = signaldeck-runtime-20261014。对 /home/dev/Desktop/deepseek/deepseek-项目/10-signaldeck 做只读实跑验证：
     22 步门禁、前端 check/build、宿主 build:host+冒烟、无显示器尽力启动、交付包核对。
硬约束：无人值守不提问；项目仓只读，只写 runs/；不伪造 PASS，环境不可得写 SKIP+原因；不 push。
完成或确认阻塞时写出 runs/signaldeck-runtime-20261014/DONE（一行结论）。
```

## 2. 参数与命令

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run signaldeck-runtime-20261014 --template templates/specialized/signaldeck-runtime-verify \
  --goal-file kickoff/signaldeck-runtime-verify-goal.txt \
  --project-root /home/dev/Desktop/deepseek/deepseek-项目/10-signaldeck \
  --scope '只读 10-signaldeck/**；只写 runs/**' --tdo 3
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate signaldeck-runtime-20261014 --role pmo --timeout 3600
python3 scripts/wf.py squad signaldeck-runtime-20261014 \
  --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3' --timeout 3600 --jobs 3
python3 scripts/wf.py state signaldeck-runtime-20261014 STATUS qa-pending
python3 scripts/wf.py delegate signaldeck-runtime-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate signaldeck-runtime-20261014 --role pmo --timeout 3600
python3 scripts/wf.py new-round signaldeck-runtime-20261014   # R2：失败复现与报告
```

## 3. 分片

| WS | 范围 | 产出 |
| --- | --- | --- |
| WS-1 | `tests/**` + 门禁 | 22 步结果表（PASS/FAIL/SKIP+耗时+证据） |
| WS-2 | `src/frontend/**`、`src/desktop/**` | check/build/build:host 结果与产物清单 |
| WS-3 | 运行尝试 + `交付包/**` | 启动结论（跑到哪/卡在哪/缺什么）+ 交付包核对 |

## 4. 坑

- 无显示器：先试 `xvfb-run`；不可用就记录并降级到 host 冒烟/静态资源检查。
- `npm ci` 可用（锁文件已在）；装新包记 ISSUES 跳过。
- 项目仓 git root 是 `../deepseek-项目`，只读即可，不要 commit。
