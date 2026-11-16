# TASK — P1 hard constraints（W2/W3/W4/W5/R04b + R09/R10/R11/R12）

## 0. 边界

只改：
- `workflow-group/scripts/**`
- `workflow-group/tests/**`
- `workflow-group/WORKFLOW-TAGS.md`
- `workflow-group/templates/specialized/openrig-workflow-master/{README,ENTRYPOINTS,ARCHITECTURE}.md`
- `.github/workflows/wf-validate.yml`
- 本 run `reports/**`

不改 OpenRig 产品代码；不 commit/push；不设金额预算；pre-existing dirty 不得覆盖。

## 1. Packet A — W2/W3/W4

### W2 preflight 失败路径副作用

`scripts/openrig_preflight.py`：

- 先跑 **无副作用** 的 `run_context` / `run_docs` 检查；失败立即返回（rc=1），**不得**注入 `AGENTS.md`、**不得**写 monitor `target.json`、**不得**启动 `yueyue-monitor.service`。
- 只有 pre-check 通过后，才允许 `inject_agents` 与 `register_monitor`。
- 注入后再跑 workspace block 存在性检查；`ok=all(required checks)` 语义不变。
- `--advisory` 仍只影响 rc，不伪造 `ok:true`。

测试：临时 workspace + 不存在 run-id → rc1；AGENTS.md 字节不变；monitor target 不写。

### W3 run-meta 回填

- `wf.py new-run` 已写 `.run-meta.json`（P0），确认保留。
- 新增 `wf.py meta-set <run-id> --project-root PATH [--scope TEXT] [--json]`，写/更新 `.run-meta.json`。
- `wf.py baseline` 对无 meta 的历史 run 仍要求 `--project-root`；错误信息必须给 `meta-set` / `--project-root` 两条修复路径。
- 测试：旧 run 无 meta → meta-set → baseline 可运行。

### W4 file snapshot

- 新增 `scripts/snapshot_files.py`：
  - `--out <json> --label before|after --path <file-or-dir>...`
  - 对每个文件写 `{path, bytes, sha256, mtime, label, capturedAt}`。
  - 不存在文件记 `exists:false`，不抛。
  - 只读；输出 JSON。
- 或提供等价 `wf.py snapshot-files`，但必须可对 pre-existing untracked 文件记录 before/after。
- 测试：临时 untracked 文件 before/after 均记录；缺失文件不崩。

## 2. Packet B — R09/R10

### R09 docs gate

- 修 `WORKFLOW-TAGS.md` 的 canonical 计数：以 `scripts/doc_consistency.py --check` 实测为准（当前 actual=61）。
- 在 `.github/workflows/wf-validate.yml` 的 `pytest` 后增加：
  - `python3 workflow-group/scripts/doc_consistency.py --check`
  - `python3 workflow-group/tests/test_doc_consistency.py`
- 不改 CI 触发范围，不引入联网依赖。
- 测试/验证：`doc_consistency --check` rc=0；`test_doc_consistency.py` rc=0。

### R10 managed block 审计（只读 WARN）

- 新增 `scripts/audit_managed_blocks.py`：
  - `--path` 可重复（文件/目录，目录递归）。
  - 解析 `<!-- BEGIN OpenRig MANAGED BLOCK: <id> -->`。
  - 输出 JSON：`{files:[{path, blocks:[{id,startLine,endLine,kind,ownerRig,warning}]}], summary}`。
  - `kind`：preflight/managed/unknown；`ownerRig` 无法从 block id 推断时为 `null`。
  - 只读；默认 rc=0；`--strict` 在存在 `ownerRig == null` 的 managed block 时 rc=1（用于后续接线，默认不启用）。
- 不迁移命名空间，不改 `managed-blocks.ts`。
- 测试：临时文件含 2 个块 → JSON 正确；无块 → summary=0；`--strict` 对 orphan 块 rc=1。

## 3. Packet C — R11/R12

### R11 `openrig-run` 顺序 wrapper

新增 `scripts/openrig_run.py`（或同名可执行脚本）：

```
openrig-run check --run-dir <run-dir> [--json] [--allow-daemon-down] [--strict-render]
openrig-run start --run-dir <run-dir> [--dry-run] [--timeout 120] [--json]
```

`check` 顺序与失败语义：

1. 读 `openrig/OPENRIG-BRIDGE.json`；缺/坏 → rc2。
2. `verify_render.py --run-dir ...`；默认 WARN 不阻塞；`--strict-render` 时 mismatch 阻塞。
3. `tools/openrig_bridge.py doctor --run-dir ...`；rc≠0 → 阻塞。
4. `<openrigCli> workflow validate <workflowSpec> --json`；rc≠0 → 阻塞。
5. `<openrigCli> ps --nodes --rig <rigName> --json`：
   - daemon down → 默认阻塞；`--allow-daemon-down` 降级为 WARN；
   - daemon up → 必须所有 bridge `seatMap` target 都存在且 `startupStatus == "ready"`，否则阻塞。
6. 输出 `{ok, checks[], next[]}`；`ok=false` 时 rc=1（除非显式 `--allow-*` 降级项）。

`start`：

- 先执行 `check --allow-daemon-down`。
- `--dry-run` 只打印/返回顺序命令，不执行任何 live 动作。
- 非 dry-run：`daemon start --no-kernel --port <daemonPort>` → `up` → 轮询 `ps` 直到 seatMap 全 ready（timeout）→ `workflow validate` → `workflow instantiate`。
- 任一步失败立即停并回滚提示（不自动删 home/DB）。
- 不替代 `workflow instantiate` 的幂等判断；重复 start 由 rig 自身报错。
- 测试：fake `rig` 脚本模拟 ready/incomplete/daemon-down；`check` 三种 rc；`start --dry-run` 不调用 fake rig。

### R12 复制/生成边界

在 `workflow-group/README.md` 或 `templates/specialized/openrig-workflow-master/ENTRYPOINTS.md` 增加一小节：

- 人写的控制面文档：复制模板、人工维护。
- 机器执行的 bundle：`render_master.py` 生成；不要在生成后手改；run 特化必须走 `render-specialize` 记录（见 Packet D）。
- 升级只对新 run 重渲染，不改在跑 run 的绑定图。

## 4. Packet D — W5/R04b

### W5 render specialization

- `verify_render.py` 增加 `--specializations <json>`（默认自动读 `<run-dir>/openrig/render-specializations.json`）。
- schema：
```json
{"schemaVersion":1,"runId":"...","files":{"rig.yaml":{"bytes":123,"sha256":"...","reason":"..."},"workflow.yaml":{...}}}
```
- 若 manifest 与磁盘不符，但 specialization 条目与磁盘 bytes/sha 精确一致 → 视为合法特化，`ok:true`，item 标 `specialized:true`；stale specialization 仍 mismatch。
- 新增 `wf.py render-specialize <run-id> --path <rel> --reason TEXT [--json]`，写/更新 `openrig/render-specializations.json`。
- 测试：无 specialization 时 mismatch → 默认 rc0/ok:false；有 exact specialization → rc0/ok:true；stale specialization → mismatch；`--strict` 有 exact specialization → rc0。

### R04b FINAL 路径兼容

- `wf_close_lint.py --strict` 接受：
  - `run_dir/FINAL.md` 或 `run_dir/reports/FINAL.md`（优先 reports/FINAL.md）。
- `closeout.json` 的 FINAL entry 可按实际路径校验。
- 测试：只放 `reports/FINAL.md` → PASS；只放根 `FINAL.md` → PASS；两者都缺 → ERROR；revision/mtime 语义保持。
- 不要放宽 `closeout.json`、sha256、revision 链检查。

## 5. 验收命令

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

## 6. 证据

每个 packet 写 `reports/evidence/<packet>/`：changed-files、before/after sha256、tests 日志、负向输出、真实 rc。
QA 独立复跑：全量 pytest、六条入口、至少 8 个负向用例、scope diff、产品仓零改动、AGENTS/target 副作用检查。
