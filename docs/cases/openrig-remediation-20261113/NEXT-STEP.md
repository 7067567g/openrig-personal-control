# Next step

交给执行智能体时，第一句话：

```text
先完整阅读 docs/cases/openrig-remediation-20261113/REMEDIATION-PLAN.md。
从 R0 冻结与基线开始，不要先跑任何产品轮。
每完成一个 R 阶段，写证据并跑该阶段验收；未通过不得进入下一阶段。
```

执行顺序：

```text
R0 冻结/基线
R1 状态对账
R2 30 轮重新分类
R3 Driver 原子化/恢复
R4 行为级验收
R5 独立 QA
R6 Telemetry
R7 外部 Android 隔离
R8 安全脱敏
R9 Git/CI
R10 恢复 30 轮
```

禁止：

```text
- 先跑一轮看看
- git add -A 盲提交
- 把 NEED_MAIN 当 PASS
- 把 token 检查当行为验收
- 临时插入轮次不走变更单
- 把真实设备 IP/token/截图/UI dump/logcat 写进仓库
```
