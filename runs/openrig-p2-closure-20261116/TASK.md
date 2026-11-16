# TASK — P2 closure（R13/R14 + F-3/F-5）

## 0. 边界

只改 `workflow-group/scripts/**`、`workflow-group/tests/**`、`workflow-group/WORKFLOW-TAGS.md`、本 run `reports/**`。
不改 OpenRig 产品代码；不 commit/push；不设金额预算；pre-existing dirty 不得覆盖。

## 1. Packet — R13 只读 invariants probe

新增 `scripts/workflow_invariants_probe.py`：

```
workflow_invariants_probe.py --run-dir <run-dir> [--workflow <path>] [--json]
```

- 默认读 `<run-dir>/openrig/workflow.yaml`；只读，不调用 daemon/rig。
- 用标准库做文本结构探测（不要新增 PyYAML 依赖）：
  - 提取 `steps[*].id`；
  - 提取每个 step 的 `depends_on` 列表；
  - 提取 `next_hop.on.failed` 目标；
  - 输出 `steps[]`、`duplicateIds[]`、`missingDependsOn[]`、`missingNextHopTargets[]`、`unreachable[]`、`terminal[]`、`problems[]`、`ok`。
- `ok=false` 条件：重复 step id、depends_on 指向不存在 step、next_hop.failed 指向不存在 step。
- `unreachable` 为 WARN，不影响 `ok`。
- 不改 workflow engine，不新增 `invariants.checks[]` 字段。

测试：
- 临时工作流：合法 DAG → ok true、terminal 正确。
- 重复 id、缺失 depends_on 目标、缺失 next_hop 目标 → ok false。
- 无 live 调用证明：用 monkeypatch 包 subprocess.run，probe 不触发。

## 2. Packet — R14 paved-road next

在 `scripts/openrig_run.py` 增加子命令：

```
openrig-run next --run-dir <run-dir> [--json]
```

- 输出 canonical 顺序：
  1. `openrig-run check`
  2. `openrig-run start --dry-run`
  3. `openrig-run start`
  4. `verify_render --strict`
  5. `wf.py archive-gate`
- 只读，不执行任何命令；缺 bridge 时 rc=2。
- 同时打印入口说明：local-only vs hybrid 的选择提示（不阻断）。
- 测试：next 输出顺序/无 subprocess 调用；缺 bridge rc2。

## 3. Packet — F-3 closeout actual FINAL

`scripts/wf_close_lint.py --strict`：

- 解析到的 FINAL 路径优先 `reports/FINAL.md`，其次根 `FINAL.md`。
- `closeout.json` 必须包含该 **实际解析路径** 的 entry（sha256 由现有逻辑校验）。
- `reports/FINAL.md` 与根 `FINAL.md` 同时存在且内容不同时，只 attest 根文件必须 ERROR。
- 保持 revision/mtime 逻辑不变。
- 测试：P1 双 entry → PASS；只有根 entry 但 reports 是实际解析路径 → ERROR。

## 4. Packet — F-5 WORKFLOW-TAGS 旧表

- `WORKFLOW-TAGS.md` §1.1 表格里仍写 `canonical 37`；改为与顶部声明/实测一致（62），或明确写“以顶部声明为准”。
- `doc_consistency.py --check` 必须 rc=0。

## 5. 验收

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/doc_consistency.py --check
.venv/bin/python scripts/workflow_invariants_probe.py --run-dir runs/openrig-p2-closure-20261116 --json
.venv/bin/python scripts/openrig_run.py next --run-dir runs/openrig-p2-closure-20261116 --json
.venv/bin/python scripts/wf_close_lint.py --run openrig-p2-closure-20261116 --strict
```

QA 必须独立复跑：全量 pytest、5 条负向、scope diff、产品仓零改动、无 live daemon 调用。
