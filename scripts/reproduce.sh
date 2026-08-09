#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python3 src/generate_dataset.py
.competition/bin/contestctl audit-data
python3 scripts/data_contract.py
python3 src/train_model.py
./scripts/build.sh
python3 scripts/capture_hardware.py
python3 -m unittest discover -s tests -v
./build/reflexedge_scalar --dataset data/processed/test.csv --repeat 5000 --output reports/baseline.json
./build/reflexedge_neon --dataset data/processed/test.csv --repeat 5000 --output reports/optimized.json
python3 src/compare_results.py
python3 scripts/build_demo_evidence.py
python3 scripts/rights_check.py
python3 scripts/validate_buidl.py

echo "ReflexEdge reproduction complete. Read reports/comparison.md."
