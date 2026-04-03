#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$ROOT_DIR/build}"
BENCH_BIN="${BENCH_BIN:-$BUILD_DIR/tiny_mnk_bench}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/results/ncu}"

M="${M:-32}"
N="${N:-256}"
K="${K:-75}"
WARMUP="${WARMUP:-5}"
ITERS="${ITERS:-50}"
LABEL="${LABEL:-tiny_mnk_reference}"

mkdir -p "$OUT_DIR"

ncu \
  --set full \
  --target-processes all \
  --replay-mode kernel \
  --export "$OUT_DIR/tiny_mnk" \
  "$BENCH_BIN" \
  --m "$M" \
  --n "$N" \
  --k "$K" \
  --warmup "$WARMUP" \
  --iters "$ITERS" \
  --label "$LABEL" \
  --csv-out "$OUT_DIR/benchmark.csv"

python "$ROOT_DIR/scripts/export_results.py" \
  --reference-json "$ROOT_DIR/config/observed_tiny_mnk_kernels.json" \
  --benchmark-csv "$OUT_DIR/benchmark.csv" \
  --ncu-csv "$OUT_DIR/tiny_mnk.ncu.csv" \
  --output "$OUT_DIR/summary.json"
