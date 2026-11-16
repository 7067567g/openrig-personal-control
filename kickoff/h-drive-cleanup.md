# H 盘专项整理 · 启动文档（P0 安全预检版）

> 目标：对用户确认的 H 盘范围做只读全量盘点、可回滚隔离、逐条安全门控与独立复核。
> 本启动包默认**不执行任何 H 盘写操作**；P0 预检、用户确认范围、门控初始化完成后才进入 P1 只读盘点。
> 当前环境若没有可访问的 H 盘挂载点，必须停在 P0 并回执 BLOCKED，不得猜路径/自动 mount/用临时目录冒充 H 盘。
> **H 盘只在 Windows 侧可见时，先读 `kickoff/h-drive-windows-plan.md`**：Windows 侧走 PowerShell move-only 门控，不直接套用 POSIX 版 `hdrive_gate.py`。

## 1. 粘给新会话的提示词

```text
你是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group
先读：README.md、WORKFLOW.md、roles/MAIN.md、roles/SAFETY.md、
      kickoff/h-drive-cleanup.md、templates/specialized/h-drive-cleanup/SPEC.md
任务：为用户确认的 H 盘范围建立专项整理 run。
硬规则：
1) 先只做 P0 预检 + 用户范围确认，不执行任何 H 盘写操作；
2) 所有 H 盘写动作必须经 scripts/hdrive_gate.py；门控 FAIL 的 action 必须由独立 SAFETY 逐条审核；
3) red 动作还需要独立人工 human-approve；禁止批量/自审/代签/先跑后补；
4) 默认只隔离、不 purge；隔离区、保留期、是否 purge 必须由用户写入 DECISIONS；
5) 不得猜 H 盘路径。若 H 盘未挂载/范围不明/隔离区未定，写 BLOCKED 并等用户。
完成 P1 只读盘点与 P2 计划后停止，等用户确认，不得自行进入执行。
```

## 2. P0 预检（先跑，失败即停）

```bash
# 当前门控执行器按 POSIX 路径校验；WSL 示例：
test -d /mnt/h && findmnt -T /mnt/h
```

- 若命令失败 / 没有挂载点：不要继续建 action，不要创建隔离区，不要用其他盘代替；回执“H 盘未挂载，等待用户”。
- 用户必须明确给出：
  - H 盘根（挂载后的 POSIX 路径；当前执行器不接受 `H:\` 原生盘符）；
  - 第一轮范围（至少一个目录，禁止默认全盘）；
  - 隔离区路径（H 盘根内，不能等于根）；
  - 保留期；
  - 是否允许 purge（默认不）；
  - SAFETY 与人工批准人（独立身份）。

## 3. 建档与 P1（只读）

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group

python3 scripts/wf.py new-run h-drive-cleanup-YYYYMMDD \
  --template templates/specialized/h-drive-cleanup \
  --goal-file kickoff/h-drive-cleanup-goal.txt \
  --project-root /mnt/h \
  --scope "runs/<run-id>/** + 经 hdrive_gate.py 放行的 H 盘动作" \
  --tdo 1

# 主会话先把用户确认结果写入 DECISIONS.md 的 D-002–D-006
# 再初始化门控（用户名、路径、隔离区按实际替换）
python3 scripts/hdrive_gate.py init --run h-drive-cleanup-YYYYMMDD \
  --root /mnt/h --quarantine-root /mnt/h/_整理隔离区 \
  --safety-reviewer safety-a1 --human-approver user

python3 scripts/wf.py brief --role pmo --run h-drive-cleanup-YYYYMMDD
```

P1 只做只读盘点，产物写 run 目录；**不要 propose 写 action，不要 execute**。

## 4. P2/P3 才进入写动作

```bash
# P2：逐项处置计划 → actions.jsonl → 门控
python3 scripts/hdrive_gate.py propose --run <run-id> --file actions.jsonl --agent tdo-a1
python3 scripts/hdrive_gate.py gate --run <run-id>
python3 scripts/hdrive_gate.py status --run <run-id> --json

# P3：FAIL 逐条审核；red 再加人工批准
python3 scripts/hdrive_gate.py review --run <run-id> --action ACT-0001 \
  --reviewer safety-a1 --verdict approve|reject --digest <digest> \
  --reason "逐条依据" --evidence "reports/...."
python3 scripts/hdrive_gate.py human-approve --run <run-id> --action ACT-0001 \
  --approver user --digest <digest> --reason "业务必要性/保留期确认"

# P4：一次执行一条；失败即停
python3 scripts/hdrive_gate.py run --run <run-id> --action ACT-0001 --agent tdo-a1
```

## 5. 关键坑

- `H:\` 不能直接当 WSL/执行器路径；先确认 `/mnt/h` 或用户实际 POSIX 挂载路径。路径不对就停，不要猜。
- `test -d` 成功不等于已挂载；必须 `findmnt -T` 看到挂载点。
- `quarantine` 目标必须在隔离区内且不存在；隔离区存在性、父目录、空间在执行前都会重新检查。
- `exec` 是受控例外，不是通用后门；解释器/破坏性命令永久不可执行，且必须有 dry-run 证据/回滚方案 + 安全审核 + 人工批准。
- 任何 action 原文改动都会使 digest 失效；不要手改 JSON，要重新 propose 新 action。
- 默认不 purge；purge 只在隔离区、保留期、用户明确确认后逐条双批。
