# Independent paired benchmark trials

5 independent processes per engine, 500,000 raw sensor frames per process. Execution order alternates to reduce order and thermal bias.

| Metric | Median speedup | Minimum | Maximum |
| --- | ---: | ---: | ---: |
| Model kernel p50 | 12.33× | 11.10× | 26.88× |
| Model kernel p95 | 17.89× | 8.65× | 33.14× |
| Model kernel throughput | 31.91× | 5.76× | 81.72× |
| Raw sensor → action p50 | 2.39× | 2.26× | 2.70× |
| Raw sensor → action p95 | 6.06× | 2.35× | 13.57× |
| Raw sensor → action throughput | 3.03× | 2.11× | 7.41× |
| Raw sensor → action CPU-time proxy | 2.44× | 2.28× | 2.69× |

## Action agreement and BRAKE safety

Action counts are deterministic corpus results and match across both engine reports and all paired trials.

| Metric | Count |
| --- | ---: |
| Full GO/HOLD/BRAKE disagreements | 15 |
| BRAKE-boundary disagreements | 3 |
| Int8 BRAKE false-negative disagreements vs scalar | 0 |
| Additional int8 BRAKE decisions vs scalar | 3 |
| Added ground-truth false negatives vs scalar | 0 |

## Gates

- [x] all_trials_kernel_p95_faster
- [x] all_trials_pipeline_p95_faster
- [x] all_trials_pipeline_throughput_faster
- [x] all_trials_cross_engine_action_metrics_match
- [x] action_metrics_consistent_across_trials
- [x] all_trials_zero_int8_brake_false_negative_disagreements
- [x] all_trials_zero_added_false_negatives
