.PHONY: data audit train build test benchmark verify reproduce

data:
	python3 src/generate_dataset.py

audit:
	.competition/bin/contestctl audit-data
	python3 scripts/data_contract.py

train:
	python3 src/train_model.py

build:
	./scripts/build.sh

test:
	python3 -m unittest discover -s tests -v

benchmark:
	./build/reflexedge_scalar --dataset data/processed/test.csv --repeat 200 --output reports/baseline.json
	./build/reflexedge_neon --dataset data/processed/test.csv --repeat 200 --output reports/optimized.json
	python3 src/compare_results.py

verify:
	python3 scripts/rights_check.py
	python3 scripts/validate_buidl.py

reproduce:
	./scripts/reproduce.sh
