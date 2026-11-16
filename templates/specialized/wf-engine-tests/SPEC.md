# SPEC — workflow-group 引擎测试 + CI + P5 遗留（P12）

## 0. 分层声明

baseline: composite/fix-wave@1.0.0
contracts: audit@1.0.0, optimize@1.0.0, verify@1.0.0

> 特化规则，优先于通用手册。目标：给烧额度引擎本身补测试与 CI（1910 行脚本零单测），并落地 P5 复盘遗留 S-1/S-2/S-3。

## 1. R1（2 路并行）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-1 | `workflow-group/tests/**`（新建）、`workflow-group/scripts/wf.py`（仅修为过测试的缺陷） | `wf.py` 测试：状态机守卫（`_delegate_guards` 四种不匹配）、锁 TTL/`--steal`/安全释放、`append-status` 的 `--also` 过滤（被 gitignore 的 `*.log` 必须跳过+告警且整条提交成功——复现 F9 事故）、`commit` 路径与 `ledger` 汇总、`doctor` 报错分支。**验收：临时 run 夹具下 pytest 全绿；每个反例先红后绿** |
| WS-2 | `workflow-group/tests/**`、`.github/workflows/wf-validate.yml`（新建） | `issues.py`（ID/枚举/S1 规则/close 需决策）与 `burner/run_queue.py`（mock HTTP：DONE 判定、心跳、余额下限、失败熔断）测试；CI workflow 跑 python 语法+pytest。**验收：mock 不联网；CI 文件 YAML 合法；`python3 -m pytest workflow-group/tests -q` 全绿** |

## 2. R2（1 路）

| WS | 写权限 | 任务与验收 |
| --- | --- | --- |
| WS-3 | `workflow-group/scripts/wf.py`、`workflow-group/burner/run_queue.py`、`workflow-group/templates/**` | P5 遗留 S-1/S-2/S-3：`--also` 过滤落地；delegate/squad 心跳可见性；new-run 预填 per-WS 交接占位。**验收：S-1 用 gitignore 文件复现被跳过；S-2 mock 慢响应有心跳行；模板冒烟 `new-run` + `doctor` PASS** |

## 3. 禁止

- 不改 `workflow-group/roles/**`、不改 KB 正式域；不 push；只提交 workflow-group 内路径；
- 不为通过测试而放宽断言（先红后绿要留证据）。

## 4. DoD

- pytest 全绿且覆盖上述分支；CI workflow 提交；S-1/S-2/S-3 有回归测试；
- `reports/final.md`；ISSUES 无 open S1/S2。
