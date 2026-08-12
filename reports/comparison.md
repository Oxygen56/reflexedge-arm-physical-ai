# ReflexEdge benchmark comparison

**Evidence verdict: VERIFIED FOR LOCAL CLAIM.**

- Evidence architecture: `arm64`
- Frozen test rows: 2500
- Repeats per engine: 500
- Dataset SHA-256: `40c9395be7cc2ea20cbcd2b288d83e15e6ad9e378bbee5e9202e26cb0c6d0b26`

## Raw sensor-to-action pipeline

This is the end-to-end Physical AI path: raw 64-beam distance and velocity input, feature encoding, quantization when applicable, model inference, and GO/HOLD/BRAKE policy.

| Metric | Scalar FP32 | Fused int8 Arm path | Change |
| --- | ---: | ---: | ---: |
| p50 latency | 2611.97 ns | 1031.25 ns | 2.53x speedup |
| p95 latency | 10738.54 ns | 4703.12 ns | 2.28x speedup |
| Throughput | 194955/s | 338816/s | +73.8% |
| CPU-time proxy | 2537.53 ns/inf | 976.08 ns/inf | 61.5% lower |

## Model inference kernel

Features are pre-encoded for this microbenchmark; CSV loading and sensor encoding are excluded.

| Metric | Scalar FP32 | Int8 Arm NEON | Change |
| --- | ---: | ---: | ---: |
| p50 latency | 317.69 ns | 13.03 ns | 24.38x speedup |
| p95 latency | 856.75 ns | 76.84 ns | 11.15x speedup |
| Throughput | 2081103/s | 15524254/s | +646.0% |
| CPU-time energy proxy | 372.66 ns/inf | 27.33 ns/inf | 92.7% lower |
| Model bytes | 584 | 160 | 72.6% lower |
| Peak RSS | 9748480 | 10076160 | +3.4% |
| Accuracy | 0.98240 | 0.98200 | -0.040 pp |
| Total ground-truth false negatives | 6 | 5 | newly introduced cases: 0 |

## Action agreement and BRAKE safety

These counts use the same frozen test frames but answer different questions. Full action agreement compares all three commands; the safety gate is directional and asks whether int8 ever drops a scalar BRAKE.

| Metric | Count | Definition |
| --- | ---: | --- |
| Full three-state action disagreements | 15 | Scalar and int8 emit different `GO` / `HOLD` / `BRAKE` commands |
| BRAKE-boundary disagreements | 3 | One engine emits `BRAKE` and the other emits `GO` or `HOLD` |
| Int8 BRAKE false-negative disagreements vs scalar | 0 | Scalar emits `BRAKE`; int8 emits `GO` or `HOLD` |
| Additional int8 BRAKE decisions vs scalar | 3 | Int8 emits `BRAKE`; scalar emits `GO` or `HOLD` |
| Added ground-truth false negatives vs scalar | 0 | True brake label, scalar emits `BRAKE`, and int8 emits `GO` or `HOLD` |

## Independent process trials

Across 5 alternating-order paired trials, the median raw sensor-to-action speedups were 2.39x p50, 6.06x p95, and 3.03x throughput.

## Claim boundaries

- These are local measurements on the hardware recorded in `reports/hardware.json`, not a cross-device benchmark.
- End-to-end latency starts from in-memory raw distance/velocity arrays and ends after action-policy evaluation; physical sensor I/O and actuator transport are outside the timed region.
- CPU time per inference is an energy proxy. Direct energy in joules remains unmeasured and is not claimed.
- Peak RSS measures the full benchmark process; small model-size savings may not materially change process RSS.
- Synthetic sensor frames enable deterministic safety regression testing; they do not establish field safety certification.

## Gates

- [x] real_arm64_hardware
- [x] same_dataset_and_rows
- [x] cross_engine_action_metrics_match
- [x] action_metrics_are_consistent
- [x] zero_int8_brake_false_negative_disagreements
- [x] zero_added_safety_false_negatives
- [x] accuracy_loss_within_half_point
- [x] optimized_p95_is_faster
- [x] optimized_model_is_smaller
- [x] optimized_pipeline_p95_is_faster
- [x] optimized_pipeline_throughput_is_higher
- [x] independent_trials_ready
- [x] direct_energy_not_fabricated
