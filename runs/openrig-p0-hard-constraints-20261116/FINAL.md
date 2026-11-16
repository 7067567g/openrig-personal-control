<!-- wf-doc
run: openrig-p0-hard-constraints-20261116
round: 1
doc: FINAL
owner: MAIN
state: closed
updated: 2026-11-16
-->

# FINAL — P0 hard constraints（R01–R07 + R08）

> 写者：MAIN（close_round）｜ 判定：**PASS-WITH-WARN** ｜ 本轮只交付 P0；R09–R14（P1/P2）明确未实现。
> 独立 QA：`reports/QA-VERDICT.md`（PASS-WITH-WARN，5 条 WARN，无 FAIL）。

## 0. 结论

P0 的六个硬门（R01/R02/R03/R04/R05/R06/R07）全部实现为可失败、可复跑的机器门，R08 为每个门提供了真实负向测试。MAIN 在 close 阶段独立复跑全量 pytest（259 passed）与 TASK §5 入口；产品仓与 scope 相对规划基线零新增越界；无 commit/push。QA 的 5 条 WARN 已逐条处置（§5），其中 W1（FINAL 路径）在 close 内解决，W2/W4 转入下一轮，W3/W5 为已记录的已知行为。

## 1. R01–R07 交付与验收

| 门 | 交付 | 验收证据 | 结果 |
| --- | --- | --- | --- |
| R05 | `openrig_preflight.py` 真检查：`ok=all(required)`，缺 workspace/run-id/block/docs fail-closed；`--advisory` 只改 rc | `evidence/closeout/final-preflight-advisory.txt`(rc0/ok:false)、`final-preflight-positive.txt`(rc0/ok:true)、QA `neg-preflight-no-context.txt`(rc1) | PASS |
| R06 | `required_components.py` + doctor 顶部检查 + `issues.py` 无 openpyxl 导入/JSONL 降级 | `final-doctor.json`(rc0, errors=[])、QA `neg-required-components-empty-root.json`(rc1, 8/8 install_hint)、`neg-issues-no-openpyxl-jsonl-fallback.txt` | PASS |
| R02 | `.run-meta.json`、`baseline`/`verify-baseline`、排除本 run 目录 | `final-baseline-literal.txt`(rc1, 见 W3)、`final-baseline-recapture.txt`(rc0)、`final-verify-baseline.txt`(rc0)、QA `verify-baseline-final.txt`(rc1, statusAdded=4 C files) | PASS |
| R03 | `evidence_run.sh`：pipefail、真实 rc、stdout/stderr sha256、原文 | QA `neg-evidence-run-exit7.txt`(rc7)、`neg-evidence-run-pipefail.txt`(rc1) | PASS |
| R01 | `wf.py archive-gate`：dry-run 复用 guard strict COMPLETE | QA `neg-archive-gate-partial.txt`(gate rc2)、`neg-archive-gate-missing-guard.txt`(rc3)、`fake-archive-gate-complete.txt`(rc0)，marker 命令未执行 | PASS |
| R04 | `wf_close_lint.py --strict` + `evidence-record` + revision 链 | 本节 FINAL + `reports/evidence/closeout.json`；`evidence/closeout/close-lint-strict.txt`；QA `neg-close-strict-*` 四类 ERROR、`pos-close-strict-good-run.txt` | PASS |
| R07 | `verify_render.py`：默认 WARN、`--strict` ERROR、坏 manifest rc2 | `final-verify-render-default.txt`(rc0/ok:false)、`final-verify-render-strict.txt`(rc1)、QA `neg-verify-render-missing-manifest.txt`(rc2)、`pos-verify-render-clean.txt`(ok:true) | PASS |

## 2. R08 负向覆盖

QA 独立复跑 14 条负向用例，覆盖 R01/R03/R04/R05/R06/R07；每条断言的是失败语义本身（rc、`ok:false`、ERROR code、缺字段），不是“打印了就算”。清单与原文见 `reports/evidence/qa/negative-cases.txt`。

## 3. close 阶段独立复跑（MAIN）

| # | 命令（缩写） | rc | 结果 |
| --- | --- | --- | --- |
| 1 | `.venv/bin/python -m pytest tests -q -p no:cacheprovider` | 0 | 259 passed（`evidence/closeout/final-full-pytest.txt`） |
| 2 | `openrig_preflight.py --json --advisory` | 0 | `ok:false`，未伪造 ok（`final-preflight-advisory.txt`） |
| 3 | `openrig_preflight.py --json --run-id … --workspace KB --run-dir …` | 0 | `ok:true`，5/5 required；`AGENTS.md` sha256 前后均为 `53eed071…`（`final-preflight-positive.txt`） |
| 4 | `wf.py baseline <run> --json`（TASK 字面命令） | 1 | 缺 `.run-meta.json`，明确要求 `--project-root`（W3，`final-baseline-literal.txt`） |
| 4b | `wf.py baseline <run> --project-root KB --json` | 0 | 重新捕获收口快照（`final-baseline-recapture.txt`） |
| 5 | `wf.py verify-baseline <run> --json` | 0 | 收口快照即时校验无漂移（`final-verify-baseline.txt`）；漂移检测证据见 QA `verify-baseline-final.txt`（rc1，恰好 4 个 Packet C 文件） |
| 6 | `verify_render.py --run-dir … --json` | 0 | `ok:false` 的 live render drift WARN（W5）；`--strict` 同输入 rc=1（`final-verify-render-strict.txt`） |
| 7 | `wf.py doctor <run> --json` | 0 | `errors=[]`（`final-doctor.json`） |

## 4. 独立 QA 结论

- 全量 pytest：rc=0，259 passed。
- 六入口：真实 rc 见 QA `six-entrypoints.txt`，与 MAIN close 复跑一致（baseline 字面命令的 rc=1 已在 W3 说明）。
- scope：相对启动快照新增恰好 10 个路径、删除 0；内容变化路径全部落在 PROJECT §4 包边界内。
- 产品仓：HEAD/status/diff/dirty 四值与规划基线完全一致（29 dirty，未覆盖）。
- QA 判定 **PASS-WITH-WARN**，无 FAIL，可进入 close。

## 5. WARN 处置

| # | WARN | 处置 | 去向 |
| --- | --- | --- | --- |
| W1 | `wf_close_lint.py` 只认 run 根 `FINAL.md`，而 PROJECT 要求 `reports/FINAL.md` | close 同时写根级 `FINAL.md` 与 `reports/FINAL.md`（内容一致），先写 FINAL 再 `evidence-record`，最后 strict lint；未放宽检查 | 已解决；下一轮可统一路径约定（R04b） |
| W2 | preflight 在“校验失败”时也先注入/写 monitor，失败路径有持久副作用 | 门本身 fail-closed，QA 已恢复 side effect；本轮不改实现 | 下一轮 P1：注入延后到 run_context/run_docs 通过之后 |
| W3 | TASK §5 的 `baseline` 字面命令对本 run rc=1（无 `.run-meta.json`） | 记录字面 rc=1；close 用 `--project-root` 重新捕获收口快照并 verify rc=0 | 下一轮 P1：`new-run` 元数据回填或命令文档补参数 |
| W4 | Packet C 两个启动时已 untracked 文件缺 before-sha256（记 n/a） | 文件 after/当前 sha 已对齐，无异常；不伪造 before | 下一轮 P1：`git hash-object` 或先复制快照 |
| W5 | live render drift（4 文件 bytes mismatch） | 按 D-005 接受 WARN；未重渲染、未重写 manifest；语义完整性已核对 | 下一轮 S3：manifest 与 run 特化 guidance 同源化 |

## 6. 范围、产品仓与安全

- 相对启动快照新增 10 个路径（A 3 / B 3 / C 4）；修改 `scripts/issues.py`、`scripts/wf.py`、`tests/test_issues.py`、`tests/test_wf.py`，以及内容变化的 `scripts/openrig_preflight.py`、`scripts/wf_close_lint.py`、`tests/test_wf_close_lint.py`。全部在 PROJECT §4 包边界内。
- 根 `AGENTS.md` 的 `OPENRIG-PREFLIGHT` managed block 是 TASK §5 授权的唯一 scope 例外：`629742bf… → 53eed071…`，close 复跑后未再变化。
- 产品仓 `/home/a7067567g/下载/deepseek/deepseek-项目/10-openrig-deepseek`：HEAD `e932ae94…`、status `3b64cf90…`、diff `dc564a37…`、dirty 29 —— 与规划基线一致（`evidence/closeout/final-product-baseline.txt`）。
- 无 commit、无 push、无 tag；无 teardown/删除；无金额预算。

## 7. 明确未实现

R09–R14（CI 集成、block audit、wrapper、lockfile、workflow engine invariants 等）未实现，也不得被本轮表述为已实现。

## 8. 下一轮候选

1. P1：W2（preflight 失败路径副作用）、W3（baseline 元数据/命令）、W4（before-sha 取证）。
2. S3：W5（render manifest 与 run 特化 guidance 同源）。
3. R04b：FINAL 路径约定统一为 `reports/FINAL.md`（或 linter 兼容两者），减少双写。
4. 仍不进入 P2，直到 P1 收口且有独立 QA。
