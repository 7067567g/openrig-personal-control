# SPEC — 分发/同步/运维加固（P10）

## 0. 分层声明

baseline: composite/ops-hardening@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

> 特化规则，优先于通用手册。依据：C 侦察（2026-10-14）。
> 仓库：`/home/dev/Desktop/deepseek` 下多个目录，**部分无 git 版本控制**（根、50-记录等）——写前必须确认目标路径是否在版本控制内，未纳管的改动要留 run 报告清单。

## 1. R1（3 路并行）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-1 | `镜像维护.sh`、`镜像核查.sh`、根 `README.md §六`、`50-记录与维护/工作区维护/**`（除镜像日志历史本体）、新增 `tests/` | C1 镜像/日志治理：README 与脚本能力对齐（移除 `--apply` 漂移）；**镜像日志保留策略**（保留最近 N 次 + 其余 zstd 归档，5.3G→可控）；给 `classify()` 补 A→B/B→A/冲突 三文件夹具单测，`--check` rc=0/1 可断言。**验收：夹具测 rc；归档可解回原 self.tsv；`grep -- '--apply' 脚本+README` 归零** |
| WS-2 | `40-工具/deepseek-workspace/**`、`归档/<repo>-backup-YYYYMMDD/**`（新增 git bundle） | C3 多仓健康+灾备：`sync-all.sh` 升级为只读健康报告（remote 存在性/领先落后/dirty）；新增 `backup-all.sh` 用 `git bundle --all` 落归档；文档修正 remote 真值（交付物/快捷方式 remote=0、项目/KB ahead）。**验收：bundle 可 `git clone` 复验；对 remote 空+ahead>0 报 WARN；不 push** |
| WS-3 | `10-运行时/**-packages-frozen.txt`（只新增文件，不改 venv） | C7 运行时可复现：逐 venv 从 `site-packages/*.dist-info` 反推 frozen（name==version），产出 18 份 frozen + 漂移表 + 体积清单。**验收：18 份齐全；与历史 desktop-tools 清单逐行可复现；不改 venv** |

## 2. R2（1 路，单写者）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-4 | `30-分发与同步/packages/**`、`50-记录与维护/工作区维护/打包脚本_*.sh`、`50-记录与维护/工作区维护/打包备份记录_*.md` | C2 分发包重建+发布门禁：修复 v5 脚本为当前布局可复跑（参数化 CUR）；重打 KB/项目快照 + manifest + `.sha256` + `LATEST.json`；新增 packages 核查（zip 条目 ↔ manifest ↔ LATEST 三向一致）。**验收：`sha256sum -c` 全 OK；manifest file_count/字节与 zip 一致；篡改 1 字节/缺条目反例必须 FAIL；包内明确记录快照 HEAD hash** |

## 3. R3（可选，时间允许）

| WS | 写权限 | 任务 |
| --- | --- | --- |
| WS-5 | `链接核查.sh`、新增 `运维核查.sh`、`快捷方式/**` | C4 三查门禁化（链接/镜像/KB 一条命令，误报修复：URL 解码、代码块剔除）+ C6 快捷方式 apps.json 校验器（绝对路径/缺目标反例 FAIL），收口脏工作树 |

## 4. 禁止

- 不 push；不动 `归档/` 既有内容与任何 venv 内部；无版本控制的目录改动必须在 run 报告里列出文件与 diff 摘要；
- TDO 只改不提交，主会话每轮 `wf.py commit`（能提交的仓库才提交，根目录留报告）；白名单外只读。

## 5. DoD

- 镜像 `--check` 夹具 rc 可断言 + 日志体积下降且可解；bundle 可 clone；18 份 frozen；
- packages 三向一致 + 反例 FAIL + 记录 HEAD；`reports/final.md`；ISSUES 无 open S1/S2。
