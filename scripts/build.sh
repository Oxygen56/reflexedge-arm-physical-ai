#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ ! -f artifacts/generated/model_weights.h ]]; then
  echo "model header missing; run src/train_model.py first" >&2
  exit 2
fi

mkdir -p build
cxx="${CXX:-clang++}"
common=(-std=c++17 -Wall -Wextra -Werror -Iartifacts/generated src/reflexedge.cpp)

"$cxx" "${common[@]}" -O3 -fno-vectorize -fno-slp-vectorize -DREFLEXEDGE_BASELINE \
  -o build/reflexedge_scalar

arch="$(uname -m)"
if [[ "$arch" == "arm64" || "$arch" == "aarch64" ]]; then
  "$cxx" "${common[@]}" -O3 -march=armv8.6-a+dotprod -DREFLEXEDGE_OPTIMIZED \
    -o build/reflexedge_neon
else
  "$cxx" "${common[@]}" -O3 -DREFLEXEDGE_OPTIMIZED -o build/reflexedge_neon
fi

echo "built scalar and optimized engines for $arch"
