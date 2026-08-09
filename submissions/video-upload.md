# Public video upload package

## Title

ReflexEdge — An Auditable Arm Physical AI Brake Reflex

## Description

ReflexEdge turns deterministic 64-beam range-sensor frames into a learned collision-risk score and a GO, HOLD, or BRAKE action on real Arm64 hardware.

Measured on Apple M4 Arm64 over the same frozen 2,500-row test set. Five alternating-order paired trials, 500,000 raw sensor frames per engine per trial:

- 3.01× median p95 speedup for raw sensor → action
- 2.83× median p50 speedup
- 2.76× median throughput speedup
- 72.60% fewer model bytes
- zero added false negatives

CPU time per inference is labeled only as an energy proxy; no direct joules are claimed. Peak process RSS increased, so the memory reduction claim applies only to model bytes.

Source and reproduction: https://github.com/Oxygen56/reflexedge-arm-physical-ai

Interactive evidence demo: https://reflexedge-arm-ai.jiangth99.chatgpt.site

Built for the Arm Create: AI Optimization Challenge Physical AI track.

## Upload settings

- Visibility: Public
- Audience: Not made for kids
- License: Standard platform license unless the entrant deliberately chooses another
- Category: Science & Technology
- Language: English
- Captions: Video contains on-screen English evidence and no speech
- Thumbnail: `demo/site/public/og.png`
- Video file: `demo/video/reflexedge-evidence-demo.mp4`

Do not upload until the entrant confirms the final public title, visibility, and account action.
