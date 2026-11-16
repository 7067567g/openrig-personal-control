# v1.1.0 self-optimization validation

本目录保存 master 自己作为工作流目标的一次真实自优化结果。

## 运行

```text
run-id: openrig-master-selfopt-20261020
control-plane: workflow-group
execution-plane: OpenRig 5-seat rig openrig-master-selfopt
workflow: openrig-workflow-master-selfopt
```

## 结果

- PMO 产出 `SELF-OPT-PLAN.md`；
- TDO-OC 完成 generator OC-1/2/3；
- TDO-DSH 完成 bridge DSH-1/2/3/4 + WS-3b P-001/P-002 修复；
- QA 初检 QA_FAIL（P-001/P-002 S2），WS-3b 后最终复核 **QA_PASS / QA_RECHECK_PASS**，open S1/S2=0；
- 母版版本升级 `1.0.0 → 1.1.0`。

## 自优化发现

- DECISIONS 缺少写入审计，单一写者需要工具强制；
- 授权存在不等于 packet 已创建，管理流程需要显式派单；
- untracked 母版缺 pre/post baseline；本目录提供 `BASELINE-post.sha256`；
- Workflow graph 缺 QA→TDO rework 边；引擎 resume 可用，但图形契约应在 v1.2 补 waiting/back edge；
- `render-manifest.json` 的 sha256 只在同一 output-dir 内可比。

## 证据

- `SELF-OPT-PLAN.md`
- `TDO-OC-REPORT.md`
- `TDO-DSH-REPORT.md`
- `TDO-DSH-FIX-REPORT.md`
- `QA-SELF-OPT.md`
- `QA-SELF-OPT-RECHECK.md`
- `FINAL-SELF-OPT.md`
- 运行完整证据：`runs/openrig-master-selfopt-20261020/evidence/`
