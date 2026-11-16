# OpenRig 本地工作流重整 · 启动提示词

> 用法：把本文件 + `openrig-local-refit-goal.txt` 交给主会话/PMO。  
> 本工作流不接入 OpenRig 自身；OpenRig 只是被调查和被重整的源码。

## 主会话启动

```bash
cd workflow-group
python3 scripts/wf.py new-run openrig-local-refit-20261018 \
  --template templates/specialized/openrig-local-refit \
  --goal-file kickoff/openrig-local-refit-goal.txt \
  --tdo 1

python3 scripts/wf.py doctor openrig-local-refit-20261018
```

## PMO 首轮重点

1. 先读 `SPEC.md`，确认写权限与“不启动 OpenRig”的硬边界。
2. 把环境探测拆成“静态存在性”与“真实可用性”两栏：
   - `command -v` / `--version` / `--help`；
   - `opencode auth list`、`opencode debug paths`；
   - `opencode models`、`opencode session list`、`opencode run` 的真实结果/超时/错误。
3. 记录默认代理与 `--noproxy '*'` 的差异；不要把代理导致的 TLS 失败误判为软件不可用。
4. OpenRig 盘点必须覆盖 `package.json` engines、runtime 列表、daemon/queue/workflow/topology/tests/UI/docs，不能只列 README。
5. 在 §6 给主会话一个明确结论：R2 是否 go、在哪个自有副本改、哪些删除/隐藏动作需要单独拍板。

## TDO 证据

- 环境报告：`runs/<run-id>/reports/env-probe.md`
- 原始命令输出：`runs/<run-id>/reports/evidence/env-*.txt`
- OpenRig 盘点：`runs/<run-id>/reports/openrig-inventory.md`
- 重整方案：`runs/<run-id>/reports/round2-refit-plan.md`

## 禁止

- `rig daemon start` / `rig up` / `rig workflow` 作为本 run 执行面；
- 修改 `60-外部仓库/openrig`；
- 把“安装成功”“--help 成功”“build 成功”写成“运行时可用”；
- 粘贴 API key、完整 auth.json、完整会话正文。
