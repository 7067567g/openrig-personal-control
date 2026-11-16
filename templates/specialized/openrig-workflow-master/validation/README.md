# Master smoke validation — 2026-10-20

本目录是 `render_master.py` 生成物对 OpenRig 的一次真实 smoke 记录。
测试 run-id：`master-smoke-20261020`；生成 rig：`openrig-master-smoke`；
workflow：`openrig-workflow-master-smoke`。

> **留存边界（快照日期 2026-10-20）**：`workflow-group/runs/master-smoke-20261020/`
> 与 `workflow-group/runs/openrig-workflow-master-scratch-20261020/` 两个 run 目录
> **已不存在**；本目录只保留当时的抓取文件（JSON/TXT），不声称 run 目录仍可复跑。
> 可复跑的是工具级检查（`render_master.py` / `tools/openrig_bridge.py` doctor /
> `sha256sum -c`），不是当时的 OpenRig 会话。

## 结果

| 步骤                       | 结果                                                                 |
| -------------------------- | -------------------------------------------------------------------- |
| render bundle              | PASS                                                                 |
| `rig up --plan`            | planned，errors=[]                                                   |
| `rig workflow validate`    | ok=true，5 steps，只有 declared-not-enforced / role-not-live warning |
| `rig up` 真实启动          | completed，5 nodes launched                                          |
| seat readiness             | 5/5 running/ready                                                    |
| `rig workflow instantiate` | 成功，entry owner=`control-pmo@openrig-master-smoke`                 |
| `rig workflow show`        | active，currentStep=plan，frontier packet 指向 PMO                   |
| `rig workflow abort`       | aborted，packet closed                                               |
| `rig down`                 | sessionsKilled=5，snapshot 生成                                      |
| `daemon stop`              | PASS                                                                 |
| cleanup                    | 无残留 daemon/tmux/runner                                            |

## 模板实例化验证

2026-10-20 使用 `wf.py new-run` 从本模板创建 scratch run：

```text
run-id: openrig-workflow-master-scratch-20261020
doctor: PASS (errors=0, warns=1; 仅 STATUS 尚未写进度)
PROJECT/DECISIONS 占位符: 已全部替换
```

验证后删除 scratch run，不保留空 run；因此
`workflow-group/runs/openrig-workflow-master-scratch-20261020/` 同样未留存，
本目录仅有 `wf-newrun.txt` / `wf-newrun-doctor.txt` 抓取结果。

## 工具验证

- `render-smoke.txt`：render_master.py 渲染含动态 rig/workflow/bridge 的 bundle；
- `bridge-doctor.txt`：openrig_bridge.py 校验 bridge 字段、spec、CLI 和 seat map，PASS；
- `wf-newrun.txt` / `wf-newrun-doctor.txt`：从模板实例化 scratch run，doctor PASS（仅 STATUS 无进度 warning）。

## 证据文件

- `rig-plan.json`
- `workflow-validate.json`
- `rig-up.json`
- `ps.txt`
- `workflow-instantiate.json`
- `workflow-show.json`
- `workflow-abort.json`
- `rig-down.json`
- `daemon-stop.txt`

- `wf-newrun.txt`
- `wf-newrun-doctor.txt`
- `render-smoke.txt`
- `bridge-doctor.txt`

## 快照完整性（v1.1.0 post baseline）

- 快照日期：2026-10-20
- 历史抓取文件保留：本目录的 `rig-*.json` / `ps.txt` / `workflow-*.json` / `daemon-stop.txt` 等
  smoke 抓取文件均在；对应 `master-smoke-20261020` 与 `openrig-workflow-master-scratch-20261020`
  run 目录**未留存**（见上方留存边界）。
- 校验命令（模板根）：`sha256sum -c BASELINE-post.sha256`
  - 本轮改动前（v1.1.0 提交树）：**35/35 OK（rc=0）**，见
    `evidence/dsh/ws3-1b-baseline-head.txt`（`git archive HEAD` 解包后校验）。
  - 本轮收口后（全量重算）：**35/35 OK（rc=0）**；`CHANGELOG.md`、`validation/README.md`、
    `tools/openrig_bridge.py` 三行已随本轮变更刷新，见
    `evidence/dsh/ws3-3-baseline-verify.txt` 与收口重算记录。
- `BASELINE-post.sha256` 的 `#` 头记录 version / generated-at / commit / pre 基线缺失声明；
  本轮为全量重算（35 行按当前树计算），pre→post 差异哈希不可得（v1.0.0 无 pre 基线）。
