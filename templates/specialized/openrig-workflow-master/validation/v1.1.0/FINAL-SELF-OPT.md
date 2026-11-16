# FINAL-SELF-OPT — 自优化结果

> run: `openrig-master-selfopt-20261020`
> 目标：用 openrig-workflow-master v1.0.0 自举，产出一个更适合自应用、接入、管理和优化的新母版。
> 最终母版版本：**1.1.0**
> 母版提交：`c29ea6bea357451a0c0738c593133148a2ac5c1a`（workflow-group）

## 1. 结果

- PMO 产出 `SELF-OPT-PLAN.md`：5 维审计 + 文件不相交的 OC/DSH 工作包。
- TDO-OC 完成 OC-1/2/3：generator 参数校验、`--dry-run`/`--json`、render manifest、声明式产物表。
- TDO-DSH 完成 DSH-1/2/3/4：status 指标、doctor 交叉校验、capture 清单/密钥扫描、ARCHITECTURE queue/SAFETY 契约。
- QA 初检为 QA_FAIL（P-001/P-002 S2）；TDO-DSH 按 D-009/D-011 完成 WS-3b；QA 最终复核为 **QA_PASS**，open S1/S2=0。
- MAIN/收口：VERSION 1.1.0，README/CHANGELOG 更新，`BASELINE-post.sha256` 建立，母版入 git。
- 自优化过程发现并记录：DECISIONS 写入审计/单一写者、授权≠派单、untracked 母版 baseline、workflow graph 缺 QA→TDO rework 边；进入 v1.2 候选。

## 2. 验证快照

- OpenRig 5-seat rig：5/5 ready。
- workflow validate：ok=true，5 steps。
- workflow instantiate：entry packet → `control-pmo@openrig-master-selfopt`。
- QA 最终：**QA_PASS**；P-001/P-002 已关闭。
- `render_master.py`：dry-run/JSON/manifest/placeholder guard PASS。
- `tools/openrig_bridge.py`：doctor live PASS；safetyMode=off / schemaVersion=999 均 FAIL；status/capture PASS。
- `wf.py new-run` scratch：doctor PASS（仅暂无 STATUS 进度 warning），已删除。
- `rig workflow validate`：ok=true；仅有 declared-not-enforced warning。

## 3. 已知限制 / v1.2 候选

- `render-manifest.json` 的 sha256 仅同 output-dir 可比；路径相对化留 v1.2。
- OpenRig v1 workflow graph 缺 QA→TDO rework 边；引擎已有 `workflow resume`，但图内应在 v1.2 增加 waiting/back edge。
- SAFETY 仍是契约，执行器未实现；高风险动作必须独立门控。
- DECISIONS 缺写入审计；下一版应加 diff/hash 链。
- 授权存在 ≠ 派单存在；下一版应有明确的 packet 创建检查。

## 4. 证据

- `SELF-OPT-PLAN.md`
- `TDO-OC-REPORT.md`
- `TDO-DSH-REPORT.md`
- `TDO-DSH-FIX-REPORT.md`
- `QA-SELF-OPT.md`
- `evidence/oc/`、`evidence/dsh/`、`evidence/qa/`
- 母版验证副本：`templates/specialized/openrig-workflow-master/validation/v1.1.0/`
