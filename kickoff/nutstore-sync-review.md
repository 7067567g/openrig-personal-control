# obsidian-nutstore-sync 个人版全盘审查修订 · 启动文档（P6）

> 目标仓库：`/home/dev/Desktop/deepseek/20-工作区/obsidian-nutstore-sync`（独立 git，分支 `personal/phone-ai-tools`）
> 已知：426 个 ts/tsx、~20 个 vitest 单测、eslint+tsc+esbuild 构建；依赖需 `node scripts/bootstrap-deps.mjs`。

## 1. 粘给新会话的提示词

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/delegation-briefs.md、kickoff/nutstore-sync-review.md、templates/specialized/nutstore-sync-review/SPEC.md
任务：run-id = nutstore-review-20261014。对 obsidian-nutstore-sync 个人版做全盘审查与修订：
     先装依赖，再按 SPEC §3 七片逐文件审查 426 个 ts/tsx，修复 bug（复现+回归测试），最后全量门禁全绿。
硬约束：无人值守不提问；写权限以 SPEC §3 为准；不 push、不改分支/tag、不删文件；不伪造通过。
完成或确认阻塞时写 runs/nutstore-review-20261014/DONE（一行结论）。
```

## 2. 前置与命令

```bash
# 0) 依赖（一次性，后台跑 + 轮询）
cd /home/dev/Desktop/deepseek/20-工作区/obsidian-nutstore-sync
nohup node scripts/bootstrap-deps.mjs > /tmp/nutstore-bootstrap.log 2>&1 &
# 轮询 tail /tmp/nutstore-bootstrap.log，直到出现完成标志或失败

# 1) 建档
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run nutstore-review-20261014 --template templates/specialized/nutstore-sync-review \
  --goal-file kickoff/nutstore-sync-review-goal.txt \
  --project-root /home/dev/Desktop/deepseek/20-工作区/obsidian-nutstore-sync \
  --scope 'src/**, tests/**, scripts/**, main.js, dist/**, manifest.json, *.config.*' --tdo 7
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate nutstore-review-20261014 --role pmo --timeout 3600

# 2) R1 七片并行审查+修订
python3 scripts/wf.py squad nutstore-review-20261014 \
  --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3,tdo-a4:WS-4,tdo-a5:WS-5,tdo-a6:WS-6,tdo-a7:WS-7' \
  --timeout 7200 --jobs 7
python3 scripts/wf.py state nutstore-review-20261014 STATUS qa-pending
python3 scripts/wf.py delegate nutstore-review-20261014 --role qa --timeout 3600
python3 scripts/wf.py delegate nutstore-review-20261014 --role pmo --timeout 3600
python3 scripts/wf.py commit --repo /home/dev/Desktop/deepseek/20-工作区/obsidian-nutstore-sync \
  --run nutstore-review-20261014 --round 1 --message 'R1 分区审查与修复' -- src tests scripts main.js dist manifest.json

# 3) R2 全量门禁 + 跨片修复（WS-8），R3 收口
python3 scripts/wf.py new-round nutstore-review-20261014
python3 scripts/wf.py squad nutstore-review-20261014 --agents 'tdo-b1:WS-8' --timeout 7200 --jobs 1
```

## 3. 分片（写权限互斥，见 SPEC §3）

| WS | 目录 | 文件数 |
| --- | --- | --- |
| WS-1 | `src/ai/chat/**` | 81 |
| WS-2 | `src/ai/tools/**` + `src/ai/skills/**` | 56 |
| WS-3 | `src/ai/{providers,core,transport,mcp,catalog}` + `src/ai/*.ts` | ≈29 |
| WS-4 | `src/utils/**` | 77 |
| WS-5 | `src/sync/**` + `src/fs/**` | 43 |
| WS-6 | `src/components/**` + `src/views/**` + `src/settings/**` + `src/i18n/**` | ≈79 |
| WS-7 | services/storage/api/model/types/shims/events/diagnostics | ≈56 |
| WS-8(R2) | 全量测试/构建/构建产物重生成 + 跨片修复 | — |

## 4. 坑

- `pnpm install` 会因私有 tarball 401；必须 `node scripts/bootstrap-deps.mjs`。
- `main.js`/`dist/` 是构建产物：R1 谁都不许动，R2 由 WS-8 全量重生成并核对（避免七片各改一份）。
- `pnpm test:obsidian` 需要 Obsidian 本体 → 预计 SKIP，记录原因即可。
- 提交只走 `wf.py commit`（只 add 明确路径）；仓库很脏时绝不 `git add -A`。
