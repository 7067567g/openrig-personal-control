<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: PROJECT
owner: PMO
state: pmo-plan
updated: <DATE>
-->

# PROJECT — <PROJECT-NAME>

> 写者：PMO ｜ 主会话只读 §6（+ 本文件头状态字段）｜ 其他角色只读本文件 + `SPEC.md`
> 特化：本文件已预填判据/范围/分区；PMO 只需校验、细化与补 §6。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | `<GOAL>` |
| 项目根 | `<PROJECT-ROOT>` |
| 写权限白名单 | `<WRITE-SCOPE>`（TDO 只许改这些路径；违反按事故记 ISSUES） |
| 只读边界 | `WORKFLOW.md`、`roles/**`、`templates/**`、`scripts/**`、`DESIGN.md`、既有 `runs/**`、插件仓整仓只读 |
| 主会话 | 人/主会话模型 |
| 编制 | PMO×1 / TDO×<TDO-N> / QA×1 |
| 当前轮次 | Round <ROUND-N> |
| 终止判据 | 达成：G1–G3 全过且 ISSUES 无 open S1/S2；终止：连续 2 轮无进展或主会话叫停 |

## 1. 目标与成功判据

- **G1 示例参考可参照（EXAMPLE.md）**：一个新会话只读它，就能说出一个 run 的目录形态、四件套样子、一轮命令流水与合格线。
  - 判据：SPEC §3 WS-1 的 7 项全覆盖；≤250 行；每段摘录 ≤15 行；每段有 run 证据；QA 抽 3 段回源核对一致。
- **G2 演进说明可特化（EVOLUTION.md）**：三轴（进阶/本地化/特化）各就各位；13 个特化模板全部入表；每条有证据。
  - 判据：≤200 行；三轴 + checklist + 未决齐全；13/13 模板行；数字可复算；QA 抽 5 条回源核对。
- **G3 入口与非规范边界**：`README.md` 目录地图新增两行；两文件页首均有“非规范”声明；未改规范/角色/模板/脚本/DESIGN。
  - 判据：`grep -n "非规范"` 命中两次；`git diff --name-only` 仅白名单；`wf.py doctor` 无新增 error。

**反目标（明确不做）**：

- 不做第二份规范：不复述 `WORKFLOW.md` 规则、不新增流程规则；
- 不修改既有 run 四件套与 reports；不重排 `runs/` 目录；
- 不动插件事务（本 run 只服务 workflow-group 自身文档）；
- 不引入外部依赖、不改脚本。

## 2. 范围

### 2.1 范围内（写权限见 SPEC §2）

- `EXAMPLE.md`（WS-1）
- `EVOLUTION.md`、`README.md` 目录地图两行（WS-2）
- `runs/<RUN-ID>/**`（两份证据报告）

### 2.2 范围外

- `WORKFLOW.md`、`roles/**`、`templates/**`、`scripts/**`、`DESIGN.md`：只读；
- 既有 `runs/**`：只读，仅作证据；
- 插件仓 `obsidian-nutstore-sync-phone-ai-tools/**`：只读（本地化实例证据）。

### 2.3 假设与依赖

- 14 个 run 全部 closed（`runs/*/PROJECT.md` 头 state=closed）；
- 13 个特化模板在 `templates/specialized/`；插件仓有 `LOCALIZATION.md` 与 `runs/nutstore-tools-rebuild-20261015/**` 可读；
- 本机 `opencode` 直连可用；`wf.py delegate` 可自动起服务。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据来源 | 采集方式 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | EXAMPLE 覆盖项 | 0/7 | 7/7 | 待采集 | `EXAMPLE.md` | 逐项对照 + QA 抽检 |
| M2 | EXAMPLE 行数/摘录长度 | — | ≤250 / ≤15 行每段 | 待采集 | `EXAMPLE.md` | `wc -l` + 抽段 |
| M3 | EVOLUTION 三轴 + 模板台账 | 0 | 3 轴 + 13/13 模板 | 待采集 | `EVOLUTION.md` | 逐行对照 + 复算命令 |
| M4 | EVOLUTION 行数/证据率 | — | ≤200 / 100% 有证据 | 待采集 | `EVOLUTION.md` | `wc -l` + 抽条回源 |
| M5 | 入口更新 | 0 行 | README 目录地图 +2 行 | 待采集 | `README.md` | `git diff` |
| M6 | 自检 | — | `pytest` 通过 + `doctor` 无新增 error | 待采集 | 命令输出 | 实跑 |

## 4. 分任务（Workstreams）

| WS | 任务 | 产出物（路径） | 验收判据 | 依赖 | 建议执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| WS-1 | EXAMPLE.md 示例参考 | `EXAMPLE.md`；`runs/<RUN-ID>/reports/ws1-example.md` | SPEC §3 WS-1 7 项 + M1/M2；每段有证据 | — | TDO | 待开始 |
| WS-2 | EVOLUTION.md 演进说明 + README 入口 | `EVOLUTION.md`；`README.md`（+2 行）；`runs/<RUN-ID>/reports/ws2-evolution.md` | SPEC §3 WS-2 7 项 + M3/M4；13/13 模板 | — | TDO | 待开始 |
| QA | 独立核查与登记 | `ISSUES.xlsx` 当轮新增行 | SPEC §6 DoD 逐条；抽检回源 | WS-1/2 | QA | 待开始 |

## 5. 轮次计划与结论

- **R1**：WS-1 / WS-2 并行；QA 核查；PMO 收轮；主会话拍板（本 run 目标单一，若 DoD 达成即关闭）。
- 不做 R2，除非 QA 发现必须回源的 S1/S2 缺口。

## 6. PMO 上报区（唯一给主会话的摘要）

<!-- PMO 在收轮后填写：结论 / 待拍板选项 A/B + 建议 / 下轮编制建议 / 风险 -->
