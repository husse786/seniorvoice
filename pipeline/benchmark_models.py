#!/usr/bin/env python3
"""Benchmark LLM models for SeniorVoice — measures tok/s, TTFT, and German quality.

Works with both local Ollama and cloud APIs (Kimi, OpenAI-compatible).
Models are tested one-by-one with explicit unloading between tests to avoid
memory pressure on the Pi.

Usage:
    # Benchmark local Ollama models (isolated, one-by-one)
    python benchmark_models.py gemma3:4b gemma3:1b llama3.2:3b --rounds 3 2>/dev/null

    # Benchmark cloud API model
    python benchmark_models.py kimi-k2.6 --api-base https://api.moonshot.ai/v1 --api-key sk-...

    # Detailed per-round output
    python benchmark_models.py gemma3:4b --rounds 3 --detailed

    # Export results as JSON (for Grafana / analytics)
    python benchmark_models.py gemma3:4b gemma3:1b --json results.json
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path

from logging_config import get_logger, setup_logging
from config import DB_PATH

log = get_logger("benchmark")

# ---------------------------------------------------------------------------
# SQLite logging (best-effort — never crashes the benchmark)
# ---------------------------------------------------------------------------

_BENCHMARK_INIT_SQL = """\
CREATE TABLE IF NOT EXISTS benchmark_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    run_id            TEXT NOT NULL,
    model             TEXT NOT NULL,
    model_variant     TEXT NOT NULL DEFAULT 'stock',
    prompt            TEXT NOT NULL,
    prompt_number     INTEGER NOT NULL,
    round_number      INTEGER NOT NULL,
    tokens_per_second REAL,
    ttft_ms           REAL,
    total_ms          REAL,
    token_count       INTEGER,
    response_text     TEXT,
    is_cold_start     INTEGER NOT NULL DEFAULT 0,
    error             TEXT DEFAULT NULL,
    api_base          TEXT,
    num_rounds        INTEGER,
    timeout           INTEGER
);

CREATE TABLE IF NOT EXISTS benchmark_aggregates (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    run_id            TEXT NOT NULL,
    model             TEXT NOT NULL,
    model_variant     TEXT NOT NULL DEFAULT 'stock',
    valid_count       INTEGER,
    error_count       INTEGER,
    avg_tps           REAL,
    avg_ttft_ms       REAL,
    avg_total_ms      REAL,
    min_ttft_ms       REAL,
    max_ttft_ms       REAL,
    cold_ttft_ms      REAL,
    api_base          TEXT,
    num_rounds        INTEGER
);
"""


def _get_db_connection() -> sqlite3.Connection:
    """Open SQLite DB and ensure benchmark tables exist."""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_BENCHMARK_INIT_SQL)
    return conn


def db_insert_result(run_id: str, model: str, variant: str, prompt: str,
                     prompt_number: int, round_number: int, result: dict,
                     is_cold_start: bool, api_base: str, num_rounds: int,
                     timeout: int) -> None:
    """Insert a single benchmark run result. Best-effort."""
    try:
        conn = _get_db_connection()
        try:
            conn.execute(
                "INSERT INTO benchmark_results "
                "(run_id, model, model_variant, prompt, prompt_number, round_number, "
                "tokens_per_second, ttft_ms, total_ms, token_count, response_text, "
                "is_cold_start, error, api_base, num_rounds, timeout) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, model, variant, prompt, prompt_number, round_number,
                 result.get("tokens_per_second"), result.get("ttft_ms"),
                 result.get("total_ms"), result.get("token_count"),
                 result.get("response"), int(is_cold_start),
                 result.get("error"), api_base, num_rounds, timeout),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        log.warning("DB insert failed (result): %s", e)


def db_insert_aggregate(run_id: str, model: str, variant: str,
                        stats: dict, api_base: str, num_rounds: int) -> None:
    """Insert aggregate stats for a model. Best-effort."""
    try:
        conn = _get_db_connection()
        try:
            conn.execute(
                "INSERT INTO benchmark_aggregates "
                "(run_id, model, model_variant, valid_count, error_count, "
                "avg_tps, avg_ttft_ms, avg_total_ms, min_ttft_ms, max_ttft_ms, "
                "cold_ttft_ms, api_base, num_rounds) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, model, variant,
                 stats.get("valid"), stats.get("errors"),
                 stats.get("avg_tps"), stats.get("avg_ttft_ms"),
                 stats.get("avg_total_ms"), stats.get("min_ttft_ms"),
                 stats.get("max_ttft_ms"), stats.get("cold_ttft_ms"),
                 api_base, num_rounds),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        log.warning("DB insert failed (aggregate): %s", e)


TEST_PROMPTS = [
    "Erklaere mir in zwei Saetzen, warum Bewegung im Alter wichtig ist.",
    "Was kann ich gegen Schlafprobleme tun? Antworte kurz und einfach.",
    "Erzaehle mir einen kurzen Witz auf Deutsch.",
    "Ich habe heute Geburtstag. Was koenntest du mir wuenschen?",
]

SYSTEM_PROMPT = (
    "Du bist SeniorAgent, ein freundlicher Sprachassistent fuer aeltere Menschen. "
    "Antworte auf Deutsch, kurz und klar (2-3 Saetze)."
)


def ollama_unload(api_base: str, model: str) -> None:
    """Unload a model from Ollama memory via keep_alive=0."""
    # Extract Ollama base (strip /v1 suffix if present)
    base = api_base.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]

    url = f"{base}/api/generate"
    payload = {"model": model, "keep_alive": 0}
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception:
        pass  # Best-effort; model might not be loaded


def benchmark_stream(api_base: str, model: str, prompt: str, api_key: str = "", timeout: int = 120) -> dict:
    """Stream a prompt and measure timing metrics."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    payload = {"model": model, "messages": messages, "stream": True}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{api_base}/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    t_start = time.perf_counter()
    ttft = None
    tokens = []

    try:
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
                    if ttft is None:
                        ttft = (time.perf_counter() - t_start) * 1000
                    tokens.append(delta)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        return {"error": str(e), "model": model, "prompt": prompt[:50]}

    t_total = (time.perf_counter() - t_start) * 1000
    full_text = "".join(tokens)
    token_count = len(tokens)  # SSE chunks approximate token count

    return {
        "model": model,
        "prompt": prompt[:50],
        "response": full_text,
        "token_count": token_count,
        "ttft_ms": round(ttft, 1) if ttft else None,
        "total_ms": round(t_total, 1),
        "tokens_per_second": round(token_count / (t_total / 1000), 1) if t_total > 0 else 0,
    }


def compute_stats(results: list[dict]) -> dict:
    """Compute aggregate stats from a list of results, excluding cold-start (first run)."""
    valid = [r for r in results if "error" not in r]
    errors = len(results) - len(valid)

    if not valid:
        return {"valid": 0, "errors": errors}

    # Separate cold-start (first result) from warm results
    warm = valid[1:] if len(valid) > 1 else valid

    avg_tps = sum(r["tokens_per_second"] for r in warm) / len(warm)
    avg_ttft = sum(r["ttft_ms"] for r in warm) / len(warm)
    avg_total = sum(r["total_ms"] for r in warm) / len(warm)
    min_ttft = min(r["ttft_ms"] for r in warm)
    max_ttft = max(r["ttft_ms"] for r in warm)
    cold_ttft = valid[0]["ttft_ms"] if valid else None

    return {
        "valid": len(valid),
        "errors": errors,
        "avg_tps": round(avg_tps, 1),
        "avg_ttft_ms": round(avg_ttft, 0),
        "avg_total_ms": round(avg_total, 0),
        "min_ttft_ms": round(min_ttft, 0),
        "max_ttft_ms": round(max_ttft, 0),
        "cold_ttft_ms": round(cold_ttft, 0) if cold_ttft else None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark LLM models for SeniorVoice (Ollama + Cloud)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("models", nargs="+", help="Model names to benchmark")
    parser.add_argument("--api-base", default="http://localhost:11434/v1",
                        help="API base URL (default: Ollama localhost)")
    parser.add_argument("--api-key", default="", help="API key (for cloud backends)")
    parser.add_argument("--rounds", type=int, default=3, help="Runs per prompt (default: 3)")
    parser.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")
    parser.add_argument("--detailed", action="store_true", help="Show per-round metrics")
    parser.add_argument("--json", metavar="FILE", help="Export raw results to JSON file")
    parser.add_argument("--no-db", action="store_true", help="Skip SQLite logging")
    parser.add_argument("--variant", default="stock",
                        help="Model variant tag, e.g. 'stock', 'tuned', 'quantized' (default: stock)")
    args = parser.parse_args()

    setup_logging()
    run_id = uuid.uuid4().hex[:12]
    use_db = not args.no_db

    total_runs = len(args.models) * len(TEST_PROMPTS) * args.rounds
    print(f"\n  SeniorVoice LLM Benchmark")
    print(f"  Models: {', '.join(args.models)}")
    print(f"  API: {args.api_base}")
    print(f"  Variant: {args.variant}")
    print(f"  Prompts: {len(TEST_PROMPTS)} x {args.rounds} rounds = {total_runs} total runs")
    print(f"  Mode: Sequential (unload between models)")
    print(f"  DB: {DB_PATH if use_db else 'disabled (--no-db)'}")
    print(f"  Run ID: {run_id}")
    print(f"  {'=' * 60}\n")

    all_results: dict[str, list[dict]] = {}

    for model_idx, model in enumerate(args.models, 1):
        # Unload any previously loaded model to free RAM
        if model_idx > 1 and not args.api_key:
            prev_model = args.models[model_idx - 2]
            ollama_unload(args.api_base, prev_model)
            time.sleep(2)  # Let Ollama release memory

        print(f"  [{model_idx}/{len(args.models)}] {model}", end="", flush=True)

        model_results = []
        error_count = 0
        run_counter = 0

        for i, prompt in enumerate(TEST_PROMPTS):
            for r in range(args.rounds):
                result = benchmark_stream(
                    api_base=args.api_base,
                    model=model,
                    prompt=prompt,
                    api_key=args.api_key,
                    timeout=args.timeout,
                )
                model_results.append(result)
                is_cold = run_counter == 0
                run_counter += 1

                # DB: insert individual result
                if use_db:
                    db_insert_result(
                        run_id=run_id, model=model, variant=args.variant,
                        prompt=prompt, prompt_number=i + 1, round_number=r + 1,
                        result=result, is_cold_start=is_cold,
                        api_base=args.api_base, num_rounds=args.rounds,
                        timeout=args.timeout,
                    )

                if "error" in result:
                    error_count += 1
                    print("x", end="", flush=True)
                    break
                else:
                    print(".", end="", flush=True)

                    if args.detailed:
                        print(f"\n        R{r+1} P{i+1}: "
                              f"{result['tokens_per_second']:.1f} tok/s | "
                              f"TTFT {result['ttft_ms']:.0f}ms | "
                              f"Total {result['total_ms']:.0f}ms", end="", flush=True)

        # Show inline summary for this model
        stats = compute_stats(model_results)
        if stats["valid"] > 0:
            print(f"  -> {stats['avg_tps']} tok/s, TTFT {stats['avg_ttft_ms']:.0f}ms")
        else:
            print(f"  -> FAILED ({error_count} errors)")

        # DB: insert aggregate stats for this model
        if use_db:
            db_insert_aggregate(
                run_id=run_id, model=model, variant=args.variant,
                stats=stats, api_base=args.api_base, num_rounds=args.rounds,
            )

        all_results[model] = model_results

    # Unload last model
    if not args.api_key:
        ollama_unload(args.api_base, args.models[-1])

    # --- RANKING TABLE ---
    print(f"\n  {'=' * 60}")
    print(f"  RANKING (sorted by tok/s, excluding cold-start)")
    print(f"  {'=' * 60}")
    print(f"  {'#':<3} {'Model':<20} {'tok/s':>7} {'TTFT':>8} {'Total':>9} {'Cold TTFT':>10} {'Err':>4}")
    print(f"  {'-' * 3} {'-' * 20} {'-' * 7} {'-' * 8} {'-' * 9} {'-' * 10} {'-' * 4}")

    # Build ranking data
    ranking = []
    for model, results in all_results.items():
        stats = compute_stats(results)
        stats["model"] = model
        ranking.append(stats)

    # Sort by avg tok/s descending (failed models last)
    ranking.sort(key=lambda s: s.get("avg_tps", 0), reverse=True)

    for rank, stats in enumerate(ranking, 1):
        model = stats["model"]
        if stats["valid"] == 0:
            print(f"  {rank:<3} {model:<20} {'FAILED':>7} {'-':>8} {'-':>9} {'-':>10} {stats['errors']:>4}")
        else:
            cold = f"{stats['cold_ttft_ms']:.0f}ms" if stats["cold_ttft_ms"] else "-"
            print(f"  {rank:<3} {model:<20} {stats['avg_tps']:>6.1f} "
                  f"{stats['avg_ttft_ms']:>6.0f}ms "
                  f"{stats['avg_total_ms']:>7.0f}ms "
                  f"{cold:>10} {stats['errors']:>4}")

    # --- QUALITY SAMPLES ---
    print(f"\n  {'=' * 60}")
    print(f"  GERMAN QUALITY SAMPLES (last response per model)")
    print(f"  {'=' * 60}")

    for model, results in all_results.items():
        # Get last valid response for each prompt
        valid = [r for r in results if "error" not in r]
        if not valid:
            print(f"\n  [{model}] - no valid responses")
            continue

        print(f"\n  [{model}]")
        seen_prompts = set()
        for r in reversed(valid):
            prompt_key = r["prompt"]
            if prompt_key not in seen_prompts:
                seen_prompts.add(prompt_key)
                # Truncate response to keep output readable
                resp = r["response"].replace("\n", " ").strip()
                if len(resp) > 120:
                    resp = resp[:117] + "..."
                print(f"    -> {resp}")
            if len(seen_prompts) >= 2:  # Show 2 samples per model
                break

    # --- RECOMMENDATION ---
    if len(ranking) > 1 and ranking[0]["valid"] > 0:
        best = ranking[0]
        print(f"\n  {'=' * 60}")
        print(f"  RECOMMENDATION: {best['model']}")
        print(f"  {best['avg_tps']} tok/s avg | {best['avg_ttft_ms']:.0f}ms TTFT (warm)")
        print(f"  Review German quality samples above to confirm.")
        print(f"  {'=' * 60}")

    print()

    # --- JSON EXPORT ---
    if args.json:
        export = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "config": {
                "api_base": args.api_base,
                "rounds": args.rounds,
                "timeout": args.timeout,
                "prompts": TEST_PROMPTS,
            },
            "models": {},
        }
        for model, results in all_results.items():
            stats = compute_stats(results)
            export["models"][model] = {
                "stats": stats,
                "runs": results,
            }

        with open(args.json, "w") as f:
            json.dump(export, f, indent=2, ensure_ascii=False)
        print(f"  Results exported to: {args.json}\n")


if __name__ == "__main__":
    main()
