# Memory incident — 2026-11-13 15:19–15:39

## 结论

这是一次**全局内存耗尽（global OOM）**，不是单一进程泄漏，也不是 `memory-guard` 造成的。

主因是：

```text
多个 dsh-terminal cgroup 的内存峰值 4.6G / 7.0G / 11.1G
+ GNOME Shell 峰值 4.3G
+ localsearch-3 峰值 2.1G
+ ComfyUI 峰值 2.8G
+ Chrome / WeChat / dsh-web 等
```

在 14GB RAM（+4GB swap）的机器上触发全局 OOM。内核和 systemd-oomd 选择杀掉 Chrome、WeChat、Chromium、GNOME Shell，而**真正的大头 dsh-terminal 反而没有先被杀**。

## 关键证据

### Kernel OOM

```text
15:19:28 oom-kill: constraint=CONSTRAINT_NONE ... global_oom
         task_memcg=.../org.gnome.Shell@ubuntu.service, task=chrome, pid=7661
15:20:20 Out of memory: Killed process 7661 (chrome)
         anon-rss:240168kB, oom_score_adj:300
```

### systemd-oomd

```text
15:20:15 Killed app-gnome-wechat-3843.scope due to memory pressure ... 93.53% > 50% for >20s
15:20:15 Killed app-org.chromium.Chromium-5108.scope ... 97.54% > 50% for >20s
```

### dsh-terminal cgroup 峰值

```text
14:57:40 dsh-terminal-13200-0602e74a4cfb.scope: 7.0G memory peak (stopped on client request)
15:20:14 dsh-terminal-13200-f7a7f808cfe5.scope: 4.6G memory peak
15:33:42 dsh-terminal-13200-d968fd0f174b.scope: 11.1G memory peak, 2.2G swap peak
```

当前（15:47 左右）仍有一个 dsh-terminal：

```text
dsh-terminal-119299-620631d56bfd.scope
MemoryCurrent = 4.6G
MemoryPeak    = 4.8G
cgroup 内 /bin/bash RSS 只有 ~6MB
```

### 关键解释

`/bin/bash` 本身只有几 MB，但 cgroup `MemoryCurrent` 4.6–11.1G，说明**大部分是 page cache / 子进程读取的大文件缓存**，不是 bash 自身堆内存。

`~/.dsh` 目录约 **27G**，包含大量 checkpoint/归档/大文件。Broad `rg`/`find`/`git`/`zstd`/`grep` 扫描会把大量文件页计入该 dsh-terminal cgroup，导致：

```text
cgroup memory 4–11G
-> 全局 MemAvailable 下降
-> systemd-oomd / kernel OOM 选择杀 Chrome/WeChat/GNOME
-> 用户看到“微信/浏览器/桌面被杀”，但真正的 dsh 终端 cgroup 仍在
```

## 为什么 memory-guard 不是原因

`memory-guard.service` 从 **15:38:44** 才开始运行，晚于 15:19/15:20 的 OOM。它只是事故后的缓解脚本，当前阈值：

```text
Chrome  < 2500MB -> 关 Chrome
ComfyUI < 2000MB -> 停 ComfyUI
SD      < 1400MB -> 杀 SD
Chat/VM < 900MB  -> 关微信/QQ/VM
Critical< 700MB  -> 全清
```

问题：

- 它**不处理 dsh-terminal/opencode**；
- 真正占内存的 dsh cgroup 不会被它杀；
- 它可能先把 Chrome/WeChat/ComfyUI 杀掉，造成“内存守护误伤”的体感。

## 建议

1. 给 dsh-terminal/opencode 加 cgroup 限制：
   ```text
   MemoryHigh=2G
   MemoryMax=3G
   ```
   或由 `dsh` 启动时使用 `systemd-run --property=MemoryMax=...`。
2. `memory-guard` 增加 dsh/opencode 目标，优先级应高于 Chrome/WeChat：
   ```text
   先限制/重启 dsh-terminal，再考虑关 Chrome/WeChat
   ```
3. 禁止/限制 broad scan：
   - 不跑 `rg /home`、`find ~/.dsh`、`git log -p --all` 大仓；
   - 用 `rg --max-filesize 10M`、`head`、`find -mmin`、目标路径；
   - 大文件读取后主动 `sync; echo 3 > drop_caches`（需权限）或重启 dsh terminal。
4. 给 `~/.dsh` 做容量治理：27G 的 checkpoint/归档不应长期与工作区混放。
5. 监控：
   - `systemd-cgtop --order=memory`
   - `systemctl --user show dsh-terminal-*.scope -p MemoryCurrent -p MemoryPeak`
   - `MemAvailable < 2G` 告警。
6. 保留 4GB swap，但不要把 swap 当安全垫；本次 swap 峰值 2.2G。

## 结论一句话

> 内存事故不是微信桥或 OpenRig 单点泄漏，而是 **dsh-terminal cgroup 在大文件扫描时把 page cache 吃到 4.6–11.1G**，叠加桌面/ComfyUI/Chrome/WeChat 后触发全局 OOM；OOM 选择了 Chrome/WeChat/GNOME 作为牺牲品，真正的大头 dsh terminal 反而没被优先处理。


## 已实施（2026-11-13）

- `auto_driver.py` seat 启动改为 `systemd-run --user --scope`：
  - `MemoryHigh=5G`
  - `MemoryMax=6G`
  - `MemorySwapMax=1G`
  - `MemoryAccounting=yes`
- seat stdout/stderr 重定向到 `reports/sctg/logs/`，不再 `capture_output` 全收进 Python 内存。
- 每轮写 `reports/sctg/telemetry.jsonl`，记录 `MemoryPeak` / `MemorySwapPeak`。
- `memory-guard` 优先处理可牺牲应用（Chrome/ComfyUI/SD/WeChat），dsh-terminal 只做最后兜底：
  - 自动 seat cgroup：`MemoryHigh=5G` / `MemoryMax=6G` / `MemorySwapMax=1G`
  - 交互 dsh-terminal：仅 critical 路径最后兜底 `MEM_DSH_MB=4000`，`MemoryHigh=5G` / `MemoryMax=6G` / `MemorySwapMax=1G`
  - 正常压力路径先关 Chrome/ComfyUI/SD/WeChat，避免打断工作流
- 详细语义和监控命令见 `MEMORY-LIMITS.md`。


## 长驻服务限制

- `dsh-app.service`：`MemoryHigh=512M` / `MemoryMax=1G` / `MemorySwapMax=256M`
- `dsh-web.service`：`MemoryHigh=2500M` / `MemoryMax=4G` / `MemorySwapMax=1G`
- 通过用户级 drop-in + `systemctl --user set-property --runtime` 应用，未重启服务。
- `dsh-terminal-*.scope` 独立 cgroup，仍由 `memory-guard` 在 critical 路径最后兜底。


## 全局 slice 与并发降级

- `dsh.slice`：`MemoryHigh=8G` / `MemoryMax=9G` / `MemorySwapMax=2G`
- 第一个 seat：heavy 5G/6G/1G
- 第二个 seat：light 3.5G/4.5G/0.5G
- `auto_driver` 用 `$XDG_RUNTIME_DIR/dsh-heavy-seat.lock` 判断 heavy/light；锁忙自动降级，不阻塞、不杀已有工作流。
