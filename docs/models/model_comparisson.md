# LLM Model Comparison — SeniorVoice

Benchmark results for LLM models tested for the SeniorVoice voice assistant.
Local models run on Raspberry Pi 5 (16 GB, ARM64, CPU-only via Ollama).
Cloud model accessed via API from the Pi.

## Ranking — Model Selection (Phase 1, isolated sequential testing, 02–03.05.2026)

| # | Model | Type | Size | tok/s | TTFT (warm) | Total (avg) | Cold TTFT | German Quality | Status |
|---|-------|------|------|-------|-------------|-------------|-----------|----------------|--------|
| 1 | gemma3:1b | Local | 815 MB | 3.8 | 1327ms | ~7.5s | 6.9s | Acceptable | **Selected** |
| 2 | gemma3n:e2b | Local | 5.6 GB | 2.4 | 2263ms | ~23s | 23s | Good | Runner-up |
| 3 | granite4.1:3b | Local | 2.1 GB | 2.2 | 1515ms | ~23s | 17s | Mixed | Weak |
| 4 | gemma3:4b | Local | 3.3 GB | 1.7 | 2516ms | ~22s | 14.7s | Excellent | Too slow |
| 5 | gemma3n:e4b | Local | 7.5 GB | 1.7 | 3037ms | ~29s | 37s | Good | Too slow |
| 6 | kimi-k2.6 | Cloud | — | 6.0 | 11719ms | ~13s | 8297ms | Excellent | Too slow (TTFT) |
| 7 | liquidai/lfm2.5-350m | Local | 379 MB | 4.6 | 1178ms | ~8s | 1524ms | Poor | Disqualified |
| 8 | llama3.1:8b | Local | 4.9 GB | 1.3 | 2689ms | ~60s | 34s | Poor | Disqualified |
| 9 | mistral:7b | Local | 4.4 GB | 1.3 | 2339ms | ~78s | 32s | Poor | Disqualified |
| 10 | gemma4:e2b | Local | 7.2 GB | 0.5 | 82s | ~97s | 101s | Excellent | Disqualified (thinking) |
| 11 | gemma4:e4b | Local | 9.6 GB | 0.3 | 175s | ~213s | 142s | Excellent | Disqualified (thinking) |
| -- | qwen3:4b | Local | 2.6 GB | ~0.1 | minutes | 4-12 min | -- | -- | Disqualified (thinking) |
| -- | qwen2.5:3b | Local | -- | 2.9 | ~500ms | -- | -- | Very poor | Disqualified (broken German) |

**After tuning (Phase 2):** `gemma3:1b-prod` @ 2.8 GHz OC reaches **10.4 tok/s** (+174% vs. baseline). See [Performance Tuning](#performance-tuning-gemma31b) section below.

## Test Conditions

- **Hardware**: Raspberry Pi 5, 16 GB RAM, NVMe SSD (Crucial P310), CPU-only inference
- **Local (Ollama)**: Q4_K_M quantization (unless noted), flash attention enabled
- **Cloud (Kimi)**: API call from Pi over WiFi, same prompt set
- **Prompts**: 4 German prompts x 3 rounds per model
- **Metrics**: Cold-start excluded from averages; first run = cold TTFT
- **Isolation**: Models tested sequentially with explicit unloading between tests (keep_alive=0)
- **Phase 1 (Model Selection)**: All models with 4 threads, default num_ctx, CPU Governor `ondemand`, 2.4 GHz stock clock
- **Phase 2 (Tuning)**: gemma3:1b variants with CPU Governor `performance`, thread/context/overclock tuning

## Detailed Results

### gemma3:1b -- CANDIDATE

- **Test date**: 02.05.2026 (isolated)
- **Size**: 815 MB RAM
- **Results**: 3.8 tok/s, TTFT 1327ms (warm avg), ~7.5s total
- **Pros**: Fastest model, smallest footprint, fast cold-start (6.9s)
- **Cons**: Uses "du" instead of "Sie", occasionally nonsensical ("Der Körper braucht stillen Input!"), simpler/shorter responses
- **German quality**: Acceptable -- grammatically mostly correct but informal tone, inconsistent phrasing quality
- **Sample**: "Schlafprobleme können oft durch Stress und weniger Schlaf sein."

### gemma3n:e2b -- CANDIDATE

- **Test date**: 02.05.2026 (isolated)
- **Size**: 5.6 GB RAM
- **Results**: 2.4 tok/s, TTFT 2263ms (warm avg), ~23s total
- **Pros**: Good German quality, proper "Sie" usage, natural phrasing, good jokes
- **Cons**: Large model (5.6 GB), slow cold-start (23s), longer responses
- **German quality**: Good -- proper Hochdeutsch, polite, natural
- **Sample**: "Warum können Geister so schlecht lügen? Weil man sie immer durchschaut!"

### granite4.1:3b -- WEAK

- **Test date**: 02.05.2026 (isolated)
- **Size**: 2.1 GB RAM
- **Results**: 2.2 tok/s, TTFT 1515ms (warm avg), ~23s total
- **German quality**: Mixed -- some correct responses but also broken German ("Lösche gerne einen süßen Kuchen zu dir!", "Warum flog der Affe mit einem Radar?")
- **Note**: IBM model, German not a primary training language

### gemma3:4b -- BEST QUALITY, TOO SLOW

- **Test date**: 02.05.2026 (isolated)
- **Size**: 3.3 GB RAM
- **Results**: 1.7 tok/s, TTFT 2516ms (warm avg), ~22s total
- **Note**: Previous session measured 2.4 tok/s under memory pressure -- isolated performance is actually lower
- **German quality**: Excellent -- correct Hochdeutsch, proper "Sie" form, natural warmth, appropriate sentence length

### gemma3n:e4b -- TOO SLOW

- **Test date**: 02.05.2026 (isolated)
- **Size**: 7.5 GB RAM
- **Results**: 1.7 tok/s, TTFT 3037ms (warm avg), ~29s total, 37s cold
- **German quality**: Good -- similar to gemma3n:e2b but larger/slower with no benefit
- **Note**: 7.5 GB is close to RAM limit; no advantage over e2b variant

### llama3.1:8b -- DISQUALIFIED

- **Test date**: 02.05.2026 (isolated)
- **Results**: 1.3 tok/s, TTFT 2689ms, ~60s total
- **Reason**: Too slow (60s per response), poor German (grammar errors, mixes "du/Sie", "Bewegung hilft bei dem Wetter mich besser zu fühlen"), verbose responses (77-113 tokens vs target 2-3 sentences)

### mistral:7b -- DISQUALIFIED

- **Test date**: 02.05.2026 (isolated)
- **Results**: 1.3 tok/s, TTFT 2339ms, ~78s total
- **Reason**: Too slow (78s per response), poor German ("Muskelstarkheit", "Verätzlichkeit", "Schlaps"), extremely verbose (100-176 tokens), ignores "kurz" instruction

### gemma4:e2b -- DISQUALIFIED (thinking model)

- **Test date**: 02.05.2026 (isolated)
- **Results**: 0.5 tok/s, TTFT 82s (warm!), ~97s total
- **Reason**: Internal chain-of-thought before output (82s TTFT warm). German quality is excellent but speed is completely unusable for a voice assistant.

### gemma4:e4b -- DISQUALIFIED (thinking model)

- **Test date**: 02.05.2026 (isolated)
- **Results**: 0.3 tok/s, TTFT 175s (warm!), ~213s total
- **Reason**: Even slower than e2b (3+ minutes per response). Same thinking model issue. Best German quality of all models tested, but 175s TTFT makes it impossible to use.

### liquidai/lfm2.5-350m -- DISQUALIFIED

- **Test date**: 03.05.2026 (Phase 2A)
- **Type**: Local (Ollama), Q8_0 quantization
- **Size**: 379 MB (354M parameters)
- **Architecture**: LFM2 (Liquid Foundation Model), 128k max context
- **Results**: 4.6 tok/s, TTFT 1178ms (warm avg), 1524ms cold
- **Pros**: Smallest model, fastest cold-start of all models (1524ms vs ~4800ms for gemma3:1b)
- **Cons**: German quality unacceptable for SeniorVoice — incoherent jokes, grammatical errors, poor instruction-following (gives 4 sentences when asked for 2)
- **German quality**: Poor — "Ein Kurzhändler kaufte ein Brot vom Markt" (incoherent joke), broken sentence structure
- **Note**: Despite promising speed metrics, German language output is not suitable for the elderly target audience

### kimi-k2.6 (Cloud) -- TOO SLOW (TTFT)

- **Test date**: 03.05.2026
- **Type**: Cloud API (Moonshot AI, `https://api.moonshot.ai/v1`)
- **Results**: 6.0 tok/s, TTFT 11719ms (warm avg), ~13s total
- **TTFT range**: 5489ms – 32679ms (highly variable)
- **Pros**: Excellent German quality, proper "Sie" form, natural Hochdeutsch, appropriate response length, good jokes
- **Cons**: TTFT of 5.5–32.7s means user waits too long before hearing anything; network-dependent; API sunset 25.05.2026
- **German quality**: Excellent -- perfect Hochdeutsch, polite, warm, varied responses
- **Sample**: "Bewegung hält Ihren Körper fit, stärkt Muskeln und Gelenke und hilft, Stürze zu vermeiden. Sie tut auch dem Herzen gut und hebt die Stimmung, damit Sie länger selbstständig bleiben."
- **Note**: Despite 6.0 tok/s (highest), the 11.7s avg TTFT makes it *slower* to first spoken word than gemma3:1b (1.3s TTFT + ~3s first sentence = ~4s)

### qwen3:4b -- DISQUALIFIED (thinking model)

- **Test date**: 02.05.2026
- **Reason**: Thinking model (Qwen3 4B Thinking 2507) with 4-12 minutes per response.

### qwen2.5:3b -- DISQUALIFIED

- **Test date**: 02.05.2026 (earlier session)
- **Reason**: Broken German ("stärkt den Immunsystem", "vielen frohsinstensten geburtsTag!"). 2.9 tok/s but unusable quality.

---

## Performance Tuning (gemma3:1b)

After selecting gemma3:1b as the primary candidate (Phase 1), systematic tuning was performed in Phase 2 (03.05.2026).

### Tuning Levers Tested

Each lever's impact is shown as the incremental change from applying that lever alone. Cumulative results in the [Full Tuning Benchmark Results](#full-tuning-benchmark-results) table below.

| Lever | Incremental Impact | Details |
|-------|-------------------|---------|
| CPU Governor `performance` | +24% (3.8 → 4.7 tok/s) | Fixes all 4 Cortex-A76 cores at max frequency instead of dynamic `ondemand` scaling |
| `num_thread=3` (vs. 4 default) | +73% (4.8 → 8.3 tok/s) | Leaving 1 core free for Ollama server + OS eliminates thread contention |
| `num_thread=2` | +46% (4.8 → 7.0 tok/s) | Better than 4 threads but 3 is the sweet spot |
| `num_ctx=512` (vs. 4096 default) | ~0% (4.7 → 4.6 tok/s) | No measurable throughput gain; but reduces KV-cache memory (sufficient for voice assistant) |
| Overclock 2.8 GHz | +32% (7.9 → 10.4 tok/s) | `arm_freq=2800`, `over_voltage_delta=25000`, temp stable at 62.6°C |
| Overclock 3.0 GHz | +3% vs. 2.8 GHz (10.4 → 10.7 tok/s) | Marginal gain at double voltage — rejected for production |

### Production Model: `gemma3:1b-prod` @ 2.8 GHz OC

Configuration: `FROM gemma3:1b` + `num_thread=3`, `num_ctx=512`, `num_batch=128`, CPU Governor `performance`, overclock 2.8 GHz

| Metric | Value |
|--------|-------|
| tok/s (warm) | **10.4** |
| TTFT warm | **698ms** |
| TTFT cold | 5138ms |
| Total improvement | **+174%** vs. original baseline (3.8 tok/s) |
| Temperature under load | 62.6°C, no throttling |
| Time to first spoken word (with streaming) | **~2.5s** (698ms TTFT + ~1.8s first sentence) |

### Full Tuning Benchmark Results

| # | Configuration | Clock | num_ctx | Threads | tok/s | TTFT warm | TTFT cold | vs. 3.8 Baseline |
|---|---------------|-------|---------|---------|-------|-----------|-----------|-------------------|
| 1 | **gemma3:1b-prod (OC)** | **2.8 GHz** | 512 | 3 | **10.4** | **698ms** | 5138ms | **+174%** |
| 2 | gemma3:1b-prod (OC) | 3.0 GHz | 512 | 3 | 10.7 | 664ms | 4932ms | +182% |
| 3 | gemma3:1b (3 threads) | 2.4 GHz | 4096 | 3 | 8.3 | 914ms | 4869ms | +118% |
| 4 | gemma3:1b-prod | 2.4 GHz | 512 | 3 | 8.1 | 915ms | 4811ms | +113% |
| 5 | gemma3:1b (2 threads) | 2.4 GHz | 4096 | 2 | 7.0 | 1003ms | 5984ms | +84% |
| 6 | gemma3:1b (stock) | 2.4 GHz | 4096 | 4 | 4.8 | 1183ms | 4739ms | +26% |
| 7 | gemma3:1b-tuned | 2.4 GHz | 512 | 4 | 4.6 | 1114ms | 4754ms | +21% |
| 8 | liquidai/lfm2.5-350m | 2.4 GHz | 4096 | 4 | 4.6 | 1178ms | 1524ms | +21% |

### Key Insights

1. **Thread count is the dominant lever** — reducing from 4 to 3 threads doubled throughput. On a 4-core CPU, using all cores for inference starves the Ollama server process and OS scheduler.
2. **CPU Governor gives a free +24%** — `performance` mode eliminates frequency ramp-up latency.
3. **Overclock stacks multiplicatively** — 2.8 GHz on top of thread tuning yields +174% total, more than the theoretical +17% from clock speed alone (LLM inference also benefits from faster memory controller).
4. **Context window reduction (`num_ctx`) has no throughput impact** — but is still useful for reducing memory footprint.
5. **3.0 GHz is not worth it** — only +3% over 2.8 GHz at double the voltage delta; poor risk/reward for a 24/7 device.

---

## Recommendation

**Production model: `gemma3:1b-prod` @ 2.8 GHz overclock.**

After systematic model selection (12 models) and performance tuning, `gemma3:1b-prod` delivers the best balance of speed and German quality for the SeniorVoice voice assistant:

| Metric | Value |
|--------|-------|
| Throughput | 10.4 tok/s (warm) |
| Time to first token | 698ms (warm) |
| Time to first spoken word | ~2.5s (with streaming TTS) |
| German quality | Acceptable (needs system prompt tuning for "Sie" form) |
| RAM usage | 815 MB |
| Temperature | 62.6°C under load, no throttling |

### Why not the alternatives?

| Model | Reason for rejection |
|-------|---------------------|
| Kimi k2.6 (Cloud) | 11.7s avg TTFT (up to 32.7s); API sunset 25.05.2026 |
| gemma3:4b | Excellent German but 1.7 tok/s — too slow even after tuning |
| gemma3n:e2b | Good German but 5.6 GB RAM + 23s per response |
| gemma4 series | Thinking models with 82–175s TTFT — unusable |
| llama3.1:8b / mistral:7b | Poor German + too slow |
| qwen2.5:3b / qwen3:4b | Broken German / thinking model |
| liquidai/lfm2.5-350m | Fast but incoherent German |

### Remaining steps

- System prompt optimization for gemma3:1b (enforce "Sie" form, constrain response length)
- Ollama as systemd service with model pre-load (eliminate ~5.1s cold-start TTFT)
- Pipeline as systemd service (auto-start on boot, depends on Ollama)
- `gemma3:1b-prod` integration into pipeline config (`LLM_MODEL=gemma3:1b-prod`)

---

*Last updated: 03.05.2026*
