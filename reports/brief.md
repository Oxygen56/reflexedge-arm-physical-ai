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
- Safety gate: no new false-negative brake decisions on the frozen test corpus; accuracy loss <= 0.5 percentage points.
- Performance gate: repeated warm benchmark, p50/p95 latency and throughput derived from raw JSON.

## Current state

- Official deadline and live Join availability were reconfirmed on 2026-08-10; joining awaits the required click-time confirmation.
- The full sensor-to-action pipeline runs on a real Apple M4 Arm64 host with NEON and DotProd available.
- Five independent, alternating-order paired trials show median raw sensor-to-action speedups of 2.83× p50, 3.01× p95, and 2.76× throughput; every trial improved p95 and throughput.
- The 1.25M-inference final run shows 1,966.12 ns → 402.34 ns p50 and 5,480.60 ns → 700.50 ns p95 for the raw sensor-to-action path. Model bytes fall 72.60%.
- Optimized test accuracy is 98.20% versus 98.24% baseline, with zero added false negatives. Final-run peak process RSS increased 2.60%; direct joules were not measured.
- Tests, data audit, rights gate, public replay site, and a 57-second evidence video are complete locally. Public hosting, repository publication, Join, and final Devpost submission remain external actions.
