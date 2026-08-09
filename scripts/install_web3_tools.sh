#!/usr/bin/env bash
set -euo pipefail

if ! command -v forge >/dev/null 2>&1; then
  echo "Installing Foundry. Restart your shell or source your profile after this completes."
  curl -L https://foundry.paradigm.xyz | bash
  foundryup
fi

if command -v pnpm >/dev/null 2>&1; then
  mkdir -p web3
  cd web3
  if [ ! -f package.json ]; then
    pnpm init
  fi
  pnpm add -D hardhat @nomicfoundation/hardhat-toolbox @openzeppelin/contracts
fi

if [ -d .venv ]; then
  source .venv/bin/activate
else
  python3 -m venv .venv
  source .venv/bin/activate
fi
python -m pip install --upgrade pip
python -m pip install -r requirements/web3-python.txt

echo "Web3 contest tools requested. Verify with: .competition/bin/contestctl toolcheck"
