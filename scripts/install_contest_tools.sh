#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r requirements/base.txt
python -m pip install -r requirements/gbdt.txt

echo "Contest Python environment ready. Activate with: source .venv/bin/activate"
