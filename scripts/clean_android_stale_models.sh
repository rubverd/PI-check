#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="$ROOT_DIR/mobile/app/src/main/java/es/uva/picheck/data/model"

STALE_FILES=(
  "ComparisonAnalysisResult.kt"
  "ComparisonModels.kt"
  "MobSFReportInfo.kt"
  "VersionAppInfo.kt"
  "VersionReportInfo.kt"
  "ComparisionAnalysisResult.kt"
  "ComparisionModels.kt"
)

for file in "${STALE_FILES[@]}"; do
  path="$MODEL_DIR/$file"
  if [[ -e "$path" ]]; then
    rm -f "$path"
    echo "Removed stale Android model: $path"
  fi
done

echo "Android model cleanup completed. Current model files:"
find "$MODEL_DIR" -maxdepth 1 -type f -name '*.kt' -printf '%f\n' | sort
