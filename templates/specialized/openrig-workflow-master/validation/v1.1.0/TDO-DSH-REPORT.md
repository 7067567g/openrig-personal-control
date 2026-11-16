# TDO-DSH-REPORT — WS-3（bridge / 诊断 / 文档）

| 项 | 值 |
| --- | --- |
| run | `openrig-master-selfopt-20261020` |
| packet | `qitem-20261019202230-6650a1af`（flow `implement_dsh`） |
| claim | 2026-10-19T20:23:54Z，`rig queue claim` |
| 写权限（SELF-OPT-PLAN §4） | `tools/openrig_bridge.py`、`ARCHITECTURE.md`、`TDO-DSH-REPORT.md`、`evidence/dsh/**` |
| 结论 | **PARTIAL（QA 复核前）**：DSH-1/2/3 PASS；DSH-4 的 P-001/P-002 已由 WS-3b 自验补齐（见 `TDO-DSH-FIX-REPORT.md`），待 QA 重跑 doctor 与 §5.4 检查后转 PASS。1 个 live 分支（transcripts 目录直读）受 DSH seat 沙箱限制，已用等价分支验证并列为 QA 复核项 |

## 1. 改动清单（仅白名单内）

### 1.1 `templates/specialized/openrig-workflow-master/tools/openrig_bridge.py`（126 → 545 行）

| 区域 | 行 | 改动 |
| --- | --- | --- |
| 常量/工具 | 32–87 | `SCHEMA_VERSION=2`、密钥模式、UTC `generatedAt`、`run_cli` 对 `FileNotFoundError`/超时返回结构化 rc（不再 traceback）、`_sha256` |
| `status` | 90–221 | 新增 `seats{total,ready,nodes}`、`workflow{instance,status,step,owner,frontier}`（按 bridge.workflowId 选 active 实例，读 `frontierPackets`）、`queue{total,pending,in-progress,blocked}`（按 `@<rig>` 过滤）、`sources`、`errors`、`degraded`；先落盘 `OPENRIG-STATE.json` 再输出；`--json`；`0` 全就绪 / `2` 降级 |
| `capture` | 223–323 | `capture-manifest.json`（`path/bytes/sha256`、`source{kind,dir}`、`generatedAt`）；密钥扫描 `sk-<token>`/`OPENAI_API_KEY=`/`Bearer <token>`，命中只报 `file:line:kind` 并 `rc=3`；目录不可读时逐 seat 回退 `rig transcript`；`--source`/`--out`；`rc≠0/部分失败`仍写 manifest |
| `doctor` | 395–526 | bridge ↔ `rig.yaml`（name、每个 member 的 cwd）↔ `workflow.yaml`（id、target.rig、roles 与 `preferred_targets`、seat 的 rig 后缀）交叉校验；`openrigHome` 可写/可创建；WS-3b 追加 `schemaVersion=1` 与 `policy.safetyMode ∈ {on-demand,always}` 校验；每条不一致输出 `FAIL <field> bridge=… spec=…`；PyYAML 缺失时用内置最小解析器（字段读不到即 FAIL，不假 PASS） |
| CLI | 528–545 | `--json`（status）、`--source`/`--out`（capture）；退出码与帮助文本对齐 |

### 1.2 `templates/specialized/openrig-workflow-master/ARCHITECTURE.md`（332 → 381 行）

- §4.3（170–202）：三命令的读取/写出/退出码表；`status --json` 与落盘字段一致；`capture` 清单可复算脚本；扫描模式与“不打印密钥”；`rc=2` 仍有部分证据。
- §4.5（218–242）：收口四步的命令/成功判据/证据路径表；明确 `rc=2/3` 不得写成 PASS。
- §3.2（69–91）：bridge 字段表补 `schemaVersion=1` 与 `policy.safetyMode ∈ {on-demand,always}`，并写明 doctor 校验。
- §5.4（292–307）：队列/工作流调优契约（packet 粒度上限、`tier`/`priority`、`max_hops`↔`depends_on`、fan-out、stale claim、禁止直接写 DB）。
- §7（349–368）：SAFETY 契约（`action_class`、`gate_result`、人工批准前置、账本路径、失败处理）+ bridge 载体（`schemaVersion`/`policy.safetyMode`）校验行，明示**本轮不实现执行器**；与 `SELF-OPT-PLAN §2.4` 的枚举/账本差异见报告 §7。

### 1.3 未改

`render_master.py`、`templates/**`、`VERSION`、`CHANGELOG.md`、`README.md`、`SPEC.md`、`DECISIONS.md`；live bundle 的 `OPENRIG-BRIDGE.json` / `rig.yaml` / `workflow.yaml`；queue/workflow 数据库（唯一写操作是按 packet 自身要求 claim）。

## 2. 验收命令与结果

在 `workflow-group/` 下执行；DSH seat 需 `export OPENRIG_URL=http://127.0.0.1:47893`（普通 seat 继承 `OPENRIG_HOME` 即可）。

| ID | 命令 | rc | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| DSH-1 | `python3 tools/openrig_bridge.py status --run-dir runs/… --json` | 0 | `json.loads` OK；seats 5/5；instance `01M5AX5…`；step/owner 齐全；queue 0/2/0 | `evidence/dsh/dsh1-status.json`、`dsh1-status.txt` |
| DSH-1b | 同上，临时 bridge `openrigCli=/bin/false` | 2 | 降级仍写 `OPENRIG-STATE.json`，`errors` 4 条 | `dsh1-status.txt` §B |
| DSH-2 | `python3 tools/openrig_bridge.py doctor --run-dir runs/…` | 0 | PASS；`home=/tmp/… missing but creatable`（沙箱视图） | `dsh2-doctor.txt` §A |
| DSH-2b | 临时 bridge `rigName=openrig-WRONG` | 1 | 首行 `FAIL rigName bridge=openrig-WRONG spec=openrig-master-selfopt` | `dsh2-doctor.txt` §B |
| DSH-2c | PyYAML 缺失路径 `_fallback_yaml` | 0 | rig name/members、workflow id/rig/roles/preferred_targets 均可读 | `dsh2-doctor.txt` §C |
| DSH-3 | `python3 tools/openrig_bridge.py capture --run-dir runs/… --out evidence/dsh/transcripts` | 0 | 5 文件 / 24586 B；manifest `scan.ok=true`；sha256 5/5 复算一致 | `dsh3-capture.txt`、`transcripts/capture-manifest.json` |
| DSH-3b | 临时 fixture 含 3 类假密钥 | 3 | 3 处命中仅报 `fixture.log:2/3/4`；KEY 值未出现在 stdout/stderr/manifest | `dsh3-capture.txt` §B |
| DSH-4 | `diff -u <pre-edit> ARCHITECTURE.md` | 1（有差异） | 90 行 diff（含 superseded 头）；前后 sha256 已记录 | `dsh4-arch-diff.txt` |

## 3. DSH 逐项结论

### DSH-1 — PASS

- `status` 现在一次聚合三类实时事实：seat ready、workflow frontier、queue 活跃计数；`generatedAt` 为 UTC。
- 退出码：`0` = seats 全 ready 且三类采集成功且找到实例；`2` = 任一降级（seat 未全 ready / 采集 rc≠0 / 实例缺失）。
- `rc=2` 时先写 `OPENRIG-STATE.json`，失败原因进 `errors[]` 与 `sources{}.rc`；“所有采集命令 rc≠0 仍落部分证据”已用 §B 实测。
- 实现选择：用 `workflow list --json` 而非 `workflow show <id>`，因为 list 的 `frontierPackets[]` 同时给出两个并行分支的 step/owner；实例仍按 `bridge.workflowId` + `status=active` 选定。

### DSH-2 — PASS

校验集合：bridge 必填字段、spec/project root/CLI 存在、rig name、每个 member 的 cwd、workflow id、`workflow.target.rig`、bridge 与 workflow 的 role 集合（缺/多都报）、每个 role 的 `preferred_targets`、每个 seat 的 `@<rig>` 后缀、`openrigHome` 可写或父目录可创建。

- live bundle：PASS，无 FAIL 行。
- 漂移：改 `rigName` 后 FAIL 首行直指 `rigName`；其余报错是同一字段的级联不一致（target.rig、各 seat 后缀），不是噪声检查。
- 未用 PyYAML 时走内置最小解析器；解析不出即 FAIL，不会把空文档当 PASS。

### DSH-3 — PASS（live 目录分支待 QA 复核）

- manifest 每文件记录 `path/bytes/sha256`，并记录 `source.kind`、`source.dir`、`generatedAt`；5/5 哈希已独立复算一致。
- 扫描命中 `rc=3`，只输出 `file:line:kind`；fixture 的假 key 值在 stdout/stderr/manifest 中均不存在（`LEAK_CHECK=PASS`）。
- **环境事实**：DSH seat 的 bash 运行在 `--tmpfs /tmp` 沙箱内，看不到 daemon home 的 transcripts 目录，因此 live 走 `cli-fallback`（`rig transcript`）；`transcripts-dir` 分支已用 fixture 目录验证。QA 在非沙箱 seat 跑默认命令应得到 `source.kind=transcripts-dir`，这是本报告唯一的“live 分支未在本人 seat 复现”项。

### DSH-4 — PARTIAL（WS-3b 自验已补齐，待 QA 复核）

- §4.3/§4.5 命令/退出码/证据契约已写入；§5.4 调优契约按 P-001 补齐；§7 SAFETY 契约 + bridge 载体（`schemaVersion`、`policy.safetyMode`）校验行已写入，明示不实现执行器。
- P-002 已落地：`doctor` 校验 `schemaVersion=1` 与 `policy.safetyMode ∈ {on-demand,always}`；live PASS，`safetyMode=off` rc1（`FAIL policy.safetyMode …`），`schemaVersion=999` rc1（`FAIL schemaVersion …`）。
- 枚举/账本与计划 §2.4 的设计差异保留（D-009 接受），逐项见报告 §7.1；修复与自验见 `TDO-DSH-FIX-REPORT.md`。**QA 重跑并关闭 P-001/P-002 前，不宣称最终 PASS。**

## 4. 契约 ↔ 实现对齐表（DSH-4）

| ARCHITECTURE 契约 | 实现/行为 | 证据 |
| --- | --- | --- |
| `status` 输出 seats/workflow/queue/generatedAt | `cmd_status` 组装同一 state 对象并落盘 | `dsh1-status.json` |
| `status --json` 与落盘字段一致 | 同一 `state` 变量 `json.dumps` 到 stdout 与文件 | `dsh1-status.txt` §A |
| `status` 退出码 0/2 | `return 2 if degraded else 0` | §A rc0；§B rc2 |
| `rc≠0` 仍落部分证据 | 先写文件、后返回；`errors`/`sources` 保留失败 | `dsh1-status.txt` §B |
| `capture` 清单含 files/bytes/sha256/source/time | `manifest["files"]` + `source` + `generatedAt` | `capture-manifest.json` |
| `capture` 密钥扫描 rc3 且不打印值 | `_scan_secrets` 只记 `file/line/kind`；`cmd_capture` rc3 | `dsh3-capture.txt` §B |
| `capture` 无文件/来源不可用/部分 seat 失败 rc1 仍写 manifest | 先写 manifest 再返回；`ok=false` | 代码 258–323；fixture 未覆盖 rc1（见 §5） |
| `doctor` 不一致格式 `FAIL <field> bridge=… spec=…` | `fmt()` 输出未加引号的标量 | `dsh2-doctor.txt` §B |
| `doctor` 交叉校验 bridge↔rig↔workflow↔home | `_doctor_check` 全部字段逐项比较 | `dsh2-doctor.txt` §A/B |
| `openrigHome` 可写或可创建 | 存在→`os.access(W_OK)`；不存在→父目录可写 | §A `missing but creatable` |
| SAFETY 动作类别/gate 枚举/人工批准/账本路径 + bridge 载体 | 文档契约；无执行器代码；枚举/账本差异保留（D-009 接受）；`doctor` 已校验 `schemaVersion=1` 与 `policy.safetyMode` | `dsh4-arch-diff.txt` §7；`fix-2/3-*` |

## 5. 未决项 / 薄弱点

1. **live transcripts 目录直读未在 DSH seat 复现**：沙箱屏蔽 `/tmp`，已实现并验证 `cli-fallback` 与 fixture 目录分支；QA 需在非沙箱 seat 跑一次默认 `capture` 确认 `source.kind=transcripts-dir`。
2. `capture` 的 `rc=1`（来源不可用 / 部分 seat 失败）已实现“仍写 manifest”，但未构造完整证据；可用一个不存在的 `--source` 复现。
3. `doctor` 的 `openrigHome` 在沙箱内显示 `missing but creatable`；非沙箱 seat 应显示 `exists writable`，属同一检查的两条分支。
4. `templates/specialized/openrig-workflow-master/` 在本仓库快照中未跟踪，`git diff --stat ARCHITECTURE.md` 为空；`dsh4-arch-diff.txt` 是对“反推 pre-image”的真实 diff（前后 sha256 见文件头），不是伪造的 git diff。MAIN 收口纳入版本控制后可改用 `git diff`。
5. `capture` 的 `cli-fallback` 依赖运行中的 daemon；收口 `daemon stop` 后只能走目录分支，符合“先冻结证据再停 daemon”的顺序。
6. SAFETY 执行器按计划不实现；本报告不声称任何 SAFETY 动作已被门控。
7. ~~**I-10 漏项**~~：已由 **WS-3b（D-009/D-011）** 关闭——`doctor` 校验 `policy.safetyMode` 与 `schemaVersion`，§5.4/§7 契约补齐；见 `TDO-DSH-FIX-REPORT.md`。`gate_result`/账本的设计差异仍按 §7.1 登记（D-009 接受）。

## 6. 证据清单

```text
runs/openrig-master-selfopt-20261020/
├── OPENRIG-STATE.json                         # status 最后一次 live 落盘（5/5 ready）
├── TDO-DSH-REPORT.md                          # 本文件
├── TDO-DSH-FIX-REPORT.md                      # WS-3b（P-001/P-002）修复验收
└── evidence/dsh/
    ├── dsh1-status.json                       # status --json 原样输出
    ├── dsh1-status.txt                        # live rc0 + 降级 rc2 部分证据
    ├── dsh2-doctor.txt                        # live PASS + rigName 漂移 FAIL + YAML fallback
    ├── dsh3-capture.txt                       # live capture + 哈希复算 + 假 key rc3/不泄露
    ├── dsh4-arch-diff.txt                     # ARCHITECTURE 前后 diff（WS-3b 前快照，头部已标 superseded-by）
    ├── fix-1-doctor-live.txt                  # live doctor PASS
    ├── fix-2-doctor-safetyMode.txt            # safetyMode=off → FAIL policy.safetyMode
    ├── fix-3-doctor-schemaVersion.txt         # schemaVersion=999 → FAIL schemaVersion
    ├── fix-3b-doctor-schemaVersion-missing.txt # 缺失 schemaVersion → FAIL（额外）
    ├── fix-6-sha256.txt                      # WS-3b 后产物哈希对齐
    ├── fix-7-repro.txt                       # doctor + 两个负例的一条命令复跑
    ├── fix-4-arch-p001-terms.txt              # §5.4 必需术语核对
    ├── fix-5-arch-p002.txt                    # §3.2/§7 与 render_master 对齐
    └── transcripts/
        ├── capture-manifest.json              # 5 文件 / 24586 B / sha256 / scan.ok=true
        └── *@openrig-master-selfopt.log       # 5 seats transcript（.gitignore 忽略，仅留盘）
```

代码/文档基线哈希（WS-3b 后）：`openrig_bridge.py` = `8c449235efdeed37b482976f80bd3ee320f0c44982eceef5771d047edf521c92`；`ARCHITECTURE.md` = `9fd734a33956ed23b63d1544fc8b639e349876cb87416ef49e0d56ebf0b51b97`。

## 7. 与 SELF-OPT-PLAN §2.4（I-10）的差异及理由

> 本节是 PMO 2026-10-19 20:32Z 核对后的补记，2026-10-19T20:39Z 由 WS-3b（D-009/D-011）更新：**I-10 的 doctor 枚举校验已落地**（`policy.safetyMode` + `schemaVersion`），P-001 §5.4 契约已补齐；其余枚举/账本差异保留并按下表登记。验收见 `TDO-DSH-FIX-REPORT.md`。

### 7.1 I-10 逐项对照

| I-10 要求 | 交付现状 | 判定 / 理由 |
| --- | --- | --- |
| `action_class`: `delete` / `publish` / `hdrive_write` / `perm_change` | `read-only` / `write-reversible` / `delete-irreversible` / `external-publish` / `permission-change` / `hdisk-write` | **差异**。按「可逆性 + 授权域」分类，覆盖计划四类并补只读/可逆写；`hdisk-write` 与 `hdrive_write` 命名不同。若 QA 按计划字面，判不一致；对齐只需改文档枚举，不影响代码 |
| `gate_result`: `gate_pass` / `gate_fail` / `safety_pending` / `safety_reject` / `executed_ok` / `executed_bad` | `PASS` / `FAIL` / `NEEDS-HUMAN` / `EXPIRED` | **差异**。交付把「gate 决策」与「执行结果」分开：`executed_ok/bad` 是执行后事实，应由账本 `executed_at/evidence/result` 记录，不应作为 gate 返回值；`NEEDS-HUMAN` 覆盖 `safety_pending`，`EXPIRED` 覆盖批准过期。计划把两者合并在一个枚举里 |
| 前置条件：独立 SAFETY seat ≠ 提出者/执行者/QA/人工批准人 | 具名 human `approve` + 不得自批/批量批准；未把「独立 seat」写成硬前置 | **差异**。本轮 D-005 为 `on-demand`，且 I-10 明确「不新增 seat 到默认 rig」；把独立 seat 写成硬前置会与默认 rig 冲突。启用 SAFETY 的 run 应在该 run 的 SPEC 中显式声明 seat 与隔离关系 |
| 账本：`safety/{actions,gates,reviews,human-approvals,executions}/` 目录 | `runs/<run-id>/safety/gate-ledger.jsonl` 单文件 | **差异，已获 PMO 认可**（20:32Z：“单 JSONL 我认可更简”）。理由：单文件原子追加、无跨文件一致性；每条记录用 `type` 区分 action/gate/review/approval/execution |
| bridge `policy.safetyMode` ∈ {`on-demand`,`always`}；doctor 对 `"off"` 临时 bridge FAIL、live `on-demand` PASS | live 值为 `on-demand`；`doctor` 已校验 `on-demand|always`，缺失/非法值 FAIL | **已落地（P-002）**：live PASS；`safetyMode=off` → `FAIL policy.safetyMode bridge=off spec=on-demand|always` rc1；`schemaVersion=999` → `FAIL schemaVersion bridge=999 spec=1` rc1 |
| D-006：闭包字段上游行为标注 | §7 不引用 `closureReason`/`closureTarget` | **条件未触发**，无差异。若未来触及，按 UPSTREAM SIDE + `workflow-projector.ts:1089-1096` + `transitionNote` 标注 |

### 7.2 schemaVersion 语义

| 对象 | 当前值 | 语义 / 谁该升 |
| --- | --- | --- |
| `OPENRIG-BRIDGE.json` | `1` | **bridge 文件形状**版本。本轮未增删字段，保持 1；只有增删字段或改字段语义时才升 2。WS-3b 后 `doctor` **要求必须为 `1`**，缺失/非 1 报 `FAIL schemaVersion` |
| `OPENRIG-STATE.json`（status） | `2` | 工具**输出工件**版本。DSH-1 新增 `seats/workflow/queue/sources/errors/degraded`，故为 2 |
| `capture-manifest.json`（capture） | `2` | 工具输出工件版本。DSH-3 新增 `files/bytes/sha256/source/scan/generatedAt`，故为 2 |
| doctor 是否校验 bridge.schemaVersion | 是（WS-3b） | 只接受 `1`；缺失/非 1 报 `FAIL schemaVersion`。若未来 bridge 形状升 2，先更新本契约与 doctor 的已知版本集合 + 迁移提示 |

**兼容口径**：bridge 是输入契约（形状未变，仍 1）；status/capture 是本工具的新输出（2）。两者版本号独立演进，不要求相等；读取方应按各自对象的 `schemaVersion` 分支，不能拿输出 2 去要求 bridge 升 2。

### 7.3 对 QA 的建议

- I-10 的 `doctor` 枚举校验：**已落地（P-002）**；QA 重跑 live PASS + `safetyMode=off` rc1 + `schemaVersion=999` rc1 即可关闭。
- 其余枚举/账本差异：若 QA 严格按 `SELF-OPT-PLAN §2.4` 字面对齐，判不一致是合理的；是否接受差异由 PMO/QA 决定，本报告不自行豁免。
