#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$ROOT_DIR/build}"
BENCH_BIN="${BENCH_BIN:-$BUILD_DIR/tiny_mnk_bench}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/results/nsys}"

M="${M:-32}"
N="${N:-256}"
K="${K:-75}"
WARMUP="${WARMUP:-5}"
ITERS="${ITERS:-50}"
LABEL="${LABEL:-tiny_mnk_reference}"

mkdir -p "$OUT_DIR"

nsys profile \
  --trace=cuda,nvtx,osrt \
  --sample=none \
  --force-overwrite=true \
  --output "$OUT_DIR/tiny_mnk" \
  "$BENCH_BIN" \
  --m "$M" \
  --n "$N" \
  --k "$K" \
  --warmup "$WARMUP" \
  --iters "$ITERS" \
  --label "$LABEL" \
  --csv-out "$OUT_DIR/benchmark.csv"
