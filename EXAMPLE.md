# EXAMPLE — 工作流示例参考（v1.2 / 2026-11-11）

> **非规范**：本文是新 run 的教学示例，不定义规则；与 `WORKFLOW.md`、`roles/`、`templates/` 冲突时以后者为准。
> 当前规范：`WORKFLOW.md` v1.2（2026-11-11）；权威链见 `WORKFLOW.md §0`。
> 用法：用本文理解一个 run 的目录形态、四件套当前长什么样、状态迁移怎么走；不要把它当作可直接复制执行的完整脚本。

## 1. 选材与定位

### 1.1 当前 v1.2 主标本：`signaldeck-refactor-20261025`

- 选择理由：它同时具备多轮执行、`baseline`/`contracts` 双声明、`ROUND-PLAN.md`、`SPEC.md`、PROJECT `wf-doc` 机器字段、DECISIONS 多轮决策和 ISSUES 台账，适合展示当前规范层。
- 当前状态：Round 7，`PROJECT.state=plan-ready`，执行仍在进行；因此它是“当前形态”标本，不是“已关闭”标本。
- 主要证据：`runs/signaldeck-refactor-20261025/PROJECT.md:1-12`、`:89-140`；`ROUND-PLAN.md:1-7`；`DECISIONS.md:112-124`；`STATUS-Round-7.md:1-24`。

### 1.2 closed/终态形态标本：`signaldeck-runtime-20261014`

- 该 run 是 **v1.0 历史 run**，只用于展示“`PROJECT: closed` + 终局 `D-xxx` + 资产去向”的形态。
- **不作为 v1.2 规范符合性证据**：它的 PROJECT 头没有当前 `tags/primary_type/maturity/baseline/contracts` 机器字段，文件内容和字段约定仍属于旧版。
- 主要证据：`runs/signaldeck-runtime-20261014/PROJECT.md:1-8`；`DECISIONS.md:64-72`。
- 备选说明：`runs/yueyue-governance-20261110` 当前尚未执行，故不选作 closed 标本；若未来它完成并留下完整终态证据，可重新评估。

### 1.3 数字口径

- 本文不写死“全库有多少 run/多少 closed run”。需要统计时运行：
  ```bash
  find workflow-group/runs -mindepth 1 -maxdepth 1 -type d | wc -l
  grep -l '^state: closed' workflow-group/runs/*/PROJECT.md | wc -l
  ```
- run 内的 306/306、24/24、28 PASS 等数字是 `PROJECT.md` 的目标/证据值，不是全库统计；引用时看对应 `PROJECT §1/§3` 和 `reports/**`。
- 结论：全库数量以 `runs/` 实测为准；不要从旧文档复制计数。

## 2. 目录形态（v1.2 当前 run）

```text
runs/signaldeck-refactor-20261025/
├── PROJECT.md          # PMO 维护；唯一给主会话的上行摘要在 §6
├── SPEC.md             # 本 run 特化；§0 声明 baseline/contracts
├── ROUND-PLAN.md       # 本轮唯一 contract + produces/gate/budget/NOT-DOING
├── DECISIONS.md        # 主会话写；D-xxx + 编制时间线 + 判词
├── STATUS-Round-7.md   # TDO 持锁逐条追加；本轮进度/阻塞/交接
├── ISSUES.xlsx         # QA 新增问题/风险/变更；JSONL 可作为核对导出
├── DELEGATIONS.md      # 委派/回执留痕（按工具支持生成）
├── delegations/        # BRIEF/RECEIPT 原件
├── reports/            # 本轮产出、证据、门禁日志
├── logs/               # 运行日志；常被 .gitignore 忽略，只作现场证据
└── .locks/             # STATUS 锁目录；不入库
```

- `SPEC.md` 与 `ROUND-PLAN.md` 是 v1.2 中真实存在的运行文档；不要再把工作流理解成只有四份文件。
- `reports/` 和 `logs/` 不是第五、第六份四件套，而是 TDO 的 WS 产出；`--also` 只能指向本 run 内、会被 git 跟踪的产物。
- 旧 run 目录可能没有 `ROUND-PLAN.md`、`SPEC.md` 或机器字段；这是历史兼容，不应拿来当新 run 模板。

## 3. 四件套与当前 v1.2 形态

### 3.1 PROJECT 的 `wf-doc` 头

当前 v1.2 主标本的实际头（原样摘录）：

```text
<!-- wf-doc
run: signaldeck-refactor-20261025
round: 7
doc: PROJECT
owner: PMO
state: plan-ready
updated: 2026-11-04
tags: template/signaldeck-refactor, baseline/refactor-decompose
primary_type: composite/refactor-decompose
maturity: M2
baseline: composite/refactor-decompose@1.0.0
contracts: research@1.0.0, diff@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0
-->
```

- 基础字段：`run` / `round` / `doc` / `owner` / `state` / `updated`。
- 机器字段：`tags` / `primary_type` / `maturity` / `baseline` / `contracts`。新 run 若带 `SPEC.md`，`wf.py new-run` 会从 `SPEC §0` 和 baseline 注册表自动写入；旧 run 可能没有，属于历史兼容，不应反推为当前必填。
- `owner: PMO` 表示 PROJECT 内容归 PMO。`state` 只由 `wf.py state/new-round` 迁移，不手改。

### 3.2 S0 bootstrap 与 PMO 唯一写者

v1.2 的 PROJECT 写者边界：

- `PROJECT.md` 归 PMO；`wf.py new-run` 后到 PMO 首次接手阶段 S1 前是 **S0 bootstrap 窗口**。
- 窗口内主会话只可填 PROJECT `§0` 元信息与 `§1` 的 G1 目标/终止判据。
- PMO 接管后（最迟 `plan-ready`）窗口关闭，主会话不得再写 `PROJECT.md`。
- 这是单一写者的窄例外，不是“主会话可以随时改 PROJECT”；详见 `WORKFLOW.md §4` 的 PROJECT 契约例外。

### 3.3 SPEC §0 与 ROUND-PLAN

当前 v1.2 主标本的 SPEC 声明：

```text
baseline: composite/refactor-decompose@1.0.0
contracts: research@1.0.0, diff@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0
```

当前轮 `ROUND-PLAN.md`（原样摘录）：

```text
# ROUND-PLAN — R7 optimize

contract: optimize@1.0.0
produces: 10-signaldeck/tests/gate-steps.json, 10-signaldeck/tests/gate-steps.windows.json, 10-signaldeck/tests/verification/verify-windows-gate-parity.mjs, runs/signaldeck-refactor-20261025/reports/GATE-LOCK-R7.md
gate: node tests/verification/verify-windows-gate-parity.mjs; node scripts/verify-tool-build.mjs; node scripts/verify-tool-lib.mjs; node scripts/verify-boundaries.mjs; node scripts/verify-semantic-inventory.mjs; bash tests/run-linux.sh
budget: target=1 WS (WS-12); TDO=1; time<=1.5h; round=7/12
NOT-DOING: 不改 rule/geo（R8）；不改 host（R9）/frontend+观测（R10）；不动 cleaned 两清单（Q-17 A）；不删除文件；不 push
```

- `contract` 声明本轮唯一原子轮型；`produces/gate/budget/NOT-DOING` 必须齐全。
- 计划门未过时不要开工；SPEC 只能在上层规则之上加严，不能放宽 `WORKFLOW.md §0` 的四条硬约束。

### 3.4 STATUS 状态与写入方式

STATUS 允许的 state，从 `WORKFLOW.md §4` 当前契约为：

```text
tdo-pending → tdo-in-progress → qa-pending → qa-done → closed
```

当前主标本的 `STATUS-Round-7.md` 处于 `tdo-in-progress`，每条进度由持锁 TDO 追加：

```text
| 2026-11-04 05:23 | tdo-a2 | WS-12 | 开始执行 WS-12…… | 读 SPEC/PROJECT/DECISIONS；基线 parity 10 PASS | 进行中 |
| 2026-11-04 05:24 | tdo-a2 | WS-12 | WS-12 实现受阻…… | patch: reports/patches/r7-gate-lock.patch；staging parity 10 PASS | 阻塞 |
```

- 一次写入 = `lock → 追加 1 条 → commit（按需）→ unlock`；推荐用 `append-status`。
- 状态字段只由唯一执行者迁移；命令必须带 `<run>` 与 `--by`。
- `state=qa-done/closed` 时 STATUS 正文不应再有“进行中/阻塞”行；关闭前由 `wf_close_lint.py` 机检。

### 3.5 DECISIONS 与 ISSUES

当前主标本的决策账本展示多轮决策与编制重定：

```text
### D-008（Round 7）R7 编制、gate 上锁落点与委派后端
- **决策**：R7 编制 PMO×1 / TDO×1 / QA×1；TDO 唯一 WS-12（gate 上锁）；……
- **编制**：PMO×1 / TDO×1 / QA×1
- **状态**：生效
```

ISSUES 行必须带来源、严重度、建议动作；例如当前台账中的 R-012 为 S3 风险：

```text
ID: R-012
类型: 风险
标题: gate 上锁未完成，治理仍非强制
严重度: S3
状态: 新建
来源: STATUS-Round-6.md B-001
```

- `ISSUES.xlsx` 由 QA 新增；PMO 只有在 `DECISIONS.md` 明确授权（D-xxx）时，才可更新既有行的「状态」「关联决策ID」两列。
- `S1/S2` 问题不得无处置通过；关闭前还要看 `wf_close_lint.py`。

### 3.6 closed/终态示例（历史 v1.0）

`signaldeck-runtime-20261014` 只用于展示关闭形态：

```text
<!-- wf-doc
run: signaldeck-runtime-20261014
round: 2
doc: PROJECT
owner: PMO
state: closed
updated: 2026-10-14
-->
```

对应终局决策（`DECISIONS.md:64-72`）写明：

```text
### D-005（Round 2）判定「达成」并关闭 run
- **决策**：……判本 run **达成**；PROJECT.md 置 `closed`；资产去向 = runs/signaldeck-runtime-20261014/**……
- **状态**：达成
```

注意：该 run 是 v1.0 历史 run，只是“closed + D-xxx + 资产去向”的形态示例，**不能作为 v1.2 合规证据**。

## 4. 一轮 copy-paste 流水（v1.2）

以下命令是示意；`<run-id>` 换成实际 run id，所有状态迁移必须带 `--by`。

### 4.1 S0 开局与 S1 计划

```bash
cd workflow-group

python3 scripts/wf.py new-run <run-id> --goal "一句话目标" --tdo 1 \
  --template templates/specialized/signaldeck-refactor

# 主会话只读 §6；PROJECT §0/§1 的 bootstrap 写权限见 §3.2
python3 scripts/wf.py brief --role pmo --run <run-id>
```

PMO 完成计划后由 PMO 执行：

```bash
python3 scripts/wf.py state <run-id> PROJECT plan-ready --by pmo
```

### 4.2 S2 执行

```bash
python3 scripts/wf.py brief --role tdo --run <run-id> --agent tdo-a1

python3 scripts/wf.py append-status <run-id> \
  --agent tdo-a1 --ws WS-1 \
  --action "完成 X" --evidence "path/to/evidence；命令结果" \
  --also runs/<run-id>/reports/evidence.md
```

主会话收齐 TDO 回执后：

```bash
python3 scripts/wf.py state <run-id> STATUS qa-pending --by main
```

### 4.3 S3 QA

```bash
python3 scripts/wf.py brief --role qa --run <run-id>

# QA 核查完成后自行迁移
python3 scripts/wf.py state <run-id> STATUS qa-done --by qa
```

### 4.4 S4 PMO 收轮与 S5 主会话拍板

```bash
python3 scripts/wf.py brief --role pmo --run <run-id>

# PMO 完成 §3/§4/§5/§6 收轮后
python3 scripts/wf.py state <run-id> PROJECT waiting-main --by pmo

# 主会话只读 PROJECT §6，写 DECISIONS.md（D-xxx + 编制 N'）
# 然后继续下一轮或进入关闭流程
python3 scripts/wf.py new-round <run-id>
```

### 4.5 关闭流程

先跑关闭语义检查（只读），**ERROR=0** 才允许继续：

```bash
python3 scripts/wf_close_lint.py --run <run-id>
# 期望：RESULT PASS 或 PASS_WITH_WARNINGS；ERROR 必须为 0
```

然后由主会话执行：

```bash
python3 scripts/wf.py state <run-id> PROJECT closed --by main
# 可选
python3 scripts/wf.py state <run-id> DECISIONS closed --by main
python3 scripts/wf.py state <run-id> STATUS closed --by main
```

当前主标本 `signaldeck-refactor-20261025` 是进行中的 R7，不是关闭样本；对它跑 `wf_close_lint.py` 会因历史 `STATUS-Round-6.md` 仍含阻塞行而报 `status_has_unfinished_rows`。这正好说明：**关闭前要把历史状态冲突清零，不能把“plan-ready”当作“可关闭”**。

### 4.6 模板/索引改动的自检

修改模板、标签索引、角色或规范后必须跑：

```bash
python3 scripts/doc_consistency.py --check
```

它检查模板登记覆盖、baseline/contracts 计数、失效跨引用和关键命令的 `--by` 形状；rc 非 0 时先修文档，不要继续发布模板。

## 5. 常见坑（v1.2）

1. **把 PROJECT 当主会话文档**：只有 S0 bootstrap 窗口可写 §0 元信息与 §1 G1；PMO 接管后主会话只读 §6。
2. **state 命令漏 `--by`**：PMO 收轮、主会话关闭、QA 完成都必须显式 `--by`；`append-status` 才自动处理锁和状态。
3. **把旧 run 当新模板**：旧 run 缺 `ROUND-PLAN.md`、机器字段或新 state 口径，只作历史证据。
4. **`--also` 指向被忽略文件**：`*.log`、`logs/**`、`burner/` 可能导致整条进度提交失败；关键结果内联到报告。
5. **只看 `PROJECT closed` 不看收口证据**：关闭前要同时有 `wf_close_lint.py` ERROR=0、终局 D-xxx 的资产去向和 ISSUES 处置。
6. **引用旧章节号**：本章节号以当前 `WORKFLOW.md` v1.2 为准；遇到已被重编号或无法解析的旧引用，应回到当前 `WORKFLOW.md` 的标题和编号重新定位。

## 6. 维护说明

- 本文是 v1.2 的示例快照；`WORKFLOW.md` 版本、四件套形态或状态机变化后，重新摘录受影响小节，不在旧例上打补丁。
- 主标本若更换，先在 run 的 `DECISIONS.md` 记一条选择理由，再更新 §1/§3/§6。
- 所有摘录给 `runs/<id>/文件:行` 或可复跑命令；全库统计使用第 1 节的数字口径命令，不在正文抄写旧计数。
- 旧的 `EXAMPLE` 历史文本可由 git 历史追溯；不要把它和新 run 教材混用。
