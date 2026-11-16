# 00 — Round 1 执行计划（P1 hard constraints）

> run: `openrig-p1-hard-constraints-20261116` ｜ 轮次：1 ｜ 作者：MAIN（`plan` 包）
> 权威顺序：`TASK.md` > `SPEC.md` > `PROJECT.md`；本文件只做拆分与验收口径，不改判据。
> 硬约束：只改 `workflow-group/scripts/**`、`workflow-group/tests/**`、`workflow-group/WORKFLOW-TAGS.md`、
> `workflow-group/templates/specialized/openrig-workflow-master/{README,ENTRYPOINTS,ARCHITECTURE}.md`、
> `.github/workflows/wf-validate.yml`、本 run `reports/**`；不 commit/push；不覆盖 pre-existing dirty。

## 1. 目标与边界

把 P1 的六个缺口做成可失败、可复跑的机器门：

- **W2** preflight 失败路径不产生副作用（AGENTS.md / monitor target / systemd）；
- **W3** 历史 run 可用 `wf.py meta-set` 回填 `.run-meta.json`；
- **W4** `scripts/snapshot_files.py` 可对 untracked 文件记录 before/after；
- **R09** `WORKFLOW-TAGS.md` canonical 计数与目录实测一致，并接入 CI；
- **R10** `scripts/audit_managed_blocks.py` 只读枚举 managed block，orphan 可 `--strict` 失败；
- **R11** `scripts/openrig_run.py check/start` 顺序 wrapper，fail-closed；
- **R12** 复制/生成边界写进母版 ENTRYPOINTS；
- **W5** `verify_render.py` 支持合法 render specialization；
- **R04b** `wf_close_lint.py --strict` 兼容根 `FINAL.md` 与 `reports/FINAL.md`。

**不包含**：R13/R14、OpenRig 产品代码、其它 run、`workflow-group/README.md`、模板正文重写、任何删除/发布/权限变更。

## 2. 规划基线（只读事实，2026-11-15T16:49Z 复测）

| 项 | 值 | 来源 |
| --- | --- | --- |
| KB HEAD | `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac` | `git rev-parse HEAD` |
| KB status sha256 | `b4b8dca1caa3091e8fc56b902fe281e299b09f9fa0256ac64c00f6331951367e` | 排除本 run 目录；与基线一致 |
| KB diff sha256（基线时刻） | `cd0c7c3397b697dbb15df4c92c3fe69c27d25247e3015d157a9ba168f4c271db` | `00-baseline.txt` |
| KB diff sha256（plan 时刻） | `d26a5ceccd8c2d265860600fb869fd478f6712f03060aa28e6c2470ba91f0b5a` | 复测，见 §2.1 |
| 产品仓 | `/home/a7067567g/下载/deepseek/deepseek-项目/10-openrig-deepseek` | — |
| 产品 HEAD | `e932ae94e4c07b619c39902f29db949464ebb295` | 只读 |
| 产品 status sha256 | `3b64cf901a0c232fbbae7e5937111671a01be558c910ae09132756fe54b7e269` | 29 条 pre-existing dirty |
| 产品 diff sha256 | `2cbcef6ebf021e87f1e084092af0c0105872057249ee72a2aff2eaf7c4d0e4f7` | 只读 |
| 运行时 | `.venv/bin/python` 3.12.15、pytest 9.0.2、`rig` openrig-local 0.1.4 | `--version` |
| 全量 pytest 基线 | `259 passed`，rc=0 | `pytest tests -q` |
| `doc_consistency --check` | rc=1；`canonical` 声明 55、实测 **62**；baseline 9=9、specialized 26=26 已一致 | 实测 |

### 2.1 基线漂移（必须显式处理）

`00-baseline.txt` 于 `16:47:32Z` 采集，之后仓库根 `AGENTS.md`（mtime `00:48:07 +08:00`）发生过一次外部写入，
导致 `git diff` 内容变化而 `status --porcelain` 路径集合不变（status sha 仍一致）。

处理规则（Packet A 起手执行）：

1. 先把 `reports/evidence/00-baseline.txt` 复制为 `reports/evidence/00-baseline.original.txt` 留档；
2. 重跑 `wf.py baseline openrig-p1-hard-constraints-20261116 --json` 生成新基线；
3. 新基线作为 scope diff 的比较基准；**AGENTS.md 的本次漂移不得算作实现改动**，但也不得由实现方回滚；
4. QA 需核对：漂移仅限 `AGENTS.md`，未混入本任务实现内容。

### 2.2 canonical 计数说明

TASK 写「当前 actual=61」，实测为 **62**——多出的 1 个正是本 run 目录自身被创建后的结果。
Packet B 必须以**实测值**为准（当前 62），不得照抄 TASK 的 61；若 Packet B 期间又新增 run 目录，
以 `doc_consistency.py --check` 输出为准并记录原因。

## 3. 包边界（文件级，单写者）

### 3.1 Packet A — W2/W3/W4（`impl_preflight_evidence`）

新建：

- `scripts/snapshot_files.py`
- `tests/test_snapshot_files.py`

修改：

- `scripts/openrig_preflight.py`
  - 顺序：**无副作用 pre-check**（`preflight_file` / `required_components` / `run_context` / `run_docs`）→ 任一 required 失败即返回 rc=1（`--advisory` 时 rc=0），且 `injectedAgents=null`、`monitor=null`；
  - 仅 pre-check 全过后才 `inject_agents` 与 `register_monitor`；
  - 注入后再跑 `check_workspace_context`；
  - `ok = all(required checks)` 语义不变；`--advisory` 仍只影响 rc，绝不伪造 `ok:true`。
- `scripts/wf.py`（**仅**新增 `meta-set <run-id> --project-root PATH [--scope TEXT] [--json]`；`new-run` 写 meta 行为保持）
  - `baseline` 缺 projectRoot 的错误信息必须同时给出 `meta-set` 与 `--project-root` 两条修复路径。
- `tests/test_openrig_preflight.py`（新增无副作用负向用例）
- `tests/test_wf_baseline.py`（旧 run 无 meta → meta-set → baseline 可跑）

禁止：Packet B/C/D 的 `doc_consistency`、`audit_managed_blocks`、`openrig_run`、`verify_render`、`wf_close_lint`。

### 3.2 Packet B — R09/R10（`impl_ci_blocks`）

新建：

- `scripts/audit_managed_blocks.py`
- `tests/test_audit_managed_blocks.py`

修改：

- `workflow-group/WORKFLOW-TAGS.md`（仅顶部时效声明计数 `canonical=55` → 实测值）
- `.github/workflows/wf-validate.yml`（`pytest` 后追加 `doc_consistency.py --check` 与 `test_doc_consistency.py`；不改触发范围）

禁止：改 `managed-blocks.ts`、迁移 block 命名空间、给 `--strict` 设默认开启。

### 3.3 Packet C — R11/R12（`impl_wrapper_boundary`）

新建：

- `scripts/openrig_run.py`
- `tests/test_openrig_run.py`

修改：

- `workflow-group/templates/specialized/openrig-workflow-master/ENTRYPOINTS.md`（R12 复制 vs 生成边界）

禁止：改 `workflow-group/README.md`（不在 TASK §0 白名单）、改 `workflow instantiate` 语义、在 `--dry-run` 中调用任何 live 命令。

### 3.4 Packet D — W5/R04b（`impl_close_render`）

新建（可选其一，若拆测试文件）：

- `tests/test_wf_render_specialize.py`

修改：

- `scripts/verify_render.py`（`--specializations <json>`；默认读 `<run-dir>/openrig/render-specializations.json`）
- `scripts/wf.py`（**仅**新增 `render-specialize <run-id> --path <rel> --reason TEXT [--json]`）
- `scripts/wf_close_lint.py`（strict 接受 `run_dir/FINAL.md` 或 `run_dir/reports/FINAL.md`，优先 `reports/FINAL.md`）
- `tests/test_verify_render.py`、`tests/test_wf_close_lint.py`

禁止：放宽 `closeout.json`、sha256、revision 链检查；改动 manifest 语义。

### 3.5 共享文件串行

`scripts/wf.py` 被 A（meta-set）与 D（render-specialize）共用；执行顺序固定 A → B → C → D。
后包起手前必须：前包已 handoff、`git status` 无半成品、`pytest` 无新增红。

## 4. 行为契约（实现必须逐条满足）

### 4.1 W2 preflight 顺序

| # | 动作 | 失败时 |
| --- | --- | --- |
| 1 | `preflight_file` / `required_components` / `run_context` / `run_docs` | 立即返回；**零写入** |
| 2 | `inject_agents`（有 `--workspace` 时） | 记录到 `injectedAgents` |
| 3 | `register_monitor`（有 run_dir 且未 `--no-monitor`） | 记录到 `monitor` |
| 4 | `check_workspace_context` | 计入 `ok` |

### 4.2 W4 snapshot 输出

每条 `{path, bytes, sha256, mtime, label, capturedAt, exists}`；缺失文件 `exists:false` 且不抛异常；只读。

### 4.3 R10 block 审计

`kind ∈ {preflight, managed, unknown}`；`ownerRig` 无法推断为 `null`；
默认 rc=0；`--strict` 仅在存在 `ownerRig == null` 的 **managed** block 时 rc=1。

### 4.4 R11 check 顺序与 rc

| # | 检查 | 失败语义 |
| --- | --- | --- |
| 1 | 读 `openrig/OPENRIG-BRIDGE.json` | 缺/坏 → rc2 |
| 2 | `verify_render.py` | 默认 WARN；`--strict-render` 阻塞 |
| 3 | `tools/openrig_bridge.py doctor` | rc≠0 阻塞 |
| 4 | `openrigCli workflow validate <spec> --json` | rc≠0 阻塞 |
| 5 | `openrigCli ps --nodes --rig <rigName> --json` | daemon down 默认阻塞，`--allow-daemon-down` 降 WARN；up 时所有 seatMap target 必须存在且 `startupStatus=="ready"` |

输出 `{ok, checks[], next[]}`；`ok=false` → rc=1（被显式降级项除外）。

### 4.5 R11 start

先 `check --allow-daemon-down`；`--dry-run` 只返回命令序列、零 live 调用；
非 dry-run 顺序 `daemon start --no-kernel --port` → `up` → 轮询 `ps` 到全 ready（timeout）→ `workflow validate` → `workflow instantiate`；
任一步失败立即停并给回滚提示，**不自动删 home/DB**。

### 4.6 W5 specialization

manifest 与磁盘不符、但 specialization 条目 `bytes`+`sha256` 与磁盘精确一致 → `ok:true`、item `specialized:true`；
stale specialization 仍 mismatch；`--strict` 遇 exact specialization 不失败。

### 4.7 R04b FINAL 双路径

`reports/FINAL.md` 优先，其次根 `FINAL.md`；两者皆缺 → ERROR；`closeout.json` entry、sha256、revision 语义不变。

## 5. 测试矩阵（每门至少 1 个负向）

| 门 | 正例 | 负向用例 | 命令 | 期望 |
| --- | --- | --- | --- | --- |
| W2 | 完整 workspace + 有效 run | 临时 workspace + 不存在 run-id | `pytest tests/test_openrig_preflight.py` | rc1；AGENTS.md 字节不变；`target.json` 未生成；无 `systemctl start` |
| W2 | 同上 | 缺 run docs | 同上 | `run_docs=false`，仍零写入 |
| W2 | 全通过 | — | 同上 | `ok:true`，注入发生在 pre-check 之后 |
| W3 | 旧 run 无 meta | 不先 meta-set 直接 baseline | `pytest tests/test_wf_baseline.py` | 报错含 `meta-set` 与 `--project-root`；meta-set 后 rc0 |
| W4 | untracked 文件 before/after | 快照缺失文件 | `pytest tests/test_snapshot_files.py` | 两次均记录、sha 可区分；`exists:false` 不崩 |
| R09 | 计数与实测一致 | 人为改回 55 | `doc_consistency.py --check` | rc=0；改回后 rc=1 |
| R10 | 临时文件 2 块 | 无块 / orphan 块 | `pytest tests/test_audit_managed_blocks.py` | JSON 正确 / summary=0 / `--strict` rc=1 |
| R11 | fake rig ready | incomplete seat / daemon down | `pytest tests/test_openrig_run.py` | rc0 / rc1 / rc1（`--allow-daemon-down` 时 rc0） |
| R11 | — | `start --dry-run` | 同上 | 不调用 fake rig（用调用计数断言） |
| R11 | — | bridge 缺失/坏 JSON | 同上 | rc2 |
| W5 | exact specialization | 无 specialization / stale specialization | `pytest tests/test_verify_render.py` | `ok:true` / mismatch / mismatch |
| W5 | `--strict` + exact | `--strict` + stale | 同上 | rc0 / rc1 |
| R04b | 仅 `reports/FINAL.md`；仅根 `FINAL.md` | 两者皆缺；sha/revision 不符 | `pytest tests/test_wf_close_lint.py` | PASS/PASS / ERROR / 各自 ERROR |

QA 至少 8 条负向，覆盖 ≥4 个门。

## 6. 验收入口（TASK §5，原样执行并记真实 rc）

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/doc_consistency.py --check
.venv/bin/python scripts/openrig_preflight.py --json --advisory
.venv/bin/python scripts/audit_managed_blocks.py --path /home/a7067567g/下载/deepseek/deepseek-知识库/AGENTS.md --json
.venv/bin/python scripts/openrig_run.py check --run-dir runs/openrig-p1-hard-constraints-20261116 --json --allow-daemon-down
.venv/bin/python scripts/openrig_run.py start --run-dir runs/openrig-p1-hard-constraints-20261116 --dry-run --json
.venv/bin/python scripts/verify_render.py --run-dir runs/openrig-p1-hard-constraints-20261116 --json
.venv/bin/python scripts/wf_close_lint.py --run openrig-p1-hard-constraints-20261116 --strict
```

每条记录：命令、cwd、开始/结束时间、真实 rc、stdout/stderr 摘要或 hash。建议经 `scripts/evidence_run.sh` 执行，禁止手工抄 rc。

### 6.1 两类预期非零

- `wf_close_lint --strict` 在 `close_round` 之前预期失败（尚无 FINAL/closeout）——这是正确行为，须记录 rc≠0 与原因，不得为变绿删检查。
- `openrig_run.py check` 在 daemon 未起时带 `--allow-daemon-down` 应 rc=0；不带时为 rc=1。两种都跑并对比。

## 7. 无产品变更规则（G5）

1. **只读对象**：OpenRig 产品仓、`workflow-group/templates/**`（除 §3.3 指定 ENTRYPOINTS）、`workflow-group/roles/**`、其它 `runs/**`。
2. **三值对比**：每包结束、QA、close 时重算产品仓 `HEAD` / `status --porcelain` sha256 / `git diff` sha256，必须与 §2 一致。
3. **发现差异即 STOP**：只撤销本次新增部分；绝不 `git checkout/restore/stash` 产品仓；绝不回滚 pre-existing dirty；证据标 `product-change-detected`。
4. **KB 侧**：以 §2.1 刷新后的基线为准；允许变化仅限 §3 文件与本 run `reports/**`。
5. 不得 `git add -A`、commit、push、tag；不得设置金额预算。

## 8. 证据与交付

每个 packet 落 `reports/evidence/<A|B|C|D>/`：

- `changed-files.txt`：路径 + create/modify + before/after sha256；
- `targeted-pytest.txt`：命令、rc、失败输出（如有）；
- `negative-*.txt`：每个负向命令原始输出与 rc；
- `scope.txt`：该包结束时 `git status --porcelain` 过滤视图。

QA 额外落 `reports/evidence/qa/`：`full-pytest.txt`、`negative-cases.txt`（≥8 条）、`entrypoints.txt`、
`scope-diff.txt`、`product-baseline.txt`、`AGENTS-target-side-effects.txt`；并写 `reports/QA-VERDICT.md`（逐条 PASS/WARN/FAIL/SKIP + 证据路径）。

close 落 `reports/FINAL.md` 与 `reports/evidence/closeout.json`（path/bytes/sha256/command/rc/revision/reason）。

## 9. 停止条件

任一情况立即停包，handoff `waiting`/`failed`，不自行绕过：

- 需要改 §3 之外的文件（尤其 `workflow-group/README.md`）才能让测试变绿；
- 产品仓三值出现差异且无法只撤销本次新增；
- pre-existing dirty 被覆盖或需要回滚；
- 某个门只能靠删检查/放宽断言变绿；
- 需要 `--execute` teardown、删除、commit/push、金额预算；
- TASK 与实测冲突且无法用「实测优先 + 记录原因」消解（如 canonical 计数再次漂移）。

## 10. 交接

`plan` 完成。下一步 `impl_preflight_evidence`（TDO-OC）起手只需读：

- `TASK.md` §1、§5、§6；
- `PROJECT.md` §1/§2/§3.1/§5；
- 本文件 §2.1/§3.1/§4.1/§5/§7/§9；
- `runs/openrig-p1-hard-constraints-20261116/reports/evidence/00-baseline.txt`。

先执行 §2.1 基线刷新，再动代码。不要预读 Packet B/C/D 细节，避免跨包改文件。
