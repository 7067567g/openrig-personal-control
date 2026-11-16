# SPEC — OpenRig Workflow Master v1.2.0 更新

## 0. 分层声明

baseline: composite/two-plane-orchestration@1.0.0
contracts: strategy@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0

> 本文件是该 run 的特化规则，优先于通用 WORKFLOW / roles 中冲突的部分。
> 本 run 更新母版本身：目标是 `workflow-group/templates/specialized/openrig-workflow-master/**`，不是 OpenRig parent 源码。

## 1. 任务与 release 定义

把 `openrig-workflow-master` 从 v1.1.0 升到 v1.2.0。v1.2 的主题是 **可搬迁、可返工、可复算的可发布母版**，只包含以下核心面：

1. **Bridge v2 / bundle 可搬迁**：bridge 内 bundle 路径相对化；doctor 兼容 v1 legacy；同输入跨 output-dir 产物一致。
2. **有界 QA→TDO 返工**：使用 OpenRig 既有 `next_hop.on` + `loop_guards.max_hops`，让 QA 失败回到正确 TDO 并能再次 QA；不得发明引擎 API。
3. **发布完整性**：v1.2 pre/post baseline、VERSION/CHANGELOG/README/ARCHITECTURE/SPEC/validation 同步；P-004 doctor 文档清单修复。
4. **验证与收口**：测试全绿；render/doctor/workflow validate/instantiate/一次失败返工投影/teardown 有证据；QA PASS；open S1/S2=0。

## 2. 写权限与文件面

### 2.1 可写

| 路径 | 写者 | 用途 |
| --- | --- | --- |
| `workflow-group/runs/<RUN-ID>/**` | PMO/TDO/QA/MAIN 按角色 | 四件套、报告、证据 |
| `workflow-group/templates/specialized/openrig-workflow-master/render_master.py` | WS-A（TDO-OC） | generator / bridge v2 |
| `workflow-group/templates/specialized/openrig-workflow-master/tools/openrig_bridge.py` | WS-A（TDO-OC） | doctor / v1 兼容 |
| `workflow-group/templates/specialized/openrig-workflow-master/templates/workflow.yaml.tpl` | WS-B（TDO-DSH） | 返工边 |
| `workflow-group/templates/specialized/openrig-workflow-master/templates/rig.yaml.tpl` | WS-B（TDO-DSH） | 仅在返工边需要新 seat 时改；否则不动 |
| `workflow-group/templates/specialized/openrig-workflow-master/tools/master_baseline.py` | WS-B（TDO-DSH） | 可选：pre/post baseline 生成/校验；不写 final baseline |
| `workflow-group/tests/test_render_master_portability.py` | WS-A | G1 定向测试（新文件） |
| `workflow-group/tests/test_openrig_bridge_doctor.py` | WS-A | 现有 doctor 测试的 v2 增补 |
| `workflow-group/tests/test_workflow_rework.py` | WS-B | G2 定向测试（新文件） |
| `workflow-group/tests/test_master_release.py` | WS-B | baseline/release 自检测试（新文件，可选） |
| `workflow-group/templates/specialized/openrig-master-v12/**` | MAIN | 本 run 模板 |
| `workflow-group/kickoff/openrig-master-v12*` | MAIN | 核对与目标 |

### 2.2 仅 MAIN 在收口阶段可写

- `openrig-workflow-master/VERSION`
- `openrig-workflow-master/CHANGELOG.md`
- `openrig-workflow-master/README.md`
- `openrig-workflow-master/ARCHITECTURE.md`
- `openrig-workflow-master/SPEC.md`
- `openrig-workflow-master/BASELINE-pre.sha256`
- `openrig-workflow-master/BASELINE-post.sha256`
- `openrig-workflow-master/validation/v1.2.0/**`
- `openrig-workflow-master/validation/README.md`

> TDO 只交 change note + 文件清单 + hash；不得在 handler 阶段改 release 元数据，防止并发覆盖和哈希漂移。

### 2.3 只读

- `/home/dev/Desktop/deepseek/60-外部仓库/openrig/**`
- `/home/dev/Desktop/deepseek/deepseek-项目/10-openrig-deepseek/**`（默认只读）
- KB 正式正文域 `00-overview/` … `99-archive/`
- 非本 run 的其他 `workflow-group/runs/**`

## 3. 工作包边界

### WS-A（TDO-OC）Bridge v2 / portability

- 改 `render_master.py`：bridge `schemaVersion: 2`；bundle 内路径相对化（`bundleDir: "."`、`rigSpec: "rig.yaml"`、`workflowSpec: "workflow.yaml"`）；保持 `projectRoot`/`openrigHome`/`openrigCli` 的运行语义。
- 改 `tools/openrig_bridge.py`：doctor 支持 v1 legacy 与 v2；v2 路径必须相对且不得逃逸 bundle；补 P-004 对应实现检查（runId/bundleDir/openrigCli）。
- 测试：同一 run、同一参数渲染到两个临时 output-dir，5 个生成文件逐字节一致；v2 正例、路径逃逸负例、v1 legacy 正例。
- 不得改 workflow.yaml.tpl、release 文档、baseline。

### WS-B（TDO-DSH）有界返工 + baseline 工具

- 改 `workflow.yaml.tpl`：设计并落地显式 QA 失败返工路径；必须用既有 `next_hop.on` 与 `loop_guards.max_hops`。
- 在 `tests/test_workflow_rework.py` 用静态 spec 断言 + 可行时用 parent OpenRig `rig workflow validate` 证明：失败边存在、目标 step 正确、返工环可回到 QA、有可执行 hop guard。
- 如交付 `tools/master_baseline.py`：只做生成/校验辅助，按排序、注释头、排除自身；不得写 `BASELINE-pre/post.sha256`。
- 返工设计若存在两个合法形态，交 `PROJECT §6` 让 MAIN 拍板，不得自选后隐藏。
- 不得改 render_master.py、openrig_bridge.py、release 文档、baseline。

### WS-C（MAIN）Release 收口

- WS-A/WS-B QA PASS 后统一改 VERSION/CHANGELOG/README/ARCHITECTURE/SPEC/validation。
- 动代码前建立 `BASELINE-pre.sha256`；全部落定后建立 `BASELINE-post.sha256` 并复算。
- 将当前 Unreleased audit-fix 归并到 `## 1.2.0`；加 `## 1.3 候选` 接住明确延后的项目。
- 最终测试、baseline、doctor、E2E、teardown 结果写 `validation/v1.2.0/RELEASE.md`。

## 4. 证据格式

每项证据至少给出：

```text
[PASS/WARN/FAIL/SKIP] <检查项> | cmd: <可复跑命令> | rc: <退出码> | evidence: <run 内路径>
```

- 每个 TDO 包必须有 packet id / workflow step / session id（脱敏）/ transcript 指针或原始抓取。
- 改动文件给出改前/改后 sha256。
- 反证成对：修复前症状 + 修复后行为。
- baseline 必须用 `sha256sum -c` 复算，不能只贴生成命令。
- 禁止 secret、完整对话正文、auth 内容入证据。

## 5. 验收与完成定义

- `pytest workflow-group/tests -q` 全绿。
- `VERSION=1.2.0`；CHANGELOG 有 `## 1.2.0` 与 `## 1.3 候选`。
- `BASELINE-pre.sha256` 与 `BASELINE-post.sha256` 均有注释头且 post `sha256sum -c` rc=0。
- render 两次不同 output-dir 的 5 个产物逐字节一致。
- bridge doctor v2 live PASS；v1 legacy PASS；至少 3 类负例 rc=1 且指名字段。
- workflow validate rc=0；instantiate 成功；一次 QA 失败返工投影证据；`max_hops` 配置可复核。
- teardown 后无本 run 残留 daemon/tmux/runner。
- QA 全部判据有 PASS/WARN/FAIL/SKIP；open S1/S2=0；PROJECT §6 无主待办=0。
- 不修改 parent OpenRig 源码；不改 KB 正式域；不 push。

## 6. 明确非目标

- SAFETY 执行器、DECISIONS hash-chain/单一写者强制、授权→packet 自动核对；
- queue→STATUS 回填、多项目 registry、成本/延迟遥测、Tier B 全量 self-check；
- daemon/CLI/TUI/UI 重写、runtime adapter 删除、外部仓库修改、push。
