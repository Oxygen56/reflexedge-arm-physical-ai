# ReflexEdge

## Inspiration

Physical AI becomes dangerous when optimization is treated as a speed-only exercise. A quantized model can be faster while silently changing the action that matters. ReflexEdge is a compact, auditable collision reflex: a 64-beam range frame enters a learned model and leaves as a deterministic `GO`, `HOLD`, or `BRAKE` command, with performance and safety evaluated together.

## What it does

ReflexEdge replays deterministic range and closing-speed sensor frames through two inference paths on Arm64 hardware:

1. a frozen scalar FP32 reference implementation; and
2. an int8 implementation with an Arm NEON dot-product kernel.

Both paths use the same learned logistic-risk model, decision threshold, test rows, and action policy. The optimized result is accepted only if it improves measured performance without adding a safety-critical false-negative brake decision.

## How we built it

The project contains a rights-clean synthetic sensor generator, deterministic train/validation/test splits, a dependency-free Python trainer and quantizer, two C++17 inference binaries, an Arm64 hardware capture, repeated benchmark harnesses, safety regression tests, a public evidence dashboard, and a 57-second evidence video.

The baseline is compiled with vectorization disabled. The optimized path quantizes features and weights to int8 and uses Arm NEON/DotProd intrinsics for the learned dot product. A one-sided safety bias is calibrated on validation data only; it deliberately favors an extra brake over a missed brake. The test set remains frozen until the final comparison.

## Measured result on Arm

All numbers below come from 12.5 million inferences per engine over the same frozen 2,500-row test set on an Apple M4 Arm64 host with NEON and DotProd available.

| Metric | Scalar FP32 | int8 Arm NEON | Change |
| --- | ---: | ---: | ---: |
| p50 latency | 208.34 ns | 11.72 ns | 17.78× faster |
| p95 latency | 377.59 ns | 62.50 ns | 6.04× faster |
| throughput | 479,485/s | 9,194,583/s | +1,817.6% |
| model bytes | 584 | 160 | −72.60% |
| test accuracy | 98.24% | 98.20% | −0.04 points |
| false negatives | 6 | 5 | zero added |

CPU time per inference fell by 90.26% and is labeled only as an energy proxy. We did not measure or claim direct joules. Peak process RSS increased by 9.98%, so the memory reduction claim applies only to model bytes.

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
