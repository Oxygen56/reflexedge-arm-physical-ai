# Competition Brief

## Identity

- Contest: Arm Create: AI Optimization Challenge
- Platform: Devpost
- URL: https://arm-ai-optimization-challenge.devpost.com/
- Submission deadline: 2026-08-14 16:00 PDT / 2026-08-15 07:00 Beijing
- Track: Physical AI
- Project: ReflexEdge

## Winning thesis

ReflexEdge is a safety-oriented, judge-replayable Physical AI system: range-sensor input becomes learned collision-risk inference and then a brake/hold/go action. The optimization story is controlled rather than anecdotal: scalar FP32 is frozen before int8 Arm NEON work; both engines receive the same frames and are compared on latency, throughput, CPU-time energy proxy, peak memory, model bytes, accuracy, action agreement, and safety-critical false negatives.

## Judging target

- Technological implementation (40): real Arm64 execution, handwritten NEON dot product, raw logs, safety equivalence gate.
- UX/DX (15): one-command reproduction, no paid service, deterministic judge replay.
- Potential impact (20): reusable evaluation harness for robotics and embedded safety controllers.
- WOW (25): a visual sensor-to-brake replay with live performance and safety proof, understandable inside 30 seconds.

## Rules and constraints

- Public MIT or Apache-2.0 repository required.
- English description, Arm build/run/validation instructions, and free judge access required.
- Third-party tools, models, APIs, and data require authorization and compatible licenses.
- Demonstration video should be public and under three minutes.
- Published rules allow third-party technical assistance and do not publicly ban Codex; any submission-form disclosure must be answered truthfully.
- Do not claim direct energy in joules without a supported meter. Do not claim hardware runs without raw Arm64 logs.

## Validation design

- Data: deterministic, in-repository synthetic 64-beam range and closing-speed frames; no private or external dataset.
- Split: seed-derived, fixed train/test files; test rows are never used for gradient updates.
- Baseline: scalar FP32 logistic risk model, vectorization disabled at compile time.
- Optimization: symmetric int8 weights/features plus Arm NEON dot-product kernel.
- Safety gate: zero int8 BRAKE false-negative disagreements versus scalar and zero added ground-truth false negatives on the frozen test corpus; accuracy loss <= 0.5 percentage points.
- Performance gate: repeated warm benchmark, p50/p95 latency and throughput derived from raw JSON.

## Current state

- The official deadline is 2026-08-15 07:00 Beijing, and Devpost Join is verified for account `Oxygen56`.
- The full sensor-to-action pipeline runs on a real Apple M4 Arm64 host with NEON and DotProd available.
- Five independent, alternating-order paired trials show median raw sensor-to-action speedups of 2.39× p50, 6.06× p95, and 3.03× throughput; every trial improved p95 and throughput.
- The 1.25M-inference final run shows 2,611.97 ns → 1,031.25 ns p50 and 10,738.54 ns → 4,703.13 ns p95 (raw value: 4,703.125 ns) for the raw sensor-to-action path. Model bytes fall 72.60%.
- Optimized test accuracy is 98.20% versus 98.24% baseline. Across 2,500 frozen test frames, 15 exact `GO` / `HOLD` / `BRAKE` commands differ; three cross the BRAKE boundary and all three are additional int8 BRAKE decisions. Int8 drops zero scalar BRAKE decisions and adds zero ground-truth false negatives. Final-run peak process RSS increased 3.36%; direct joules were not measured.
- Tests, data audit, rights gate, public repository, replay site, and corrected 62.4-second evidence video are complete and publicly revalidated. The public video is https://youtu.be/hFZvz4ntvbc. Devpost Join, the saved 4/5-step draft, and the uploaded project thumbnail are verified. Arm Developer Program membership, the final rules confirmation, and final submission remain external gates.
