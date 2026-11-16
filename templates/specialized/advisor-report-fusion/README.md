# advisor-report-fusion — 多份顾问报告的筛选、合并与处置

> 适用场景：同一主题收到多份分析/审计/顾问报告，需要在**不把报告当事实源**的前提下，抽取问题、去重合并、裁决冲突，并把可执行项送入有证据的修复波次。
> 本模板默认 **local-only**：只在 workflow-group 控制面工作，不启动 OpenRig daemon；若确实需要双平面执行，再显式切到 hybrid，并遵守 `openrig-workflow-master` 的隔离与归档门。

## 输入

- 2 份以上报告文件（Markdown/文本），保留原始路径，不复制正文到 run（避免第二事实源）。
- 每个报告的文件 `sha256`、行数、生成时间与实际读取范围。
- 可访问的代码树/规范树，用于把报告断言转成可复核证据。

## 输出

```text
runs/<RUN-ID>/
  reports/00-source-inventory.md      # 来源、哈希、读取范围、证据边界
  reports/claim-register.jsonl        # 逐条 claim（未去重，机器可读）
  reports/01-fusion-matrix.md         # 去重后的 canonical 问题簇 + 来源并集
  reports/02-disposition.md           # accept_now/next/park/reject/already_done
  reports/03-source-coverage.md       # 报告章节 → 问题簇覆盖表
  reports/04-implementation.md        # 本轮处理/修改与证据（若有）
  reports/05-verification.md          # 独立复跑、反例、未验证项
  reports/06-summary.md               # 决策者摘要
```

## 快速开始

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
python3 scripts/wf.py new-run <run-id> \
  --template templates/specialized/advisor-report-fusion \
  --goal "筛选/合并/处置多份顾问报告" \
  --project-root /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group \
  --scope 'runs/<run-id>/**; templates/**; scripts/**; tests/**' \
  --tdo 3

python3 templates/specialized/advisor-report-fusion/check_fusion.py \
  --register runs/<run-id>/reports/claim-register.jsonl \
  --require-disposition
```

## 关键约束

- 报告中的 `[FACT]`/“事实”字样本身不是证据；必须回到代码、文件、命令或运行产物复核。
- 推断和建议可以保留，但必须标注 `claim_type` 与 `evidence_status`，不得升级成事实。
- 同一底层机制的重复表述合并为一个问题簇；来源、冲突与反证必须保留并集。
- `accept_now` 必须有 owner、可复跑验收命令、写权限边界；`reject` 必须有拒绝理由；`park` 必须有触发条件。
- 不因报告写“M3/清零/百分比”而自动升级成熟度；成熟度只能由真实 run 证据决定。
- 不在本模板中启动/销毁用户既有 OpenRig daemon，不直接写 queue/workflow DB。

## OpenRig 专项提示

- 检查 `ARCHIVE-MANIFEST.json` / `MANIFEST.json` 的 `archiveStatus`；只有 `COMPLETE` 且必需五类归档项存在，才算严格归档样本。
- `teardown` 硬守卫必须以可执行调用链或测试证明；文档中的“应加守卫”不算已实现。
- bridge `schemaVersion: 2` 是当前契约；v1 legacy 只读兼容，不得当新样本。
- `SAFETY` 执行器只有在存在真实 digest/gate/review/human-approve 调用与负面测试时才算落地。
