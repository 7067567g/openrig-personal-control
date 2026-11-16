# RELEASE — openrig-workflow-master v1.2.0

| 项                     | 值                                                           |
| ---------------------- | ------------------------------------------------------------ |
| 母版版本               | `1.2.0`（`VERSION`）                                         |
| 主题                   | 可搬迁、可返工、可复算的可发布母版                           |
| 产生该版本的 run       | `workflow-group/runs/openrig-master-v12-20261020`            |
| live workflow instance | `01M5B2VJ3708YKB0FCJ9Q97KX5`（**改前 v1 图**，见 §3）        |
| 返工投影所用隔离实例   | `01M5B3HD9ZQPTQWMK2X09N3FS8`（独立 probe HOME，已 teardown） |
| 本文件写入时点         | 2026-10-20（R1 `close_round` / WS-C）                        |

> 本文件区分**已验证**与**待复核**。凡标「待 R2」者，不得被引用为已验收。

## 1. 本版本交付了什么

1. **bridge v2 / bundle 可搬迁**：`OPENRIG-BRIDGE.json` 升 `schemaVersion: 2`，bundle 内路径相对（`bundleDir: "."`、`rigSpec: "rig.yaml"`、`workflowSpec: "workflow.yaml"`），`projectRoot`/`openrigHome`/`openrigCli` 保持运行期绝对；同 run 同参数渲染到两个 output-dir，5 个产物逐字节一致。
2. **有界 QA→TDO 返工边**：workflow 模板改为分支专属 QA（`qa_opencode` / `qa_dsh` / `qa_join`），各分支 `next_hop.on.failed` 静态回边到本分支 TDO；只用既有 `next_hop.on` + `loop_guards.max_hops`（=10），不新增引擎字段/API。
3. **发布完整性**：`VERSION=1.2.0`；`CHANGELOG.md` 含 `## 1.2.0` 与 `## 1.3 候选`；README/ARCHITECTURE/SPEC 同步；pre/post baseline 成对可复算。
4. **入口与调用说明**：新增 `ENTRYPOINTS.md`，明确 local-only / hybrid / 接续 run 三种入口、控制面→OpenRig 调用链，以及 KB GitHub issue 与 `deepseek-项目` `tickets-as-code` 的双票制边界。

## 2. 验收矩阵

| #   | 判据                                  | 结论                               | 证据 / 说明                                                                                                                                                                                      |
| --- | ------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| M1  | 全仓 pytest                           | **PASS（环境限定，R2 复跑）**     | A：`rig`+`node` → **139 passed / rc=0**；B（CI 等价，无 `rig` 有 `node`）→ **137 passed + 2 skipped / rc=0**（提交后复跑，`evidence/qa/M1-R2-B-after-commit.txt`）；C（无 `node`）→ 135/4，已文档化前置。三环境细分见 §4 |
| M2  | bridge v2 + 相对路径 + 逃逸拒绝       | **PASS**                           | v2 正例 rc=0 `schema=2`；绝对 `workflowSpec` / 绝对 `bundleDir` / 逃逸 `rigSpec` 三类负例 rc=1 且指名字段（QA 独立复跑）                                                                         |
| M3  | 跨 output-dir 5/5 逐字节一致          | **PASS**                           | 两次渲染 5 产物 sha256 全等，`diff -r` rc=0（QA 独立复跑）                                                                                                                                       |
| M4  | v1 legacy 可读                        | **PASS**                           | v1 bridge → doctor rc=0 且输出迁移提示，未静默改写（QA 独立复跑）                                                                                                                                |
| M5  | 返工边 validate + failed 投影         | **PASS**                           | `validate` ok=true / stepCount=7 / 0 error；真实 `--exit failed` 投影：`nextStepId=implement_opencode`、`hopCount=3`，再 handoff 后回到 `qa_opencode`、`hopCount=4`，终态 `completed/hopCount=7` |
| M6  | VERSION + CHANGELOG 双小节            | **PASS（本次写入）**               | `VERSION=1.2.0`；`## 1.2.0` + `## 1.3 候选`                                                                                                                                                      |
| M7  | pre/post baseline 可复算              | **PASS（MAIN 实测）**              | **post：37 文件 37/37 OK，`sha256sum -c` rc=0**。pre（36 文件）是改动前快照：WS-A/WS-B 完成时复算 33 OK + 3 预期差异；WS-C 写入 release 面后复算 **27 OK + 9 个预期差异**，9 项恰为声明改动集（ARCHITECTURE / CHANGELOG / README / SPEC / VERSION / render_master.py / tools/openrig_bridge.py / templates/workflow.yaml.tpl / BASELINE-post），另有新增 `validation/v1.2.0/RELEASE.md` 不在 pre 内 |
| M8  | E2E：5/5 ready + validate/instantiate | **PASS（R2，按模板字节重绑定）** | 5/5 running/ready；R2 新渲染发布形状 spec `ok=true / stepCount=7`；R1 的真实 failed-exit 投影对**同一模板字节**（sha256 `73915634…`）仍成立，diff 仅 id/rig 名差异（`evidence/qa/M8-R2-binding.txt`）。QA **未**在 live rig 上 instantiate，避免向 control-pmo 投 `plan` 包污染在跑队列 |
| M9  | QA 全判据有结论 + open S1/S2=0        | **PASS**                          | 判据 100% 有结论；**open S1=0、open S2=0**（P-001 由 D-018 显式接受并关闭；P-002 superseded by P-004；P-004/P-005 修复并验证后关闭）。见 §5/§9 |
| M10 | 本 run 0 残留 | **PASS（后补，见 §9.4）** | 2026-10-20 06:52 CST：47896/47897 无监听；无 seat/runner/tmux；临时 home 与 render 目录已清。证据：`runs/openrig-master-v12-20261020/evidence/main/M10-teardown-*.{json,txt}` |

## 3. 本 run 自身 bundle 的 legacy 说明（强制披露，不可省略）

按 D-014，逐条写明——**缺少任一条即视为本发布说明不合格**：

- **(a)** 本 run 自己的 bundle（`runs/openrig-master-v12-20261020/openrig/`）**停留在 legacy `schemaVersion:1`**，其 `bundleDir`/`rigSpec`/`workflowSpec` 是**绝对路径**。
- **(b)** 原因是**因果**而非偏好：该 bundle 由**改前 generator** 在 PRECHECK 阶段（05:59:22）渲染，早于 TDO packet 投递（06:04）；live 实例 `01M5B2VJ…` 正由其实例化。
- **(c)** `doctor` 对其判 PASS 属于 **v1 legacy 只读兼容**（D-007），**不代表 v2**。
- **(d)** v1.2 的 v2 证据在 **M2**（`schema=2` + 相对路径 + 逃逸负例）与 **M3**（跨 output-dir 5/5 逐字节一致），不在本 run 的 bundle 上。
- **(e)** 拒绝「收口前重渲染本 run bundle」的理由：会用在跑实例的旧图与 bundle 的新形状自相矛盾、使 D-011/D-013 依赖的「本实例=改前 v1 图」前提失真、并作废 M3 的 hash 证据链；且 v2 证明力已由 M2/M3 覆盖，重渲染无新增证明力。

> 读者不应从本 run 的 bundle 推断 v1.2 产物形态。要看 v1.2 产物，请直接 `python3 render_master.py --run-id <x> --project-root <repo> --output-dir <tmp>/openrig --json`，再对 `<tmp>` 跑 `doctor`。

## 4. pytest 的环境前置（D-012 / D-016 / P-002）

全仓 `pytest workflow-group/tests -q` 的结论**必须连同环境陈述**，禁止只写「全绿」：

| 环境                     | 结果                      | 失败例                                                                                                                                                       |
| ------------------------ | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `rig` 与 `node` 均可解析 | **139 passed / 0 failed** | —                                                                                                                                                            |
| 缺 `rig`（保留 `node`）  | **137 passed / 2 failed** | `test_render_master_portability.py::{test_rendered_bundle_passes_doctor_v2, test_bundle_is_relocatable}`（doctor 经 `run_cli` 返回 rc=127「CLI not found」） |
| 缺 `node`（rig shim 在但其 exec 的 node 不可用） | **135 passed / 4 failed** | `test_workflow_rework.py` 的 3 个 parser/validator 例 + `test_openrig_bridge_doctor::test_live_run_still_passes`（MAIN 亲测） |
| 两者皆缺 | **133 passed / 6 failed** | 上述两组并集 |

## 5. 已知执行面缺陷（未在本 run 修复）

- **P-001（S2）**：一次 `rig send` 产生**两次**投递到 `control-main`，击穿单一写者并写出重复决策 ID（事故与去重见 `DECISIONS` D-009/D-010；本次 accepted 见 D-016）。
- **根因未定**：有证据的只有「一次发送 → 两次投递」；`qitem-…8cbd6f91` 的 transition 日志显示唤醒只投递**一次**（D-010 已撤回「重复唤醒」归因）。
- **为何不修**：本 run 禁止修改 `60-外部仓库/openrig` 与 `deepseek-项目/10-openrig-deepseek`（D-005），故只登记、不实现。
- **去向**：`CHANGELOG.md ## 1.3 候选`之「wake/delivery 幂等去重 + 唤醒快照新鲜度」；同族样本（stuck 误报、stale wake）见 `QA-REPORT.md` P-001/R-001 与 `PROJECT §6` IC-1。

## 6. M10（teardown）的时点

teardown **不在** R1 `close_round` 执行（D-016）：R2 的复核必须使用同一 rig/daemon。M10 只能作为**最后一轮 QA PASS 之后**的收尾动作。因此：

- 本文件**不声称** M10 完成；
- 最终 teardown 证据（`rig ps` 空、tmux 无本 run session、daemon 停止、无 runner 残留）写入最终轮的证据目录，并在该轮 replicate 本文件的 M10 行。

## 7. 复跑命令

```bash
# M1（两种环境都要跑）
cd workflow-group && python3 -m pytest tests -q
env PATH=<PATH minus seat-bin> python3 -m pytest tests -q    # 期望 137/2

# M2/M4：现场渲染 v2 bundle 再 doctor
cd workflow-group/templates/specialized/openrig-workflow-master
python3 render_master.py --run-id rel-1 --project-root <repo> --output-dir /tmp/rel/x/openrig --json
python3 tools/openrig_bridge.py doctor --run-dir /tmp/rel/x

# M3：两目录逐字节
python3 render_master.py --run-id rel-2 --project-root <repo> --output-dir /tmp/rel/a/openrig --json
python3 render_master.py --run-id rel-2 --project-root <repo> --output-dir /tmp/rel/b/openrig --json
diff -r /tmp/rel/a/openrig /tmp/rel/b/openrig

# M5
rig workflow validate workflow-group/runs/openrig-master-v12-20261020/evidence/dsh/M5-workflow-rendered-real-rig.yaml --json

# M7
cd workflow-group/templates/specialized/openrig-workflow-master && sha256sum -c BASELINE-post.sha256
```

## 8. 尚未完成（不得被引用为已验收）

- **M10 teardown（唯一剩余项）**：由 MAIN 在 WS-F 执行，须为**最后动作**（D-016）。检查清单与当时残留见 §9.3；执行后在本文件回填事实行。
- `P-002`/`P-003` 的 ISSUES 行政收尾：`P-002` superseded by `P-004`；`P-003` 由 PMO 依 D-023 关闭（记录用「补齐并重排」）。均已非阻断。

## 9. R2（WS-E）独立复核结论

> packet `qitem-20261019223516-5ee71148fc8915fc` ｜ 复核时点 2026-10-20 06:42–06:46 CST ｜ 详见 `QA-REPORT.md §8`

### 9.1 判据

| 判据 | 结论 |
| --- | --- |
| M1-A（`rig`+`node`） | PASS — 139 passed / rc=0 |
| M1-B（无 `rig`、有 `node`，CI 等价） | PASS — 137 passed + 2 skipped / rc=0，两条 SKIP 均带具名理由 |
| M1-C（无 `node`） | WARN — 135 passed / 4 failed，属已文档化前置（§4） |
| M6 | PASS — `VERSION=1.2.0`；CHANGELOG 双小节 |
| M7(post) | PASS — 37/37 OK / rc=0（提交后复跑） |
| M8 | PASS — 5/5 ready；新渲染 spec `ok=true / stepCount=7`；投影按模板字节重绑定 |
| M10 | PASS（后补）：见 §9.4；QA 复核时未拆任何东西 |

**G3（M6/M7/M8）= PASS**，阻塞解除依据：MAIN 提交 `6581ad8`；QA 核验 `git rev-parse HEAD:workflow-group/tests/test_render_master_portability.py` = `da1faa14c5340219e18df1d71b6db6ec8220c312`（与其在树内实测的 blob 完全一致）。

### 9.2 为什么 M8 可以「按字节重绑定」而不再跑一次 probe

模板字节未变（`workflow.yaml.tpl` sha256 `73915634e3d94190a576bef00dd279777dd6d179187e23d8391d59e483a2d7e4`，与 R1 交付时记录的 post-hash 相同）；新渲染 spec 与 R1 probe spec 归一化后仅剩 id / rig 名差异。因此 R1 的**真实 exercised 投影**（hop 3 回 `implement_opencode` → hop 4 再进 `qa_opencode` → 终态 hop=7）对同一字节仍然成立，且重跑会向 live rig 注入 `plan` 包、污染在跑队列。MAIN 接受该论证，**不**要求重跑。

### 9.3 M10 teardown 检查清单（MAIN 执行，QA 未执行）

1. `rig ps --nodes` 无 `running` seat；2. `rig workflow status --json` 无 `active`/`waiting` 实例（R1 failed 实例作为过程记录保留）；3. `rig queue list --all-rigs --json` 只剩 terminal 行；4. 47896（live daemon）与 47897（R1 probe）均不再监听；5. `evidence/dsh/probe/home` 等隔离目录已清；6. 无遗留 tmux session / runner 进程；7. 结果在本文件记一行事实。

执行前（06:46Z 由 QA 记录）的残留：live rig 5/5 running；1 个 failed 实例（R1，保留）；队列仅 WS-E 包在 in-progress；47897 已 `000`，47896 正常响应。

- **R2 复核**：M6/M7(post)/M8(完整 E2E)/M10 须由新一轮 QA 复核；本轮 QA 仅验收 WS-A/WS-B，已明确「不得以本轮 PASS 代替发布验收」。
- **P-002/P-003 的 ISSUES 收尾**：P-002 已由本文件落实；P-003 需 PMO/QA 按实证关闭或重开。

### 9.4 teardown 执行（M10，最终动作）

- **执行者/时点**：MAIN（外部收口会话），2026-10-20 06:52 CST（R2 WS-F 的最终动作）。
- **执行前残留**：live rig 5/5 `running/ready`；1 个 `failed` workflow 实例（R1 `01M5B2VJ…`，作为过程记录保留）；队列无 pending/in-progress/blocked；端口 47896 正常、47897 已关；QA 未拆任何 daemon/rig/tmux。
- **实际命令与结果（原始证据：`evidence/main/M10-teardown-commands.txt`、`M10-teardown-down.json`、`M10-teardown-daemon-stop.txt`、`M10-teardown-post.txt`）**：
  1. `rig down openrig-openrig-master-v12-20261020 --json` → rc=1，返回 `sessionsKilled=0`、`alreadyStopped=true`、`errors=[]`、`deleted=false`。此前的 detached teardown 已停止全部 seat，故 down 是幂等确认为已停，不是失败。
  2. `rig daemon stop` → rc=0，输出 `Daemon stopped`。
  3. 事后复验：47896 / 47897 均无监听；无 `cli-agent-runner` / `opencode run` / `dsh --profile` / `rig daemon` 进程；默认 tmux 无 session。
- **隔离目录清理**：`/tmp/openrig-workflow-openrig-master-v12-20261020`、`/tmp/openrig-v12-pre-a`、`/tmp/openrig-v12-pre-b`、`/tmp/v12-current-check` 在 `realpath` 校验后删除；`M10-teardown-post.txt` 记录删除后状态。
- **结论**：M10 PASS（本 run 的 live seat/daemon/runner/tmux 残留为 0）；R1 failed 实例作为 OpenRig 历史记录保留，不作为 active 残留。

### 9.5 收口后补记（不改变 v1.2.0 验收）

- **P-006（S3）**：QA 负控制实验证明 `requires_rig` 保留的是“CLI 可解析”，而 `doctor` 本身不执行 live CLI 命令；P-004/P-005 的 CI 修复仍成立。按 **D-025** 接受为 1.3 候选「doctor 静态/live 拆分」，不重开 1.2.0。
- **R-003（S4）**：`CHANGELOG ## 1.3 候选` 已补 `queue packet body 512 字符截断` 条目；R-003 已按 D-024 关闭，去向由承诺变为工件。
- **最终 ledger**：ISSUES 全部行已关闭；`wf.py doctor` = PASS（errors=0, warns=0）。
