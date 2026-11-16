# SPEC — 工作流文档提炼（示例参考 + 演进说明）

## 0. 分层声明

baseline: composite/postmortem-meta-governance@1.0.0
contracts: audit@1.0.0, strategy@1.0.0, optimize@1.0.0, verify@1.0.0

> 本文件是本 run 的**特化规则**，与通用 `WORKFLOW.md`/`roles/*` 冲突时以本文件为准。
> 通用规则仍然有效：文档即接口、单一写者、STATUS 加锁逐条提交、分歧不落地。
> 目标：`workflow-group/` 自身（KB 母本）。本 run 产出物是**非规范文档**，不是第二事实源。

## 1. 任务

把已积累的实测结果（14 个 closed run、13 个特化模板、`DESIGN.md` §6–9、插件仓本地化副本）提炼成两份**非规范**文档，服务“可拷贝、可参照、可特化”：

1. `EXAMPLE.md` — **示例参考 / 标本**：一个新 run 从模板到收口长什么样，一轮怎么走完，合格线在哪。
2. `EVOLUTION.md` — **演进与特化说明 / 台账**：按进阶 / 本地化 / 特化三轴记录“往哪改、改了什么、证据、现状”。

两文件页首必须写明：非规范；冲突以 `WORKFLOW.md` / `roles/` / `templates/` 为准。

## 2. 写权限分区（一份写权限只给一个 WS）

| WS | 写权限（相对 `workflow-group/`） | 只读输入 | 产出物 | 波次 |
| --- | --- | --- | --- | --- |
| WS-1 | `EXAMPLE.md`（新建）；`runs/<RUN-ID>/reports/ws1-example.md` | `README.md`、`WORKFLOW.md`、`roles/*`、`templates/*`、全部 `runs/*`（重点 STATUS/DECISIONS/DELEGATIONS） | `EXAMPLE.md` + 选材与证据报告 | R1 |
| WS-2 | `EVOLUTION.md`（新建）；`README.md`（**仅目录地图加两行**）；`runs/<RUN-ID>/reports/ws2-evolution.md` | `DESIGN.md`、14 个 run、13 个特化模板、`kickoff/*`、插件仓副本 `LOCALIZATION.md` 与 `runs/nutstore-tools-rebuild-20261015/**` | `EVOLUTION.md` + README 两行 + 台账证据报告 | R1 |

写权限互斥；除上表外不改任何文件。**不改** `WORKFLOW.md`、`roles/**`、`templates/**`、`scripts/**`、`DESIGN.md`、既有 `runs/**` 实例。

## 3. 覆盖要求（硬）

### WS-1：`EXAMPLE.md` 必须覆盖

1. 选材说明：主标本 run-id、选择理由、适用流程版本、复核日；
2. 模板 → 实例：`templates/` 到 `runs/<id>/` 的目录树对照；
3. 四件套带注释摘录（每段 5–15 行）：PROJECT 头/§1/§4/§6；STATUS 进度/阻塞/交接；DECISIONS 一条 D-xxx；ISSUES 一行 P/R/C；
4. 一轮 copy-paste 流水：new-run → brief pmo → delegate pmo → brief tdo ×N → append-status → state qa-pending → brief qa → PMO 收轮 → 主会话 DECISIONS → new-round/closed；每步一行 DoD + 常见坑指针；
5. 至少 3 个最小变体（TDO×1 快跑 / TDO×N 并行 / 带 SPEC 特化），各指向真实 run-id；
6. 真实 run 证据索引：14 个 run 按场景归类（burn / 真实项目 / 多轮收口 / 自测 / 复盘…）；
7. 维护说明：流程版本变化后重新摘录，不在旧例上打补丁。

### WS-2：`EVOLUTION.md` 必须覆盖

1. 阅读法：三轴 + 字段（方向 | 动机 | 改了什么 | 证据 | 状态），每条 1–2 行；
2. **进阶轴**：文档即接口 → 锁 + 逐条提交 → 状态机 + doctor → opencode 直连 → 真实项目（白名单 / squad / ledger）→ SPEC 特化 → burner → 幂等 / 心跳 / 余额差记账；
3. **本地化轴**：上游形态 | 本地形态 | 落点文件 | 坑与约束；至少覆盖（无 opencode → dsh headless、openpyxl 解释器、无 burner、`--also` 基准、git 只读 → `--no-commit`、路径漂移、票仓/deck 只读边界）；
4. **特化轴**：13 个特化模板逐行台账（模板 | 场景 | 关键分区 | 实测 run | 状态）+ 方向归纳（审计 / 修复 / 取证 / 收口 / 运维 / 自测…）；
5. 复制 checklist：带什么、换什么、首跑验证（`doctor` + `pytest`）；
6. 未决与待验证；
7. 维护规则：append-only；无证据不写；规则变化以 `WORKFLOW.md`/`DESIGN.md` 为准。

## 4. 证据规范

| 类型 | 必须给的证据 |
| --- | --- |
| EXAMPLE 摘录 | 可定位到 `runs/<id>/文件 + 小节/行`；个人路径用占位符 |
| EVOLUTION 每条 | `run-id` / `commit` / `DESIGN.md §` 至少一种 |
| 统计数字 | 复算命令（如 `ls runs | wc -l`、`ls templates/specialized`） |
| 本地化实例 | 文件名 + 具体行/小节；引用插件仓时给出仓库名与路径 |

## 5. 禁止

- 不复述、不改写 `WORKFLOW.md` 规则，不引入新规则；两文件均不得写成规范语气。
- 不改白名单外路径；不改既有 run 原件；不改 `templates/**`、`roles/**`、`scripts/**`、`DESIGN.md`。
- 不虚构 run、数字、引文；所有摘录必须来自已 DONE 的真实 run。
- 不选 `signaldeck-audit-20261013` 当主标本（153 文件 / 39 委派，极端值）。
- 不 `git add -A`；提交由主会话按轮统一做。

## 6. 完成定义（DoD）

- `EXAMPLE.md`：≤250 行；§3 每段摘录 ≤15 行；7 项全覆盖；每段有可定位证据。
- `EVOLUTION.md`：≤200 行；三轴完整；13 模板逐行；每条有证据。
- `README.md`：目录地图新增 EXAMPLE/EVOLUTION 两行，原表格与其余内容不变。
- 两文件页首有非规范声明（`grep -n "非规范"` 可查）。
- `runs/<RUN-ID>/reports/ws1-example.md`、`ws2-evolution.md` 产出，含数字复算命令。
- `python3 -m pytest tests -q` 通过；`python3 scripts/wf.py doctor <RUN-ID>` 无新增 error。

## 7. 波次建议

- R1：WS-1 / WS-2 并行（写权限互斥）。
- 若 QA 发现缺口，R2 只做补洞，不扩范围。
