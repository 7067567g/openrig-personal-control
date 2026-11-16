# openrig-local-refit 特化模板

## 用途

用现有 `workflow-group` 本地模式（四件套 + `wf.py` + OpenCode 会话）调查和重整 OpenRig，**不启动 OpenRig daemon，不把 OpenRig 当作本流程的运行底座**。

## 实例化

```bash
cd workflow-group
python3 scripts/wf.py new-run <run-id> \
  --template templates/specialized/openrig-local-refit \
  --goal-file kickoff/openrig-local-refit-goal.txt \
  --tdo 1
python3 scripts/wf.py doctor <run-id>
```

## 已知环境坑（2026-10-18 实测）

| 坑 | 表现 | 处理 |
| --- | --- | --- |
| OpenCode Go API key 过期 | `opencode run` 返回 `UnknownError`；加 `--print-logs --log-level DEBUG` 后是 401 `api_key_expired` | 到 OpenCode Console 新建 key 并替换 auth；重新登录不会续期 |
| OpenCode 版本跟 Node 前缀走 | Node24=`1.17.12`，Node26=`1.19.3`；OpenRig 只支持 Node22/24 | 固定 `OPENRIG_OPENCODE_BIN`；推荐在 Node24 装 1.19.3 |
| 默认代理破坏 HTTPS | GitHub/raw/nodejs/npm/opencode.ai 的 curl 报 TLS EOF；无代理可访问 | 关键命令显式 unset `HTTP(S)_PROXY`；`npm ci` 也必须无代理 |
| 全局 OpenCode 数据很重 | `opencode.db` 3GB+，8 个插件，重复 skill 警告 | seat 使用隔离 `HOME`/`XDG_*`；不要把全局 DB 带入每个 seat |
| 资源有限 | 4 vCPU / 5.8GB RAM，可能仅 ~2GB available | 初始并发 1–2；不要照搬 5 TDO |
| 外部 clone 只读 | `60-外部仓库/openrig` 是参考上游 | R2 必须用自有副本 `deepseek-项目/10-openrig-deepseek` |
| GitHub API/SSH 可用但 HTTPS 网页不通 | `gh` token 无效；GitHub API 直连可用、网页超时 | 用 API/SSH 获取证据；不要依赖网页登录 |

## 环境检查最小命令集

```bash
# 主机
uname -a; nproc; free -h; df -h /home /tmp

# Node/OpenCode 两份版本
for v in v24.18.0 v26.4.0; do
  /home/dev/.nvm/versions/node/$v/bin/node -v
  /home/dev/.nvm/versions/node/$v/bin/opencode --version
done

# OpenCode 静态命令（不调用模型）
timeout 30 opencode auth list
timeout 30 opencode debug paths
timeout 30 opencode models
timeout 30 opencode session list -n 1 --format json

# OpenCode 真实调用（仅在 key 有效时；会耗费 token）
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  opencode run --print-logs --log-level DEBUG --format json \
  --model opencode-go/deepseek-v4.1-flash "Reply with exactly OK"

# OpenRig 构建（Node24，无代理）
cd /home/dev/Desktop/deepseek/60-外部仓库/openrig
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy npm run build -w packages/daemon

# 本地工作流自检
cd workflow-group
python3 -m pytest tests -q
python3 scripts/wf.py doctor <run-id>
```

## 判读规则

- `command -v` / `--version` / `--help` 成功 ≠ 运行时可用。
- `opencode models` 能列出模型 ≠ API key 可调用。
- `opencode run` 默认只显示 `UnknownError`；必须加 `--print-logs --log-level DEBUG` 或读取日志。
- 不允许把 API key、完整 auth.json、完整会话正文写入 run 报告。
