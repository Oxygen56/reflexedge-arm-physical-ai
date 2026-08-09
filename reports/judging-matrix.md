# Judging matrix

| Criterion | Judge-facing proof | Acceptance condition |
| --- | --- | --- |
| Technological implementation (40) | scalar FP32 baseline, int8 NEON kernel, compiler flags, Arm64 hardware log, raw benchmark JSON, safety regression tests | real Arm64 run; reproducible speed and model-size improvement; no new critical false negatives |
| UX / DX (15) | `./scripts/reproduce.sh`, deterministic replay, expected output, clear failure messages | fresh checkout reaches the same report without paid services or secrets |
| Potential impact (20) | reusable sensor schema, portable scalar fallback, explicit safety gate, machine-readable evidence | another robotics developer can replace the simulator with a live adapter without changing the evaluation contract |
| WOW (25) | live sensor fan, risk meter, brake action, before/after metrics on one screen | core idea and verified improvement are visible in the first 30 seconds of the demo |

## Disqualifier matrix

| Risk | Preventive gate |
| --- | --- |
| Merely runs on Arm | baseline-to-optimized comparison is mandatory |
| Fabricated hardware or power result | raw host fingerprint and logs; direct joules omitted until metered |
| Unsafe quantization regression | false-negative and action-agreement gate |
| Missing public rights | MIT license plus dependency/data ledger |
| Judge cannot access hardware | deterministic offline replay and expected-output package |
| AI assistance undisclosed | precise Codex disclosure draft held for the actual form; never guessed |
