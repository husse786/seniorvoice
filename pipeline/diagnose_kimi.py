"""
Kimi API diagnostic script — run on the Pi to verify that LLM calls actually
reach the Moonshot Cloud and to measure realistic cloud latency.

Usage on Pi:
    cd ~/seniorvoice/pipeline
    source ../.venv/bin/activate
    export LLM_API_KEY=<moonshot-key>
    python diagnose_kimi.py

What it checks:
  1. Whether LLM_API_KEY is set
  2. Network reachability of api.moonshot.ai
  3. Actual Kimi API call — measures TTFT + total latency
  4. Local Ollama call (if available) for comparison
  5. Prints a clear verdict: Cloud confirmed / Fell back to local
"""

import json
import os
import time
import urllib.error
import urllib.request


KIMI_API_BASE = os.getenv("LLM_API_BASE", "https://api.moonshot.ai/v1")
KIMI_API_KEY = os.getenv("LLM_API_KEY", "")
KIMI_MODEL = os.getenv("LLM_MODEL", "kimi-k2.6")
KIMI_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))

OLLAMA_API_BASE = os.getenv("LLM_OLLAMA_API_BASE", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("LLM_OLLAMA_MODEL", "gemma3:1b-prod")

TEST_PROMPT = "Erkläre mir in zwei Sätzen, was ein Sprachassistent ist."
TEST_MESSAGES = [
    {"role": "system", "content": "Du bist ein hilfreicher Assistent. Antworte kurz auf Deutsch."},
    {"role": "user", "content": TEST_PROMPT},
]


def _post_streaming(api_base: str, model: str, api_key: str, timeout: int):
    """Stream tokens from an OpenAI-compatible endpoint, return (ttft_ms, total_ms, token_count, full_text)."""
    url = f"{api_base}/chat/completions"
    payload = {"model": model, "messages": TEST_MESSAGES, "stream": True}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    t_start = time.perf_counter()
    ttft_ms = None
    token_count = 0
    full_text = ""

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            delta = chunk["choices"][0]["delta"].get("content", "")
            if delta:
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - t_start) * 1000
                token_count += 1
                full_text += delta

    total_ms = (time.perf_counter() - t_start) * 1000
    return ttft_ms, total_ms, token_count, full_text


def check_network(hostname: str) -> bool:
    """Quick TCP reachability check on port 443."""
    import socket
    try:
        socket.setdefaulttimeout(5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((hostname, 443))
        return True
    except Exception:
        return False


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def main():
    print("\nSeniorVoice — Kimi API Diagnostic")
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # ── 1. API Key Check ─────────────────────────────────────────
    section("1. API Key")
    if KIMI_API_KEY:
        masked = KIMI_API_KEY[:6] + "..." + KIMI_API_KEY[-4:]
        print(f"  ✅  LLM_API_KEY set: {masked}")
    else:
        print("  ❌  LLM_API_KEY is NOT set!")
        print("      Without a key, llm_backend.py will NOT add an Authorization header.")
        print("      Moonshot API will return HTTP 401 → backend falls back to local Ollama.")
        print("      → This is likely why tests appeared 'slow': they ran locally, not in cloud.")

    # ── 2. Network Reachability ───────────────────────────────────
    section("2. Network: api.moonshot.ai")
    reachable = check_network("api.moonshot.ai")
    if reachable:
        print("  ✅  api.moonshot.ai reachable on port 443")
    else:
        print("  ❌  api.moonshot.ai NOT reachable — check internet connection / firewall")

    # ── 3. Kimi API Call ─────────────────────────────────────────
    section(f"3. Kimi Cloud API Call  ({KIMI_MODEL})")
    if not KIMI_API_KEY:
        print("  ⚠️   Skipping — no API key set (would get HTTP 401)")
        kimi_ok = False
        ttft_kimi = total_kimi = tok_kimi = None
        kimi_text = ""
    else:
        print(f"  Endpoint : {KIMI_API_BASE}/chat/completions")
        print(f"  Model    : {KIMI_MODEL}")
        print(f"  Prompt   : {TEST_PROMPT}")
        print(f"  Timeout  : {KIMI_TIMEOUT}s")
        print("  Sending request ... (streaming)")
        try:
            ttft_kimi, total_kimi, tok_kimi, kimi_text = _post_streaming(
                KIMI_API_BASE, KIMI_MODEL, KIMI_API_KEY, KIMI_TIMEOUT
            )
            kimi_ok = True
            tok_per_s = tok_kimi / (total_kimi / 1000) if total_kimi else 0
            print(f"  ✅  Response received!")
            print(f"      TTFT       : {ttft_kimi:.0f} ms")
            print(f"      Total time : {total_kimi:.0f} ms")
            print(f"      Tokens     : {tok_kimi}")
            print(f"      tok/s      : {tok_per_s:.1f}")
            print(f"      Reply      : {kimi_text[:200].strip()}")
        except urllib.error.HTTPError as e:
            kimi_ok = False
            ttft_kimi = total_kimi = tok_kimi = None
            kimi_text = ""
            print(f"  ❌  HTTP {e.code}: {e.reason}")
            if e.code == 401:
                print("      → API key rejected. Verify LLM_API_KEY value is correct.")
            elif e.code == 429:
                print("      → Rate limit hit. Wait and retry.")
        except Exception as e:
            kimi_ok = False
            ttft_kimi = total_kimi = tok_kimi = None
            kimi_text = ""
            print(f"  ❌  Error: {e}")

    # ── 4. Local Ollama Call ──────────────────────────────────────
    section(f"4. Local Ollama Call  ({OLLAMA_MODEL})")
    print(f"  Endpoint : {OLLAMA_API_BASE}/chat/completions")
    print(f"  Model    : {OLLAMA_MODEL}")
    print("  Sending request ... (streaming)")
    try:
        ttft_ollama, total_ollama, tok_ollama, ollama_text = _post_streaming(
            OLLAMA_API_BASE, OLLAMA_MODEL, "", 60
        )
        ollama_ok = True
        tok_per_s_local = tok_ollama / (total_ollama / 1000) if total_ollama else 0
        print(f"  ✅  Response received!")
        print(f"      TTFT       : {ttft_ollama:.0f} ms")
        print(f"      Total time : {total_ollama:.0f} ms")
        print(f"      Tokens     : {tok_ollama}")
        print(f"      tok/s      : {tok_per_s_local:.1f}")
        print(f"      Reply      : {ollama_text[:200].strip()}")
    except Exception as e:
        ollama_ok = False
        ttft_ollama = total_ollama = tok_ollama = None
        print(f"  ⚠️   Ollama not available: {e}")
        print("      (This is fine if Ollama is not running)")

    # ── 5. Verdict ────────────────────────────────────────────────
    section("5. Verdict")
    if kimi_ok:
        tok_per_s_cloud = tok_kimi / (total_kimi / 1000) if total_kimi else 0
        print(f"  ✅  CLOUD CONFIRMED — Kimi API responded")
        print(f"      Cloud TTFT  : {ttft_kimi:.0f} ms")
        print(f"      Cloud tok/s : {tok_per_s_cloud:.1f}")
        if ollama_ok:
            tok_per_s_local2 = tok_ollama / (total_ollama / 1000) if total_ollama else 0
            print(f"      Local TTFT  : {ttft_ollama:.0f} ms")
            print(f"      Local tok/s : {tok_per_s_local2:.1f}")
            if ttft_kimi and ttft_ollama and ttft_kimi > ttft_ollama:
                print(f"\n  ℹ️   Cloud TTFT is {ttft_kimi/ttft_ollama:.1f}× slower than local Ollama.")
                print("      Local gemma3:1b-prod has lower TTFT — consistent with benchmark findings.")
    elif not KIMI_API_KEY:
        print("  ❌  CLOUD NOT REACHED — LLM_API_KEY missing")
        print("      → Previous 'Kimi' tests likely ran on local Ollama (silent fallback).")
        print("      → Set LLM_API_KEY and re-run this script to confirm cloud access.")
        if ollama_ok:
            print(f"\n  ✅  Local Ollama IS running ({OLLAMA_MODEL})")
            print("      Your previous tests used this, not the Kimi cloud API.")
    else:
        print("  ❌  CLOUD NOT REACHED — API returned an error")
        print("      Check error details above.")

    print("\n")


if __name__ == "__main__":
    main()
