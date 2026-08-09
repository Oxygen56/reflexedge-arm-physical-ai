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
| p50 latency | 1966.12 ns | 402.34 ns | 4.89x speedup |
| p95 latency | 5480.60 ns | 700.50 ns | 7.82x speedup |
| Throughput | 330872/s | 2216602/s | +569.9% |
| CPU-time proxy | 1976.73 ns/inf | 434.20 ns/inf | 78.0% lower |

## Model inference kernel

Features are pre-encoded for this microbenchmark; CSV loading and sensor encoding are excluded.

| Metric | Scalar FP32 | Int8 Arm NEON | Change |
| --- | ---: | ---: | ---: |
| p50 latency | 365.88 ns | 7.81 ns | 46.83x speedup |
| p95 latency | 2278.79 ns | 29.97 ns | 76.04x speedup |
| Throughput | 735774/s | 46768382/s | +6256.4% |
| CPU-time energy proxy | 408.14 ns/inf | 12.87 ns/inf | 96.8% lower |
| Model bytes | 584 | 160 | 72.6% lower |
| Peak RSS | 10092544 | 10354688 | +2.6% |
| Accuracy | 0.98240 | 0.98200 | -0.040 pp |
| False negatives | 6 | 5 | added: 0 |

## Independent process trials

Across 5 alternating-order paired trials, the median raw sensor-to-action speedups were 2.83x p50, 3.01x p95, and 2.76x throughput.

## Claim boundaries

- These are local measurements on the hardware recorded in `reports/hardware.json`, not a cross-device benchmark.
- End-to-end latency starts from in-memory raw distance/velocity arrays and ends after action-policy evaluation; physical sensor I/O and actuator transport are outside the timed region.
- CPU time per inference is an energy proxy. Direct energy in joules remains unmeasured and is not claimed.
- Peak RSS measures the full benchmark process; small model-size savings may not materially change process RSS.
- Synthetic sensor frames enable deterministic safety regression testing; they do not establish field safety certification.

## Gates

- [x] real_arm64_hardware
- [x] same_dataset_and_rows
- [x] zero_added_safety_false_negatives
- [x] accuracy_loss_within_half_point
- [x] optimized_p95_is_faster
- [x] optimized_model_is_smaller
- [x] optimized_pipeline_p95_is_faster
- [x] optimized_pipeline_throughput_is_higher
- [x] independent_trials_ready
- [x] direct_energy_not_fabricated
