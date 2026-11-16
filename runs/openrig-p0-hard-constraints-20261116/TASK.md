# TASK — P0 hard-constraint stack（R01–R07 + R08）

## 0. 边界

只改 `workflow-group/scripts/**`、`workflow-group/tests/**`、本 run `reports/**`。不改 OpenRig 产品代码、模板正文、`runs/` 其它目录。
不 commit/push；不设金额预算；pre-existing dirty 不得覆盖。

## 1. 目标

把“读了也判不出来”的入口问题变成可失败、可复跑的机器门：

- **R05** preflight 真检查：`ok = all(required checks)`，缺上下文/缺注入 fail-closed。
- **R06** required-components：依赖缺失给安装命令；`issues.py` 不在 import 期崩溃；doctor 顶部检查。
- **R02** baseline / verify-baseline：HEAD/status/diff sha256，排除本 run 目录。
- **R03** evidence_run：真实 rc、pipefail、stdout/stderr hash。
- **R01** archive-gate：复用 `openrig-teardown.py` 的 strict COMPLETE 语义。
- **R04** close lint strict：FINAL.md + closeout evidence manifest + sha256 + revision 最小通道。
- **R07** verify-render：消费 `render-manifest.json`，默认 WARN，`--strict` 才 ERROR。
- **R08** 每个硬门至少一个负向测试。

## 2. Packet A — R05/R06

### 2.1 新文件

`scripts/required_components.py`

```python
def check_components(root: Path) -> list[dict]:
    # 每项: {id, group, required, ok, detail, install_hint}
```

组：

- `machine`：Python >= 3.12、`openpyxl`、`pytest`（required）。
- `control`：`PROJECT.md`、`DECISIONS.md`、`STATUS-Round-n.md`、`ISSUES.xlsx` 模板存在（required）。
- `openrig`：`render_master.py`、`tools/openrig_bridge.py`、`PREFLIGHT.md`、`ENTRYPOINTS.md`（required）。
- `runtime`：`rig` CLI 可发现（required=false，warn）；产品 `scripts/openrig-teardown.py` 可发现（required=false，warn）。

缺 `openpyxl` 时 `detail` 必须给出可执行安装提示，例如：
`source workflow-group/.venv/bin/activate` 或 `workflow-group/.venv/bin/pip install -r workflow-group/requirements-dev.txt`。

### 2.2 `scripts/issues.py`

`except ImportError` 后，模块级别的 `THIN = Side(...)`、`BORDER = Border(...)`、`WRAP = Alignment(...)` 不得再执行；改为 `if HAS_OPENPYXL:` 保护或惰性函数。目标是缺 openpyxl 时 `import issues` 成功、`read_rows()` 仍可走 JSONL 降级。

### 2.3 `scripts/openrig_preflight.py`

- 增加 `--advisory`（保留旧行为出口：`ok:false` 但 rc=0）。
- 输出至少：
  - `ok`（仅当所有 `required` checks 为 true）
  - `checks: [{id, required, ok, detail, installHint?}]`
  - `reasons: [str]`
- 默认 rc：`ok` 为 false → 1；`ok` 为 true → 0。
- 必查：
  1. `preflight_file`：PREFLIGHT.md 存在。
  2. `required_components`：调用 `check_components(ROOT)`；任一 required 失败 → fail。
  3. `workspace_context`：`--workspace` 必须给出；给出时检查 `AGENTS.md` 中 `OPENRIG-PREFLIGHT` managed block 存在且包含本次 run-id（未给 run-id 时至少存在块）。
  4. `run_context`：`--run-id` 必须给出；对应 `runs/<run-id>` 存在。
  5. `run_docs`：`PROJECT.md`、`DECISIONS.md`、`ISSUES.xlsx`、至少一个 `STATUS-Round-*.md` 存在。
- `--advisory` 只影响 rc，不伪造 `ok:true`。
- 现有 monitor 注册/注入逻辑保留；注入成功不能替代块存在性检查（注入后重新读文件）。

### 2.4 `scripts/wf.py doctor`

- 顶部调用 `check_components`；任一 required 失败 → `errors` 追加：
  `required-components: <id> — <detail> — <install_hint>`。
- 即使缺少 openpyxl，也不得出现 `'NoneType' object is not callable`；ISSUES 检查若无法执行，给出明确 SKIP/ERROR。
- 不改变现有 doctor 其它语义。

### 2.5 测试

新增/修改：

- `tests/test_required_components.py`：正常环境 required 全 ok；用临时 root 缺模板 → 对应 required false；缺 openpyxl 的 detail/install_hint 可由 monkeypatch 注入。
- `tests/test_openrig_preflight.py`：
  - 无 `--workspace`/`--run-id` → `ok:false`, rc=1；
  - `--advisory` → `ok:false`, rc=0；
  - 有 workspace 但无 managed block → fail；
  - 注入后块存在 + run 目录齐全 → `ok:true`, rc=0；
  - 缺 run docs → fail。
- `tests/test_issues.py`：模拟 `HAS_OPENPYXL=False` 时 import 不崩、read_rows 走 JSONL。
- `tests/test_wf.py`：doctor 在缺组件时给出 required-components 错误，而不是 NoneType。

## 3. Packet B — R02/R03

### 3.1 run meta

`wf.py new-run` 写 `.run-meta.json`：

```json
{"runId":"...","projectRoot":"...","scope":"...","template":"...","createdAt":"..."}
```

已有 run 没有该文件时，`baseline` 必须允许 `--project-root` 显式传入。

### 3.2 `wf.py baseline` / `verify-baseline`

```bash
python3 scripts/wf.py baseline <run-id> [--project-root PATH] [--json]
python3 scripts/wf.py verify-baseline <run-id> [--json]
```

写：

- `reports/evidence/00-baseline.json`
- `reports/evidence/00-baseline.txt`

字段至少：

```json
{
  "schemaVersion": 1,
  "runId": "...",
  "projectRoot": "...",
  "capturedAt": "...",
  "head": "...",
  "statusLines": ["..."],
  "statusSha256": "...",
  "diffSha256": "...",
  "diffStat": "...",
  "excludePaths": ["workflow-group/runs/<run-id>"],
  "toolVersions": {"python": "...", "pytest": "...", "rig": "..."}
}
```

- 必须排除本 run 目录（status 与 diff 都不计），否则收口必然自相矛盾。
- `verify-baseline` 用同一 projectRoot/excludePaths 重算；HEAD/status/diff 任一不同 → rc=1，打印结构化 diff。
- 不要求 git 工作树干净；只要求“相对基线未变”。

### 3.3 `scripts/evidence_run.sh`

用法：

```bash
scripts/evidence_run.sh --out <file> --label <name> -- <cmd...>
scripts/evidence_run.sh --out <file> --label <name> --shell '<shell pipeline>'
```

- `set -o pipefail`；`--shell` 用 `bash -o pipefail -c`。
- 文件头写：
  `command=`, `cwd=`, `started_at=`, `finished_at=`, `rc=`, `stdout_sha256=`, `stderr_sha256=`
- 后接 `--- stdout ---` / `--- stderr ---` 原文。
- 必须保留真实 rc；命令失败时 wrapper 也返回该 rc。
- 不得吞掉 stderr。

### 3.4 测试

- `tests/test_wf_baseline.py`：临时 git 仓库 + 临时 run；baseline→verify=0；改一个文件→verify=1；本 run 目录内新增文件不触发 verify 失败。
- `tests/test_evidence_run.py`：`--shell 'printf x; exit 7'` → rc=7 且文件含 `rc=7`；`--shell 'false | tail'` → rc=1（pipefail 生效）且 stdout/stderr hash 存在。

## 4. Packet C — R01/R04/R07

### 4.1 `wf.py archive-gate`

```bash
python3 scripts/wf.py archive-gate <run-id> [--archive-root PATH] [--json]
```

- 复用产品 guard：`<KB parent>/deepseek-项目/10-openrig-deepseek/scripts/openrig-teardown.py`，可用 `OPENRIG_TEARDOWN_GUARD` 覆盖。
- 只做 dry-run，不执行 teardown。
- guard rc=0 → `ok:true`；rc=2 → `ok:false`，原样带 guard JSON 的 `archiveStatus/missing`。
- 找不到 guard → rc=3，明确“guard missing”，不得假装通过。

### 4.2 `wf_close_lint.py --strict` + evidence manifest

- 保留现有默认行为；新增 `--strict`。
- 默认模式：FINAL.md 缺失 → WARN（兼容历史）。
- `--strict`：
  - `FINAL.md` 必须存在。
  - `reports/evidence/closeout.json` 必须存在且 schemaVersion=1。
  - 每条 entry 必须有 `path`、`bytes`、`sha256`、`command`、`rc`、`revision`、`reason`。
  - 对每条 entry 重新计算 bytes/sha256，必须一致。
  - `FINAL.md` 的 mtime 不得晚于 `closeout.json` 的 `closedAt`？若晚于，必须有 `reports/evidence/revisions/REV-*.json` 记录新 digest 与 reason。
- 新增 `wf.py evidence-record`：

```bash
wf.py evidence-record <run-id> --path <rel> --command '<cmd>' --rc <n> \
  [--revision N] [--reason TEXT] [--json]
```

写/更新 `reports/evidence/closeout.json`，自动算 bytes/sha256；默认 revision=1、reason="initial closeout"。

- **最小 revision 通道**：`--revision N --reason ...` 允许替换同 path 的旧 entry；必须保留 `replacesSha256` 字段。`close_lint --strict` 校验 revision 链不倒退。

### 4.3 `scripts/verify_render.py`

```bash
python3 scripts/verify_render.py --run-dir runs/<run-id> [--strict] [--json]
```

- 读 `openrig/render-manifest.json`。
- 对每个 `files[*]` 重算 bytes/sha256；输出 `ok`、`mismatches[]`、`checked[]`。
- 默认：有 mismatch → rc=0 但 `ok:false`（WARN 语义）；`--strict` → rc=1。
- manifest 缺失/坏 JSON → rc=2，不得假装通过。

### 4.4 测试

- `tests/test_archive_gate.py`：fake guard complete→rc0；partial→rc2/ok false；missing guard→rc3；不得执行 marker 命令。
- `tests/test_wf_close_lint.py`：strict 缺 FINAL→ERROR；缺 closeout.json→ERROR；entry sha 不符→ERROR；revision 倒退→ERROR；合法 manifest→PASS。
- `tests/test_verify_render.py`：未改→rc0/ok true；改一字节→默认 rc0/ok false；`--strict`→rc1；缺 manifest→rc2。
- `tests/test_evidence_record.py`：record 算 sha；二次 revision 保留 replacesSha256。

## 5. 验收命令

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/openrig_preflight.py --json --advisory
.venv/bin/python scripts/openrig_preflight.py --json --run-id openrig-p0-hard-constraints-20261116 \
  --workspace /home/a7067567g/下载/deepseek/deepseek-知识库 \
  --run-dir runs/openrig-p0-hard-constraints-20261116  # 期望 ok:true 或明确 fail
.venv/bin/python scripts/wf.py baseline openrig-p0-hard-constraints-20261116 --json
.venv/bin/python scripts/wf.py verify-baseline openrig-p0-hard-constraints-20261116 --json
.venv/bin/python scripts/verify_render.py --run-dir runs/openrig-p0-hard-constraints-20261116 --json
```

`openrig_preflight` 的 workspace 注入若尚未存在，必须由实现者用 `--workspace` 注入后再跑；不允许为了让 `ok:true` 而删检查。

## 6. 证据

每个 packet 在 `reports/evidence/<packet>/` 落：changed-files、before/after sha256、tests 日志、negative-case 输出。
QA 必须独立复跑：全量 pytest、至少 5 个负向用例、scope diff、产品仓零改动。
