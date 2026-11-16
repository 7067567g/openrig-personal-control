# SPEC — 月月bot 微信桥单用户可靠性专项治理

## 0. 分层声明

baseline: composite/fix-wave@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

## 1. 前提与边界

本 run 的前提是：

- 微信桥固定服务单个 owner，本机可信；
- 多用户 ACL、跨用户隔离、鉴权/审批/审计、路径安全沙箱、远程攻击面加固 **不在本轮范围**；
- 任何治理动作不得降低日常操作便利性：不新增用户必须执行的确认步骤，不改变现有命令入口，不引入周期性系统消息，不改动对话风格；
- 允许为验证而重启本机 `dsh-web` / `dsh-weixin`，但必须先快照、后变更、再恢复；
- 不得删除用户对话、记忆、媒体、归档；清理只针对日志/构建缓存/可再生成的临时产物；
- 不得执行 `git push`，不得改知识库 canonical 母版；项目不是 git 仓库时以快照 + sha256 清单为准。

## 2. 一句话目标

在不牺牲单用户日常使用便利性的前提下，把微信桥从“正常文字聊天可用”提升为“运行态可控、消息不丢不重、媒体不覆盖、超时可收尾、日志与存储有界、版本与文档可维护”的稳定形态，并留下可复跑的验收证据。

## 3. 成功判据（全部满足才算 DONE）

### G1 运行态

1. `dsh-web.service` 与 `dsh-weixin.service` 均由 systemd 管理，3080 只有一个监听者；`dsh-web` 不再持续 `NRestarts` 增长，`StartLimitBurst` 生效。
2. 桥的单实例锁 owner 与 `dsh-weixin` MainPID 一致；控制面 `wxctl ping` 成功。
3. 重启后桥能重新加载 15 个 session 映射（数量以实际为准），`check:preset` 通过。

### G2 消息可靠性

4. 入站消息处理链路有持久化确认语义：任务成功入队或明确失败前不推进游标；桥正常退出等待 route 链收尾。
5. 对重复 `message_id`/同一游标重放有去重；不因一次崩溃丢消息或重复执行副作用。
6. 前台/后台任务在重启恢复时不会把活跃队列项静默丢弃。

### G3 数据完整性

7. 多图/同名文件接收使用唯一路径，不互相覆盖；一次 N 张图最终 N 个文件。
8. `outbox` 文件名含 taskId/短哈希，同标题同分钟不覆盖。
9. `TaskStore` 只裁剪终态历史，queued/running 永不因 50 条上限消失。
10. `web-sessions.json` 损坏时只读保护并明确告警，不被后续写入覆盖。
11. 中文 stdout/stderr 分块解码不产生乱码。
12. headless 后端对图片任务要么正确传图，要么明确回执“当前后端不支持看图”，不得声称图片已作为附件。
13. 所有敏感 JSON/状态写入使用原子写；进程崩溃不产生半写文件。

### G4 控制语义

14. 任务超时/取消后主动 cancel 对应 DSH 会话，下一次任务不因 `session-busy` 无谓失败。
15. `steer`/`cancel` 收到 `{ok:false}` 时如实回报失败，不显示“已并进/已停”。

### G5 资源与运维

16. `service.log`、`web-3080.log`、`control.log` 有轮转或大小上限；日志不含可复用的二维码/token 明文。
17. 媒体/outbox 有保留策略；日志/媒体/outbox 不再无限增长。
18. 建立每日自动备份（`~/.dsh/clawbot-bridge` + `memory/`），至少保留 7 份，且有一次恢复演练证据。
19. 媒体下载和子进程输出有超时/上限，不因单条消息或长任务无限吃内存。

### G6 工程化

20. 版本号单一来源：`package.json` 为唯一版本源；README/CLI/CORE VERSION 不再出现互相矛盾的 5 套版本号。
21. 用户可见菜单/帮助、`CAPABILITIES.md`、`SELF.md`、`README-v3.md` 对“助理能做什么”的描述一致。
22. 项目纳入 git（或至少建立可回滚快照 + 明确变更清单），清理 `.bak-*`/`.before-*`/构建缓存，`npm pack` 不再包含 `vendor/**/.build` 与历史备份。
23. 增加最小 CI/本地一键门禁：Node 测试、Python 测试、命令漂移、preset 检查；`test:loop` 不再指向不存在文件。

### G7 验收

24. 现有 156 个 Node 用例 + 4 个 Python 用例全部通过。
25. 新增回归测试覆盖本 SPEC 的 G2–G4 每一项；每个缺陷至少有一个“修复前失败/修复后通过”的证据。
26. 完成一次单用户真实链路 E2E：文字、多图、文件、超时取消、重启恢复、状态/最近/回忆、长回复文件交付。
27. 完成一次短 soak（≥ 2 小时或 ≥ 30 轮）并记录 0 丢失、0 重复执行、无明显内存增长。
28. 输出 `reports/FINAL.md`，逐条映射 G1–G7 到证据路径与命令输出。

## 4. 工作流分片

| WS | 名称 | 写权限 | 主要产出 |
| --- | --- | --- | --- |
| WS-0 | 基线与快照 | `governance-20261110/**`、快照目录 | `BASELINE-pre.sha256`、staging 副本、回滚脚本 |
| WS-1 | 运行态治理 | `~/.config/systemd/user/*`、部署脚本、`governance-20261110/evidence/ws1/**` | systemd 修复、3080 单实例证据、重启验证 |
| WS-2 | 消息可靠性 | staging 副本 `lib/task-store.mjs`、`lib/archive.mjs`、`weixin-bot.mjs`、`test/*` | 游标/去重/drain 实现 + 回归测试 |
| WS-3 | 数据完整性 | staging 副本 `lib/ilink-media.mjs`、`lib/deliver.mjs`、`lib/core.mjs`、`lib/web-sessions.mjs`、`test/*` | 唯一命名、outbox、headless 图片、UTF-8、原子写 |
| WS-4 | 控制语义 | staging 副本 `lib/task-runner.mjs`、`lib/web-backend.mjs`、`test/*` | 超时 cancel、steer/cancel 结果校验 |
| WS-5 | 资源与运维 | 运维脚本、systemd 日志配置、备份脚本、`governance-20261110/**` | 轮转/保留/备份/恢复演练/流式上限 |
| WS-6 | 工程化 | `package.json`、README/docs、`.gitignore`、CI、打包配置 | 版本单一来源、文档一致、git/CI、包瘦身 |
| WS-7 | 独立验收 | `governance-20261110/reports/**`、`evidence/ws7/**` | 独立复跑、反例、soak、FINAL 映射 |
| WS-8 | 主控收口 | `governance-20261110/STATE.md`、`reports/FINAL.md` | 轮次推进、阻塞登记、最终 DONE/BLOCKED |

同一时刻每个文件只能有一个写者；WS-2/3/4 先改 staging 副本，WS-7 通过后才允许 WS-8 应用到 live。

## 5. 完整缺陷票清单

| ID | 级别 | 缺陷 | 验收 |
| --- | --- | --- | --- |
| YY-001 | P0 | `dsh-web` 3080 EADDRINUSE 无限重启，手工进程占用端口 | 单监听、NRestarts 不增长、systemd 健康 |
| YY-002 | P0 | 部署双份/入口不一致，`run-service.sh` 与仓库脚本漂移 | 单一启动入口，sha256 对比通过 |
| YY-003 | P1 | 消息游标先落盘后处理，崩溃漏消息 | 收件持久队列 + 确认后推进游标 |
| YY-004 | P1 | 无 messageId 去重，重放会重复执行 | 重放测试 0 重复 |
| YY-005 | P1 | 退出不等待 routeChains | drain 测试通过 |
| YY-006 | P1 | TaskStore 50 条上限静默丢活跃任务 | 55 条入队不丢 queued/running |
| YY-007 | P1 | 多图/同名文件接收路径碰撞 | 12 张图 = 12 个唯一文件 |
| YY-008 | P1 | outbox 同标题同分钟覆盖 | 两次同名任务产出两个文件 |
| YY-009 | P1 | headless 丢弃 imagePaths | 带图任务有路径或明确 unsupported |
| YY-010 | P1 | 超时后不 cancel DSH 会话 | 超时后 wait_idle 通过 |
| YY-011 | P1 | steer/cancel 的 `{ok:false}` 被当成功 | 失败回执正确 |
| YY-012 | P1 | UTF-8 分块解码损坏 | 分块中文测试通过 |
| YY-013 | P1 | web-sessions 损坏后被覆盖 | 损坏文件保持原字节 |
| YY-014 | P1 | 敏感/状态文件非原子写 | 崩溃注入后文件可解析 |
| YY-015 | P2 | CDN 下载无超时、整文件入内存 | 超时/流式上限测试 |
| YY-016 | P2 | 子进程 stdout/stderr 无上限 | 输出上限/尾部保留 |
| YY-017 | P2 | 日志无轮转 | 轮转后旧日志归档 |
| YY-018 | P2 | 媒体/outbox 无保留策略 | 超期清理且不删对话归档 |
| YY-019 | P2 | 无自动备份/恢复演练 | 备份存在 + 恢复演练通过 |
| YY-020 | P2 | 版本号 5 套并存 | 单一来源 + 校验脚本 |
| YY-021 | P2 | 菜单/帮助/文档能力描述矛盾 | 一致性检查通过 |
| YY-022 | P2 | 46 个备份文件、61MB .build 进包 | 包体 ≤10MB，无 .build/.bak |
| YY-023 | P2 | `test:loop` 指向不存在文件 | 命令可运行或删除 |
| YY-024 | P2 | 稳定 client_id 缺失，重试可能重复发 | 发送重试幂等测试 |
| YY-025 | P3 | typing releaseAll 引用计数不清零 | 退出后无 typing interval |
| YY-026 | P3 | local-io 出站媒体可能走真实发送（若使用 local-io） | local-io 媒体测试不调用真实 sendMedia |

## 6. 多轮心跳执行协议

本 run 由 OpenRig 单 seat 持续执行，不依赖主会话：

1. 每轮开始读 `governance-20261110/STATE.md`，只做 `next` 指向的未完成票。
2. 每完成一项：写 `evidence/<ticket>/`（命令、输出尾部、sha256、失败/通过对照），更新 `STATE.md` 的 completed/next/lastHeartbeat。
3. 每轮结束必须留下可复跑命令；不得只写“已完成”。
4. 心跳由 OpenRig watchdog `periodic-reminder` 每 600 秒唤醒；收到 `HEARTBEAT` 后继续 `STATE.md` 的 next。
5. 全部 G1–G7 满足 → 写 `DONE`（含 FINAL 路径）并停止 watchdog。
6. 只有遇到不可自行解决的硬外部依赖才写 `BLOCKED`（原因、已尝试、需要什么），不要用“需要确认”作为默认阻塞。
7. 不重复执行已完成票；若发现已完成项有回归，开 `REGRESS-<id>` 并优先修复。

## 7. 证据格式

每个票目录至少包含：

```text
evidence/<YY-ID>/
  before.txt        # 修复前失败命令 + 输出
  after.txt         # 修复后通过命令 + 输出
  diff.md           # 变更文件清单 + 摘要
  sha256.txt        # 关键产物 hash
```

`reports/FINAL.md` 必须有一张 G1–G7 × 证据路径 × 验收命令的映射表。

## 8. 禁止项

- 不做多用户 ACL、审批流、路径安全沙箱、远程鉴权加固；
- 不新增用户必须执行的命令/确认；
- 不删除对话、记忆、媒体、归档；
- 不改写人设/对话风格；
- 不 `git push`、不 `rm -rf` 用户数据、不覆盖唯一备份；
- 不为让测试变绿而删测试或降低断言；
- 不把“服务重启成功”当作“治理完成”。

## 9. DoD

- G1–G7 全绿；
- `reports/FINAL.md` 存在且映射完整；
- `DONE` 存在且 `STATE.md` 的 completed 数 = 票总数；
- 无 open S1/S2 issue。
