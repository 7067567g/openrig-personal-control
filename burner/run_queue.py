#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_queue.py — 烧额度调度器

顺序拉起"主会话"（opencode + DeepSeek 官方 key），每个主会话跑完一个任务包并写出
runs/<run-id>/DONE 后，再拉下一个；直到队列跑完、额度耗尽或出现 burner/STOP。

用法:
  python3 burner/run_queue.py --probe        # 自检：起服务+发一条最小消息+删会话
  python3 burner/run_queue.py --dry-run      # 只打印将要发送的提示词
  python3 burner/run_queue.py                # 正式常驻（建议 nohup/setsid 后台）
  python3 burner/run_queue.py --once         # 只跑队列第一个 pack
  python3 burner/run_queue.py --from 3       # 从第 3 个 pack 开始
停止: touch burner/STOP  （在每个会话边界生效；不等当前会话）

环境变量:
  DEEPSEEK_API_KEY   官方 key（必须由环境提供；不回退读任何文件）
  BURNER_BALANCE_FLOOR  余额下限 CNY（默认取 queue.json）
  BURNER_PORT        外层服务端口（默认 4711）
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # workflow-group/
RUNS = ROOT / "runs"
BURN = ROOT / "burner"
QUEUE = BURN / "queue.json"
LOG = BURN / "burner.log"
STATE = BURN / "state.json"
STOP = BURN / "STOP"


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_queue():
    q = json.loads(QUEUE.read_text(encoding="utf-8"))
    return q


def load_key():
    """Read the API key from the environment only.

    A shipped tool must not go looking for secrets in the user's shell config
    or any credential store; the environment is the single supported source.
    """
    return os.environ.get("DEEPSEEK_API_KEY", "").strip()


def http(method, url, body=None, timeout=60):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw.strip() else {}


def balance_cny(key):
    try:
        req = urllib.request.Request("https://api.deepseek.com/user/balance",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        infos = d.get("balance_infos") or []
        return float(infos[0]["total_balance"]) if infos and d.get("is_available") else None
    except Exception as e:
        log(f"WARN 查询余额失败: {e}")
        return None


def start_server(key, port):
    env = dict(os.environ)
    env["DEEPSEEK_API_KEY"] = key
    out = open(BURN / "server.log", "ab")
    proc = subprocess.Popen(
        ["opencode", "serve", "--pure", "--port", str(port), "--hostname", "127.0.0.1"],
        cwd=str(ROOT), env=env, stdout=out, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            http("GET", base + "/api/health", timeout=3)
            return proc, base
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError(f"opencode serve 退出 code={proc.returncode}（看 burner/server.log）")
            time.sleep(1)
    raise RuntimeError("opencode serve 30s 内未就绪")


def new_session(base, model, agent, title):
    body = {"title": title,
            "model": {"id": model["id"], "providerID": model["providerID"]},
            "agent": agent,
            # 无人值守：禁止提问阻塞（问题一律走文档 ISSUES/DECISIONS）
            "permission": [{"permission": "question", "pattern": "*", "action": "deny"}]}
    if model.get("variant"):
        body["model"]["variant"] = model["variant"]
    s = http("POST", base + "/session", body, timeout=180)
    sid = s.get("id") or (s.get("data") or {}).get("id")
    if not sid:
        raise RuntimeError(f"建会话失败: {s}")
    return sid


def send(base, sid, text, model, timeout):
    body = {"model": {"providerID": model["providerID"], "modelID": model["id"]},
            "agent": "minimal",
            "parts": [{"type": "text", "text": text}]}
    if model.get("variant"):
        body["model"]["variant"] = model["variant"]
    return http("POST", f"{base}/session/{sid}/message", body, timeout=timeout)


def prompt_for(pack):
    return f"""你是 workflow-group 的主会话。本次 run-id = {pack['run_id']}。
工作目录：{ROOT}

先读（按顺序）：README.md、WORKFLOW.md（重点 §2/§3/§4.1/§5/§9/§9.1）、
roles/delegation-briefs.md、{pack['kickoff']}、{pack['spec']}

任务：严格按 {pack['kickoff']} 的计划执行；run-id 固定用 {pack['run_id']}。

无人值守硬规则：
1. 全程不要向用户提问；需要用户拍板的事记入 DECISIONS/PROJECT §6 待决，然后继续其它可做项。
2. 一路推进（R1/R2/R3…），不要交完一波就停；每轮按 SOP 走完 QA/PMO/决策/提交。
3. 写权限以 SPEC 为准；白名单外只读；TDO 只改不提交，主会话每轮用 wf.py commit 提交明确路径；永不 push。
4. 完成 DoD，或确认遇到无法继续的阻塞（写明卡点）时，写出 runs/{pack['run_id']}/DONE，
   内容一行：达成/阻塞 + 一句结论。写完 DONE 才结束。
5. 长命令纪律（重要）：wf.py delegate/squad 可能跑几十分钟。执行时优先后台：
   `nohup python3 scripts/wf.py ... > runs/<run-id>/logs/<步骤>.log 2>&1 &`
   然后轮询元数据（runs/<run-id>/DELEGATIONS.md 行数增长、STATUS 的 wf-doc 头、wf.py doctor），
   不要在前台空等；若确要前台执行，给 bash 工具显式设置超大 timeout（≥7200000ms）。
   全量门禁（bash tests/...）同样放后台 + 轮询日志尾部。

现在开始。"""


def delegations_lines(run_id):
    p = RUNS / run_id / "DELEGATIONS.md"
    if not p.exists():
        return 0
    return len(p.read_text(encoding="utf-8", errors="replace").splitlines())


def run_pack(pack, base, q, from_index):
    run_id = pack["run_id"]
    done = RUNS / run_id / "DONE"
    blocked = RUNS / run_id / "BLOCKED"
    # 幂等：已完成/已阻塞的 pack 不再重复拉起主会话（F1：kb-debt 2026-10-14 被重跑，
    # 仅消耗 63664 tokens 换来写 DONE，委派新增 0）。确需重跑时先删 runs/<id>/DONE。
    if done.exists() or blocked.exists():
        mark = "DONE" if done.exists() else "BLOCKED"
        log(f"SKIP {run_id}（已存在 {mark}，跳过；需重跑请先删除）")
        return "skipped"
    log(f"=== PACK 开始: {pack.get('name', run_id)}（{run_id}）===")
    before = delegations_lines(run_id)
    model = q["main_model"]
    sid = new_session(base, model, q.get("opencode_agent", "minimal"),
                      f"burner {run_id}")
    log(f"session={sid} model={model['providerID']}/{model['id']} 已建")
    msg = prompt_for(pack)
    max_nudges = int(q.get("max_nudges", 6))
    timeout = int(q.get("send_timeout_sec", 21600))
    for attempt in range(max_nudges + 1):
        if STOP.exists():
            log("STOP 文件出现，结束当前 pack")
            return "stopped"
        if attempt > 0:
            msg = (f"继续执行 run-id={run_id}（上一轮结束但还没写 DONE）。"
                   f"完成 DoD 或确认阻塞时，写出 runs/{run_id}/DONE（一行结论）；"
                   "需要用户拍板的先记 DECISIONS/PROJECT §6 待决，继续其它可做项。")
            log(f"nudge #{attempt} session={sid}")
        # 心跳：send 是单次阻塞调用（F3：实测单条 send 可跑 68/42/98 分钟且期间无任何日志，
        # 无法区分"在跑"与"卡死"）。放进线程里跑，主线程按 heartbeat_sec 记心跳行。
        box = {}

        def _do_send():
            try:
                box["r"] = send(base, sid, msg, model, timeout)
            except Exception as e:
                box["err"] = e

        hb = int(q.get("heartbeat_sec", 300))
        t0 = time.time()
        th = threading.Thread(target=_do_send, daemon=True)
        th.start()
        while th.is_alive():
            th.join(timeout=hb)
            if th.is_alive():
                log(
                    f"HEARTBEAT session={sid} 已等待 {int(time.time() - t0)}s "
                    f"委派行={delegations_lines(run_id)} done={done.exists()}"
                )
        if "err" in box:
            log(f"ERROR 发送失败: {str(box['err'])[:300]}")
            return "error"
        r = box["r"]
        info = r.get("info", {}) or {}
        tok = info.get("tokens", {}) or {}
        log(f"session={sid} 返回（cost={info.get('cost')} tokens={tok.get('total')}）")
        time.sleep(3)
        if done.exists() or blocked.exists():
            mark = "DONE" if done.exists() else "BLOCKED"
            log(f"PACK 结束({mark}): {run_id}；委派新增行 {delegations_lines(run_id) - before}")
            return "done"
    log(f"PACK 未完成（未写 DONE）: {run_id}")
    return "unfinished"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--from", dest="start", type=int, default=1)
    args = ap.parse_args()

    q = load_queue()
    key = load_key()
    if not key:
        print("FATAL 未设置 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(2)
    floor = float(os.environ.get("BURNER_BALANCE_FLOOR", q.get("balance_floor_cny", 1.0)))
    port = int(os.environ.get("BURNER_PORT", "4711"))

    packs = q["packs"][max(0, args.start - 1):]
    if args.dry_run:
        for p in packs:
            print("=" * 70)
            print(prompt_for(p))
        return

    log(f"调度器启动：packs={len(packs)} 余额下限=¥{floor} 主模型="
        f"{q['main_model']['providerID']}/{q['main_model']['id']}")
    proc, base = start_server(key, port)
    log(f"外层服务就绪: {base}（pid={proc.pid}）")
    try:
        if args.probe:
            sid = new_session(base, q["main_model"], q.get("opencode_agent", "minimal"),
                              "burner-probe (可删)")
            r = send(base, sid, "只回复两个字：就绪", q["main_model"], 300)
            txt = [p.get("text") for p in (r.get("parts") or []) if p.get("type") == "text"]
            log(f"PROBE 回复={txt} 成本={r.get('info', {}).get('cost')}")
            try:
                http("DELETE", f"{base}/session/{sid}", timeout=30)
            except Exception:
                pass
            return

        fails = 0
        zero_progress = 0
        for p in packs:
            if STOP.exists():
                log("STOP 文件存在，调度器退出")
                break
            bal = balance_cny(key)
            if bal is not None:
                log(f"官方余额 ¥{bal:.2f}")
                if bal < floor:
                    log(f"余额低于下限 ¥{floor}，停止")
                    break
            before_lines = delegations_lines(p["run_id"])
            result = run_pack(p, base, q, args.start)
            after_lines = delegations_lines(p["run_id"])
            # 记账口径（F4）：session 的 info.cost 远小于官方余额下降（实测 P1–P4 合计
            # cost≈$0.0034，而余额 ¥32.18→¥27.29）。以余额差为预算口径，逐 pack 打差额。
            after_bal = balance_cny(key)
            if bal is not None and after_bal is not None:
                log(
                    f"PACK {p['run_id']} 结束({result}) 余额 ¥{bal:.2f} → ¥{after_bal:.2f}"
                    f"（Δ¥{after_bal - bal:.2f}）委派新增 {after_lines - before_lines} 行"
                )
            if result in ("done", "unfinished") and after_lines <= before_lines:
                zero_progress += 1
                log(f"WARN {p['run_id']} 委派无新增（连续 {zero_progress} 个）")
            else:
                zero_progress = 0
            if result == "error":
                fails += 1
                log(f"ERROR 失败计数 {fails}")
                if fails >= 3:
                    log("连续失败 3 次，停止")
                    break
            else:
                fails = 0
            if zero_progress >= 3:
                log("连续 3 个 pack 委派无新增，疑似 worker 侧额度耗尽/异常，停止")
                break
            if args.once:
                break
            time.sleep(10)
        log("队列结束")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
