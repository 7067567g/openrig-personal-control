<!-- wf-evidence
run: openrig-master-selfopt-20261020
round: 1
doc: QA-SELF-OPT-RECHECK
owner: QA
state: pass
updated: 2026-10-20
-->

# QA-SELF-OPT-RECHECK — P-001 / P-002 聚焦复核（WS-3b 后）

> 复核快照：`2026-10-19T20:51:30Z`（本地 `2026-10-20 04:51:30 +0800`）。
> 依据：`QA-SELF-OPT.md` 初检/最终报告、`TDO-DSH-FIX-REPORT.md`、`TDO-DSH-REPORT.md`、`DECISIONS.md` D-009/D-011、当前 `ARCHITECTURE.md` / `tools/openrig_bridge.py` / `render_master.py`。
> 写权限：本文件 + `evidence/qa/recheck-*` + `ISSUES.xlsx`（issues.py）；**未改母版文件**。
> **结论：QA_RECHECK_PASS**。P-001/P-002 均通过；`ISSUES.xlsx` 中两条均 `已关闭`（D-011）；open S1/S2 = 0。保留 1 条非阻断 WARN（FIX 报告行号因 MAIN 04:44 改动略旧）。
> 历史证据说明：`evidence/qa/qa7-precheck-gaps.txt` 是 20:34Z 初检快照（当时 §5.4 未升级、doctor rc0），仅用于记录缺口；当前验收以本文件的 `recheck-*` 为准。

## 0. 复核摘要

| # | 复核项 | 判定 | 结果 |
| --- | --- | --- | --- |
| 1 | P-001：ARCHITECTURE §5.4 全部要求的 queue tuning terms | **PASS** | 11/11 术语命中；CLI flags 与 workflow.yaml 键真实存在 |
| 2 | P-002：doctor live / safetyMode=off / schemaVersion=999 / 文档一致性 | **PASS** | live rc0；两例非法 bridge 均 rc1 且指名字段；§3.2/§7 与 `render_master.py` 一致 |
| 3 | FIX 报告与 evidence 哈希；旧 dsh4 标记 | **PASS**（WARN） | 4/4 claimed sha256 与当前文件一致；dsh4 `superseded-by` 计数=1；FIX 行号 143/172→实际 149/178（非哈希问题） |
| 4 | live `doctor --run-dir ...` | **PASS** | rc=0，5 seats + home exists writable |
| 5 | P-001/P-002 关闭与 open S1/S2 | **PASS** | 两条 `已关闭（D-011）`；open S1/S2 = 0 |

**复核快照哈希**（详见 `evidence/qa/recheck-snapshot.txt`）：

```text
openrig_bridge.py      8c449235efdeed37b482976f80bd3ee320f0c44982eceef5771d047edf521c92
ARCHITECTURE.md        9fd734a33956ed23b63d1544fc8b639e349876cb87416ef49e0d56ebf0b51b97
render_master.py       4f0e32e6e215c0004e2859bbfeac30719163af5f7f078844234552e812bafcee
TDO-DSH-FIX-REPORT.md  415d60c4cf34a010e4cad9001af3745d939fb9835c2c220e224e5a0291bb3eb1
TDO-DSH-REPORT.md      8b224d080138796c74c5ebca21566008d188af3848e6714574c6df4ce717de75
dsh4-arch-diff.txt     3f9f63dd77c9820cfe6b9a211b973124a54d1663b56ad83161836dca24a5f63a
ISSUES.xlsx            e97133cb14920a02611db6a4596c61b9fad905b98677767ea31d15f1fb1eb5b7（含 R-001）
```

---

## 1. P-001 — §5.4 queue tuning 契约

命令/脚本输出：`evidence/qa/recheck-p001-terms.txt`。抽取 `### 5.4` 到 `### 5.5` 之间的正文，逐项断言：

| 要求术语（按本轮口径） | 命中 |
| --- | --- |
| packet 粒度 ≤1 个文件面 | **True** |
| packet 粒度 ≤3 个任务 | **True** |
| `tier`（含 fast/routine/deep/critical） | **True** |
| `priority`（含 routine/urgent/critical） | **True** |
| `rig queue` | **True** |
| 禁止直接写 sqlite | **True**（`禁止直接写 sqlite/queue 表`） |
| `max_hops` | **True** |
| `depends_on` | **True** |
| `fan-out` | **True** |
| `join` | **True** |
| `stale claim` | **True** |

`all_required=True`。§5.4 现为 7 行表（粒度、tier、priority、max_hops↔depends_on、fan-out/join、stale claim、写入面），每行有“落点/命令”。

真实命令/字段抽查：

- `rig queue create --help` 含 `--body-file`、`--tier`、`--priority`（见 `recheck-p001-terms.txt`）。
- `rig queue list --help` 含 `--state`；`rig queue unclaim --help` 含 `--reason`。
- live `workflow.yaml` 含 `steps[].depends_on`、`loop_guards.max_hops`（`max_hops: 10`）。
- queue row 有 `tier` / `priority` / `closureRequiredAt` 字段（`qa9-ws3b-p001-commands.txt`）。

**P-001：PASS。**

---

## 2. P-002 — doctor 载体校验与文档一致性

命令与结果：`evidence/qa/recheck-p002-doctor.txt`。

| 用例 | 命令 | rc | 实际输出 |
| --- | --- | --- | --- |
| live run | `python3 tools/openrig_bridge.py doctor --run-dir runs/openrig-master-selfopt-20261020` | **0** | `PASS bridge …`；`home=/tmp/openrig-master-selfopt-home exists writable` |
| `policy.safetyMode="off"` | `python3 tools/openrig_bridge.py doctor --run-dir /tmp/qa-recheck-safety` | **1** | `FAIL policy.safetyMode bridge=off spec=on-demand\|always` |
| `schemaVersion=999` | `python3 tools/openrig_bridge.py doctor --run-dir /tmp/qa-recheck-schema` | **1** | `FAIL schemaVersion bridge=999 spec=1` |

文档/实现一致性：

- `ARCHITECTURE.md:75`：`schemaVersion` 当前必须为 `1`，缺失/非 1 → `FAIL schemaVersion`。
- `ARCHITECTURE.md:86/88`：`policy.safetyMode` 仅允许 `on-demand`（默认）/`always`，缺失或其它值 → `FAIL policy.safetyMode`；与 `render_master.py` 生成值一致。
- `ARCHITECTURE.md:351/359–360`：§7 SAFETY 契约含 bridge 载体两行，并声明不执行 gate。
- `render_master.py:149`：`"schemaVersion": 1`；`:178`：`"safetyMode": "on-demand"`。

> 说明：FIX 报告 §3.1 引用 `render_master.py:143/172`，因 MAIN 在 04:44 又更新了该文件，当前行号为 `149/178`；**值一致**，属于行号漂移，不是 P-002 功能缺口。

**P-002：PASS。**

---

## 3. 报告/证据哈希与旧 dsh4 标记

验证输出：`evidence/qa/recheck-hashes.txt`。

| 产物 | 报告声称（FIX §3.3 / DSH §7） | 实际 sha256 | 判定 |
| --- | --- | --- | --- |
| `openrig_bridge.py` | `8c449235…` | `8c449235…` | MATCH |
| `ARCHITECTURE.md` | `9fd734a3…` | `9fd734a3…` | MATCH |
| live `OPENRIG-BRIDGE.json` | `20e09336…` | `20e09336…` | MATCH |
| `dsh4-arch-diff.txt` | `3f9f63dd…` | `3f9f63dd…` | MATCH |

- `dsh4-arch-diff.txt` 头部有 `# superseded-by: WS-3b fix-*.txt`，`grep -c` = **1**；其 `sha256 after=5b82d56d…` 是 WS-3b 前 ARCH，**不应**与当前 `9fd734a3…` 比对。
- `fix-6-sha256.txt` 的 4 行 sha256 与上表一致。
- FIX 报告 §3.1 的 `render_master.py:143/172` 行号陈旧（实际 149/178），值一致 → 非阻断 WARN。

**哈希/证据：PASS（1 WARN：行号）。**

---

## 4. live doctor 复跑

```bash
python3 tools/openrig_bridge.py doctor --run-dir runs/openrig-master-selfopt-20261020
# rc=0
# PASS bridge runId=openrig-master-selfopt-20261020 rig=openrig-master-selfopt workflow=openrig-workflow-master-selfopt
#   home=/tmp/openrig-master-selfopt-home exists writable
```

**PASS。**

---

## 5. ISSUES 关闭

按本轮要求，再次以 D-011 关闭（幂等；此前 20:43Z 已关闭一次）：

```bash
python3 scripts/issues.py close runs/openrig-master-selfopt-20261020/ISSUES.xlsx P-001 --decision D-011
# [OK] P-001 已关闭（D-011） rc=0
python3 scripts/issues.py close runs/openrig-master-selfopt-20261020/ISSUES.xlsx P-002 --decision D-011
# [OK] P-002 已关闭（D-011） rc=0
```

`issues.py list`：

```text
P-001  1  问题  S2  已关闭  否  I-7 §5.4 队列调优契约未落地
P-002  1  问题  S2  已关闭  是  I-10 SAFETY 契约与 doctor safetyMode/schemaVersion 校验未按计划落地
```

`list --open-only --severity S1` 与 `--severity S2` 均为空。

**PASS；open S1/S2 = 0。**

---

## 6. 最终判定

**QA_RECHECK_PASS。**

- P-001：§5.4 全部要求术语/命令/字段命中，关闭（D-011）。
- P-002：live doctor rc0；`safetyMode=off` 与 `schemaVersion=999` 均 rc1 且指名字段；ARCH §3.2/§7 与 `render_master.py` 一致，关闭（D-011）。
- 证据哈希 4/4 与当前文件一致；旧 `dsh4-arch-diff` 已标 `superseded-by`（计数 1）。
- 无 open S1/S2。唯一 WARN：FIX 报告对 `render_master.py` 的行号引用陈旧（143/172→149/178），不影响哈希/验收。

证据索引（均在 `evidence/qa/`）：

```text
recheck-p001-terms.txt
recheck-p002-doctor.txt
recheck-hashes.txt
recheck-issues.txt
recheck-issues-s3.txt
recheck-snapshot.txt
```

---

## 7. 追加流程风险 R-001（S3，不计入 S2）

按 MAIN 20:44Z 要求，在 `ISSUES.xlsx` 登记流程事故：

```bash
python3 scripts/issues.py add runs/openrig-master-selfopt-20261020/ISSUES.xlsx \
  --round 1 --type 风险 --severity S3 --status 已决议 --owner 主会话 \
  --title "流程事故：DECISIONS 重复 D-011 被整文件提交（D-014/D-017）" ...
python3 scripts/issues.py update ... R-001 --decision D-014
```

结果：`R-001`（风险 / S3 / 已决议 / D-014）。内容引用：
- `DECISIONS.md` D-014（非主会话重复 D-011、随 `e988f40` 入库、`28f038a` 清除）；
- D-017（撤回对具体个人的归因，保留“未授权 §1 写入 + 提交前未 diff 非本人段落”两项事实）；
- 预防动作：提交前 diff、执行侧只写本人文档/回执、后续给 DECISIONS/PROJECT/ISSUES 写入留 diff/hash 审计。

复核后 `--open-only --severity S1/S2` 均为空；R-001 是 S3 流程风险，**不影响 P-001/P-002 的 S2 判定**，也不构成 open S2。`ISSUES.xlsx` 当前哈希 `e97133cb…`。

证据：`evidence/qa/recheck-issues-s3.txt`。
