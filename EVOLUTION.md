# EVOLUTION — 演进与特化台账（非规范）

> **非规范**：本文件是台账/说明，不是规则，也不是第二事实源。与 `WORKFLOW.md` / `roles/` / `templates/` 冲突时以后者为准。
> 依据 `DESIGN.md` §6–9、14 个 closed run、13 个特化模板、插件仓本地化副本；每条给 `DESIGN.md §` / `run-id` / `commit` 至少一种证据。
> **阅读法**：三轴——进阶（能力上线顺序）/ 本地化（跨仓适配）/ 特化（按目录 SPEC）。条目字段：`方向 | 动机 | 改了什么 | 证据 | 状态`，每条 1–2 行。
> **维护**：append-only；无证据不写；规则变化以 `WORKFLOW.md` 为准，`DESIGN.md` 只记录理由。

## 1. 进阶轴（流程能力上线顺序）

| 方向                            | 动机                                 | 改了什么                                                              | 证据                                                                                                 | 状态   |
| ------------------------------- | ------------------------------------ | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------ |
| 文档即接口                      | 主会话只看 §6，不能读正文            | 四件套 + `wf-doc` 元信息块 + PROJECT §6 唯一上行通道                  | `DESIGN.md` §1                                                                                       | 已落地 |
| 锁 + 逐条提交                   | 多 TDO 并发写同一 STATUS 会覆盖      | 目录锁（`mkdir` 原子）+ 一条一提交                                    | `DESIGN.md` §2；`WORKFLOW.md` §5；`runs/signaldeck-runtime-20261014/STATUS-Round-1.md` WS-2 薄弱点 3 | 已落地 |
| 状态机 + doctor                 | 流程"卡在哪"要机械可判               | 显式 state 值 + `wf.py doctor` 体检                                   | `DESIGN.md` §1；`runs/wf-engine-tests-20261014`                                                      | 已落地 |
| opencode 直连                   | 省人工粘贴 brief                     | `serve/delegate`（v1 同步 API，仅 opencode 1.x）；默认 `minimal` + flash | `DESIGN.md` §6；`WORKFLOW.md` §9（实测 2026-10-12）                                                  | 已落地 |
| 真实项目（白名单/squad/ledger） | 项目仓混有他人改动，越界成本高       | PROJECT §0 写权限白名单；`squad` 并行；`ledger` 记账；只 add 明确路径 | `DESIGN.md` §7；`WORKFLOW.md` §9.1；`runs/signaldeck-runtime-20261014`                               | 已落地 |
| SPEC 特化                       | 真实场景"一目录一任务"，白纸规划太慢 | `SPEC.md` + `new-run --template`；四条约束不可覆盖                    | `DESIGN.md` §8；`templates/specialized/kb-debt-burn/SPEC.md`；`runs/kb-debt-20261013`                | 已落地 |
| burner                          | 无人值守烧额度                       | `burner/run_queue.py` 顺序拉起主会话，写 `runs/<id>/DONE`             | `DESIGN.md` §9；`WORKFLOW.md` §9.2；`runs/burn-postmortem-20261014`                                  | 已落地 |
| 幂等 / 心跳 / 余额差记账        | 重跑、卡死、低估烧额三类事故         | DONE/BLOCKED 先查；`heartbeat_sec`；逐 pack 记余额差                  | `WORKFLOW.md` §9.2；`DESIGN.md` §9；`burner/burner.log`（kb-debt 重跑 63664 tokens）                 | 已落地 |

## 2. 本地化轴（跨仓适配）

> 实例：插件仓副本 `/home/dev/Desktop/deepseek/obsidian-nutstore-sync-phone-ai-tools/workflow-group/`（适配日 2026-10-15）。
> 字段：`上游形态 | 本地形态 | 落点文件 | 坑与约束`。

| 上游形态                             | 本地形态                                                                | 落点文件                           | 坑与约束                                                                                                                                                                          |
| ------------------------------------ | ----------------------------------------------------------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| opencode 直连 `serve/delegate/squad` | 本机 opencode 为 v2.x（2026-10-15 实测 v2.0.21，2026-10-20 为 v2.0.32）：v1 HTTP 端点与 v2 不兼容（`/api/health` 404、`POST /session` 405；v2 在 `/api/*` + Basic 认证）→ 插件线新增 `scripts/opencode_delegate.py`（`opencode run --format json`）；`dsh_delegate.py` 保留备选。**本仓 `scripts/` 未内置这两个 adapter** | 插件线 `LOCALIZATION.md` §2.1 | `wf.py serve_start` 已加 v2 版本守卫：在拼 `--pure`/发 HTTP 前 rc=1 + 可执行提示；`delegate`/`squad` 默认自动拉起服务，因此同经此失败；显式 `--server` 指向 v1 服务保留原路径。v2 实际委派需 `opencode run` 或外部 adapter（插件线 `opencode_delegate.py`）。v2 HTTP 适配登记插件线 EVOLUTION §5（冷启动/无 session 成本，见 DESIGN §6） |
| `python3` 直接跑                     | `workflow-group/.venv/bin/python`                                       | `LOCALIZATION.md` §2(L43–45)       | 系统 `python3` 无 pip/openpyxl，导入 openpyxl 退出 3（硬失败，非 SKIP）；`doctor` / `pytest(test_issues)` 必用 venv                                                               |
| `burner/` 烧额度调度器               | 未复制                                                                  | `LOCALIZATION.md` §1(L14)          | `serve/delegate/squad` 不可用；保留 `brief` 供在其他环境人工执行                                                                                                                  |
| `--also` 相对仓库根                  | 按**当前工作目录**解析                                                  | `LOCALIZATION.md` §2(L47–54)       | 混用（在 `workflow-group/` 下传 `workflow-group/runs/...`）→ `workflow-group/workflow-group/...`，`git add` 128，进度落盘未提交；`dsh_delegate.py` 生成提示当前即混用（待 R2 修） |
| 默认提交                             | `--no-commit`                                                           | `LOCALIZATION.md` §2(L55–56)       | 本机 `.git/` 只读，提交必失败；改用 `--no-commit` 并在回执说明                                                                                                                    |
| `ROOT` 指向 KB `workflow-group/`     | 自动指向本仓 `workflow-group/`；项目根 `--project-root "$PWD"`          | `LOCALIZATION.md` §1(L11–12)       | 避免路径漂移；run 实例化时写入真实路径                                                                                                                                            |
| 四件套 + DECISIONS 账本              | 与仓库 `.ticket-store` 票仓真源分离                                     | `LOCALIZATION.md` §3(L62–63)       | 两边不互写：落票写 `.ticket-store/tickets/00NN.toml` 的 `[[items]]`，不新增票号；deck map/issue 不替代四件套                                                                      |
| 上游资料直接落盘                     | 只记自有审计结论/链接                                                   | `LOCALIZATION.md` §4(L65–68)       | notools（`lizongying/notools`）2026-10-15 无 LICENSE，不落盘其文档/源码；缓存 `docs/reference/notools/.cache/` 不入 git                                                           |

## 3. 特化轴（按目录 SPEC 台账）

> **2026-10-23 分层更新**：canonical 新增 `templates/contracts/`（7 个冻结原子轮型 + PLAN-GATE/VERDICT + LOCK）和 `templates/baseline/`（当前 9 个复合类型基准模板，历史时点为 10 个）；当前 namespace 分 atomic / baseline / specialized。逐项标签、主攻方向和成熟度见 `WORKFLOW-TAGS.md`、`templates/baseline/REGISTRY.md`。下列旧表只保留历史领域模板记录，不再代表全部特化资产。

> 13 个特化模板逐行（复算：`ls templates/specialized | grep -v README.md | wc -l`=14，含本 run 模板 `wf-docs-distill`；既有 13）。
> 字段：`模板 | 场景 | 关键分区 | 实测 run | 状态`。

| 模板                        | 场景                             | 关键分区                         | 实测 run                          | 状态   |
| --------------------------- | -------------------------------- | -------------------------------- | --------------------------------- | ------ |
| `kb-method-action`          | 方法论实战验证 + 消费闭环        | 写权限分区 + 全内容/证据         | `kb-method-action-20261014`       | closed |
| `signaldeck-runtime-verify` | 回答"它真的能跑吗"               | 写权限 + 证据格式                | `signaldeck-runtime-20261014`     | closed |
| `kb-claim-verify`           | KB 全库断言核验（长跑）          | §2 写权限 + §3 全内容 + §4 证据  | `kb-claim-verify-20261014`        | closed |
| `burn-postmortem`           | 烧额度复盘与工作流回写           | §2 写权限 + §3 证据 + §5 DoD     | `burn-postmortem-20261014`        | closed |
| `nutstore-sync-review`      | nutstore 个人版全盘审查修订      | §3 一 WS 一目录（8 片）          | `nutstore-review-20261014`        | closed |
| `kb-consume-interface`      | KB 消费接口与检索增强            | §1 热文件互斥 + 精确到文件写权限 | `kb-consume-20261014`             | closed |
| `kb-fix-wave`               | KB 按票修订 + 断言门禁化         | §1 域互斥 + §2 门禁化            | `kb-fix-20261014`                 | closed |
| `project-freeze-facts`      | 冻结声明红 + 隐藏差量 + 契约补测 | §1 文件互斥（父仓）              | `project-freeze-20261014`         | closed |
| `dist-ops-hardening`        | 分发/同步/运维加固               | §1 R1 三路 + §2 R2 单写者        | `dist-ops-20261014`               | closed |
| `geophysics-correctness`    | 物探正确性回归与格式契约         | §1 仓库内文件互斥（3 路）        | `geophysics-correctness-20261014` | closed |
| `wf-engine-tests`           | 引擎测试 + CI + P5 遗留          | §1 两路 + §2 R2 收遗留           | `wf-engine-tests-20261014`        | closed |
| `ops-reliability`           | 在跑自动化可靠性 + 入口健康      | §1 R1 三路 + §2 R2               | `ops-reliability-20261014`        | closed |
| `kb-debt-burn`              | KB 欠账清理（唯一带预填四件套）  | §2 多 WS 写权限（含正式域豁免）  | `kb-debt-20261013`                | closed |

**方向归纳**：审计（claim-verify / signaldeck-runtime-verify）→ 修复（kb-fix-wave / project-freeze-facts）→ 取证/回归（geophysics-correctness）→ 收口（dist-ops-hardening / nutstore-sync-review）→ 运维（ops-reliability）→ 自测（wf-engine-tests / burn-postmortem）→ 消费闭环（kb-consume-interface / kb-method-action）。除 burner 类"纯自测"外暂无新形态；`signaldeck-audit-20261013` 无对应特化模板（走 `kickoff/signaldeck-full-audit-burn.md`）。

## 4. 复制 checklist（新仓适配）

- **带什么**：`scripts/`（`wf.py` + `issues.py`）、`roles/`、`templates/`、`WORKFLOW.md`；`burner/` 与 opencode 直连按目标环境决定是否带。
- **换什么**：`ROOT` / 项目根（`--project-root`）、依赖声明（`requirements.txt`）、历史 `runs/`（默认只留 `README.md`）、特化模板（按需复制，不必全带）。
- **首跑验证**：`workflow-group/.venv/bin/python workflow-group/scripts/wf.py doctor <run-id>`（无新增 error）+ `python3 -m pytest workflow-group/tests -q`（全绿）；本仓无内置 v2 CLI adapter：自动委派需插件线 `opencode_delegate.py`（`opencode run` 封装）或直接 `opencode run`；`wf.py delegate/squad` 仅适用 opencode 1.x（v2 下经 `serve_start` 守卫 rc=1，提示改用 `opencode run` / `OPENCODE_BIN`）。备选 `dsh_delegate.py`（同样在插件线）。

## 5. 未决与待验证

- `dsh_delegate.py` 生成的本地化提示与 `LOCALIZATION.md` §2 的 `--also` 基准**互相矛盾（混用形态）**，待本地化副本 R2 修（`LOCALIZATION.md` L54）。
- 本仓 opencode 直连在权限含 `git push=ask` 时无人值守会卡住，需在建 session 传 `permission` 白名单（`WORKFLOW.md` §9 规则 7，尚未在 `delegate` 暴露）。
- 本 run 特化模板 `wf-docs-distill` 的去留（PROJECT §6 Q-4）由主会话收轮拍板，本文件不预判。

### 5.1 待办候选（口述登记，未立项）

> 来源：用户 2026-10-15 口述，主会话原文登记（分五次追加，编号连续）；`T-01`–`T-08` 供后续 run / issue 引用。
> **未立项**：无 owner、无排期、无证据，不构成承诺，也不得作为待办来源；立项时必须另开 run 或在 ISSUES 登记，写 owner/去向/最晚复核轮，并在两条轴（进阶/特化）补证据。

| #    | 待办                       | 动因（原文口径）                                                                                    | 现状/回链                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | 候选方向                                                                                                                                                                                                                      | 状态   |
| ---- | -------------------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| T-01 | 并行工作流状态与资源占用   | 并行容易冲突和挤爆内存；要优化为统一注册入口和预计占用声明                                          | `DESIGN.md` §2（锁只保 STATUS 写入）、§5（锁不保产出物）、§7（`squad` 并发发 session）                                                                                                                                                                                                                                                                                                                                                                                                                                              | 并行前统一注册（run / WS / 独占资源）+ 声明预计占用（内存/进程/并发槽位），按声明准入与排队                                                                                                                                   | 待评估 |
| T-02 | 零散工作流纳入管理         | 不纳入管理最后都是散乱状态；可考虑做个插件承接工作流的登记和分发                                    | `runs/` 18 个实例、`templates/specialized/` 14 套模板；尚无统一入口/生命周期视图                                                                                                                                                                                                                                                                                                                                                                                                                                                    | 插件面板作登记/分发入口；run 元信息（goal / 模板 / state / owner）可发现、可追溯                                                                                                                                              | 待评估 |
| T-03 | 特化方式沉淀               | 不能每次都现场特化；可在插件面板加上特化模板                                                        | `DESIGN.md` §8（`SPEC.md` + `new-run --template`）、本文件 §3 特化轴                                                                                                                                                                                                                                                                                                                                                                                                                                                                | 把模板选择/生成/回填固化进面板，与 `wf.py new-run --template` 打通                                                                                                                                                            | 待评估 |
| T-04 | 项目库入库工作流与录入状态 | 项目库的入口需要特定的入库工作流；知识库需要录入状态，避免每次都重新扫                              | `content-review-queue.md` §6（Map4 #31 intake 台账：只覆盖核验队列 8 项，非源级录入状态）；`README.md`（项目 baseline / 项目登记）；`_reference/知识库构建注意事项/知识库本地化注意事项-入库肢解与细分规则.md`（入库肢解规则，参考区非规范）                                                                                                                                                                                                                                                                                        | 定义项目源 → KB 的固定入库工作流（登记 → 变更判定 → 肢解落位 → 门禁），并加源级录入状态（未登记/已登记/已肢解/已入正文/待复核 + 锚定 commit），每轮只扫状态非终态或源 commit 变化的项目                                       | 待评估 |
| T-05 | 拆解统一方案与拆解重做     | 需要综合 60- 的拆解流程和 obsidian 的拆解统一流程，制定更完善的拆解统一方案，做更完善的拆解梳理重做 | `60-外部仓库/workflow-group/README.md`「本副本特化：研究拆解」（research-decompose：D 发散/M 落实/X 执行）；`60-外部仓库/workflow-group/runs/lingshu-asset-decompose-20261016/SPEC.md`（全量拆解 → 资产索引 → 语义分块 → 架构优化）；`obsidian-nutstore-sync-phone-ai-tools/workflow-group/runs/nutstore-refactor-prep-20261016/reports/refactor-partition.md`（362 文件 P1..P9+Z0 唯一归属）及其 `freeze-baseline.md` / `gates-baseline.md`；`.../templates/specialized/nutstore-sandbox-refactor/SPEC.md`（按分区波次、行为不变） | 抽一套统一拆解契约：清点（100% 覆盖 + 唯一归属）→ 分块/分区 schema → 接口冻结与门禁基线 → 波次执行与覆盖对账；按对象类型（代码仓/文档集/研究主题）参数化，沉淀为统一 `decompose` 模板/SOP，再用它把目标对象的拆解梳理重做一遍 | 待评估 |
| T-06 | 插件各工作流状态显示       | 插件各工作流状态显示                                                                                | `scripts/wf.py`（state 存于各文档 `wf-doc` 头，如 `templates/PROJECT.md: state:`；`doctor <run-id> --json` 只覆盖单 run）；`DESIGN.md` §4「不做 Web UI/看板：避免第二个事实源」；与本表 T-02（登记/分发）、T-03（模板面板）同属插件面板簇                                                                                                                                                                                                                                                                                           | 面板提供只读「各工作流状态」：聚合 run 列表 + state / 轮次 / 编制 / 锁 / 阻塞 / 最近提交，数据直接读 `runs/<id>/**` 与 `doctor --json`，不建独立台账；写操作仍只走 `wf.py`                                                    | 待评估 |
| T-07 | 多轮工作流自动化           | 多轮工作流自动化                                                                                    | `DESIGN.md` §4「不做自动调度（主会话手动发委派）：调度逻辑靠状态机，本阶段人/主会话更便宜」；`WORKFLOW.md` §3（一轮 S1–S5 仍由主会话在 S5 拍板）、§7（终止判据）、§9.2（burner 只按 pack 顺序拉起主会话，轮内 `new-round`/`delegate` 仍手动）；`burner/run_queue.py`（等 `runs/<id>/DONE` 才拉下一个 pack）                                                                                                                                                                                                                         | 把 S5 之外的多轮循环自动化（PMO→TDO→QA→PMO→`new-round`），停机条件复用 §7 终止判据 + `doctor` + 预算/余额阈值；保留人工叫停与「分歧不落地」，状态迁移仍只按 §4.0 矩阵执行；与 T-01 强耦合（自动多轮会放大并发与烧额）         | 待评估 |
| T-08 | 待定                       | 用户预留                                                                                            | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | 待补充                                                                                                                                                                                                                        | 占位   |

## 6. 与 DESIGN 的关系（不重复造）

本文件只做时间线/台账：每条回链 `DESIGN.md §` / `run-id` / `commit`；**不收编、不改写 `DESIGN.md` §6–9**（依据 `runs/wf-docs-distill-20261015/DECISIONS.md` D-003）。
