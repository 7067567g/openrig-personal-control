# SPEC — OpenRig 调整后全量检查（README-first / evidence-first）

## 0. 分层声明

baseline: none — 直接原子组合
contracts: verify@1.0.0, audit@1.0.0

> 本文件是本 run 的特化规则，优先于通用 WORKFLOW/roles 中冲突的部分。
> 本 run 是**检查 run**：默认不改源码；发现问题只登记 ISSUE，修复需主会话另拍 D-xxx。

## 1. 任务

对已完成 OpenCode + DSH 特化的 OpenRig 自有副本做一次全量检查。检查内容由本工作流自行安排，至少覆盖：

1. **仓库完整性**：分支、提交、工作区干净；外部只读 clone 未改。
2. **静态质量**：全 workspace build、lint/typecheck、docs guard、context pack/skills mirror 检查。
3. **仓库级测试**：`npm run test:repo`、`npm run test:workspaces` 或等价串行执行。
4. **全 workspace 测试**：daemon / cli / tui / ui 四个包全部跑；不能只跑定向。
5. **特性回归**：OpenCode/DSH runner 协议、输入聚合、readiness、resume token、native skill path、workflow harness。
6. **真实 E2E**：隔离 `OPENRIG_HOME` 启动 daemon + `opencode-dsh` 5-seat rig；验证 all ready、无启动模型调用、OpenCode/DSH 真实任务、多行 envelope、同 runner 续会话。
7. **跨重启**：`rig down` 后捕获 resume metadata，`rig up --existing` 两 TDO resumed，后续任务保持同一 session id。
8. **Workflow/spec**：workflow validate + instantiate/compile（能实例化时）；rig spec `--plan`；内置 spec 可见。
9. **安全与卫生**：检查 changed diff 是否含凭证明文/泄露；检查无关进程、daemon、tmux、临时 home 是否清理；生成 AGENTS.md 不留在仓库。
10. **报告**：每条 PASS/WARN/FAIL/SKIP 带命令、退出码/超时、证据路径；FAIL 必须命名阻塞面。

## 2. 范围与写权限

| 路径 | 权限 | 用途 |
| --- | --- | --- |
| `workflow-group/templates/specialized/openrig-full-verify/**` | 可写 | 本特化模板 |
| `workflow-group/kickoff/openrig-full-verify*` | 可写 | 启动目标 |
| `workflow-group/runs/<RUN-ID>/**` | 可写 | 四件套/报告/证据 |
| `/home/dev/Desktop/deepseek/deepseek-项目/10-openrig-deepseek/**` | **默认只读** | 被检查的 OpenRig 副本；检查不改源码 |
| `/home/dev/Desktop/deepseek/60-外部仓库/openrig/**` | **只读** | 上游参考 |
| `/tmp/openrig-full-verify-*` | 可写 | 隔离 daemon home、临时项目、日志 |
| 全局 OpenCode/DSH 配置与用户数据 | **只读** | 不写入，不清理 |

## 3. 执行纪律

- 先静态后动态，先单测后真实 E2E；重测试串行，不并行跑 daemon 测试与真实 rig。
- 真实 E2E 必须用隔离 `OPENRIG_HOME` 和独立端口；不得复用/杀掉用户已有 dsh web 或 OpenRig daemon。
- 所有模型 smoke 只用最小 prompt；不输出完整对话，不打印 API key/auth 内容。
- 使用绝对 Node24 路径：
  - `OPENRIG_OPENCODE_BIN=/home/dev/.nvm/versions/node/v24.18.0/bin/opencode`
  - `OPENRIG_DSH_BIN=/home/dev/.nvm/versions/node/v24.18.0/bin/dsh`
- npm 命令默认去掉代理变量；记录代理相关失败为 WARN，不混淆代码失败。
- 检查 run 默认不修代码；若必须修，先由主会话加 D-xxx，另开 fix 动作并重跑受影响检查。
- 测试日志重定向到 run 证据目录；终端只保留摘要。

## 4. 证据格式

```text
[PASS] <检查项> | cmd: <命令> | exit: <码> | evidence: <路径>
[WARN] <检查项> | cmd: <命令> | exit: <码/超时> | why: <影响> | evidence: <路径>
[FAIL] <检查项> | cmd: <命令> | exit: <码/超时> | blocker: <阻塞面> | evidence: <路径>
[SKIP] <检查项> | why: <原因> | 后续: <补测方式>
```

## 5. 完成定义

- 仓库/静态/构建/仓库级测试/四包测试全部有明确结果；
- 新特性定向测试有结果；
- 真实 5-seat E2E、OC/DSH task、envelope、同 runner 续会话、跨 rig 重启 resume 有结果；
- workflow validate/instantiate 或明确 SKIP 原因；
- 无未解释的 S1/S2；有 FAIL 则登记 ISSUE 并给下一步；
- 报告 `reports/FULL-CHECK.md` + 证据目录完整，`wf.py doctor` PASS。
