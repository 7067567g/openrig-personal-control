# 00 — Round 1 执行计划（P0 hard constraints）

> run: `openrig-p0-hard-constraints-20261116` ｜ 轮次：1 ｜ 作者：MAIN（`plan` 包）
> 权威：`TASK.md` > `SPEC.md` > `PROJECT.md`；本文件是执行拆分与验收口径，不改判据。
> 硬约束：只改 `workflow-group/scripts/**`、`workflow-group/tests/**`、本 run `reports/**`；不 commit/push；不覆盖 pre-existing dirty。

## 1. 目标与边界

把“读了也判不出来”的入口问题变成可失败、可复跑的机器门，交付 R01–R07，并用 R08 给每个硬门至少一个负向测试。

不包含：R09–R14（P1/P2）、OpenRig 产品代码、模板正文、其它 run、KB 正式知识区、任何删除/发布/权限变更。

## 2. 规划基线（只读事实）

| 项 | 值 |
| --- | --- |
| KB HEAD | `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac` |
| KB status sha256 | `eefbb03bf2b07806f369ab0fdd544d4e1f1db55a10ae8b0d71d3aba4ffb7d4e5` |
| KB diff sha256 | `1d81f1c04b283c5742f461aa3d9173e1409023bb7be15e58167a60a6c3fcf9a0` |
| 基线文件 | `reports/evidence/00-baseline.txt`（已排除本 run 目录） |
| 产品仓 | `/home/a7067567g/下载/deepseek/deepseek-项目/10-openrig-deepseek` |
| 产品 HEAD | `e932ae94e4c07b619c39902f29db949464ebb295` |
| 产品 status sha256 | `3b64cf901a0c232fbbae7e5937111671a01be558c910ae09132756fe54b7e269` |
| 产品 diff sha256 | `dc564a37b301c610e7b451bf8eb401cea3baddb3b838bc8a7cc9c292d50e8172` |
| 产品 pre-existing dirty | 29 条（用户既有工作，只读，不得覆盖/回滚） |
| 运行时 | `.venv/bin/python` 3.12.15、pytest 9.0.2、openpyxl 3.1.5 |

## 3. 包边界（文件级）

### 3.1 Packet A — R05/R06

新建：

- `scripts/required_components.py`
- `tests/test_required_components.py`
- `tests/test_openrig_preflight.py`

修改：

- `scripts/openrig_preflight.py`（`--advisory`、`ok=all(required)`、`checks/reasons`、五项必查、注入后重读）
- `scripts/issues.py`（`HAS_OPENPYXL=False` 时不在 import 期执行 `Side/Border/Alignment`）
- `scripts/wf.py`（仅 doctor 顶部 required-components 检查 + openpyxl 降级）
- `tests/test_issues.py`（缺 openpyxl 导入 + JSONL 降级）
- `tests/test_wf.py`（仅 doctor 缺组件用例）

禁止：Packet B/C 的 `evidence_run.sh`、`verify_render.py`、`wf_close_lint.py` 及其测试。

### 3.2 Packet B — R02/R03

新建：

- `scripts/evidence_run.sh`（可执行，`set -o pipefail`）
- `tests/test_wf_baseline.py`
- `tests/test_evidence_run.py`

修改：

- `scripts/wf.py`（`new-run` 写 `.run-meta.json`；新增 `baseline` / `verify-baseline`）

禁止：Packet A 的 components/preflight/issues 逻辑；Packet C 的 close/archive/render 逻辑。

### 3.3 Packet C — R01/R04/R07

新建：

- `scripts/verify_render.py`
- `tests/test_archive_gate.py`
- `tests/test_verify_render.py`
- `tests/test_evidence_record.py`

修改：

- `scripts/wf.py`（新增 `archive-gate` / `evidence-record`）
- `scripts/wf_close_lint.py`（新增 `--strict`，默认行为不变）
- `tests/test_wf_close_lint.py`（strict 用例）

禁止：执行 teardown；修改产品 guard；触碰 Packet A/B 逻辑。

### 3.4 共享文件串行规则

`scripts/wf.py` 被三包共用。执行顺序固定为 A → B → C，任一时刻只有一个写者；后一包开始前必须确认前一包已 handoff 且工作树无半成品。若同文件出现冲突，停包上报，不强行合并。

## 4. 测试矩阵（每个硬门至少 1 个负向）

| 门 | 正例 | 负向用例 | 命令 | 期望 |
| --- | --- | --- | --- | --- |
| R05 | 注入后的 workspace + 完整 run docs | 无 `--workspace`/`--run-id` | `openrig_preflight.py --json --advisory` | `ok:false`，rc=0（advisory）；默认 rc=1 |
| R05 | 同上 | workspace 存在但无 managed block | 临时 workspace 调用 | `workspace_context=false` |
| R05 | 同上 | 缺 run docs | 临时 run 缺 PROJECT/DECISIONS/ISSUES/STATUS | `run_docs=false` |
| R06 | 正常环境 required 全 ok | 临时 root 缺 openrig 模板 | `pytest tests/test_required_components.py` | 对应 required=false + install_hint |
| R06 | `import issues` 成功 | monkeypatch `HAS_OPENPYXL=False` | `pytest tests/test_issues.py` | import 不崩；`read_rows()` 走 JSONL |
| R06 | doctor 正常 | 缺组件环境 | `pytest tests/test_wf.py` | required-components ERROR，无 NoneType |
| R02 | baseline→verify 无改动 | 改一个文件 | `pytest tests/test_wf_baseline.py` | verify rc=1，结构化 diff |
| R02 | 本 run 目录内新增 | — | 同上 | verify rc=0（排除生效） |
| R03 | 正常命令 | `--shell 'printf x; exit 7'` | `pytest tests/test_evidence_run.py` | rc=7，文件含 `rc=7` |
| R03 | 正常命令 | `--shell 'false \| tail'` | 同上 | rc=1（pipefail），stdout/stderr hash 存在 |
| R01 | fake guard complete | fake guard partial | `pytest tests/test_archive_gate.py` | rc=0/ok:true；partial→rc=2/ok:false；marker 未执行 |
| R01 | guard 存在 | guard 缺失 | 同上 | rc=3，明确 guard missing |
| R04 | 合法 FINAL+closeout | 缺 FINAL | `pytest tests/test_wf_close_lint.py` | strict ERROR |
| R04 | 同上 | 缺 closeout.json / sha 不符 / revision 倒退 | 同上 | 各自 ERROR |
| R07 | manifest 与文件一致 | 改一字节 | `pytest tests/test_verify_render.py` | 默认 rc=0/ok:false；`--strict` rc=1 |
| R07 | 同上 | manifest 缺失/坏 JSON | 同上 | rc=2，不假装通过 |

## 5. 验收入口（TASK §5）

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/openrig_preflight.py --json --advisory
.venv/bin/python scripts/openrig_preflight.py --json --run-id openrig-p0-hard-constraints-20261116 \
  --workspace /home/a7067567g/下载/deepseek/deepseek-知识库 \
  --run-dir runs/openrig-p0-hard-constraints-20261116
.venv/bin/python scripts/wf.py baseline openrig-p0-hard-constraints-20261116 --json
.venv/bin/python scripts/wf.py verify-baseline openrig-p0-hard-constraints-20261116 --json
.venv/bin/python scripts/verify_render.py --run-dir runs/openrig-p0-hard-constraints-20261116 --json
```

每条必须记录：命令、cwd、开始/结束时间、真实 rc、stdout/stderr 摘要或 hash。建议全部经 `scripts/evidence_run.sh` 执行，避免手工抄 rc。

### 5.1 preflight 正例与唯一 scope 例外

KB 根 `AGENTS.md` 规划时无 `OPENRIG-PREFLIGHT` managed block。TASK §5 要求用 `--workspace /home/a7067567g/下载/deepseek/deepseek-知识库` 注入后再跑，这会把 managed block 写进根 `AGENTS.md`——本计划中**唯一**不在 §0 写白名单内的写入。

规则：

1. 注入前记录 `sha256sum AGENTS.md`；只允许脚本写 managed block，禁止手改其它内容；注入后记录新 sha256。
2. 该文件列入 QA scope 例外，除此之外任何 `AGENTS.md` 变化都算越界。
3. 测试内部正例一律用 `tmp_path` 工作区，仓库根只注入一次。
4. 若选择不注入仓库根：如实得到 `workspace_context` fail（rc=1），用临时工作区做等价正例；不得为了 `ok:true` 删除检查。

### 5.2 `verify-baseline` 的预期 rc

实现会修改 `scripts/tests`，因此实现后 `verify-baseline` 预期返回 rc=1。它的价值不是“必须 rc=0”，而是输出结构化 diff：

- diff 路径集合必须 = 本计划 §3 的文件集合（外加本 run reports 与 §5.1 的 `AGENTS.md` 例外）；
- 不得出现产品仓、`templates/**`、`roles/**`、其它 `runs/**`；
- QA 必须人工核对路径集合，不得只看 rc。

## 6. 无产品变更规则（G5）

1. **只读对象**：产品仓、`workflow-group/templates/**`、`workflow-group/roles/**`、其它 `workflow-group/runs/**`。
2. **三值对比**：每个 packet 结束、QA、close 时重算产品仓 `HEAD` / `status --porcelain` sha256 / `git diff` sha256，必须与 §2 一致。
3. **发现差异即 STOP**：定位本次新增改动，只撤销本次新增部分；绝不 `git checkout/restore/stash` 产品仓，绝不回滚 pre-existing dirty；证据记 `product-change-detected`。
4. **KB 侧**：以 `00-baseline.txt` 为基线，允许变化仅限 §3 文件、本 run reports、§5.1 例外；其它新增改动一律越界。
5. **不得** `git add -A`、commit、push、tag；不得设置金额预算。

## 7. 证据与交付

每个 packet 在 `reports/evidence/PACKET/` 落：

- `changed-files.txt`：路径 + 动作（create/modify）+ before/after sha256；
- `targeted-pytest.txt`：命令、rc、失败输出（如有）；
- `negative-*.txt`：每个负向命令的原始输出与 rc；
- `scope.txt`：该包结束时的 `git status --porcelain` 过滤视图。

QA 额外落：

- `reports/evidence/qa/full-pytest.txt`
- `reports/evidence/qa/negative-cases.txt`（≥5 条，覆盖 ≥4 个硬门）
- `reports/evidence/qa/six-entrypoints.txt`
- `reports/evidence/qa/scope-diff.txt`
- `reports/evidence/qa/product-baseline.txt`
- `reports/QA-VERDICT.md`（逐条 PASS/WARN/FAIL/SKIP + 证据路径）

close 额外落：

- `reports/FINAL.md`
- `reports/evidence/closeout.json`（schemaVersion=1，每条 entry 含 path/bytes/sha256/command/rc/revision/reason）
- revision 记录（如有）`reports/evidence/revisions/REV-*.json`

## 8. 停止条件

出现以下任一情况立即停包并 handoff `waiting`/`failed`，不自行绕过：

- 需要改 §3 之外的文件才能让测试变绿；
- 产品仓三值出现差异且无法只撤销本次新增；
- pre-existing dirty 被覆盖或需要回滚；
- guard 行为与 TASK 判定表冲突（例如 guard rc=1 被误当通过）；
- 需要 `--execute` teardown、删除、commit/push、金额预算；
- 任何门只能靠删检查/放宽断言变绿。

## 9. 交接

`plan` 完成，下一步 `impl_preflight_components`（TDO-OC）。起手只需读：`TASK.md` §2、`PROJECT.md` §3/§4.1/§5、本文件 §3.1/§4/§6/§8，以及 `reports/evidence/00-baseline.txt`。不要预读 Packet B/C 实现细节，避免跨包改文件。
