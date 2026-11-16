# 内存限制与 dsh-terminal 治理

> 日期：2026-11-13
> 适用：`wechat-bridge-v2` / `sctg-app-feel-auto-20261113`
> 目的：避免 dsh-terminal cgroup 的 page cache 把 14GB 主机压到全局 OOM。

## 1. cgroup 参数语义

| 参数 | 含义 | 是否叠加 |
|---|---|---|
| `MemoryHigh` | 软上限；超过后内核积极回收/节流 | 否，在 `MemoryMax` 内部 |
| `MemoryMax` | RAM 硬上限；超过且回收失败会 OOM 该 cgroup | 是，与 swap 分开 |
| `MemorySwapMax` | swap 上限 | 是，与 RAM 分开 |

所以：

```text
MemoryHigh=5G
MemoryMax=6G
MemorySwapMax=1G
```

实际容量上限约为：

```text
6G RAM + 1G swap = 7G
```

不是 5G + 6G + 1G = 12G。

## 2. 为什么选 5G/6G/1G

观测：

```text
dsh-terminal cgroup 正常峰值 4.6G
病态峰值 7.0G / 11.1G
cgroup 内 /bin/bash RSS 只有几 MB
大部分是 file/page cache
```

结论：

- 3G 太紧，会把正常 4.6G 工作集压进强回收；
- 5G 作为 `MemoryHigh` 合理；
- 6G 作为硬上限可以截断 7–11G 病态峰值；
- 1G swap 只作缓冲，不把 swap 当安全垫。

## 3. 已实现的限制

### 3.1 `auto_driver.py` seat 启动

`run_seat()` 现在用：

```bash
systemd-run --user --scope --quiet \
  --unit=dsh-seat-<pid>-<ts> \
  --property=MemoryAccounting=yes \
  --property=MemoryHigh=5G \
  --property=MemoryMax=6G \
  --property=MemorySwapMax=1G \
  -- dsh --profile headless ...
```

同时：

- seat 输出重定向到 `reports/sctg/logs/Rxx-attempt-N.log`，不再 `capture_output` 全收进 Python 内存；
- 只读日志 tail；
- 超时用 `systemctl --user stop <scope>` 停整个 cgroup，不把超时当 PASS；
- 每轮写 `reports/sctg/telemetry.jsonl`，记录 `MemoryPeak` / `MemorySwapPeak`。

配置在 `tools/sctg/rounds.yaml`：

```yaml
driver:
  seat: lead
  seat_command: dsh --profile headless
  timeout_sec: 1800
  memory_high: 5G
  memory_max: 6G
  memory_swap_max: 1G
  min_available_mb: 3500
  log_tail_chars: 4000
```

### 3.2 `memory-guard` 目标顺序

`memory-guard.service` 的优先级是：

```text
Chrome > ComfyUI > SD > WeChat/VM > dsh-terminal（最后）
```

原因：Chrome、ComfyUI、SD 都是可牺牲的；dsh 工作流中断可能丢 packet，所以 dsh 只做最后兜底。

行为：

- 正常压力路径只处理 Chrome/ComfyUI/SD/WeChat/VM，不动 dsh；
- 只有 `MemAvailable < 700MB` 的 critical 路径，在清退完可牺牲应用后，才对 `dsh-terminal-*.scope` 中 `MemoryCurrent >= 4000MB` 的 scope 动态设置：
  ```text
  MemoryHigh=5G
  MemoryMax=6G
  MemorySwapMax=1G
  ```
- 这是**限制/回收**，不是直接杀 dsh；
- 自动 seat 仍有独立的 5G/6G/1G cgroup 上限，不依赖 memory-guard。

配置在 `~/.config/memory-guard.env`：

```text
MEM_DSH_MB=4000
MEM_DSH_HIGH=5G
MEM_DSH_MAX=6G
MEM_DSH_SWAP_MAX=1G
```

### 3.3 安全边界

`auto_driver` 的 seat prompt 增加：

```text
不要扫描 ~/.dsh、/home、/；
不要跑全盘 rg/find/grep；
大文件只读 head/tail；
不读取 token/凭证/截图/UI dump/logcat。
```

## 4. 监控命令

```bash
# 当前内存
grep -E 'MemTotal|MemAvailable|Cached|SwapTotal|SwapFree' /proc/meminfo

# dsh-terminal cgroup
systemctl --user list-units 'dsh-terminal-*.scope' --all --no-legend
for u in $(systemctl --user list-units 'dsh-terminal-*.scope' --all --no-legend | awk '{print $1}'); do
  systemctl --user show "$u" -p Id -p MemoryCurrent -p MemoryPeak -p MemorySwapPeak --no-pager
done

# cgroup 事件
systemctl --user show 'dsh-terminal-*.scope' -p MemoryHigh -p MemoryMax --no-pager
cat /sys/fs/cgroup/.../memory.events 2>/dev/null

# memory guard
tail -50 ~/.local/state/memory-guard.log
systemctl --user status memory-guard.service --no-pager
```

## 5. 验收

```text
auto_driver --dry-run 通过
seat 启动使用 systemd-run scope
MemoryHigh=5G / MemoryMax=6G / MemorySwapMax=1G
seat stdout/stderr 只进日志，不进 Python 内存
telemetry.jsonl 有 memory_peak
memory-guard 日志出现 dsh_last=4000MB 启动行
```

## 6. 注意

- `MemoryHigh` 不是额外容量；
- `MemoryMax` 包含 page cache，正常 4.6G file cache 会被允许；
- 6G 硬上限只截断病态峰值；
- 如果 `MemAvailable` 仍长期低于 2G，下一档调整是 `MemoryHigh=4G / MemoryMax=5G / MemorySwapMax=1G`；
- 不要用 `ulimit -v` 代替 cgroup，page cache 不受它控制。

## 7. 长驻服务的附加限制

除了自动 seat 和 dsh-terminal，微信桥相关长驻服务也加了 cgroup 限制：

### `dsh-app.service`

```text
MemoryAccounting=yes
MemoryHigh=512M
MemoryMax=1G
MemorySwapMax=256M
```

用途：微信桥独立 app server（127.0.0.1:3090）。当前常驻约 78M，峰值约 223M，1G 硬上限足够，不会影响媒体/会话正常路径。

### `dsh-web.service`

```text
MemoryAccounting=yes
MemoryHigh=2500M
MemoryMax=4G
MemorySwapMax=1G
```

用途：DSH Web / OpenCode agent host。当前约 1.9–2.2G；2.5G 软上限、4G 硬上限，避免它自己无限增长，但不切断当前会话。

### 生效方式

drop-in：

```text
~/.config/systemd/user/dsh-app.service.d/50-memory.conf
~/.config/systemd/user/dsh-web.service.d/50-memory.conf
```

运行时已通过 `systemctl --user set-property --runtime` 应用，无需重启服务。

### 注意

- `dsh-terminal-*.scope` 仍是独立 cgroup，由 `memory-guard` 在 critical 路径最后兜底；
- `dsh-web.service` 的 4G 上限不覆盖子 terminal scope，二者分开统计；
- 如果 OpenRig 使用同一个全局 `dsh-web`/`dsh-app`，这些 drop-in 是用户级全局的，所有项目共享；
- 如果 OpenRig 使用独立 daemon/seat，需要在它的 seat 启动层单独加 cgroup 限制。


## 8. 30 轮项目级检查

```bash
python3 tools/sctg/check_memory_policy.py
```

它检查：

- `rounds.yaml` 的 driver 限制为 `5G / 6G / 1G`；
- `auto_driver.py` 使用 `systemd-run` + `MemoryAccounting` + 三个限制；
- seat 输出进入日志文件；
- `RUN-STATE.json` 带同样的 `memory_limits`；
- `MemAvailable >= 3500MB`；
- `memory-guard.service` 是否 active；
- 当前 dsh-terminal scope 的 `MemoryCurrent` / `MemoryPeak`。

当前策略摘要见 `reports/sctg/MEMORY-POLICY.md`。

## 9. 全局 dsh.slice 与并发降级

单 seat 的 5G/6G/1G 不是全局上限。30 轮项目额外加了一个用户级 slice：

```text
dsh.slice
  MemoryHigh=8G
  MemoryMax=9G
  MemorySwapMax=2G
```

生效方式：

```text
~/.config/systemd/user/dsh.slice
```

`dsh.slice` 的 `MemoryMax=9G` 覆盖其下所有 seat；`systemd-run` 的 seat 必须带：

```text
--slice=dsh.slice
```

### 并发策略

```text
第一个 seat：heavy  profile  5G high / 6G max / 1G swap
第二个 seat：light  profile  3.5G high / 4.5G max / 0.5G swap
无论多少 seat：全局 dsh.slice 8G high / 9G max / 2G swap
```

实现：

- `auto_driver.py` 用 `fcntl.flock` 抢 `$XDG_RUNTIME_DIR/dsh-heavy-seat.lock`；
- 抢到锁：`seat_class=heavy`；
- 锁被占用：自动降级为 `seat_class=light`，不阻塞、不杀已有工作流；
- 每轮 `telemetry.jsonl` 记录 `seat_class`、`global_slice`、`memory_peak`；
- 全局 slice 是最后一道硬边界，防止多个 light seat 叠加穿透。

### 验证

```bash
python3 tools/sctg/check_memory_policy.py
systemctl --user show dsh.slice -p MemoryHigh -p MemoryMax -p MemorySwapMax
```

当前结果：

```text
dsh.slice: MemoryHigh=8G / MemoryMax=9G / MemorySwapMax=2G
check_memory_policy: PASS
heavy seat: 5G/6G/1G
light seat: 3.5G/4.5G/0.5G
```
