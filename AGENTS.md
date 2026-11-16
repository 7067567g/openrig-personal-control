# AGENTS — workflow-group 作业入口

> 给进入本目录的 Agent（含 opencode 委派会话）的硬入口。完整规范见 `WORKFLOW.md`。
> 文档地图：本目录入口见 [README.md](./README.md#目录地图)；跨仓总图见 [docs/openrig/README.md](docs/openrig/README.md)。

## 先做什么

1. 读 `roles/common-contract.md`（所有角色通用硬约束）。
2. 读你被委派的角色文档：主会话 → `roles/MAIN.md`；PMO / TDO / QA → 对应 `roles/*.md`；只有 SPEC 明示启用安全门控时才读 `roles/SAFETY.md`。
3. 读委派消息里指定的 run 目录（`runs/<run-id>/`）与其中对应文档。


## 新 OpenRig run 的强制前置（AI 必须执行）

启动任何新的 OpenRig rig/workflow 之前，按顺序：

1. 读 `templates/specialized/openrig-workflow-master/PREFLIGHT.md`；
2. 跑 `python3 scripts/openrig_preflight.py --json`，读取它输出的 mandatory/templates/注意事项；
3. 选定 `templates/specialized/<name>` 与 `SPEC.md §0` 的 baseline/contracts；
4. 启动 seat 时用 `--workspace <seat 工作区>` 让脚本把 preflight 注入该工作区 `AGENTS.md`，seat 的 AI 启动即会看到；
5. 用 `--run-id --rig --seat --job --run-dir --gov-dir` 让脚本把新 run 注册到只读监测台 `http://127.0.0.1:3190`（它会启动 `yueyue-monitor.service`）。

禁止跳过 1–2 直接 `rig up`；没有 preflight 注入的 seat 不得承接新 run。

## 硬规则（摘要）

- **权威链**：用户当轮指令 > `WORKFLOW.md`（canonical） > `roles/*.md` > `templates/**` > `SPEC.md`（只能加严） > `DESIGN.md`/`EVOLUTION.md`/`WORKFLOW-TAGS.md`/`EXAMPLE.md`（非规范）；冲突按 `WORKFLOW.md §0` 裁决。
- **文档是唯一交互源**：只用 run 目录内的文档交接，不在会话里传正文。
- **单一写者**：每个文档只有一个写者（见 `WORKFLOW.md` 文档契约表）；`PROJECT.md` 归 PMO，仅 S0 bootstrap 窗口 MAIN 可填 §0 元信息与 §1 G1 目标/终止判据，PMO 接管后 MAIN 不得再写。
- **先领锁再写 STATUS**：写 `STATUS-Round-*.md` 前必须 `python3 scripts/wf.py lock <run-id>`，写完（可选提交）再 `unlock`；一次只追加一条。
- **不越权读**：TDO/QA 不读与本轮无关的历史轮次；主会话不读 STATUS / ISSUES 正文（只看 `PROJECT.md` §6 上报区与 `DECISIONS.md`）。
- **不自行拍板**：遇到分歧写进文档升级，不替主会话做决定。
- **选型先查基准**：新建/大改 run 特化前先读 `templates/baseline/REGISTRY.md` 与 `templates/contracts/README.md`；`SPEC.md §0` 必须声明 `baseline:` 与 `contracts:`（无 baseline 写 `none + 理由`）。基准模板不是 run 模板，不能直接 `--template`。
- **SAFETY 仅按需且独立**：只有 `SPEC.md` 明示启用安全门控时才设 SAFETY；它只审 `gate.status=FAIL` 的 action，只写 `safety/reviews/ACT-*.json`，不得执行 action、不得写四件套（见 `roles/SAFETY.md` 与 `roles/common-contract.md` 第 16 条）。
- **状态迁移唯一执行者**：state 变化按 `WORKFLOW.md §4.0` 矩阵执行，非本表执行者不得迁移。
- **关闭先过 linter**：置 `PROJECT closed` 前运行 `python3 scripts/wf_close_lint.py --run <run-id>`，ERROR 必须为 0；历史缺口见 `reports/close-lint-20261111.txt`。
- **改模板/索引先跑一致性检查**：改 `templates/**`、`BASELINE-MAP.md`、`WORKFLOW-TAGS.md` 或角色命令后运行 `python3 scripts/doc_consistency.py --check`，ERROR 必须为 0。
- **收口**：已知游离项按「关闭收口规则」「跨轮承接规则」处理（`WORKFLOW.md §3.1/§6/§7`）；本工作流不设额外常设角色，不新建游离台账。
- **不碰正式域**：本目录不在 KB 正式区（`00-overview/` 等 8 个目录），工作流产出不要写进那里；仓库根 `AGENTS.md` 与 `00-overview/task-router.md` 只作边界确认。
- **不登记 DSH 工作区**（2026-10-23）：`runs/<run-id>/` 是产物目录，不是 DSH 工作区。座位会话用 `tools/dsh-web-shim`（`OPENRIG_DSH_BIN`）起，shim 只建会话、不建 workspace；要浏览 run 文件用已登记的「deepseek-知识库」工作区，别再给 run 目录 `workspace/create`。
