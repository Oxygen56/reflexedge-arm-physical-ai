# ReflexEdge submission package

## One-Line Pitch

A brake reflex you can audit: raw range and closing-speed sensors become learned collision risk and an actuator command on Arm64.

## Problem

Physical-AI optimization claims often measure an isolated kernel, omit control decisions, or trade speed for silent safety regressions. Robotics teams need the whole sensor-to-action path to remain reproducible and reviewable.

## Solution

ReflexEdge freezes a deterministic 64-beam sensor corpus and FP32 scalar baseline, then compares it with an int8 Arm NEON implementation on identical frames. It emits `GO`, `HOLD`, or `BRAKE`, records raw Arm64 logs, and fails closed on accuracy or braking regressions.

## Demo

- Live URL: https://reflexedge-arm-ai.jiangth99.chatgpt.site
- Video: https://youtu.be/hFZvz4ntvbc
- Repository: https://github.com/Oxygen56/reflexedge-arm-physical-ai
- Local run: `./scripts/reproduce.sh`

## Technical Architecture

Deterministic synthetic sensors → frozen logistic-risk model → scalar FP32 or int8 NEON inference → thresholded actuator command. JSON evidence connects the dataset hash, hardware identity, raw benchmark trials, action counts, rights gate, video snapshot, and public-site validation.

## Evidence

- Tests: 18 Python pipeline and negative-control tests, plus 2 rendered-site tests.
- Deployment: anonymous public demo, MIT repository, and public 62.4-second evidence video.
- Benchmark: five alternating-order paired trials report 2.39× median p50, 6.06× median p95, and 3.03× throughput speedups for raw sensor-to-action inference.
- Safety: 15 three-state action differences, 3 BRAKE-boundary differences, 0 missed scalar BRAKE decisions, and 0 added ground-truth false negatives.
- Rights and secrets: deterministic first-party data and graphics; automated rights gate passes; no private data, API keys, stock media, or pretrained weights.

## Judging Rubric Mapping

- Technological implementation: real Apple M4 Arm64 execution, handwritten NEON dot product, raw logs, and end-to-end sensor-to-actuator timing.
- UX / DX: one-command reproduction, free anonymous demo, deterministic judge replay, and explicit negative controls.
- Potential impact: reusable evidence harness for robotics and embedded safety controllers.
- WOW factor: the interactive replay makes every sensor frame, risk score, action, speedup, and safety boundary visible in seconds.
