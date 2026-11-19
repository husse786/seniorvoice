"""State of the device for the "Technik" view of the portal (admin only, B5).

Collected live on each request, nothing is stored for it:
- device: uptime, CPU temperature and load, memory, free disk, software version
- services: core running (its status file is fresh), dialog process state and
  restarts, Help channel type, input (simulated or telephone)
- AI: language model backend and model, whether it is on this device and
  answering, cloud guard, speech recognition and voice
- daily values of the last 7 days from metrics.db (count, median, 95 %)

Never conversation content, and nothing that shows whether a call is going on
right now or when single conversations took place (daily routine).
Missing values (e.g. CPU temperature on a Mac) are null.
"""

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import config
import metrics

STATUS_STALE_SECONDS = 20       # the core rewrites its status every 5 s
OLLAMA_TIMEOUT = 2.0

_version_cache: str | None = None


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def software_version() -> str:
    global _version_cache
    if _version_cache is None:
        try:
            out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 cwd=Path(__file__).parent, capture_output=True,
                                 text=True, timeout=3)
            _version_cache = out.stdout.strip() or "unbekannt"
        except (OSError, subprocess.SubprocessError):
            _version_cache = "unbekannt"
    return _version_cache


def system_info() -> dict:
    temp = _read("/sys/class/thermal/thermal_zone0/temp")
    uptime = _read("/proc/uptime")
    mem_total = mem_avail = None
    meminfo = _read("/proc/meminfo")
    if meminfo:
        for line in meminfo.splitlines():
            key, _, value = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                kb = int(value.split()[0])
                if key == "MemTotal":
                    mem_total = kb // 1024
                else:
                    mem_avail = kb // 1024
    try:
        load = [round(x, 2) for x in os.getloadavg()]
    except OSError:
        load = None
    disk = shutil.disk_usage(Path(config.MEMORY_DB_PATH).parent
                             if Path(config.MEMORY_DB_PATH).parent.exists() else "/")
    return {
        "cpu_temp_c": round(int(temp) / 1000, 1) if temp and temp.strip().isdigit() else None,
        "load": load,
        "cpus": os.cpu_count(),
        "memory_mb": {"total": mem_total, "available": mem_avail},
        "disk_free_gb": round(disk.free / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "uptime_s": int(float(uptime.split()[0])) if uptime else None,
        "version": software_version(),
    }


def core_status(now: float | None = None) -> dict:
    now = now or time.time()
    try:
        data = json.loads(Path(config.STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"running": False}
    fresh = now - float(data.get("updated", 0)) < STATUS_STALE_SECONDS
    return {"running": fresh, "started": data.get("started"),
            "input": data.get("input"), "audio": data.get("audio"),
            "channel": data.get("channel"),
            "dialog": data.get("dialog") if fresh else "aus",
            "dialog_restarts": data.get("dialog_restarts"),
            "last_restart": data.get("last_restart") or None}


def _is_local(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host in ("127.0.0.1", "localhost", "::1")


def ai_info() -> dict:
    base = config.LLM_API_BASE
    info = {"backend": "ollama" if _is_local(base) else "extern",
            "on_device": _is_local(base), "model": config.LLM_MODEL,
            "cloud_allowed": config.ALLOW_CLOUD_LLM, "reachable": None,
            "model_installed": None, "stt_model": config.WHISPER_MODEL,
            "voice": Path(config.PIPER_VOICE).stem}
    if not info["on_device"]:
        return info          # never contact an outside server from here
    root = base.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(root + "/api/tags", timeout=OLLAMA_TIMEOUT) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
        names = {m.get("name") for m in tags.get("models", [])}
        info["reachable"] = True
        info["model_installed"] = (config.LLM_MODEL in names
                                   or f"{config.LLM_MODEL}:latest" in names)
    except Exception:
        info["reachable"] = False
    return info


def collect(days: int = 7) -> dict:
    return {
        "device": system_info(),
        "services": {"core": core_status(), "api": {"running": True}},
        "ai": ai_info(),
        "latency_target_ms": 3000,
        "daily": metrics.daily_summary(days),
    }
