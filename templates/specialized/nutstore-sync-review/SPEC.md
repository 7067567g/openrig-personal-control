# SPEC — obsidian-nutstore-sync 个人版全盘审查与修订（P6）

## 0. 分层声明

baseline: composite/fix-wave@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

> 特化规则，优先于通用手册。目标仓库：`/home/dev/Desktop/deepseek/20-工作区/obsidian-nutstore-sync`
> 背景：个人改动版（分支 `personal/phone-ai-tools`，tag `personal-20260911`，上游 79d35b4）**bug 很多**，需要一轮全盘审查 + 修订。

## 1. 任务

1. **逐文件审查**全部 426 个 `src/**/*.ts(x)`：每个文件给出结论（有 bug / 无 bug / 待确认+原因）；
2. **可复现 bug 优先修**：每个 bug 必须有复现方式（测试、命令或最小步骤）与严重度；
3. **补测试**：修掉的 bug 必须留下能防回归的测试；无测试覆盖的关键路径补最小单测；
4. **门禁**：`pnpm test:unit`、`pnpm lint`（eslint+tsc）、`pnpm build` 全绿；`pnpm test:models-api` 按情况跑；
5. 产出 `runs/<RUN-ID>/reports/ws*-bugs.md` 与 `reports/final.md`（含统计与未决项）。

## 2. 前置

```bash
cd /home/dev/Desktop/deepseek/20-工作区/obsidian-nutstore-sync
node scripts/bootstrap-deps.mjs        # 专用依赖安装（.npmrc 说明：直接 pnpm install 会 401）
```

- 仓库是独立 git（分支 `personal/phone-ai-tools`）；**只提交、不 push**；
- 已知未跟踪文件 `src/utils/filter-rules.test.ts`：归 WS-4 判断去留（有效则修好并提交，无效则说明理由）。

## 3. 写权限分区（一 WS 一目录，文件边界互斥）

| WS | 写权限（仓库内相对路径） | 文件数 |
| --- | --- | --- |
| WS-1 | `src/ai/chat/**` | 81 |
| WS-2 | `src/ai/tools/**`、`src/ai/skills/**` | 56 |
| WS-3 | `src/ai/providers/**`、`src/ai/core/**`、`src/ai/transport/**`、`src/ai/mcp/**`、`src/ai/catalog/**`、`src/ai/*.ts` | ≈29 |
| WS-4 | `src/utils/**`（含未跟踪的 filter-rules.test.ts） | 77 |
| WS-5 | `src/sync/**`、`src/fs/**` | 43 |
| WS-6 | `src/components/**`、`src/views/**`、`src/settings/**`、`src/i18n/**` | ≈79 |
| WS-7 | `src/services/**`、`src/storage/**`、`src/api/**`、`src/model/**`、`src/types/**`、`src/shims/**`、`src/events/**`、`src/diagnostics/**` | ≈56 |
| WS-8（R2） | `scripts/**`、`*.config.*`、`main.js`、`dist/**`、`manifest.json` | 构建/回归 |

`LICENSE`、`PERSONAL_REVISION.md`、`.github/**` 只读；改 `manifest.json` 仅限明确不一致的字段。

## 4. 全内容与证据

- 426/426 文件必须有结论；允许按文件清单分批，但不许抽样；
- 每个 bug：现象 / 复现（命令或测试）/ 根因 / 修复 / 验证 五要素；
- 修复必须附命令输出（如 `pnpm test:unit` 对应用例、`tsc` 摘要）；
- 无法复现或需真机（Obsidian/手机）的，写 `待确认 + 缺什么`，不要硬改。

## 5. 禁止

- 不 push；不改分支/tag；不删除现有文件；不改 LICENSE 与个人版声明正文；
- 不新增运行时依赖（确需新增 → 记 ISSUES 并跳过该修复）；
- 不伪造测试/构建通过；`test:obsidian` 需要 Obsidian 环境，跑不了就记 SKIP + 原因。

## 6. DoD

- 426/426 逐文件结论表；
- bug 清单（含复现与严重度）+ 已修清单（含回归测试）；
- `pnpm test:unit` / `pnpm lint` / `pnpm build` 全绿（或对不可得项有 SKIP 说明）；
- `.prettierrc`/eslint 通过；`reports/final.md`；
- ISSUES 无 open S1/S2；项目仓每轮由主会话 `wf.py commit` 提交（不 push）。
