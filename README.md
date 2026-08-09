# ReflexEdge

**A verifiable sensor-to-brake Physical AI reference system optimized for Arm.**

[Interactive evidence demo](https://reflexedge-arm-ai.jiangth99.chatgpt.site) · [62.4-second evidence video](demo/video/reflexedge-evidence-demo.mp4) · [Measured comparison](reports/comparison.md)

ReflexEdge turns a raw 64-beam distance and radial-velocity frame into a learned collision-risk score and a deterministic `GO`, `HOLD`, or `BRAKE` command. It is designed to make every performance and safety claim reproducible: the repository freezes a scalar FP32 baseline, applies fused sensor-front-end and int8 Arm NEON optimizations, replays the exact same sensor cases through both paths, and retains raw machine-readable evidence.

The project targets the [Arm Create: AI Optimization Challenge](https://arm-ai-optimization-challenge.devpost.com/) Physical AI track. It is intentionally not a cloud tuner or a general assistant.

## Why it matters

Physical AI optimizations can fail silently: a faster quantized model is useless if it changes a safety-critical braking decision. ReflexEdge couples speed measurements with action agreement, false-negative checks, model size, memory, and a transparent energy proxy. A deterministic simulator makes the full evidence path available to judges without proprietary robots or private data.

## Pipeline

```text
64-beam distance / radial-velocity frame
              |
              v
deterministic feature encoder
  baseline: analytic weights + reference summaries
  optimized: calibration LUT + one-pass summaries
              |
              v
learned collision-risk model
  baseline: scalar FP32
  optimized: int8 Arm NEON dot product
              |
              v
safety policy -> GO / HOLD / BRAKE
```

## Reproduce

Requirements: an Arm64 macOS or Linux machine, Python 3.11+, and a C++17 compiler. The core path has no third-party runtime dependency.

```bash
./scripts/reproduce.sh
```

The command regenerates the licensed synthetic sensor corpus, trains and quantizes the model, builds both engines, runs tests, runs a final benchmark plus five alternating-order independent paired trials on the same frames, and writes comparison reports under `reports/`.

The final gate also checks anonymous access to the public repository, MIT license, evidence video, and interactive demo. Network access is therefore required only for that last publication check; the core train/build/test/benchmark path is fully local.

The judge-facing replay dashboard lives in `demo/site/`. Its public evidence module is generated from the same rights-checked JSON and CSV artifacts by `scripts/build_demo_evidence.py`; displayed numbers are not hand-entered. The pre-rendered evidence video is `demo/video/reflexedge-evidence-demo.mp4` (62.4 seconds, 1080p, silent, no third-party music).

To build and verify the dashboard:

```bash
npm --prefix demo/site ci
npm --prefix demo/site test
```

To replay visible sensor-to-action events:

```bash
./build/reflexedge_neon --dataset data/processed/test.csv --demo 20
```

## Evidence contract

- No hardware result is accepted unless `uname -m` is `arm64` or `aarch64`.
- Baseline and optimized paths use the same dataset, split, model decision threshold, and action policy.
- The primary latency claim covers in-memory raw distance/velocity input through feature encoding, quantization when applicable, inference, and action-policy evaluation. Physical sensor I/O and actuator transport are not timed.
- Raw JSON is retained; the Markdown summary is derived from it.
- Direct energy is reported only when a supported meter is available. CPU time per inference is labeled as an energy proxy, never as joules.
- Quantization must not introduce a safety-critical false negative in the frozen test corpus.
- CPU-time per inference is an explicitly labeled proxy; no direct energy-in-joules result is claimed.
- The measured peak process RSS increased; the size claim applies only to model bytes.

See [the baseline protocol](reports/baseline_protocol.md), [rights ledger](reports/rights-ledger.md), and [judging map](reports/judging-matrix.md).

## License

Code and generated project assets are released under the [MIT License](LICENSE). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependency and data provenance.
