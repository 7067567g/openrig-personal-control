# SPEC — SignalDeck 实跑验证（P3，"还没试"补课）

## 0. 分层声明

baseline: none — 直接原子组合
contracts: verify@1.0.0

> 特化规则，优先于通用手册。SignalDeck 已做过全检，本 run 只回答一个问题：**它真的能跑吗？**

## 1. 任务

对 `/home/dev/Desktop/deepseek/deepseek-项目/10-signaldeck` 做**只读实跑验证**，产出可复现的运行结论：

1. 22 步门禁：`bash tests/run-linux.sh`（记录每步 PASS/FAIL/SKIP 与耗时）；
2. 前端：`cd src/frontend && npm run check && npm run build`（记录产物）；
3. 宿主：`cd src/desktop && npm run build:host` + host 冒烟（仓库自带 `_smoke_host` 入口按 README）；
4. 运行尝试：在无显示器环境下尽力启动（xvfb/headless 优先），给出"能跑到哪一步/卡在哪、缺什么"；
5. 交付包：核对 `交付包/SignalDeck-1.0.0-win-x64*` 内容与 README 声明的一致性。

## 2. 写权限

| 路径 | 用途 |
| --- | --- |
| `runs/<RUN-ID>/**` | 报告、日志、截图/输出（唯一可写） |
| 项目仓 `/home/dev/.../10-signaldeck/**` | **只读**；不得写入/提交 |

## 3. 证据

- 每条命令：完整命令 + 退出码 + 输出摘要（前 20 行/关键行）；
- 失败项：最小复现步骤 + 结论（环境缺什么 / 代码问题）；
- 能跑通的项：必须给可复跑命令，不接受"看起来正常"。

## 4. 禁止

- 不改项目仓、不安装重型依赖（可 `npm ci` 已有锁文件；装新包需记 ISSUES 并跳过）；
- 不伪造 PASS；环境不可得的项写 `SKIP + 原因`；
- 不 push。

## 5. DoD

- 22 步门禁结果表（PASS/FAIL/SKIP + 耗时 + 证据）；
- 前端/宿主构建结果；
- 运行尝试的最终结论（能跑到哪、卡在哪、下一步需要什么）；
- `reports/runtime-verify.md` 汇总 + ISSUES 登记。
