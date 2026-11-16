# templates/specialized/issue-sync — canonical adapter（自 baseline 降级）

> 状态：**specialized adapter**（2026-10-23 从 `templates/baseline/issue-sync/` 降级）。
> 可实例化：`python3 scripts/wf.py new-run <run-id> --template templates/specialized/issue-sync`
> 分层：`baseline: none`（原 `composite/issue-sync@1.0.0` 已废止）；`contracts: research@1.0.0, verify@1.0.0, audit@1.0.0`。

## 文件边界

| 文件                                                                | 归属                  | 说明                                                                                                                   |
| ------------------------------------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `SPEC.md`                                                           | 本 adapter            | 唯一内容源：任务、写权限、管线、证据、禁止、收口                                                                       |
| `PROJECT.md` / `DECISIONS.md` / `STATUS-Round-n.md` / `ISSUES.xlsx` | `templates/` 通用母版 | `wf.py new-run` 在模板目录无同名文件时自动取通用母版（`scripts/wf.py` 的 `pick()`）；本 adapter 不复制，避免第二事实源 |

## 使用要点

1. 在 run 的 `PROJECT.md §0` 不写 `baseline: composite/...`——本 adapter 已改为原子组合；`contracts:` 固定三件（research/verify/audit）。
2. 成熟度沿用原 baseline 的 **M2**；本轮不做成熟度集中调整。
3. 若后续需要恢复为复合类型，应新开决策并把 `BASELINE.md` 重新放回 `templates/baseline/`，而不是在本文件里加回 baseline 语义。
