# h-drive-cleanup — 使用说明

> 这是 H 盘专项整理的可实例化模板，不是已启动的 run。
> **双执行后端**：同一个安全模型，按目标环境的实际可访问方式选择一种，并在 `DECISIONS.md` 固定；不得混用路径语义。
>
> | 后端 | 根路径 | 执行器 | 支持 op | 适用 |
> | --- | --- | --- | --- | --- |
> | POSIX | `/mnt/h` 等真实挂载点 | `python3 scripts/hdrive_gate.py` | mkdir/copy/move/quarantine/purge/exec（默认只允许 move/mkdir） | H 盘已挂载到 WSL/Linux |
> | Windows | `H:\` 原生盘符 | `python3 scripts/windows/hgate.py` | 仅 mkdir/move | H 盘只在 Windows 可见，经 PowerShell 调用 |
>
> 默认安全姿态：move-only、不删除、保护清单只读、一次一个 action、独立 SAFETY 逐条审核、red 人工批准、失败即停。

## 实例化

### POSIX（H 盘挂载到 WSL）

```bash
cd workflow-group
python3 scripts/wf.py new-run h-drive-cleanup-YYYYMMDD \
  --template templates/specialized/h-drive-cleanup \
  --project-root /mnt/h \
  --scope "runs/<run-id>/** + 经 scripts/hdrive_gate.py 放行的 H 盘动作" \
  --goal "对用户指定 H 盘范围做只读盘点、可回滚隔离与审计；未通过门控的指令逐条安全审核" \
  --tdo 1
```

### Windows（原生盘符，经 WSL 包装 PowerShell）

```bash
cd workflow-group
python3 scripts/wf.py new-run h-drive-cleanup-YYYYMMDD \
  --template templates/specialized/h-drive-cleanup \
  --project-root 'H:\' \
  --scope "runs/<run-id>/** + 经 scripts/windows/hgate.py 放行的 H 盘 move/mkdir 动作" \
  --goal "对用户指定 H 盘范围做 move-only 盘点、归位与审计；未通过门控/SAFETY 的指令不执行" \
  --tdo 1
```

`--tdo` 先给 1：H 盘范围在盘点前未知，P4 执行分区只能在 P1 后按顶级目录拆分；不要提前并行写。

## 启动前必须完成（两种后端相同）

1. 用户确认 H 盘根在该后端下的真实路径；Windows 写 `H:\`，POSIX 写真实挂载点并验证 `findmnt -T`。
2. 用户给出第一轮明确范围（不允许默认整盘根目录）。
3. 用户确认收纳根/隔离区、保留期、是否允许 purge；Windows 默认无 purge 分支，删除候选只移动。
4. 指定独立 SAFETY（不得是 TDO/QA/人工批准人）与人工批准人。
5. 把后端、根、范围、隔离区/收纳根、保留期、人员写入 `DECISIONS.md`；实际运行副本的 `SPEC.md` 固定选用 §4.0 的哪一个后端。
6. 选定后端执行器 `init` 成功后才允许 P1 只读盘点。
7. P1/P2 主会话确认前，不创建写 action、不执行任何 `run`。
8. `safety/` 账本可能含真实路径/输出摘要；提交/推送前必须脱敏，敏感 run 只留本地。

## 文件

| 文件 | 作用 |
| --- | --- |
| `SPEC.md` | 特化规则：双后端选择、阶段、门控、独立 SAFETY、执行/核验/DoD |
| `PROJECT.md` | 预填目标判据、指标、WS 与 PMO 上报区 |
| `DECISIONS.md` | 预置安全相关待决项 D-001–D-006 |
| `actions.example.jsonl` | POSIX action 格式示例；Windows 只支持 mkdir/move，路径必须按实际重写 |

## 后端差异（必须显式）

- **路径**：POSIX 统一用挂载点路径；Windows 统一用 `H:\` 原生路径，经 `wslpath` 仅用于 run-root/保护清单等参数转换，不把 `H:\` 混进 POSIX action。
- **op**：Windows 只有 `mkdir/move`；删除候选一律 `move` 到待确认区，不存在 `purge/exec`。POSIX 可选 op 更多，但默认模板仍只建议 `move/mkdir`。
- **run-root**：POSIX 用 `--run <run-id>` 指向 `runs/<run-id>/`；Windows 用 `--run-root` 指向 Windows/PowerShell 可访问的 run 账本目录。
- **事实源**：实际 run 若选 Windows，run 内的 `WINDOWS-RUN.md` 记录路径/门控/两轮计划，优先级按该 run 的 SPEC 声明；模板本身不预置任何真实路径或结论。
