<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: DECISIONS
owner: 主会话
state: open
updated: <DATE>
-->

# DECISIONS — OpenRig Workflow Master v1.2.0 更新

## 0. 记录规则

1. 每条决策唯一 ID，按时间只增不改。
2. 目标、删除、发布、预算、权限、跨 run 边界必须由本账本记录。
3. 执行状态由 OpenRig queue/workflow 负责，不在本文件抄写实时状态。
4. 任何“跳过 OpenRig 直接做”的降级必须单独决策并标注原因。

## 1. 决策账本

### D-001（Round 1）v1.2 核心范围

- **决策**：v1.2.0 定义为“可搬迁、可返工、可复算的可发布母版”，只做 bridge v2、QA 返工边、release/baseline/文档完整性、P-004。SAFETY 执行器、DECISIONS 写审计、授权→packet 核对、queue→STATUS 回填、多项目 registry、成本遥测、Tier B 全量 self-check 明确进入 `## 1.3 候选`。
- **理由**：当前 v1.1 遗留项跨治理/运行时/可观测三面；若全部塞入 v1.2，会失去可验收边界，并再次产生未完成承诺。
- **状态**：生效

### D-002（Round 1）bridge 路径形状升版

- **决策**：bundle 内路径改为相对路径并升 `schemaVersion: 2`；doctor 保留只读 v1 legacy 兼容；v2 路径逃逸必须 FAIL。
- **影响面**：`render_master.py`、`tools/openrig_bridge.py`、测试与文档；不改 `openrigHome`/`projectRoot` 的运行绝对语义。
- **状态**：生效

### D-003（Round 1）返工必须复用既有引擎语义

- **决策**：不得为返工新增未实现的 OpenRig 引擎字段/API；只允许 `next_hop.on` 与 `loop_guards.max_hops` 的现有语义。若单 QA 静态图无法同时回到两个 TDO，PMO 必须在 PROJECT §6 上报，由 MAIN 拍板。
- **验收**：不是“有边”即过，必须有失败 exit 投影到对应 TDO 的 live/structured 证据。
- **状态**：生效

### D-004（Round 1）release 元数据单一写者

- **决策**：VERSION、CHANGELOG、README、ARCHITECTURE、SPEC、BASELINE-pre/post、validation/v1.2.0 仅 MAIN 在 WS-A/WS-B QA PASS 后写；TDO 只交 change note/hash。
- **理由**：避免并发覆盖、baseline 哈希漂移与 release 文档口径分裂。
- **状态**：生效

### D-005（Round 1）外部仓库边界

- **决策**：本 run 不修改 `60-外部仓库/openrig` 与 `deepseek-项目/10-openrig-deepseek` 源码；若真实 E2E 发现 parent bug，登记 ISSUE + 建议，另开 D-xxx/独立 run 修。
- **状态**：生效

## 2. 待决清单

| 编号 | 待决问题 | 选项 A | 选项 B | 主会话拍板 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-1 | 返工图形状 | 单 QA + failed→rework triage，再由 PMO 定向回 TDO | 分支专属 QA（qa_oc.failed→implement_opencode；qa_dsh.failed→implement_dsh），最后 join | 按 D-003 由 PMO 证据后上报 | 待决 |
| Q-2 | bridge v1 legacy 兼容深度 | doctor 只读兼容 + 明确提示迁移 | v1 legacy 也强制相对路径（不兼容旧 bundle） | 推荐 A，保持旧证据可复跑 | 待决 |
| Q-3 | 真实 E2E 深度 | 5 seats ready + workflow validate/instantiate + 结构化返工投影 | 再加一次真实模型 QA 失败任务 | 推荐 A；B 受额度/认证影响时 SKIP 并说明 | 待决 |

## 3. 编制变更时间线

| 轮次 | PMO | TDO | QA | 变更理由 | 决策 ID |
| --- | --- | --- | --- | --- | --- |
| R1 | 1 | 2 | 1 | 初始立项 | D-001 |
