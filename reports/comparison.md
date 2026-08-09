# ReflexEdge benchmark comparison

**Evidence verdict: VERIFIED FOR LOCAL CLAIM.**

- Evidence architecture: `arm64`
- Frozen test rows: 2500
- Repeats per engine: 5000
- Dataset SHA-256: `1297cb7c3a6b5be2f190b3c2a833e1028786e8509df9803c58b7dcbd93d60f3e`

| Metric | Scalar FP32 | Int8 Arm NEON | Change |
| --- | ---: | ---: | ---: |
| p50 latency | 208.34 ns | 11.72 ns | 17.78x speedup |
| p95 latency | 377.59 ns | 62.50 ns | 6.04x speedup |
| Throughput | 479485/s | 9194583/s | +1817.6% |
| CPU-time energy proxy | 236.80 ns/inf | 23.07 ns/inf | 90.3% lower |
| Model bytes | 584 | 160 | 72.6% lower |
| Peak RSS | 15761408 | 17334272 | +10.0% |
| Accuracy | 0.98240 | 0.98200 | -0.040 pp |
| False negatives | 6 | 5 | added: 0 |

## Claim boundaries

- These are local measurements on the hardware recorded in `reports/hardware.json`, not a cross-device benchmark.
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
- [x] direct_energy_not_fabricated
