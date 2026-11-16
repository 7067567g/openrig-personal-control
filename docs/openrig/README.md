# OpenRig 跨仓文档总图

> 这份地图回答一个问题：**"我要做 X，应该去哪个仓的哪个文件？"**
> 三仓（KB 控制面 / 源码 / 使用运维）的职责、入口、常见错位都在这里。
> 更新时间：2026-11-15 ｜ 维护：workflow-group 控制面 ｜ 本文件不随任何包发布。

## 1. 三仓职责与权威边界

| 文档面 | 位置 | 回答什么 | **不**回答什么 |
| --- | --- | --- | --- |
| **KB 控制面** | `deepseek-知识库/workflow-group/`（本仓） | 目标、范围、验收判据、决策、轮次、证据指针 | 实时执行状态、seat 归属 |
| **OpenRig 执行面** | 隔离 home 的 `rig ps` / `rig queue` / `rig workflow show` / transcript | 现在谁在做、做到哪、阻塞是什么 | 项目目标、验收口径 |
| **源码 reference** | `deepseek-项目/10-openrig-deepseek/docs/reference/` | 随包发布的用户/运维参考（装、跑、命令语义） | 开发者 as-built 内部结构 |
| **源码 as-built** | `deepseek-项目/10-openrig-deepseek/docs/as-built/` | 代码结构与模块归属（**不随包**） | 用户操作步骤 |
| **使用/运维示例** | `openrig-custom-complete-usage/` | sanitized 可复制实践、误读速查、过程档案 | 源码行为事实、控制面决策 |
| **历史证据** | `workflow-group/runs/**`、`10-openrig-deepseek/var/openrig-archive/**` | 某次运行的可追溯记录 | 当前规则、当前架构 |

**一句话判据**：*能改变代码行为的只有源码；能改变验收的只有控制面；其余都是解释层。*

两份本地地图：源码仓 [DOCS-MAP.md](../../../../deepseek-项目/10-openrig-deepseek/DOCS-MAP.md)、usage 仓 [DOCS-MAP.md](../../../../openrig-custom-complete-usage/DOCS-MAP.md)。

## 2. 我想做什么 → 去哪里读

| # | 我想做什么 | 先读 | 再读（按需） | 不要从这里开始 |
| --- | --- | --- | --- | --- |
| R01 | 第一次安装、跑起来 | [源码 getting-started](../../../../deepseek-项目/10-openrig-deepseek/docs/reference/getting-started.md) | [help](../../../../deepseek-项目/10-openrig-deepseek/docs/reference/help.md) | `packages/cli/README.md` |
| R02 | 装好后跟操作员对话、开团队 | [getting-started §open-kernel](../../../../deepseek-项目/10-openrig-deepseek/docs/reference/getting-started.md) | `rig context get help` | 历史 run 的启动记录 |
| R03 | 改某个源码模块 | [as-built 索引](../../../../deepseek-项目/10-openrig-deepseek/docs/as-built/README.md) | `docs/as-built/architecture/<module>.md` | `docs/releases/v0.1.x.md` |
| R04 | 查某个命令/字段/配置的权威定义 | 源码 `docs/reference/`（按主题） | `rig <cmd> --help`（最当前） | usage 仓的示例代码 |
| R05 | 复用一次多轮工作流 | [workflow-group README](../../README.md) | [WORKFLOW.md](../../WORKFLOW.md) | `runs/<old>/PROJECT.md` |
| R06 | 新开一个 run | [PREFLIGHT](../../templates/specialized/openrig-workflow-master/PREFLIGHT.md) | [ENTRYPOINTS](../../templates/specialized/openrig-workflow-master/ENTRYPOINTS.md) | `runs/` 里的旧实例 |
| R07 | 做双平面编排（控制面 + 执行面） | 母版 [SPEC](../../templates/specialized/openrig-workflow-master/SPEC.md) + [ARCHITECTURE](../../templates/specialized/openrig-workflow-master/ARCHITECTURE.md) | ENTRYPOINTS §2/§3 | 把 queue 正文当计划 |
| R08 | 在项目里接 OpenRig | [usage DOCS-MAP](../../../../openrig-custom-complete-usage/DOCS-MAP.md) | [OPENRIG-WORKFLOW-GUIDE](../../../../openrig-custom-complete-usage/docs/OPENRIG-WORKFLOW-GUIDE.md) | 源码 `ARCHITECTURE.md` |
| R09 | 排查 LLM 误读 / 内存安全 | [LLM-MISREAD-QUICKREF](../../../../openrig-custom-complete-usage/docs/LLM-MISREAD-QUICKREF.md) | [MEMORY-SAFETY](../../../../openrig-custom-complete-usage/docs/MEMORY-SAFETY.md) | `process/STORY.md` |
| R10 | 发布 / 版本事实 | 源码 `docs/releases/README.md` | `CHANGELOG.md`（历史条目只读）、usage `docs/VERSIONING.md` | 根 `README.md` 的安装段 |
| R11 | 给 agent 装"开发 OpenRig"技能 | 源码 `.agents/skills/developing-openrig/SKILL.md` | 同内容 `.claude/skills/developing-openrig/SKILL.md` | 根 `skills/`（运行期技能套件） |
| R12 | 看某次 run 怎么翻车/怎么修 | [runs/](../../runs/)（按 run-id 进） | 蒸馏案例：[04 多仓文档治理](../../../../openrig-custom-complete-usage/docs/cases/04-multi-repo-docs-governance.md)、[05 返工/微工作流](../../../../openrig-custom-complete-usage/docs/cases/05-openrig-rework-loops.md)；本仓 `docs/cases/` | 把复盘当现行规范 |
| R13 | 查归档证据 / 收口材料 | `var/openrig-archive/MANDATORY.md` | `ARCHIVE-DECISIONS.md` | 把归档规则当运行规则 |
| R14 | 贡献 / 跟进上游 | 源码 `CONTRIBUTING.md` | `UPSTREAM-BASE`、`docs/reference/fork-and-upstream.md` | `packages/cli/README.md` |
| R15 | 做 SCTG 评测 | `SCTG-public` 稳定 kit | usage `sctg-kit/`、`workflow-group/drafts/sctg/`（**草案**） | 把 `drafts/sctg/` 当产品文档 |
| R16 | 跑文档一致性检查 | 本仓 `python3 scripts/doc_consistency.py --check` | 源码 `node scripts/check-docs-guard.mjs` + `check-docs-facts.mjs`；usage `make doc` | 用本仓检查器冒充链接检查 |

## 3. 正确位置 vs 常见错位

| # | 症状 | 正确位置 | 常见错位 | 为什么会被误入 |
| --- | --- | --- | --- | --- |
| X01 | "我在仓库里找 README 当项目入口" | 源码根 `README.md` | `packages/cli/README.md` | 两者几乎相同：根 README 多出「本地私有 `openrig-local` 源码线 + 使用仓库地址 + 改道说明」三段；差异行数以 §7 命令的当前输出为准。 |
| X02 | "我要改参考文档" | `docs/reference/README.md` | `packages/cli/daemon/docs/reference/README.md` | 后者是发版暂存的**逐字节副本**，改它不会回流 |
| X03 | "我要看当前 Spec" | 母版 `SPEC.md` | `runs/<old>/SPEC.md` | `runs/` 下 **55 个 run 目录**（56 个条目，含 `runs/README.md`）；每个 run 都有与母版同构的 `PROJECT.md`/`SPEC.md`/`DECISIONS.md` |
| X04 | "我要看强制规则" | `WORKFLOW.md` / `PREFLIGHT.md` | `var/openrig-archive/MANDATORY.md` | "MANDATORY" 字样使其看起来像现行规则（实为 184 篇历史归档） |
| X05 | "我要看 SCTG 规范" | `SCTG-public` + usage `sctg-kit/` | `workflow-group/drafts/sctg/` | 26 篇草案与稳定 kit 同名词，草案未标注成熟度 |
| X06 | "reference 和 as-built 哪个是开发文档" | as-built 讲代码，reference 讲使用且随包 | 两套索引混用 | 都在 `docs/` 下；`as-built/architecture.md` 仍是可达的 superseded 页 |
| X07 | "我要照着 usage 改源码" | 源码 `docs/as-built/` | usage `docs/ARCHITECTURE.md` | usage 是 sanitized 示例仓，不含源码行为 |
| X08 | "KB 正式入口找不到 OpenRig" | 本文件 + `00-overview/task-router.md` 的 OpenRig 行（R3 落） | 只读 `task-router.md` 的旧行 | 旧行只导向 `workflow-group/README.md`；`grep -ci openrig` 在 R3 前为 0 / 0、R3 后有 2 / 0（新增的两处即本 run 追加的路由行与 related-question）。复跑：`grep -ci openrig ../../00-overview/task-router.md ../../README.md` |
| X09 | "照抄母版里的票规则路径" | 本机 `deepseek-项目/.ticket-store/` | `ENTRYPOINTS.md` 的 `/home/dev/Desktop/...` | 母版来自另一台机器，其中 `/home/dev` 前缀指向那台机器的布局（本机等价根是 `$DS_ROOT`，见本节末复跑命令）；D-026 终态为 **12 处变量化 + 1 处保留**（示例树，带文内注解），`grep -c '/home/dev'` = **1**、`grep -c 'DS_ROOT'` = **13** |
| X10 | "改 usage 索引就行" | `docs/INDEX.md` + 对应 `*.zh-CN.md` | 只改英文 | `make doc` 检查索引覆盖、中英配对、脚本路径、机制事实 |

## 4. 命名 / 版本 / 证据规则

1. **地址优先**：给 agent 的指路必须是仓内相对路径或 `rig` 命令；禁止跨机绝对路径（`/home/dev/...`）。
2. **名字不是权威**：`组织部 = 总指挥部`；两个 `doc_consistency.py` **同名不同语义**（本仓查模板/注册表/§引用，**不查链接**；usage 仓还查 INDEX 覆盖/中英配对/脚本路径/机制事实）。
3. **状态必须随引用一起复制**：`as-built` 有 `last-verified-against-source`，`reference` 有 Status legend；只抄结论不抄状态会制造过期断言。
4. **证据三件套**：queue packet id、可复跑命令 + **无管道退出码**、文件 sha256。`cmd | tail` 后的 `$?` 是假绿。
5. **不得互相冒充**：reference ≠ as-built ≠ usage ≠ 控制面；引用任何一层都要写明层级。

## 5. 文档治理流程

```text
盘点(00-sources) → 路由(01-map) → 校对(02-changes) → 链接检查(03-verification) → QA 独立核查 → 收口(DECISIONS/STATUS)
```

- 每步产出一个报告文件，报告之间用路径互引，不复制正文；
- 链接检查逐仓用**该仓原生命令**，KB 侧"0 破链"由 run 内只读解析器证明；
- QA FAIL 只回退到紧邻 TDO 步，回退必须带"具体文件 + 缺什么 + 复跑命令"；
- 写权限按阶段互斥（P-A 控制面 / P-B 项目仓 / P-C 本轮报告），跨阶段先写证据段再开关。

## 6. 三图互链

| 图 | 位置 | 受众 |
| --- | --- | --- |
| 跨仓总图（本文件） | `workflow-group/docs/openrig/README.md` | 所有 agent 的起点 |
| 源码仓本地图 | [DOCS-MAP.md](../../../../deepseek-项目/10-openrig-deepseek/DOCS-MAP.md) | 改代码/读 as-built 的 agent |
| usage 仓本地图 | [DOCS-MAP.md](../../../../openrig-custom-complete-usage/DOCS-MAP.md) | 用 OpenRig/查误读的 agent |

> **usage 仓为公开仓，不得嵌入私有仓路径**，故 usage→本图改为按名引用（“由团队内部 KB 维护”），不提供路径链接；本图→usage、本图↔源码、源码→usage 仍为真链接。

> 维护规则：任何一图新增/移动入口，必须同一步更新另外两图的链接；三图互链用相对路径——**usage→私有仓方向除外，按名引用**；改完对可解析的边逐条 `test -e` 验证，对按名引用的边验证其文字仍在。

## 7. 本页数字的复跑命令

> 在 `deepseek-知识库/workflow-group/` 下执行。命令放在围栏块里而不是表格里：表格单元格中的 `|` 会被 GFM 当成列分隔，复制出来是残命令。

```bash
# 55 个 run 目录
ls -d runs/*/ | wc -l

# 56 个条目（55 个目录 + 1 个 runs/README.md）= 目录数 + 文件数
ls -1 runs | wc -l

# 1 处 /home/dev（示例树，带文内注解）；DS_ROOT = 13（1 声明 + 12 使用）
grep -c '/home/dev' templates/specialized/openrig-workflow-master/ENTRYPOINTS.md   # 期望 1
grep -c 'DS_ROOT'   templates/specialized/openrig-workflow-master/ENTRYPOINTS.md   # 期望 13

# 184 篇归档
find ../../deepseek-项目/10-openrig-deepseek/var/openrig-archive -name '*.md' | wc -l

# 26 篇 SCTG 草案
find drafts/sctg -name '*.md' | wc -l

# 根 README 与包内 README 的差异行数（2026-11-15T12:34:44Z 实测 5 行）
# 该数随两文件变动而变，以本行命令的当前输出为准
diff ../../deepseek-项目/10-openrig-deepseek/README.md \
     ../../deepseek-项目/10-openrig-deepseek/packages/cli/README.md | wc -l

# reference 随包、其余不随包
grep -n 'docs/reference' ../../deepseek-项目/10-openrig-deepseek/scripts/build-package.sh   # 133-136
ls ../../deepseek-项目/10-openrig-deepseek/packages/cli/daemon/docs                      # 只有 reference
```
