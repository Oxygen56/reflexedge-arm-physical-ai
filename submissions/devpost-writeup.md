# ReflexEdge

## Judge quick path

- See the complete sensor-to-action story first: https://reflexedge-arm-ai.jiangth99.chatgpt.site
- Inspect or reproduce every claim: https://github.com/Oxygen56/reflexedge-arm-physical-ai
- Headline evidence: five alternating-order paired Arm64 trials produced a 3.01× median p95 speedup, with every trial faster and zero added false-negative brake decisions.

## Inspiration

Physical AI becomes dangerous when optimization is treated as a speed-only exercise. A quantized model can be faster while silently changing the action that matters. ReflexEdge is a compact, auditable collision reflex: a 64-beam range frame enters a learned model and leaves as a deterministic `GO`, `HOLD`, or `BRAKE` command, with performance and safety evaluated together.

## What it does

ReflexEdge replays deterministic range and closing-speed sensor frames through two inference paths on Arm64 hardware:

1. a frozen scalar FP32 reference implementation; and
2. an int8 implementation with an Arm NEON dot-product kernel.

Both paths use the same learned logistic-risk model, decision threshold, test rows, and action policy. The optimized result is accepted only if it improves measured performance without adding a safety-critical false-negative brake decision.

## How we built it

The project contains a rights-clean synthetic sensor generator, deterministic train/validation/test splits, a dependency-free Python trainer and quantizer, two C++17 inference binaries, an Arm64 hardware capture, repeated benchmark harnesses, safety regression tests, a public evidence dashboard, and a 62.4-second evidence video.

The baseline is compiled with vectorization disabled and uses a reference sensor encoder. The optimized path replaces repeated angular calculations and full sorting with a calibration lookup and one-pass summaries, fuses Arm-vectorized feature quantization, and uses Arm NEON/DotProd intrinsics for the learned dot product. A one-sided safety bias is calibrated on validation data only; it deliberately favors an extra brake over a missed brake. The test set remains frozen until the final comparison.

## What we optimized

| Stage | Frozen baseline | Optimized Arm path |
| --- | --- | --- |
| Sensor front end | Recompute analytic angular weights and fully order danger values | Precomputed fixed-beam calibration lookup and one-pass top-danger summary |
| Numeric path | FP32 features and weights | Fused Arm-vectorized feature quantization and symmetric int8 weights |
| Inference kernel | Scalar accumulation with compiler vectorization disabled | 16-byte Arm NEON vectors with DotProd when available |
| Safety handling | Original learned score and shared action policy | Validation-only one-sided bias, frozen before test, favoring an extra brake over a missed brake |

The optimization is therefore not “the same application compiled on Arm.” It replaces measured hot-path work with an Arm-specific fused path while preserving a common input contract, decision threshold, action policy, and frozen evaluation set.

## Measured result on Arm

The primary result comes from five independent processes per engine, with execution order alternating to reduce order and thermal bias. Each process evaluates 500,000 raw sensor frames from the same frozen 2,500-row test set on an Apple M4 Arm64 host with NEON and DotProd available.

| Raw sensor → action metric | Median speedup | Worst trial | Best trial |
| --- | ---: | ---: | ---: |
| p50 latency | 2.83× | 2.58× | 3.88× |
| p95 latency | 3.01× | 2.37× | 4.04× |
| throughput | 2.76× | 2.58× | 3.77× |
| CPU-time proxy | 2.80× | 2.56× | 3.78× |

The separate 1.25M-frame final run measured 1,966.12 ns → 402.34 ns p50 and 5,480.60 ns → 700.50 ns p95 for the complete in-memory raw sensor-to-action path. Model bytes fell from 584 to 160 (−72.60%). Test accuracy is 98.24% → 98.20%, false negatives are 6 → 5, and there are zero added false negatives. CPU time per inference is labeled only as an energy proxy; we did not measure or claim direct joules. Peak process RSS increased by 2.60%, so the memory reduction claim applies only to model bytes.

## Why it can win

ReflexEdge is not a cloud tuner or generic assistant. It is a complete Physical AI loop whose visible output changes a machine action. Its optimization story is controlled, repeatable, and hard to fake: same frames, frozen baseline, raw JSON, real Arm64 host evidence, a non-Arm negative control, safety regression tests, and explicit claim boundaries. Judges can understand the value in seconds and reproduce it without secrets, paid services, proprietary data, or special robotics hardware.

## Reproduce on Arm64

Requirements: an Arm64 macOS or Linux system, Python 3.11+, and a C++17 compiler.

```bash
git clone https://github.com/Oxygen56/reflexedge-arm-physical-ai.git
cd reflexedge-arm-physical-ai
./scripts/reproduce.sh
```

The command regenerates the corpus, audits the data, trains and quantizes the model, builds both engines, captures Arm hardware capabilities, runs tests, benchmarks both paths, and verifies rights and package gates. Read `reports/comparison.md` for the derived result and the raw JSON files beside it for machine-readable evidence.

## Built with

Arm64, Arm NEON/DotProd intrinsics, C++17, Python, React, Vinext, FFmpeg, and ImageMagick.

## Links

- Source and reproduction: https://github.com/Oxygen56/reflexedge-arm-physical-ai
- Interactive evidence demo: https://reflexedge-arm-ai.jiangth99.chatgpt.site
- Evidence video asset: https://github.com/Oxygen56/reflexedge-arm-physical-ai/raw/main/demo/video/reflexedge-evidence-demo.mp4

## Honest boundaries

The sensor corpus is deterministic and simulated; the inference and benchmarks are executed on real Arm64 hardware. This is a reference collision reflex, not a certified vehicle or robot safety controller. We do not claim cross-device performance, direct energy in joules, field deployment, or safety certification.
