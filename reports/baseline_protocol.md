# Frozen baseline and measurement protocol

## Claim under test

On the same Arm64 host and the same frozen sensor frames, an int8 Arm NEON inference kernel can reduce collision-risk inference latency and model memory relative to a scalar FP32 kernel without introducing a safety-critical false-negative brake decision.

## Frozen components

- Dataset generator seed, scenario mix, feature count, train/test sizes.
- Train/test split and test-file checksum.
- Learned float weights, bias, and action threshold.
- Sensor feature encoder and brake/hold/go policy.
- Compiler version, flags, hardware fingerprint without serial identifiers.
- Warmup count, repeat count, and percentile calculation.

## Baseline

- FP32 learned linear risk model.
- Scalar accumulation built with loop and SLP vectorization disabled.
- Same sigmoid, threshold, and action policy as the optimized engine.

## Optimized variant

- Symmetric int8 quantization for features and learned weights.
- Arm NEON dot product using 16-byte vectors; dot-product extension when available.
- Scale restored before the same sigmoid, threshold, and policy.
- A one-sided safety bias is calibrated only on the validation split as the 99th percentile scalar-minus-int8 logit error among true-positive brake decisions plus a fixed 0.02 margin. This deliberately favors an extra brake over a missed brake and is frozen before test evaluation.

## Measurements

- p50, p95, and p99 latency per inference from repeated timed batches.
- Throughput in inferences per second.
- CPU time per inference as an energy proxy.
- Peak resident memory and model byte count.
- Accuracy, precision, recall, F1, false negatives, and baseline/optimized action agreement.

Direct energy in joules is outside the initial claim. It may be added only from a supported local meter with raw logs; estimated CPU time is never relabeled as joules.

## Acceptance gates

1. Evidence host reports `arm64` or `aarch64`.
2. Test checksum is identical for both engines.
3. Optimized engine has zero additional false-negative `BRAKE` decisions versus baseline.
4. Accuracy loss is no more than 0.5 percentage points.
5. Performance and memory claims are generated from raw JSON, not manually typed.
6. A negative control proves the validator rejects a corrupted or non-Arm evidence bundle.
