# Experiment board

The headline score is the conservative median from five independent, alternating-order raw sensor-to-action trials. Scores from different metrics are not ranked against one another.

| Stage | Evidence | Result |
| --- | --- | --- |
| Raw sensor corpus | `reports/data_contract.json` | 10,000 rows; 64 distance + 64 velocity beams; no missing, duplicate, split-overlap, schema, or bounds failures |
| Model validation | `artifacts/model.json` | 98.27% int8 validation accuracy; 99.24% recall |
| Final Arm64 run | `reports/comparison.json` | 7.82× raw-to-action p95 speedup; 0 added false negatives |
| Independent paired trials | `reports/trials.json` | 3.01× median raw-to-action p95; 2.37× minimum; all five trials faster |
| Public evidence | `reports/publication_validation.json` | repository, MIT license, demo, and video anonymously reachable |
| Submission package | `reports/buidl_validation.json` | all required artifacts present and all gates passed |

The single final run and the paired-trial distribution are both retained. Public headlines use the paired-trial median, while final-run absolute before/after values remain available for audit.
