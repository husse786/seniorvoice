# LLM Model Comparison — SeniorVoice

Benchmark results for LLM models tested for the SeniorVoice voice assistant.
Local models run on Raspberry Pi 5 (16 GB, ARM64, CPU-only via Ollama).
Cloud model accessed via API from the Pi.

## Ranking (isolated sequential testing, 02–03.05.2026)

| # | Model | Type | Size | tok/s | TTFT (warm) | Total (avg) | Cold TTFT | German Quality | Status |
|---|-------|------|------|-------|-------------|-------------|-----------|----------------|--------|
| 1 | gemma3:1b | Local | 815 MB | 3.8 | 1327ms | ~7.5s | 6.9s | Acceptable | Candidate |
| 2 | gemma3n:e2b | Local | 5.6 GB | 2.4 | 2263ms | ~23s | 23s | Good | Candidate |
| 3 | granite4.1:3b | Local | 2.1 GB | 2.2 | 1515ms | ~23s | 17s | Mixed | Weak |
| 4 | gemma3:4b | Local | 3.3 GB | 1.7 | 2516ms | ~22s | 14.7s | Excellent | Too slow |
| 5 | gemma3n:e4b | Local | 7.5 GB | 1.7 | 3037ms | ~29s | 37s | Good | Too slow |
| 6 | kimi-k2.6 | Cloud | — | 6.0 | 11719ms | ~13s | 8297ms | Excellent | Too slow (TTFT) |
| 7 | llama3.1:8b | Local | 4.9 GB | 1.3 | 2689ms | ~60s | 34s | Poor | Disqualified |
| 8 | mistral:7b | Local | 4.4 GB | 1.3 | 2339ms | ~78s | 32s | Poor | Disqualified |
| 9 | gemma4:e2b | Local | 7.2 GB | 0.5 | 82s | ~97s | 101s | Excellent | Disqualified (thinking) |
| 10 | gemma4:e4b | Local | 9.6 GB | 0.3 | 175s | ~213s | 142s | Excellent | Disqualified (thinking) |
| -- | qwen3:4b | Local | 2.6 GB | ~0.1 | minutes | 4-12 min | -- | -- | Disqualified (thinking) |
| -- | qwen2.5:3b | Local | -- | 2.9 | ~500ms | -- | -- | Very poor | Disqualified (broken German) |

## Test Conditions

- **Hardware**: Raspberry Pi 5, 16 GB RAM, NVMe SSD (Crucial P310), CPU-only inference
- **Local (Ollama)**: Q4_K_M quantization, 4 threads, flash attention enabled
- **Cloud (Kimi)**: API call from Pi over WiFi, same prompt set
- **Prompts**: 4 German prompts x 3 rounds per model
- **Metrics**: Cold-start excluded from averages; first run = cold TTFT
- **Isolation**: Models tested sequentially with explicit unloading between tests (keep_alive=0)

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

## Recommendation

**Neither local nor cloud delivers ideal speed + quality for a voice assistant.**

- Kimi Cloud has excellent German but unacceptable TTFT (11.7s avg, up to 32.7s)
- Local models are faster to first token but weaker in German quality

Best compromise candidates:
1. **gemma3:1b** (3.8 tok/s, Local) -- fastest to first spoken word (~4s with streaming), German quality needs improvement via system prompt
2. **gemma3n:e2b** (2.4 tok/s, Local) -- good German, but 23s per response is borderline

Next steps to explore:
- `num_ctx` reduction (512 instead of default) for tok/s boost
- System prompt optimization for gemma3:1b (force "Sie" form, sentence length)
- Thread count tuning (Pi 5 has 4 Cortex-A76 cores)
- Ollama systemd service with model pre-load (eliminate cold-start)

---

*Last updated: 03.05.2026*
