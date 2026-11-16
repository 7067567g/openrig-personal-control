# -*- coding: utf-8 -*-
"""WS-2 · burner/run_queue.py 单测（mock HTTP，不联网）

覆盖 PROJECT §1-G2：DONE 判定（幂等 SKIP）、心跳可见性、余额下限、失败熔断。
网络相关一律 mock：send/new_session/start_server/balance_cny 全部替换；
仅 http() 用一个本机 ThreadingHTTPServer 回环验证，不访问任何外部地址。

替补实现开关（证明用例非空转 / 先红后绿）：
  WF_RUN_QUEUE_PATH=/tmp/mutant_run_queue.py python3 -m pytest workflow-group/tests/test_run_queue.py -q
"""

import importlib.util
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]  # workflow-group/
RUN_QUEUE_PY = Path(
    os.environ.get("WF_RUN_QUEUE_PATH") or (ROOT / "burner" / "run_queue.py")
)


def _load():
    spec = importlib.util.spec_from_file_location(
        "wf_run_queue_under_test", RUN_QUEUE_PY
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rq = _load()


# --------------------------------------------------------------- 夹具 / 工具
class _TimeProxy:
    """把 run_queue 的 time.sleep 变为 no-op（心跳用的 time.time/strftime 保持真实）。"""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def sleep(self, _seconds):
        return None


class FakeProc:
    returncode = 0
    pid = 424242

    def __init__(self):
        self.terminated = False

    def terminate(self):
        self.terminated = True


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    (tmp_path / "runs" / "r1").mkdir(parents=True)
    monkeypatch.setattr(rq, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(rq, "LOG", tmp_path / "burner.log")
    monkeypatch.setattr(rq, "STOP", tmp_path / "STOP")
    monkeypatch.setattr(rq, "time", _TimeProxy(time))
    return tmp_path


def read_log(tmp_path):
    p = tmp_path / "burner.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def pack(run_id="r1", name="P-test"):
    return {
        "run_id": run_id,
        "name": name,
        "kickoff": f"runs/{run_id}/kickoff.md",
        "spec": f"runs/{run_id}/SPEC.md",
    }


def queue(packs, **over):
    q = {
        "main_model": {"providerID": "deepseek", "id": "deepseek-flash"},
        "opencode_agent": "minimal",
        "heartbeat_sec": 1,
        "send_timeout_sec": 60,
        "max_nudges": 1,
        "packs": packs,
    }
    q.update(over)
    return q


def fake_urllib(payload=None, exc=None):
    """返回可注入 run_queue 全局 urllib 的假模块（不触碰 stdlib 全局）。"""

    class _Resp:
        def __init__(self, raw):
            self._raw = raw

        def read(self):
            return self._raw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Request:
        def __init__(self, url, data=None, method=None, headers=None):
            self.url, self.data, self.method, self.headers = url, data, method, headers

    class _ReqNS:
        Request = _Request

        @staticmethod
        def urlopen(_req, timeout=None):
            if exc is not None:
                raise exc
            return _Resp(payload)

    fake = SimpleNamespace(
        request=_ReqNS,
        error=__import__("urllib.error", fromlist=["error"]),
        parse=__import__("urllib.parse", fromlist=["parse"]),
    )
    return fake


# --------------------------------------------------------------- http（本机回环）
def test_http_get_json_roundtrip(sandbox):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"ok": True, "path": self.path}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        assert rq.http("GET", base + "/api/health", timeout=5) == {
            "ok": True,
            "path": "/api/health",
        }
    finally:
        srv.shutdown()
        srv.server_close()


def test_http_empty_body_returns_empty_dict(sandbox):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        assert rq.http("POST", base + "/session", {"a": 1}, timeout=5) == {}
    finally:
        srv.shutdown()
        srv.server_close()


# --------------------------------------------------------------- balance_cny
def test_balance_cny_parses_available(sandbox, monkeypatch):
    raw = json.dumps(
        {
            "is_available": True,
            "balance_infos": [{"total_balance": "12.34", "currency": "CNY"}],
        }
    ).encode()
    monkeypatch.setattr(rq, "urllib", fake_urllib(payload=raw))
    assert rq.balance_cny("k") == 12.34


def test_balance_cny_unavailable_or_missing_is_none(sandbox, monkeypatch):
    monkeypatch.setattr(
        rq,
        "urllib",
        fake_urllib(
            payload=json.dumps(
                {"is_available": False, "balance_infos": [{"total_balance": "9"}]}
            ).encode()
        ),
    )
    assert rq.balance_cny("k") is None
    monkeypatch.setattr(
        rq, "urllib", fake_urllib(payload=json.dumps({"is_available": True}).encode())
    )
    assert rq.balance_cny("k") is None


def test_balance_cny_error_returns_none_and_warns(sandbox, monkeypatch):
    monkeypatch.setattr(rq, "urllib", fake_urllib(exc=RuntimeError("net down")))
    assert rq.balance_cny("k") is None
    assert "WARN 查询余额失败" in read_log(sandbox)


# --------------------------------------------------------------- DONE 判定（幂等）
@pytest.mark.parametrize("marker", ["DONE", "BLOCKED"])
def test_run_pack_skips_when_marker_exists(sandbox, monkeypatch, marker):
    (sandbox / "runs" / "r1" / marker).write_text("一行结论", encoding="utf-8")
    called = {"n": 0}
    monkeypatch.setattr(
        rq, "new_session", lambda *a, **k: called.__setitem__("n", called["n"] + 1)
    )
    assert rq.run_pack(pack(), "http://127.0.0.1:1", queue([pack()]), 1) == "skipped"
    assert called["n"] == 0  # 不得建会话（白烧额度）
    assert f"SKIP r1（已存在 {marker}" in read_log(sandbox)


def test_run_pack_done_after_send(sandbox, monkeypatch):
    monkeypatch.setattr(rq, "new_session", lambda *a, **k: "sid-1")
    seen = {}

    def send(base, sid, text, model, timeout):
        seen["sid"] = sid
        (sandbox / "runs" / "r1" / "DONE").write_text("达成", encoding="utf-8")
        return {"info": {"cost": 0.001, "tokens": {"total": 7}}, "parts": []}

    monkeypatch.setattr(rq, "send", send)
    assert rq.run_pack(pack(), "http://127.0.0.1:1", queue([pack()]), 1) == "done"
    log = read_log(sandbox)
    assert seen["sid"] == "sid-1"
    assert "PACK 结束(DONE)" in log
    assert "cost=0.001" in log


def test_run_pack_unfinished_without_done(sandbox, monkeypatch):
    monkeypatch.setattr(rq, "new_session", lambda *a, **k: "sid-2")
    monkeypatch.setattr(rq, "send", lambda *a, **k: {"info": {}, "parts": []})
    assert (
        rq.run_pack(pack(), "http://127.0.0.1:1", queue([pack()], max_nudges=1), 1)
        == "unfinished"
    )
    log = read_log(sandbox)
    assert "nudge #1" in log
    assert "PACK 未完成（未写 DONE）" in log


# --------------------------------------------------------------- 心跳可见性
def test_run_pack_emits_heartbeat_during_slow_send(sandbox, monkeypatch):
    monkeypatch.setattr(rq, "new_session", lambda *a, **k: "sid-hb")

    def slow_send(base, sid, text, model, timeout):
        time.sleep(1.2)
        (sandbox / "runs" / "r1" / "DONE").write_text("达成", encoding="utf-8")
        return {"info": {}, "parts": []}

    monkeypatch.setattr(rq, "send", slow_send)
    assert (
        rq.run_pack(pack(), "http://127.0.0.1:1", queue([pack()], heartbeat_sec=1), 1)
        == "done"
    )
    log = read_log(sandbox)
    assert "HEARTBEAT session=sid-hb" in log
    assert "委派行=" in log and "done=" in log


def test_run_pack_send_error_is_circuit_visible(sandbox, monkeypatch):
    monkeypatch.setattr(rq, "new_session", lambda *a, **k: "sid-err")

    def boom(*a, **k):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(rq, "send", boom)
    assert rq.run_pack(pack(), "http://127.0.0.1:1", queue([pack()]), 1) == "error"
    assert "ERROR 发送失败" in read_log(sandbox)


# --------------------------------------------------------------- main 调度循环
def _wire_main(sandbox, monkeypatch, packs, balance=lambda key: 100.0, run_pack=None):
    monkeypatch.setattr(sys, "argv", ["run_queue.py"])
    monkeypatch.setattr(rq, "load_queue", lambda: queue(packs))
    monkeypatch.setattr(rq, "load_key", lambda: "k")
    monkeypatch.setattr(
        rq, "start_server", lambda key, port: (FakeProc(), "http://127.0.0.1:1")
    )
    monkeypatch.setattr(rq, "balance_cny", balance)
    if run_pack is not None:
        monkeypatch.setattr(rq, "run_pack", run_pack)


def test_main_stops_below_balance_floor(sandbox, monkeypatch):
    monkeypatch.setenv("BURNER_BALANCE_FLOOR", "1.0")
    monkeypatch.setattr(rq, "run_pack", lambda *a: pytest.fail("余额不足不应拉起 pack"))
    _wire_main(sandbox, monkeypatch, [pack()], balance=lambda key: 0.5)
    rq.main()
    log = read_log(sandbox)
    assert "官方余额 ¥0.50" in log
    assert "余额低于下限 ¥1.0，停止" in log


def test_main_circuit_breaker_after_three_errors(sandbox, monkeypatch):
    monkeypatch.delenv("BURNER_BALANCE_FLOOR", raising=False)
    calls = {"n": 0}

    def always_error(p, base, q, start):
        calls["n"] += 1
        return "error"

    _wire_main(
        sandbox, monkeypatch, [pack(f"r{i}") for i in range(5)], run_pack=always_error
    )
    rq.main()
    assert calls["n"] == 3
    assert "连续失败 3 次，停止" in read_log(sandbox)


def test_main_stops_on_stop_file(sandbox, monkeypatch):
    (sandbox / "STOP").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        rq, "run_pack", lambda *a: pytest.fail("STOP 存在不应拉起 pack")
    )
    _wire_main(sandbox, monkeypatch, [pack()])
    rq.main()
    assert "STOP 文件存在" in read_log(sandbox)
