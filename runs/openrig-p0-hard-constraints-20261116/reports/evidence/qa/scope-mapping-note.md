# Scope diff → PROJECT §4 mapping（回应 MAIN 规则 1）

- 对照对象：`reports/evidence/impl_baseline_evidence/00-baseline.startup.txt`（启动捕获，status `eefbb03b…`）。
- 当前侧：`git status --porcelain`（默认模式，与启动捕获同模式；`-uall` 会把已有 run 目录展开，产生假差异）。
- 本 run 自身 `reports/**` 按 PROJECT §2.1 允许新增，比对时排除；否则只是把本 run 的证据文件列一遍，无法证明“无越界”。
- 完整输出：`scope-diff.txt`（新增 10、删除 0、同路径状态位变化 0）。

## 10 个新增路径 → 计划归属

| 新增路径 | 归属 |
| --- | --- |
| `scripts/required_components.py` | PROJECT §4.1 Packet A |
| `tests/test_required_components.py` | PROJECT §4.1 Packet A |
| `tests/test_openrig_preflight.py` | PROJECT §4.1 Packet A |
| `scripts/evidence_run.sh` | PROJECT §4.2 Packet B |
| `tests/test_wf_baseline.py` | PROJECT §4.2 Packet B |
| `tests/test_evidence_run.py` | PROJECT §4.2 Packet B |
| `scripts/verify_render.py` | PROJECT §4.3 Packet C |
| `tests/test_archive_gate.py` | PROJECT §4.3 Packet C |
| `tests/test_evidence_record.py` | PROJECT §4.3 Packet C |
| `tests/test_verify_render.py` | PROJECT §4.3 Packet C |

## 内容变化但状态行不变的文件（已在包证据中记录）

- `scripts/issues.py`、`scripts/wf.py`、`tests/test_issues.py`、`tests/test_wf.py`
- 根 `AGENTS.md`（TASK §5 唯一授权例外，`629742bf… → 53eed071…`）
- 启动时已是未跟踪、因此不新增 status 行：`scripts/openrig_preflight.py`、`scripts/wf_close_lint.py`、
  `tests/test_wf_close_lint.py`
