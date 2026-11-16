# KB 全库断言核验 · 启动文档（P4，长跑）

> 把 KB 正式文档里"可被现实打脸"的断言逐条核一遍。108 篇全覆盖，适合长跑烧额度。

## 1. 粘给新会话的提示词

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/kb-claim-verify-full-burn.md、templates/specialized/kb-claim-verify/SPEC.md
任务：run-id = kb-claim-verify-20261014。只读核验全部正式文档（约 108 篇）的可核断言，
     逐篇给一致/不一致/不可核结论；不全体覆盖不收口。
硬约束：无人值守不提问；只写 runs/**；不改正文、不动项目仓、不 push；不把"找不到反例"当一致。
每完成一批（15-20 篇）在 STATUS 记录进度；108/108 完成后写 runs/kb-claim-verify-20261014/DONE。
```

## 2. 参数与命令

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run kb-claim-verify-20261014 --template templates/specialized/kb-claim-verify \
  --goal-file kickoff/kb-claim-verify-goal.txt --project-root /home/dev/Desktop/deepseek/deepseek-知识库 \
  --scope '只读全库；只写 runs/**' --tdo 4
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate kb-claim-verify-20261014 --role pmo --timeout 3600
# R1：按域分批，每批一个 TDO
python3 scripts/wf.py squad kb-claim-verify-20261014 \
  --agents 'tdo-a1:BATCH-00-01,tdo-a2:BATCH-02-03,tdo-a3:BATCH-04-05,tdo-a4:BATCH-06-99' \
  --timeout 7200 --jobs 4
python3 scripts/wf.py state kb-claim-verify-20261014 STATUS qa-pending
python3 scripts/wf.py delegate kb-claim-verify-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate kb-claim-verify-20261014 --role pmo --timeout 3600
python3 scripts/wf.py new-round kb-claim-verify-20261014   # R2..Rn：补未覆盖批次 + 复验不一致项
python3 scripts/wf.py ledger kb-claim-verify-20261014
```

## 3. 分批建议（按域切，文件边界互斥）

| 批次 | 范围（示例） |
| --- | --- |
| BATCH-00-01 | `00-overview/**` + `01-project-tools/**` |
| BATCH-02-03 | `02-geophysics/**` + `03-web-game/**` |
| BATCH-04-05 | `04-ai-automation/**` + `05-methodology/**` |
| BATCH-06-99 | `06-data-assets/**` + `99-archive/**` + 根文档 |

## 4. 坑

- 文档里的 `source-ref` 指向项目 commit；核验时用 `git -C ../deepseek-项目 cat-file -e <commit>:<path>`。
- `grep` 找不到 ≠ 不一致；必须给"文档说了什么 vs 实际是什么"的对照。
- 不可核的（需外部权威/真实消费方）写 `不可核 + 原因`，不要硬编结论。
