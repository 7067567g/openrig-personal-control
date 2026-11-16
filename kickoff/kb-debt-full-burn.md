# KB 欠账清理 · 启动文档（新会话用）

> 场景：opencode 额度窗口内，把 KB 的 4 笔欠账一次清掉 + 落一套检索评测工具
> 特化模板：`templates/specialized/kb-debt-burn/`（含 `SPEC.md` 分区表、预填 PROJECT、预置决策清单）
> 目标文件：`kickoff/kb-debt-goal.txt`

## 1. 粘给新会话的提示词

```text
你现在是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group

先读（按顺序）：
1) README.md
2) WORKFLOW.md（重点 §2 编制、§3 状态机、§5 锁、§9 直连、§9.1 真实项目提交）
3) roles/delegation-briefs.md（§5 主会话每轮固定动作）
4) kickoff/kb-debt-full-burn.md（本文件）
5) templates/specialized/kb-debt-burn/SPEC.md（本 run 的分区与特化规则）

任务：按本文件 §3 的命令，用特化模板建立 run，对 deepseek-知识库 的 4 笔欠账做
     全内容范围清理：① 4 篇方法论素材入库；② 检索评测工具 + 57 条金问题基线；
     ③ I-08 12 样本补评；④ _reference 12 文件收口。把额度尽量转化为可验证成果。

硬约束：
- 主会话只委派/收账/拍板：不读 STATUS/ISSUES 正文，只读 PROJECT.md §6 决定下一轮。
- 写权限只限 SPEC §2 表内的路径；白名单外只读；不删源素材；不虚构评测数字。
- 每处改动必须过门禁（validate all / genviews --check / hygiene / 单测）；失败先修或记 ISSUES。
- 提交：TDO 只改不提交；每轮结束主会话用 wf.py commit 只 add 明确路径（KB 仓不 push）。

执行方式：严格按本文件 §3 的命令走；用 delegate/squad 发活、ledger 记账、doctor 体检、
        new-round 开轮。现在从第 1 步开始。
```

## 2. Run 参数

| 项 | 值 |
| --- | --- |
| run-id | `kb-debt-20261013` |
| 模板 | `templates/specialized/kb-debt-burn` |
| 项目根 | `/home/dev/Desktop/deepseek/deepseek-知识库` |
| 写权限 | 见 `SPEC.md` §2 分区表（本 run 显式豁免"不改正式域"） |
| 提交 | TDO 只改不提交；主会话每轮 `wf.py commit --repo <KB 仓> --run ... -- <paths>`；不 push |
| 模型 | 默认 flash；WS-6 评测/终检可换 `--model opencode-go/deepseek-v4-pro` |
| 并发 | R1 五路：`--agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-4,tdo-a4:WS-5,tdo-a5:WS-8' --jobs 5` |
| 超时 | `--timeout 3600` |

## 3. 开跑命令（照抄）

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group

# 1) 建档（特化模板：自动带 SPEC.md；PROJECT 已预填判据/范围/WS 表）
python3 scripts/wf.py new-run kb-debt-20261013 \
  --template templates/specialized/kb-debt-burn \
  --goal-file kickoff/kb-debt-goal.txt \
  --project-root /home/dev/Desktop/deepseek/deepseek-知识库 \
  --scope '05-methodology/**,00-overview/**,scripts/**,tests/**,03-web-game/00-overview/**,_reference/**,content-review-queue.md' \
  --tdo 5

# 2) 起服务（--pure + 自动预热）
python3 scripts/wf.py serve start

# 3) PMO 计划（校验/细化预填 PROJECT；产出 §6 计划摘要）
python3 scripts/wf.py delegate kb-debt-20261013 --role pmo --timeout 3600

# 4) R1 五路并行扫描/处置（每路唯一 WS）
python3 scripts/wf.py squad kb-debt-20261013 \
  --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-4,tdo-a4:WS-5,tdo-a5:WS-8' \
  --timeout 3600 --jobs 5

# 5) QA 核查 → PMO 收轮
python3 scripts/wf.py state kb-debt-20261013 STATUS qa-pending
python3 scripts/wf.py delegate kb-debt-20261013 --role qa --timeout 3600
python3 scripts/wf.py delegate kb-debt-20261013 --role pmo --timeout 3600

# 6) 主会话读 PROJECT §6 → 写 DECISIONS.md（Q-1..Q-5 拍板 + 编制）
# 7) 提交本轮 KB 变更（只 add 明确路径）
python3 scripts/wf.py commit --repo /home/dev/Desktop/deepseek/deepseek-知识库 \
  --run kb-debt-20261013 --round 1 --message 'R1 欠账清理' \
  -- 05-methodology scripts tests 03-web-game/00-overview _reference content-review-queue.md

# 8) 开 R2：WS-3（00-overview）与 WS-6（评测基线）
python3 scripts/wf.py new-round kb-debt-20261013
python3 scripts/wf.py squad kb-debt-20261013 \
  --agents 'tdo-b1:WS-3,tdo-b2:WS-6' --timeout 3600 --jobs 2
python3 scripts/wf.py ledger kb-debt-20261013
```

## 4. 波次与验收

- **R1（5 路）**：WS-1 方法论入库 / WS-2 评测工具 / WS-4 I-08 补评 / WS-5 `_reference` 收口 / WS-8 全库取证。
- **R2（2 路）**：WS-3 把 WS-1/WS-8 的清单落到 `00-overview/`（GQ 期望答案要点、路由行、生成视图）；WS-6 用 WS-2 工具跑 57 条基线 + 10 条抽样。
- **R3**：按 QA 的 ISSUES 修复 → 全量门禁 → `reports/audit-final.md` → DECISIONS 关闭。
- 全内容覆盖是硬要求：4/4 素材、12/12 样本、12/12 文件都要有逐项处置。

## 5. 节奏与熔断

| 指标 | 建议 |
| --- | --- |
| 并行 | R1 5 路；R2 2 路；有修复片再加 |
| 单轮墙钟 | 20–50 分钟（受最慢 TDO 决定） |
| 目标 | R1 出 5 份报告，R2 出评测基线，R3 全绿收口 |
| 熔断 | 连续 2 轮零新发现且门禁绿 → 收口；门禁连续失败 2 次且无法定位 → 停该片升级 |
| 收口产物 | `reports/audit-final.md`、ISSUES 清零 S1/S2、DECISIONS、DELEGATIONS + ledger |

## 6. 已知事实与坑

1. 来源目录：`_reference/方法论待入库-20260924/`（4 篇，53KB，唯一副本）；样本源件在 `../归档/02-内容包与快照/灰测样本源件-20260924/`（只读）。
2. `05-methodology/` 现有 11 篇文档；新正文需满足 frontmatter 全套 + `see-also` 指向存在文件 + 标题=H1。
3. 金问题现 57 条、无「期望答案要点」列；`golden-questions.md` 是 WS-3 独占写权限。
4. `_reference/README.md` 记录了 2026-10-02 收窄历史；WS-5 改记录要保留那张"历次收窄"表格式。
5. `_reference` 12 文件与 README 记录矛盾，**默认重新登记、不删除**；回收需 Q-4 拍板 + 用户确认。
6. 本仓 CI 只跑 KB 门禁；提交后等 `gh run watch` 绿再继续开轮（或让 PMO 收轮时捎带确认）。
