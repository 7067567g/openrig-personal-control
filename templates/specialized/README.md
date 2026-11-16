# specialized — 按任务/项目特化模板

> 用法：一个烧 token 的 run = 一个目录范围 + 一份 `SPEC.md` + 一套预填模板。
> 新增母版：`openrig-workflow-master` = workflow-group 控制面 + OpenRig 执行面的双平面混合编排；详见该目录 `ARCHITECTURE.md`。
> 实例化：`python3 scripts/wf.py new-run <run-id> --template templates/specialized/<name> ...`
> 标签化与成熟度：先看根目录 [`WORKFLOW-TAGS.md`](../../WORKFLOW-TAGS.md) 与机器清单 [`workflow-tags.json`](../../workflow-tags.json)，再决定新增/复用哪个类型。
> **选型顺序**：先查 [`../baseline/REGISTRY.md`](../baseline/REGISTRY.md) 选复合类型；再查 [`../contracts/README.md`](../contracts/README.md) 选原子轮型；最后才写领域 SPEC。
> **硬要求**：新建/大改领域模板时，`SPEC.md §0` 必须写 `baseline: composite/<name>@<version>`（无匹配写 `baseline: none + 理由`）与 `contracts: <type>@<version>,...`。缺这两行不算可交付特化。
> **现有 26 个模板的映射**：[`BASELINE-MAP.md`](BASELINE-MAP.md)。新增模板必须补行，`scripts/doc_consistency.py --check` 会核对缺行/多行；旧 run 的 SPEC 不改。
> 2026-10-23：`issue-sync` 已从 baseline 降级为本目录 adapter（`none` + research/verify/audit）。

## 一个特化模板包含什么

| 文件 | 必需 | 作用 |
| --- | --- | --- |
| `SPEC.md` | ✅ | 本 run 的特化规则：目录分区、全内容覆盖要求、证据格式、禁止项、DoD。委派消息会自动要求先读它 |
| `PROJECT.md` | 推荐 | 预填目标/范围/指标/WS 分区表，PMO 只需校验与细化；缺省时回退通用模板 |
| `DECISIONS.md` | 建议 | 预置「待决清单」（Q-1…），主会话拍板后挪进决策账本 |
| `STATUS-Round-n.md` / `ISSUES.xlsx` | 可选 | 不提供时自动回退到通用模板（保持工具兼容） |
| `README.md` / `actions.example.jsonl` | 可选 | 使用说明与安全 action 格式样例；示例路径必须重写，不能直接执行 |

> 安全关键模板（如 `h-drive-cleanup`）可启用 run 级门控执行器与独立 `SAFETY×1`。此时 `SPEC.md` 必须写明门控命令、FAIL 逐条审核、red 人工批准与绕过门控的停工规则；SAFETY 角色手册见 `../../roles/SAFETY.md`。

## 新建一个特化模板

1. 复制本目录下最接近的模板，如 `cp -r kb-debt-burn my-task`；
2. 重写 `SPEC.md`：① 写权限目录表（一 WS 一目录/一文件边界）② 全内容覆盖要求 ③ 证据格式 ④ 禁止项；
3. 改 `PROJECT.md` §1–§4：目标判据、范围、指标、WS 表（产出物写 run 内路径，验收判据可复跑）；
4. 改 `DECISIONS.md` 的待决清单（只列选项，不预写结论）；
5. 用 `--dry-run` 建一个 scratch run 校验（`new-run ... && wf.py delegate <run> --role pmo --dry-run`）；
6. 若模板启用安全门控：先在临时目录验证 `hdrive_gate.py`，再对真实盘执行；真实 H 盘根未确认/未挂载时只允许 BLOCKED，不得造样例路径硬跑。

## 分区原则（重要）

- **一份写权限只给一个 WS**；同一目录要拆多片时，按文件清单拆并写进 SPEC。
- 每片必须能回答"我覆盖了范围内哪些文件、每个怎么处置"（全内容，不许只挑重点）。
- 跨片依赖用波次（R1/R2…）解决，不靠"同时改同一个文件"。

## 母版与本地化副本（上游 / adapter 关系）

- **canonical 上游**：`deepseek-知识库/workflow-group/templates/`。原子契约、基准模板、通用四件套只在这里定义并冻结。
- **本地化 adapter**：`60-外部仓库/workflow-group/`、`obsidian-nutstore-sync-phone-ai-tools/workflow-group/` 的 `templates/specialized/*` 是领域适配层；同名模板不代表同版本，必须按路径/source 区分。
- **禁止互相覆盖**：本地化差异先进各自 `LOCALIZATION.md`；要回流 canonical，必须按 `templates/contracts/BASE-MASTER.md` §4 或 `templates/baseline/README.md` 的版本协议提交，不允许直接 `cp -r` 副本覆盖母版。
- **比对口径**：先比 `SPEC.md` 的 baseline/contracts 引用，再比领域路径、证据 schema、风险修饰；文件名相同不能作为同步完成证据。
