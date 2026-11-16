# TDO-DSH-FIX-REPORT — WS-3b（P-001 / P-002）

| 项 | 值 |
| --- | --- |
| run | `openrig-master-selfopt-20261020` |
| 触发 | QA_FAIL：P-001（S2，I-7 §5.4 契约未落地）、P-002（S2，I-10 doctor `safetyMode`/`schemaVersion` 未校验） |
| 授权 | `DECISIONS.md` D-009 + D-011（D-009=WS-3b 最小边界；D-011=I-7 §5.4 并入） |
| 范围 | `ARCHITECTURE.md` §3.2/§5.4/§7、`tools/openrig_bridge.py` 的 `_doctor_check`、本报告与 `evidence/dsh/fix-*.txt` |
| 结论 | **P-001 自验 PASS（文档）**；**P-002 自验 PASS（代码 + 文档）**；**DEFERRED：无**。QA 复核前不宣称最终 PASS |

## 1. 改动清单

| 文件 | 行 | 改动 |
| --- | --- | --- |
| `templates/specialized/openrig-workflow-master/tools/openrig_bridge.py` | 410–423 | `_doctor_check` 新增 bridge 载体校验：`schemaVersion` 必须为 `1`；`policy.safetyMode` 必须 ∈ `{on-demand, always}`；缺失/非法均输出 `FAIL <field> bridge=… spec=…`，`cmd_doctor` 返回 1 |
| `templates/specialized/openrig-workflow-master/ARCHITECTURE.md` §3.2 | 75、86、88 | bridge 字段表补 `schemaVersion=1`；`policy` 行写明 `safetyMode` 枚举与 doctor 校验 |
| `templates/specialized/openrig-workflow-master/ARCHITECTURE.md` §5.4 | 292–307 | 用可执行表替换原 5 条原则：packet 粒度上限（≤1 文件面 + ≤3 任务）、`tier`、`priority`、`max_hops`↔`depends_on`、fan-out、stale claim、写入面（禁止直接写 DB） |
| `templates/specialized/openrig-workflow-master/ARCHITECTURE.md` §7 | 351、359–360 | SAFETY 契约补 bridge 载体两行（`schemaVersion`、`policy.safetyMode`），并声明 doctor 只校验载体、不执行 gate |
| `runs/openrig-master-selfopt-20261020/TDO-DSH-REPORT.md` | 结论/§3/§4/§5/§7 | 同步为 WS-3b 后状态；保留 gate_result/账本设计差异说明 |
| `runs/openrig-master-selfopt-20261020/evidence/dsh/fix-*.txt` | — | 本次验收证据 |

**未改**：`render_master.py`、`templates/**`、`VERSION`、`CHANGELOG.md`、`README.md`、`SPEC.md`、`ISSUES.xlsx`；live `OPENRIG-BRIDGE.json` / `rig.yaml` / `workflow.yaml`；`gate_result` 枚举实现；queue/workflow 状态；未启停 daemon/rig。

## 2. P-001 验收（§5.4 契约）

| 检查项 | 结果 | 位置 |
| --- | --- | --- |
| packet 粒度上限：≤1 个文件面、≤3 个任务 | 有 | §5.4 第 1 行 |
| `tier` 规则（`fast/routine/deep/critical`；workflow 投影沿用引擎默认） | 有 | §5.4 `tier` 行 |
| `priority` 规则（`routine/urgent/critical`，urgent 需写明阻塞点，critical 仅 S1/人工门控） | 有 | §5.4 `priority` 行 |
| `max_hops` 与 `depends_on` 分工 | 有 | §5.4 对应行 |
| fan-out 判据 + join 列全部分支 | 有 | §5.4 对应行 |
| stale claim 的 `rig queue` 读法与 watchdog 机制 | 有（`queue-stuck-sweep`、`parked-owner-consumer`） | §5.4 对应行 |
| 禁止直接写 DB / 手改 bridge / 绕过 daemon | 有 | §5.4 `写入面` 行 |
| 每条指向 `rig queue` / `workflow.yaml` 键 | 有 | §5.4 “落点 / 命令”列 |

证据：`evidence/dsh/fix-4-arch-p001-terms.txt`（`section_found=True`，`tier/priority/≤1 个文件面/≤3 个任务/rig queue/直接写 sqlite/max_hops/depends_on/fan-out/stale claim` 全部 `True`）。

说明：本表是**母版级契约**，不对历史已超限 packet 追溯拆包（本轮 DSH packet 自身 4 项任务，作为历史例外保留）；新 packet 按此收口。

## 3. P-002 验收（doctor 载体校验）

| 用例 | 命令 | rc | 关键输出 | 证据 |
| --- | --- | --- | --- | --- |
| live run（`schemaVersion=1`、`safetyMode=on-demand`） | `python3 tools/openrig_bridge.py doctor --run-dir runs/openrig-master-selfopt-20261020` | **0** | `PASS bridge …` | `fix-1-doctor-live.txt` |
| 临时 bridge `policy.safetyMode="off"` | 同上，`--run-dir <tmp>/run` | **1** | `FAIL policy.safetyMode bridge=off spec=on-demand|always` | `fix-2-doctor-safetyMode.txt` |
| 临时 bridge `schemaVersion=999` | 同上，`--run-dir <tmp>/run` | **1** | `FAIL schemaVersion bridge=999 spec=1` | `fix-3-doctor-schemaVersion.txt` |
| 临时 bridge 删除 `schemaVersion`（额外） | 同上 | **1** | `FAIL schemaVersion bridge=(missing) spec=1` | `fix-3b-doctor-schemaVersion-missing.txt` |

临时 bridge 均在 `/tmp` 创建（从 live bridge 复制，仅替换目标字段与 `openrigHome`），**未写入** run 目录或 live bundle。

### 3.1 实现细节

- `schemaVersion`：`isinstance(..., bool)` 排除布尔（`True == 1`），只接受 `int == 1`；缺失按 `(missing)` 报。
- `policy`：必须是 object；`safetyMode` 只接受 `on-demand` 与 `always`；缺失或其它值（含 `always-ish`、`off`）FAIL。
- 输出统一走现有 `FAIL <field> bridge=… spec=…` 文案；`cmd_doctor` 沿用 `if failures: return 1`。
- 与 `render_master.py` 一致：`bridge["schemaVersion"] = 1`（`render_master.py:143`），`policy.safetyMode = "on-demand"`（`render_master.py:172`）。证据：`fix-5-arch-p002.txt`。

### 3.2 一条命令复跑

在 `workflow-group/` 下执行：

```bash
B=templates/specialized/openrig-workflow-master/tools/openrig_bridge.py
R=runs/openrig-master-selfopt-20261020

python3 "$B" doctor --run-dir "$R"; echo "live_rc=$?"                  # 期望 0

T=$(mktemp -d); mkdir -p "$T/run/openrig" "$T/home"
python3 - "$T" <<'PY'
import json,sys,pathlib
t=pathlib.Path(sys.argv[1]); src=pathlib.Path("runs/openrig-master-selfopt-20261020/openrig/OPENRIG-BRIDGE.json")
b=json.loads(src.read_text()); b["openrigHome"]=str(t/"home"); b["policy"]["safetyMode"]="off"
(t/"run/openrig/OPENRIG-BRIDGE.json").write_text(json.dumps(b,indent=2))
PY
python3 "$B" doctor --run-dir "$T/run"; echo "safetyMode_off_rc=$?"    # 期望 1

python3 - "$T" <<'PY'
import json,sys,pathlib
t=pathlib.Path(sys.argv[1]); b=json.loads((t/"run/openrig/OPENRIG-BRIDGE.json").read_text())
b["policy"]["safetyMode"]="on-demand"; b["schemaVersion"]=999
(t/"run/openrig/OPENRIG-BRIDGE.json").write_text(json.dumps(b,indent=2))
PY
python3 "$B" doctor --run-dir "$T/run"; echo "schemaVersion_999_rc=$?" # 期望 1
rm -rf "$T"
```

期望 `0 / 1 / 1`；完整实跑输出见 `fix-7-repro.txt`。

### 3.3 sha256 对齐（WS-3b 后）

| 产物 | sha256 | 说明 |
| --- | --- | --- |
| `openrig_bridge.py` | `8c449235efdeed37b482976f80bd3ee320f0c44982eceef5771d047edf521c92` | 含 `_doctor_check` 新校验 |
| `ARCHITECTURE.md` | `9fd734a33956ed23b63d1544fc8b639e349876cb87416ef49e0d56ebf0b51b97` | 含 §3.2/§5.4/§7 修订 |
| live `OPENRIG-BRIDGE.json` | `20e09336d330ed04a64114037840d6910c6b9aa80af78eca74d1b1a91286517c` | 只读，未改 |
| `dsh4-arch-diff.txt` | `3f9f63dd77c9820cfe6b9a211b973124a54d1663b56ad83161836dca24a5f63a` | **WS-3b 前快照**；头部 `sha256 after=5b82d56d…` 为旧 ARCH，已标 `superseded-by: WS-3b fix-*.txt` |

完整输出见 `fix-6-sha256.txt`。

> `dsh4-arch-diff.txt` 不应与当前 `ARCHITECTURE.md` 比对 sha256：它证明的是 WS-3b 前 DSH-4 的文档改动。WS-3b 的当前文件哈希以本节 + `fix-6` 为准。

## 4. 契约 ↔ 实现对齐表

| 契约 | 实现 | 证据 |
| --- | --- | --- |
| bridge `schemaVersion` 必须为 1 | `_doctor_check` 410–415 | `fix-1` rc0；`fix-3` rc1 |
| bridge `policy.safetyMode` ∈ `{on-demand, always}` | `_doctor_check` 416–423 | `fix-1` rc0；`fix-2` rc1 |
| 失败格式 `FAIL <field> bridge=… spec=…` | 复用 `fmt()`/f-string | `fix-2`、`fix-3` |
| 失败非零退出 | `cmd_doctor` `if failures: return 1` | `fix-2/3` rc1 |
| §3.2 字段表与 `render_master.py` 输出一致 | 文档行 75/86/88 + `render_master.py:143/172` | `fix-5` |
| §7 契约含 bridge 载体行 | 文档行 351/359–360 | `fix-5` |
| §5.4 可执行调优契约 | 文档 292–307 | `fix-4` |
| 不实现 gate / 不改 `gate_result` | 无新增执行器代码；§7 明示 | `fix-5` |

## 5. PASS / FAIL / DEFERRED

- **P-001：PASS（自验）**（文档契约落地，术语逐项可查；待 QA 复核）。
- **P-002：PASS（自验）**（live PASS + 两个指定 FAIL 用例 + 缺失字段用例；待 QA 复核）。
- **DEFERRED：无**。
- 保留的设计差异（非缺陷，D-009 已接受）：`gate_result` 4 值 vs 计划 6 值、单 JSONL 账本 vs 五目录、`action_class` 命名差异；仍记录在 `TDO-DSH-REPORT.md` §7.1。

## 6. 已知限制

1. 本仓库快照中 `templates/specialized/openrig-workflow-master/` 除 `render_master.py` 外仍未跟踪，`git diff --stat ARCHITECTURE.md` 可能为空；改动以文件哈希与本报告行号为准。`dsh4-arch-diff.txt` 是 WS-3b 前快照，已标 `superseded-by`，不能与当前 ARCH 哈希比对。
2. DSH seat 的 `/tmp` 被沙箱 tmpfs 屏蔽，live doctor 的 `openrigHome` 显示 `missing but creatable`；QA 在非沙箱 seat 应看到 `exists writable`，属同一检查分支。
3. §5.4 是文档契约，不改运行时代码；packet 粒度上限不会被工具强制，由 PMO/TDO 在拆包时执行。
4. `rig queue update` 无 `--priority/--tier`（已核对 CLI）：§5.4 只写 `create` 与 `handoff` 的改级路径，不承诺原地改级。
5. 旧 bridge 若省略 `schemaVersion` 现在会 FAIL（`(missing)`）；这是 D-009 的预期收紧，不是回归。
6. 本轮未触碰 queue/workflow；未重启 daemon/rig。

## 7. 收尾核实（`qitem-20261019204613-9a6d5f2b9cf784fe`）

- **STATUS**：旧行保留（04:29 的 DSH-4 完成行 + 给 QA 的 `DSH-1/2/3/4 全 PASS` 行），04:43 追加更正行；`state` 仍 `qa-pending`，未改旧行/未动 state。
- **证据时效**：`dsh4-arch-diff.txt` 的 `superseded-by` 计数 = 1；`TDO-DSH-REPORT.md` 的 §7 引用为 349–368。
- **写入面**：本收尾包只写 STATUS 一行、本节、`evidence/dsh/fix-8-closeout.txt`；WS-3b 的代码/文档改动在 04:40 前已完成，本包未再写代码。
- **并行改动说明**：`render_master.py` 当前 `HEAD=914c382`（OC/MAIN，04:45，工作树 clean）；`VERSION`/`CHANGELOG.md` mtime=04:37:59，均早于/独立于本包，不是本包写入。
- **live doctor**：`rc=0`。
