# QA-VERDICT — P1 hard constraints（W2/W3/W4/W5/R04b + R09/R10/R11/R12）

> run: `openrig-p1-hard-constraints-20261116` ｜ 轮次：1 ｜ 步骤：`qa_final` ｜ 作者：QA（独立核查方）
> 依据：`TASK.md` §5/§6、`PROJECT.md` §1–§4、`reports/00-plan.md` §4–§9、`DECISIONS.md` D-001–D-007、`reports/evidence/main-verify-decisions.txt`
> 结论：**PASS（0 FAIL；2 项已知裁决 WARN + 1 项声明限制 SKIP；发现 5 条，其中 1 条 S2 待 MAIN 处置）**；按 `handoff` 退出到 `close_round`。
> 版本：**r2**（2026-11-16 01:10 +08）。r1 交接后收到 MAIN 的上下文与 D-004–D-007；r2 合并三项「已知且有裁决」的 WARN/SKIP，并独立复核了 MAIN 的 manifest 复核结论（见 §1.1）。本文覆盖 r1，r1 的交接 digest `bbde1ad1…` 仅指向旧版。
> 环境陈述：`.venv/bin/python 3.12.15`、`pytest 9.0.2`、`rig openrig-local 0.1.4`、`node v24.22.1` 均可解析（SPEC §7 要求连同环境陈述报"全绿"）。
> 写范围声明：本 QA 只写 `reports/QA-VERDICT.md` 与 `reports/evidence/qa/**`；未改任何产出物、四件套、模板或产品仓；未写 `ISSUES.xlsx`（见 §6 F-1 的处置说明）。

## 1.1 已知且有裁决的 WARN / SKIP（不计为本轮新缺陷）

这三项是 MAIN 已用 D-004/D-005/D-006 裁定的既有事实，QA 只独立核对证据，不重复升级为缺陷：

| 项 | 结果 | 裁决 | QA 独立核对 |
| --- | --- | --- | --- |
| live run bundle 4 文件与 `render-manifest.json` 不符（`rig.yaml`、`workflow.yaml`、`guidance/team.md`、`OPENRIG-BRIDGE.json`） | **WARN** | D-004：不重渲染；`close_round` 用 `wf.py render-specialize` 登记 exact specialization | manifest 本身健康：按记录参数独立重渲染，`rig.yaml` 2078/`19fd8fab…`、`workflow.yaml` 4060/`184741…`、`agent.yaml` 222/`aabb001f…`、`guidance/team.md` 662/`192a36f6…` 与 manifest 逐字节一致（带 `--opencode-bin` 时 bridge 也一致）。漂移时序：manifest 00:47:32 → 四文件 00:47:58（+26s）。内容一致性：manifest 版含 `pmo`/`tdo-dsh`，live 版只有 3 个 pod/成员，与 `SPEC.md` §9 相符。**W5 机制本身仍以 `test_wf_render_specialize.py` 与本篇 §3 的 exact/stale 用例为准，不用 live run 当证明。** 证据：`evidence/qa/manifest-rerender.txt` |
| 母版 `BASELINE-post.sha256` 陈旧 | **WARN** | D-005：只报告，不刷新（升版超出 TASK §0） | `sha256sum -c` rc=1，35 OK / 3 FAILED；`README.md` 2026-10-23 15:39、`SPEC.md` 2026-10-23 15:15（均早于本 run），`ENTRYPOINTS.md` 2026-11-16 00:56（即 R12 改动）。不得据此宣称母版与快照一致。证据：`evidence/qa/baseline-post-check.txt` |
| Packet A/B 无 before-hash；A 的基线刷新发生在编辑之后 | **SKIP** | D-006：接受为已声明限制，不得升级为「内容哈希级证明」 | 复核 `evidence/A/changed-files.txt`：before 列记 `not-captured`，after 列与磁盘一致（见 §1.2 G6 行）。A 的 scope 结论仅由 mtime 白名单扫描 + 逐文件 after sha + 负向输出支撑。 |

## 1.2 验收判据对照（PROJECT §1 / §3）

| 判据 | 结果 | 独立证据 |
| --- | --- | --- |
| G1 W2 失败 preflight 无副作用 | **PASS** | `evidence/qa/negative-preflight-nosideeffect.txt`：rc1，workspace `AGENTS.md` sha 不变，`target.json` 未生成，`systemctl` 调用 0 次；对照用例（校验全过）才注入并有 1 次调用 |
| G1 W3 `meta-set` 回填 | **PASS** | `negative-meta-set.txt`：无 meta 的 legacy run 报错同时给 `meta-set` 与 `--project-root` 两条修复路径（rc1）；`meta-set` 后 `baseline` rc0 |
| G1 W4 untracked 快照 | **PASS** | `negative-snapshot.txt`：untracked 文件 before/after sha 可区分；缺失路径 `exists:false` 不崩；目录递归；对目标只读 |
| G2 R09 docs 计数 + CI | **PASS** | `doc_consistency.py --check` rc0；`WORKFLOW-TAGS.md` 顶部声明 canonical=62、实测一致；`.github/workflows/wf-validate.yml` 在 pytest 后新增 `doc_consistency.py --check` 与 `test_doc_consistency.py`，触发范围未改 |
| G2 R10 managed block 审计 | **PASS** | `entry-audit-agents.txt`（真实 AGENTS.md：7 块、orphan 7、rc0）、`negative-audit-blocks.txt`（2 块/0 块/递归/strict rc1）、`negative-audit-strict.txt`（strict rc1） |
| G3 R11 `openrig-run check` 失败语义 | **PASS** | `negative-openrig-run.txt`：ready rc0、incomplete rc1、missing-seat rc1、daemon-down rc1、`--allow-daemon-down` rc0、bridge 缺失/坏 JSON rc2、`--strict-render` rc1、非 strict 仅 WARN rc0 |
| G3 R11 `start --dry-run` 零 live 调用 | **PASS** | 同上：fake rig 调用计数 0；`entry-start-dryrun-live.txt`：真实 run 上 rc0、`executed=[]`、5 步计划仅回显 |
| G3 R12 复制/生成边界 | **PASS** | `templates/specialized/openrig-workflow-master/ENTRYPOINTS.md` §4.1「复制 vs 生成」两类产物 + bundle 侧三条规则现存 |
| G4 W5 render 特化 | **PASS** | `negative-render-specialization.txt`：无特化 ok=false（4 处 mismatch）；exact 特化 ok=true 且 `specialized:true`、strict rc0；stale 特化仍 mismatch、strict rc1；特化文件损坏 rc2 |
| G4 W5 `render-specialize` 守卫 | **PASS** | `negative-render-specialize-cli.txt`：`--path` 越界 rc1、空 `--reason` rc1、正常写入含 bytes/sha/reason |
| G4 R04b FINAL 双路径 | **PASS** | `negative-close-lint-dual-final.txt`：仅 `reports/FINAL.md` rc0、仅根 `FINAL.md` rc0、两者并存 rc0（reports 优先）、两者皆缺 `final_missing` rc1；sha/revision 错误仍报错（`closeout_hash_mismatch`/`revision_chain`） |
| G5 产品仓零改动 | **PASS** | `product-baseline.txt`：HEAD/status sha/diff sha 三项与 `00-plan.md` §2 完全一致（29 条 pre-existing dirty 未变） |
| G5 AGENTS/target 无残留副作用 | **PASS** | `AGENTS-target-sideeffects.txt`：根 `AGENTS.md` 自 00:48:07（任务开始前）未再变化；monitor `target.json` mtime 00:41、active 仍为旧 run、不含本 run；`yueyue-monitor.service` 自 22:17:54 起活跃（早于本 run） |
| G5 写范围零越界 | **PASS** | `scope-diff.txt`：基线之后变化的文件全部落在 TASK §0 白名单或本 run `reports/**`；`runs/<run>/DECISIONS.md` 由 MAIN 追加（D-004–D-007，控制面职责，不算实现越界） |
| G6 证据齐全 | **PASS** | A–D 每包 `changed-files.txt` 的 after sha 与磁盘逐一核对一致（18/18 可解释，唯一"DIFF"是 A 记录后 D 再次修改 `wf.py`，D 的记录与磁盘一致） |
| M1 full pytest | **PASS** | `full-pytest.txt`：**310 passed，rc=0**（基线 259，+51；不降反增） |
| M2 doc_consistency | **PASS** | `doc-consistency.txt`：0 error / 0 warning，rc=0 |
| M7 render specialization | **PASS** | 见 G4 |
| M8 close strict 双路径 | **PASS** | 见 G4；live run 现为 `final_missing`+`closeout_missing`（收轮前预期，`00-plan.md` §6.1、D-007） |
| M9 product scope | **PASS** | 见 G5 |

## 2. TASK §5 验收入口（QA 独立复跑，真实 rc）

见 `evidence/qa/entrypoints.txt`。摘要：

| # | 命令 | 真实 rc | 关键输出 |
| --- | --- | --- | --- |
| 1 | `pytest tests -q` | 0 | 310 passed in 7.72s |
| 2 | `doc_consistency.py --check` | 0 | 0 error / 0 warning |
| 3 | `openrig_preflight.py --json --advisory` | 0 | `ok:false`（无 run-id → `run_context`/`run_docs` 失败），`injectedAgents=null`、`monitor=null`；advisory 不改写 `ok` |
| 4 | `audit_managed_blocks.py --path .../AGENTS.md --json` | 0 | 7 块、`orphanManaged=7`；`--strict` rc1（预期） |
| 5 | `openrig_run.py check --json --allow-daemon-down` | 0 | bridge ok、render WARN(4)、doctor ok、workflow_validate ok、seats 3/3 ready |
| 6 | `openrig_run.py check --json`（不带 allow） | 0 | daemon 在线，语义一致 |
| 7 | `openrig_run.py start --dry-run --json` | 0 | 5 步计划，`executed=[]` |
| 8 | `verify_render.py --json` | 0 | `ok:false`，4 处 mismatch；`--strict` rc1 |
| 9 | `wf_close_lint.py --run ... --strict` | 1 | `final_missing` + `closeout_missing`（收轮前预期） |

## 3. 负向用例（QA 自建，非复读 TDO 测试）

共 **20 条**，覆盖 6 个门（要求 ≥8 条、≥4 个门）：

1. 不存在的 run-id + workspace → preflight rc1、零写入
2. 合法 run-id 但 run-dir 缺四件套 → rc1、零写入
3. 校验全过 → 之后才注入/注册（顺序对照用例）
4. bridge 缺失 → rc2
5. bridge 坏 JSON → rc2
6. seats 未 ready → rc1
7. seat 缺失 → rc1
8. daemon down → rc1
9. daemon down + `--allow-daemon-down` → rc0
10. `--strict-render` + bundle 漂移 → rc1；同 bundle 不加 strict → rc0（WARN）
11. `start --dry-run` → fake rig 调用 0 次
12. audit 无块 → `summary=0`
13. audit orphan + `--strict` → rc1
14. snapshot 缺失文件 → `exists:false`、rc0
15. legacy run 无 meta + baseline → rc1 且含两条修复路径
16. close-lint 两者皆缺 → `final_missing`
17. close-lint sha 不符 → `closeout_hash_mismatch`
18. close-lint revision 链断 → `revision_chain`
19. render stale 特化 + strict → rc1
20. render 特化文件损坏 → rc2；`render-specialize` 路径越界/空 reason → rc1

## 4. 实测补充说明（避免误读）

- **`wf.py verify-baseline` 返回 `ok:false` 是预期**：实现本身改动了 tracked 文件 `wf.py` 并新增 `wf-validate.yml`，聚合 `statusSha256`/`diffSha256` 必然变化。范围判定采用「新增/移除路径集合 + mtime 扫描」，两者均干净（`scope-diff.txt`）。
- **live run bundle 4 处 manifest 漂移**（`rig.yaml`、`workflow.yaml`、`guidance/team.md`、`OPENRIG-BRIDGE.json`）按 D-004 记 WARN：manifest 经独立重渲染复现（见 §1.1），漂移是 3-seat 特化、意图来自 `SPEC.md` §9，但未走 `render-specialize`；`close_round` 负责登记 exact specialization。在登记前 `check` 给 WARN 而非 PASS 是正确行为。
- **`preflight --json --advisory` 不带参数时 `ok:false`**：这是"缺 run-id"的正确失败语义；advisory 只压 rc，不伪造 `ok:true`。

## 5. 结论

P1 六个包（A–D）交付的机器门逐条可复现、负向可失败、失败路径无持久副作用；产品仓与四件套零越界；证据数字与磁盘一致。**实现层面判定 PASS。**

## 6. 发现与风险（QA 只报不改）

| ID | 级别 | 类型 | 发现 | 证据 | 责任 | 建议动作 |
| --- | --- | --- | --- | --- | --- | --- |
| F-1 | **S2** | 问题 | `STATUS-Round-1.md` 仍是空模板（进度表 0 条、"交接给 QA"区空），`ISSUES.xlsx` 为空；QA 只能从 queue packet + `reports/evidence/**` 起手，文档面完整性无法从 STATUS 核对 | `STATUS-Round-1.md` mtime 00:47:32（模板态）；`issues.py list` → `(无匹配行)` | MAIN（本 run 无 PMO 席） | 收轮前二选一：用 `wf.py append-status` 补 4 条包级进度 + QA 交接，或在 `DECISIONS.md` 记一条"本轮以 reports/evidence 替代 STATUS 留痕"的例外决策；二者需在 `PROJECT closed` 前落地 |
| F-2 | S3 | 限制（已裁决） | Packet A/B 无 before-hash，A 的基线属自重基线，不能作内容哈希级证明；原始 `00-baseline.original.txt` 已留档 | `evidence/A/baseline-refresh-note.md`、`scope-diff.txt` | MAIN（D-006） | **不处置**；A 的 scope 以 mtime 白名单 + 逐文件 after sha + 负向输出为准；W4 从 B 起提供真 before/after |
| F-3 | S3 | 风险 | close-lint 只按 entry 自身 `path` 校验 sha；当 `reports/FINAL.md` 与根 `FINAL.md` 同时存在且内容不同时，closeout 只 attest 根文件也能 rc0（我构造的 `both_wrong_reports` 用例） | `negative-close-lint-dual-final.txt` | MAIN（R04b 后续） | 若要收紧：要求 closeout 必须覆盖"解析出的 FINAL 实际路径"且 sha 与之一致；本轮不改（契约只要求"按实际路径校验 + reports 优先"） |
| F-4 | S3 | 风险 | `audit_managed_blocks.py --strict` 的 `ownerRig` 只认 `rig:<id>` 前缀；真实渲染器产出的块 id（`CULTURE-default.md`、`guidance/team.md` …）都不是该命名空间，strict 一开即 100% 失败 | `entry-audit-agents.txt`（7/7 orphan） | MAIN（接线前） | 接线前先定命名空间或映射表；当前默认关闭，不影响本轮 |
| F-5 | S4 | 问题 | `WORKFLOW-TAGS.md` §1.1 表格仍写 canonical=37，与顶部声明/实测 62 不一致（只有顶部被 validator 校验） | `WORKFLOW-TAGS.md` 第 8 行 vs §1.1 表 | MAIN / 文档维护 | 下轮顺手改成"以顶部声明为准"，避免读者取到旧数 |

> F-6（live bundle 漂移未进 DECISIONS）**已撤销**：D-004 已裁决并指定 `close_round` 登记 exact specialization；改列 §1.1 WARN。

**游离项检查**：以上 5 条均给了 owner 与去向，无无主项（F-6 已由 D-004 撤销）。F-1 是唯一 S2，处置责任在 MAIN 的 `close_round`；按 SPEC §7 DoD，"无 open S1/S2" 在收轮时判定，本篇只保证"已识别 + 有主人 + 有动作"。

## 7. 无法判定 / 未覆盖

- **CI 实跑**：只做静态核对（YAML 步骤、路径、依赖）；未在 GitHub Actions 上实际触发（无联网/无远端 push 授权，且本轮禁止 commit/push）。
- **`openrig_run start` 非 dry-run 全链路**：未在真实 daemon 上跑 `daemon start → up → instantiate`（会起新进程、改 live 状态，超出 QA 只读边界）；只验证了 dry-run 计划与 fake-rig 语义。
- **refs 边界**：R13/R14 不在本轮（`PROJECT.md` §2 明示）。

## 8. 证据索引（`reports/evidence/qa/`）

`full-pytest.txt`、`doc-consistency.txt`、`entry-preflight-advisory.txt`、`entry-audit-agents.txt`、
`entry-check-allow-down.txt`、`entry-check-no-allow.txt`、`entry-start-dryrun-live.txt`、`entry-verify-render.txt`、
`negative-preflight-nosideeffect.txt`、`negative-audit-blocks.txt`、`negative-audit-strict.txt`、
`negative-openrig-run.txt`、`negative-snapshot.txt`、`negative-meta-set.txt`、
`negative-render-specialization.txt`、`negative-render-specialize-cli.txt`、`negative-close-lint-dual-final.txt`、
`scope-diff.txt`、`scope-baseline.txt`、`product-baseline.txt`、`AGENTS-target-sideeffects.txt`、`entrypoints.txt`、
`manifest-rerender.txt`、`baseline-post-check.txt`。

复跑脚本（QA 自建，均在 `/tmp/opencode/qa-p1/`，不入库）：`w2-proof.sh`、`r04b-proof.sh`。
