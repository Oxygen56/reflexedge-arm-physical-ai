# Independent paired benchmark trials

5 independent processes per engine, 500,000 raw sensor frames per process. Execution order alternates to reduce order and thermal bias.

| Metric | Median speedup | Minimum | Maximum |
| --- | ---: | ---: | ---: |
| Model kernel p50 | 21.46× | 16.39× | 29.94× |
| Model kernel p95 | 16.84× | 6.40× | 36.30× |
| Model kernel throughput | 18.78× | 11.42× | 25.48× |
| Raw sensor → action p50 | 2.83× | 2.58× | 3.88× |
| Raw sensor → action p95 | 3.01× | 2.37× | 4.04× |
| Raw sensor → action throughput | 2.76× | 2.58× | 3.77× |
| Raw sensor → action CPU-time proxy | 2.80× | 2.56× | 3.78× |

## Gates

- [x] all_trials_kernel_p95_faster
- [x] all_trials_pipeline_p95_faster
- [x] all_trials_pipeline_throughput_faster
- [x] all_trials_zero_added_false_negatives
