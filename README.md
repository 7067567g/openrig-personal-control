# workflow-group — 工作流组（文档即接口的多智能体工作流）

> 一个用四份文档驱动 PMO / TDO / QA 智能体协作的工作流组；安全关键特化 run 可另设独立 SAFETY 逐条复核门控失败的动作。
> 主会话做**委派、收账、拍板，以及流程编排 / 统一提交 / 关停**（见 `roles/MAIN.md`）；智能体之间只通过文档交接。
> 文档地图：本仓文档入口见下文「目录地图」；跨仓总图见 [docs/openrig/README.md](docs/openrig/README.md)。
> 改道：历史 `runs/**` 与 `docs/cases/**` 是证据/复盘，**不是当前规范**；当前规范是 `WORKFLOW.md` 与角色手册。

## 环境

- Python 3.12（仓库根 `workflow-group/.venv`）+ Node.js 24；`issues.py` 依赖 `openpyxl`。
- **推荐先激活 venv**：`source .venv/bin/activate`。之后的 `python3 scripts/...` 才会使用带 `openpyxl` 的解释器。
- 依赖清单：`requirements-dev.txt`（openpyxl、pytest）。有网络时：`./scripts/bootstrap_env.sh` 或 `uv pip install -r requirements-dev.txt`。
- 离线环境：`scripts/test.sh` 会在 venv 缺 pytest 时回退系统 `dist-packages`；长期仍建议补装。
- 默认 `opencode` CLI 已更新到 **v2.2.7**；`wf.py delegate/squad` 的 v1 HTTP 通道只支持 opencode 1.x，因此当前请用 `wf.py brief` + 人工粘贴；如需自动委派，用 `OPENCODE_BIN` 指向 1.x。OpenRig 双平面需要 `dsh`（本机在 `~/.local/bin/dsh`）。
- 常用检查：
  ```bash
  ./scripts/test.sh                                     # 全量 workflow-group 测试
  python3 scripts/doc_consistency.py --check            # 模板/索引/引用一致性
  python3 scripts/wf_close_lint.py --run <run-id>       # 关闭语义门禁
  ```

## 30 秒上手

```bash
cd workflow-group
source .venv/bin/activate   # 使用带 openpyxl 的 Python

# 1) 开局：从模板复制四件套，填目标，建锁目录
python3 scripts/wf.py new-run <run-id> --goal "一句话目标" --tdo 2
#    特化模板（推荐用于真实项目/专项）：--template templates/specialized/<name>
#    H 盘整理（门控 + 独立安全审核员）：
#    python3 scripts/wf.py new-run h-drive-cleanup-YYYYMMDD --template templates/specialized/h-drive-cleanup --tdo 1
#    python3 scripts/wf.py new-run <run-id> --template templates/specialized/kb-debt-burn --goal-file ...

# 2) 主会话生成 PMO 委派消息（贴给 opencode 的 V4.1-Flash 会话）
python3 scripts/wf.py brief --role pmo --run <run-id>
#    PMO 写完 PROJECT.md 回执 → 主会话不读正文

# 3) 按编制数发 TDO 委派；TDO 用一条命令追加进度（自动加锁+提交）
python3 scripts/wf.py brief --role tdo --run <run-id> --agent tdo-a1
python3 scripts/wf.py append-status <run-id> --agent tdo-a1 --ws WS-1 \
  --action "完成 X" --evidence "路径/命令" --also <产出物>

# 4) 主会话切 QA → QA 核查 → PMO 收轮 → 主会话读 PROJECT §6 写 DECISIONS → 下一轮
python3 scripts/wf.py state <run-id> STATUS qa-pending --by main
python3 scripts/wf.py brief --role qa --run <run-id>
# QA 完成后执行: python3 scripts/wf.py state <run-id> STATUS qa-done --by qa
python3 scripts/wf.py brief --role pmo --run <run-id>          # S4 收轮
python3 scripts/wf.py state <run-id> PROJECT waiting-main --by pmo
# 主会话只读 PROJECT §6，写 DECISIONS.md（D-xxx + 编制 N'）
python3 scripts/wf.py new-round <run-id>

# 可选：直连 opencode API 自动委派（省去人工粘贴；详见 WORKFLOW.md §9）
python3 scripts/wf.py serve start
python3 scripts/wf.py delegate <run-id> --role pmo --timeout 900
python3 scripts/wf.py delegate <run-id> --role tdo --name tdo-a1
python3 scripts/wf.py delegate <run-id> --role qa
# 高并行（一次发 N 个 TDO，各自唯一 WS）
python3 scripts/wf.py squad <run-id> --agents 'tdo-a1:WS-1,tdo-a2:WS-2' --timeout 3600
python3 scripts/wf.py ledger <run-id>          # 烧额度账本
python3 scripts/wf.py serve stop

# 随时体检
python3 scripts/wf.py doctor <run-id>
python3 scripts/wf_close_lint.py --run <run-id>   # 关闭前必须 ERROR=0
python3 scripts/doc_consistency.py --check         # 改模板/索引/角色后必跑
```

## 目录地图

| 路径 | 作用 |
| --- | --- |
| `WORKFLOW.md` | **规范正文**：角色、状态机、文档契约、锁协议、升级与退出 |
| `AGENTS.md` | 进入本目录的 Agent 硬入口（先读角色手册） |
| `DESIGN.md` | 设计取舍、可调参数、本次不做的（YAGNI） |
| `EXAMPLE.md` | **当前 v1.2 示例参考（非规范）**；主标本见 EXAMPLE §1 |
| `EVOLUTION.md` | **非规范**：历史演进/特化台账（以 2026-10-15 记录为基线）；当前标签、冻结原子契约与基准模板见 `WORKFLOW-TAGS.md` |
| `WORKFLOW-TAGS.md` | **非规范**：OpenRig + 旧工作流多标签索引、成熟度标记、横向比对与标准特化候选；机器清单见 `workflow-tags.json` |
| `ADVISOR-GEMINI4ARGON-20261023.md` | **非规范**：外部发展顾问报告（隔离只读范围；针对双轨协议、模板三层、OpenRig 双平面、治理与路线图） |
| `ADVISOR-GEMINI4ARGON-DSH-20261023.md` | **非规范**：同一模型的纯 DSH/纯任务提示版本（无 persona，只读隔离范围） |
| `ADVISOR-QUALITY-COMPARISON-20261023.md` | **非规范**：OpenCode vs 纯 DSH 两套顾问结果的范围、指标、质量评分、共识与分歧裁决 |
| `roles/` | 主会话手册（`MAIN.md`）+ PMO/TDO/QA 手册 + `SAFETY.md`（安全关键 run）+ `delegation-briefs.md` 委派/回执模板 |
| `templates/` | 四层：四件套母版；`contracts/` 冻结原子轮型；`baseline/` 复合类型基准模板（重点参考）；`specialized/` 可实例化领域特化 |
| `scripts/wf.py` | 编排器：开局/新轮/状态/锁/追加进度/生成委派消息/体检/serve 与 delegate |
| `scripts/issues.py` | `ISSUES.xlsx` 读写：init/add/list/update/close/export |
| `scripts/wf_close_lint.py` | 关闭语义只读 linter：检查 closed run 的 active open、挂起 S1/S2 决策回链、终态决策、STATUS 未完成行；不修改文件 |
| `scripts/doc_consistency.py` | 模板/索引/引用一致性校验：specialized↔BASELINE-MAP、baseline↔REGISTRY、TAGS 计数、WORKFLOW §引用、角色命令 `--by` |
| `scripts/test.sh` | 统一测试入口；优先 `.venv/bin/python`，离线时回退系统 pytest |
| `requirements-dev.txt` | 开发依赖：openpyxl、pytest |
| `kickoff/` | 面向新会话的启动文档（含可直接粘贴的提示词 + 目标文件） |
| `runs/` | 实际项目实例，一个项目一个目录 |
| `burner/` | 烧额度调度器：顺序拉起主会话（官方 key）跑任务包，写完 `runs/<id>/DONE` 再拉下一个 |

## 四件套

| 文档 | 写者 | 回答什么问题 |
| --- | --- | --- |
| `PROJECT.md` | PMO | 目标/范围/指标/分任务/轮次结论/给主会话的上报 |
| `STATUS-Round-n.md` | TDO（持锁） | 本轮进度/下一步/阻塞（逐条提交） |
| `ISSUES.xlsx` | QA | 问题/风险/变更（含严重度与是否需主会话决策） |
| `DECISIONS.md` | 主会话 | 每轮已确认决策 + 编制（子智能体数量）变更 |

> 规则：state 变化按「状态迁移唯一执行者」矩阵（`WORKFLOW.md §4.0`）执行；已知游离项按「关闭收口规则」「跨轮承接规则」收口（`WORKFLOW.md §3.1/§6/§7`）。本工作流不设额外常设角色，不新建游离台账。

## 与知识库的关系（重要）

- 本目录**不在** KB 正式域（`00-overview/` 等 8 个目录）内，不参与 `kb-validate` / `generate-views` / 正式检索。
- 工作流产出不要写进正式域；需要沉淀为 KB 正文时，另走 KB 的正式入库流程（frontmatter + 门禁）。
- 仓库根 `AGENTS.md` 与 `00-overview/task-router.md` 只用于边界确认，不改变本目录的运行规则。


## 烧额度调度器（burner）

```bash
# 自检（起服务 + 官方 key 跑一条最小消息）
python3 burner/run_queue.py --probe
# 后台常驻：按 queue.json 顺序拉起主会话，直到队列跑完 / 余额低于下限 / 出现 STOP
setsid nohup python3 burner/run_queue.py >> burner/runner.out 2>&1 &
# 看调度日志（不是会话内容）
tail -f burner/burner.log
# 停止：当前会话结束后生效
touch burner/STOP
```

- 主会话模型在 `burner/queue.json` 的 `main_model`（官方 key：`deepseek/*`；官方 API 无 4.1-flash，只有 `deepseek-flash` 与 `deepseek-v4-pro`）。
- 外层服务只做"拉主会话"；主会话自己用 `wf.py serve/delegate/squad` 跑工作流，worker 走 opencode 额度。
- 日志与状态在 `burner/`（已 gitignore），不改读会话正文；完成信号 = `runs/<run-id>/DONE`。
- **幂等**：启动 pack 前若已存在 `runs/<id>/DONE`（或 `BLOCKED`）会 `SKIP`；要重跑先删该文件。
- **可见性/超时**：单条 send 期间每 `heartbeat_sec`（默认 300s）记一条 `HEARTBEAT`；`send_timeout_sec` 默认 7200（2h）。
- **记账**：session `cost` 远小于真实消耗，逐 pack 以「官方余额差」为准（`PACK ... 余额 ¥a → ¥b（Δ¥c）`）。
