<!-- wf-evidence
run: openrig-master-selfopt-20261020
round: 1
doc: TDO-OC-REPORT
owner: TDO-OC
state: delivered
updated: 2026-10-20
-->

# TDO-OC-REPORT — WS-2（generator/template 侧）执行报告

> 执行体：`exec-tdo-oc@openrig-master-selfopt`（OpenCode 分支）｜ 工作包：`qitem-20261019202230-5b6fef7c`
> 依据：`SELF-OPT-PLAN.md` §2.1 **I-1 / I-3** 与 §2.2 队列调优（OC-2）、§5 证据规则｜ 结论：**OC-1 / OC-2 / OC-3 全部 PASS**
> 复核轮次：PMO 20:34Z 复核后按现行计划 I-1/I-3 收紧口径（manifest schema、`renderedAt`、模板哈希、默认输出兼容），第 2 版。

## 0. 一句话结论

`render_master.py` 从“边校验边写盘”改为**先校验 → 内存渲染 → 一次性落盘**：新增 `--dry-run`、`--json`、逐产物 `render-manifest.json`（含 `renderedAt`、`files{path:{template,bytes,sha256}}`、`templates{name:sha256}`）与声明式产物表；四份 tpl 的输出仍与 v1.0.0 逐字节一致，未渲染占位符仍硬失败，默认（无 flag）stdout 保持 v1.0.0 形态。未改 `tools/openrig_bridge.py`、`ARCHITECTURE.md`、`VERSION`、`CHANGELOG.md`、`README.md`，未触碰 live bundle。

**可复现性口径（QA 按此判，勿按字面跨目录比全量）**：
- **4 个模板产物**（`rig.yaml`/`workflow.yaml`/`agents/worker/agent.yaml`/`guidance/team.md`）在任意两个 `--output-dir` 之间 `sha256` 全等；
- **同一 `--output-dir`** 重复渲染时，5 个产物 + bridge 逐字节一致；`render-manifest.json` 仅 `renderedAt` 不同（时间戳按 I-3 要求**不参与任何 sha256**）；
- `OPENRIG-BRIDGE.json` 因内嵌绝对 `bundleDir/rigSpec/workflowSpec`，**跨不同 `--output-dir` 时必然不同**（v1.0.0 既有契约，已由 **D-010** 裁决接受，见 §5-1）。

## 1. 改动清单（唯一写文件：`render_master.py`）

| 位置 | 改动 | 对应任务 |
| --- | --- | --- |
| `render_master.py:34-41` | 声明式产物表 `ARTIFACTS`（4 条 path↔template）+ `MANIFEST_FILES`（含 bridge），取代 4 段重复的 `write_text` | OC-3 |
| `render_master.py:47` | `RenderError`：把“渲染失败”与“参数错误”分成两个退出码（3 / 2） | OC-1 |
| `render_master.py:51-80` | `parse_args()` 可注入 argv；新增 `--dry-run`、`--json`、`--template-dir`；`--help` 内联退出码语义 | OC-1 / OC-3 |
| `render_master.py:83-106` | `validate_args()`：`--run-id` 形态、`--project-root` 存在、`--daemon-port` 1–65535、`--output-dir` 非空、输出目录非空且未带 `--force`；全部走 `parser.error()` → **rc=2、stderr 含字段名、写盘前失败** | OC-1 |
| `render_master.py:125-143` | `master_version()` 读 `VERSION`（只读）、`rendered_at()` 生成 UTC 时间戳、`load_template()` 缺模板即失败 | OC-2 / OC-3 |
| `render_master.py:184-208` | `artifacts_in_memory()`：所有产物 + bridge 在内存渲染，**dry-run 与真实渲染共用同一条路径** | OC-1 / OC-3 |
| `render_master.py:211-257` | `file_records()` / `template_hashes()` / `build_manifest()`：清单 `files` 为 **dict**（`path → {template,bytes,sha256}`），另记 `templates{name:sha256}`、`renderedAt`、`masterVersion`；排除自身 | OC-2 |
| `render_master.py:260-311` | `next_commands()` 产出机器可读 next steps；`report_json()` 固定 schema（`ok/dryRun/outputDir/files[]/next[]`，另保留 `nextCommands` 兼容早期草稿）；`print_human()` 恢复 v1.0.0 输出形态 | OC-1 |
| `render_master.py:314-359` | `main()` 编排：校验 → 内存渲染 → dry-run 直接返回 → 落盘 → 最后写清单；未被 `ARTIFACTS` 引用的模板给 stderr warning（不失败） | OC-1/2/3 |

`templates/**` 四个 tpl **未改动**（sha256 见 §4），只被新路径读取。

## 2. 复跑命令与退出码（可直接照跑）

```bash
cd templates/specialized/openrig-workflow-master

# I-1 / OC-1
python3 render_master.py --help                                                          # rc=0
python3 render_master.py --run-id selfopt-oc-dry --project-root /tmp \
  --output-dir /tmp/o1 --dry-run --json                                                  # rc=0，/tmp/o1 不存在
python3 render_master.py --run-id BAD_ID --project-root /tmp --dry-run                    # rc=2，stderr: --run-id
python3 render_master.py --run-id ok --project-root /tmp --daemon-port 70000 --dry-run    # rc=2，stderr: --daemon-port
python3 render_master.py --run-id ok --project-root /tmp --output-dir /tmp/o1 --json \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["ok"] and d["files"]'     # 计划 I-1 断言通过
python3 render_master.py --run-id c --project-root /tmp --output-dir /tmp/c               # 默认输出 11 行，形态同 v1.0.0

# I-3 / OC-2
python3 render_master.py --run-id mm --project-root /tmp --output-dir /tmp/m1 --json      # rc=0
python3 render_master.py --run-id mm --project-root /tmp --output-dir /tmp/m2 --json      # rc=0
python3 - <<'PY'
import json
a=json.load(open('/tmp/m1/render-manifest.json')); b=json.load(open('/tmp/m2/render-manifest.json'))
f=lambda m:{k:v['sha256'] for k,v in m['files'].items() if k!='OPENRIG-BRIDGE.json'}
assert f(a)==f(b)          # D-010：跨目录只比非 bridge 项
assert a['renderedAt'] and a['templates']
print("deterministic ok")
PY

# OC-3：声明式表 + 占位符守卫
cp -r templates /tmp/tpl-orphan && cp templates/guidance-team.md /tmp/tpl-orphan/orphan-template.md
python3 render_master.py --run-id o --project-root /tmp --template-dir /tmp/tpl-orphan \
  --output-dir /tmp/o --dry-run --json                                                    # rc=0 + warning
cp -r templates /tmp/tpl-bad && printf '\n{{MISSING_KEY}}\n' >> /tmp/tpl-bad/guidance-team.md
python3 render_master.py --run-id g --project-root /tmp --template-dir /tmp/tpl-bad \
  --output-dir /tmp/g --dry-run                                                            # rc=3，未渲染占位符，不落盘

# 执行面回归：同 live 参数渲染 → 4 产物逐字节比对 → spec 仍可 validate
python3 render_master.py --run-id openrig-master-selfopt-20261020 \
  --project-root /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group \
  --rig-name openrig-master-selfopt --workflow-id openrig-workflow-master-selfopt \
  --output-dir /tmp/live-check --json                                                      # rc=0
rig workflow validate /tmp/live-check/workflow.yaml --json                                 # rc=0，ok=true
```

## 3. 结论表

| ID | 目标 | 结论 | 关键证据（原文输出） |
| --- | --- | --- | --- |
| OC-1 / I-1 | 写盘前校验 + `--dry-run` + `--json` | **PASS** | 6 类非法参数均 `rc=2` 且 stderr 指名 `--run-id`/`--daemon-port`/`--project-root`/`--output-dir`；dry-run `rc=0` 且目标目录 `absent`；`json.loads` 得 `ok=True files=5 next=9`；默认输出 11 行、`rendered:` + `next:` 形态与 v1.0.0 相同 |
| OC-2 / I-3 | 逐产物清单（`renderedAt`/模板计入）+ 可复现 | **PASS** | `files` 为 dict（5 项）、`templates` 4 项、`renderedAt` 存在；跨目录非 bridge 4 项 sha256 全等；同目录重渲染 5 产物 + bridge `SAME`，清单仅 `renderedAt` 不同；同 live 参数渲染 4 产物与 live bundle `IDENTICAL` |
| OC-3 | 声明式产物表 + 占位符失败保留 | **PASS** | 4/4 tpl 经 `ARTIFACTS` 渲染（清单 `template=` 列可查，`templates` 4 项哈希）；`{{MISSING_KEY}}` → `rc=3` 且输出目录未创建；缺模板 → `rc=3 template not found`；未引用模板 → `rc=0` + warning |

退出码契约（写入 `--help` 与本文档）：`0` 成功（含 dry-run）、`2` 参数错误、`3` 渲染失败（占位符/缺模板/缺 `VERSION`）。

## 4. DoD 对照（SELF-OPT-PLAN I-1 / I-3 + PROJECT §4）

| DoD 项 | 判定 | 证据 |
| --- | --- | --- |
| I-1 验收脚本原样可跑 | 是 | §2；`evidence/oc/oc1-args-validation.txt`（含 plan I-1 断言行） |
| I-1 默认输出逐字兼容 v1.0.0 | 是 | 11 行 = `rendered: <dir>` + `next:` + 9 条命令，无新增行；`evidence/oc/oc1-args-validation.txt` §4 |
| I-3 `files` dict + `renderedAt` + 模板计入 | 是 | `evidence/oc/oc2-render-manifest.txt` §1/§2 |
| I-3 确定性（同参数渲染） | 是 | 同目录 5 产物 + bridge 逐字节一致；跨目录非 bridge 4 项一致（D-010） |
| I-3 不自引用、时间戳不入哈希 | 是 | 清单不含自身；`renderedAt` 仅作为顶层元数据，任何 `sha256` 只覆盖产物字节 |
| 3 项任务全部有结论 | 是（3×PASS，无“延后”） | §3 |
| 上述命令退出码 | 是 | §2 + `evidence/oc/*` |
| `git status --porcelain templates/` 只含白名单 | 是（见 §5-3） | 我只改 `render_master.py`；4 个 tpl sha256 未变（`aabb001f…`/`317db1b0…`/`8a71fa35…`/`ddc6e80a…`）；`VERSION`/`CHANGELOG.md`/`README.md` 由 MAIN 在 S5 改动，非我所为 |
| 不改 bridge/ARCHITECTURE、不覆盖 live bundle、不起 daemon | 是 | live `openrig/rig.yaml`、`OPENRIG-BRIDGE.json` mtime 未变；本包全程未启停 daemon/rig |

## 5. 已知限制 / 未决项（不隐藏）

1. **跨输出目录的清单不等（D-010 已裁决接受，不视为缺陷）**：`OPENRIG-BRIDGE.json` 记录 `bundleDir/rigSpec/workflowSpec` 绝对路径（v1.0.0 既有契约），因此不同 `--output-dir` 的 bridge 及其清单哈希必然不同；4 份模板产物完全相同。D-010 选择 A（接受为已知限制，本轮不改代码），并否决了“从清单剔除 bridge”的隐藏式做法；路径相对化列入 v1.2 候选。**承载点**：`CHANGELOG.md`「已知限制」+ `README.md`（MAIN 在 S5 写）。
2. **`renderedAt` 使清单本身不逐字节可复现**：I-3 明确要求该字段且规定时间戳不参与哈希，故同一 `--output-dir` 重渲染时清单文本会差一行 `renderedAt`；**产物与 `files[].sha256` 不受影响**。若需完全字节级清单比对，请比对去掉 `renderedAt` 的 JSON。
3. **`masterVersion` 随 `VERSION` 变化**：清单只读 `VERSION`；MAIN 已在 S5 把 `VERSION` 升到 `1.1.0`，后续渲染自动写 `1.1.0`（本报告证据已反映该值）。
4. **母版目录此前未被 git 跟踪**：`templates/specialized/openrig-workflow-master/` 在本包开始前整目录为 `??`，因此“越界检查”不能只靠 `git status` 区分；本报告用 mtime + sha256 作替代证据。
5. **argparse usage 噪声**：参数错误时 stderr 先打印 usage 再打印 `error: <字段>`；字段名在末行，脚本化断言请取末行。
6. **`--template-dir` 是本包新增的可测试性开关**（默认 `./templates`），不改变默认行为，仅用于 OC-3 守卫复跑。
7. **`next` 与 `nextCommands` 双写**：I-1 规定 `next[]`，早期草稿用 `nextCommands`；两者同值，保留后者避免已写脚本失效，下个版本可删。

## 6. 证据索引

| 文件 | 内容 |
| --- | --- |
| `evidence/oc/oc1-args-validation.txt` | help / dry-run 不落盘 / plan I-1 断言 / 6 个非法参数用例 / 默认输出形态检查 |
| `evidence/oc/oc2-render-manifest.txt` | 清单原文（dict + renderedAt + templates）、跨目录确定性（D-010 口径）、同目录重渲染、live 比对、`workflow validate` |
| `evidence/oc/oc3-placeholder-guard.txt` | 声明式表源码摘录、4/4 模板渲染、占位符守卫 rc=3、缺模板 rc=3、未引用模板 warning |

## 7. 关联裁决（不代拍）

- **Q-OC-1 → 已由 D-010 裁决（A：接受为已知限制）**：跨 `--output-dir` 的 bridge/manifest 差异不在 OC-2 判据内；路径相对化（原 B 方案）列入 v1.2 候选，需 render + doctor + status 同步改并升 `schemaVersion`，本轮不做。
- **QA 侧 P-002（doctor `safetyMode`/`schemaVersion` 校验）与 P-001（ARCH §5.4 调优表）均属 TDO-DSH 写权限**（`tools/openrig_bridge.py`、`ARCHITECTURE.md`），不在 WS-2 范围，本报告不作处理。
- **W-2 已处理**：manifest schema（dict + `renderedAt` + `templates`）按现行 I-3 对齐；跨目录差异口径按 D-010 收窄（见 §0/§5-1）。
