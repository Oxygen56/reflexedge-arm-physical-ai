# Experiment board

The headline score is the conservative median from five independent, alternating-order raw sensor-to-action trials. Scores from different metrics are not ranked against one another.

| Stage | Evidence | Result |
| --- | --- | --- |
| Raw sensor corpus | `reports/data_contract.json` | 10,000 rows; 64 distance + 64 velocity beams; no missing, duplicate, split-overlap, schema, or bounds failures |
| Model validation | `artifacts/model.json` | 98.27% int8 validation accuracy; 99.24% recall |
| Final Arm64 run | `reports/comparison.json` | 2.28× raw-to-action p95 speedup; 0 int8 BRAKE false-negative disagreements; 0 added ground-truth false negatives |
| Independent paired trials | `reports/trials.json` | 6.06× median raw-to-action p95; 2.35× minimum; all five trials faster |
| Public evidence | `reports/publication_validation.json` | public repository, current video asset, MIT license, live demo, action metrics, and performance snapshot validated |
| Submission package | `reports/buidl_validation.json` | complete and internally consistent; rights and publication gates pass |

The single final run and the paired-trial distribution are both retained. Public headlines use the paired-trial median, while final-run absolute before/after values remain available for audit.
