#!/usr/bin/env bash
set -euo pipefail
paper_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$paper_root/infra/scripts/compose.sh" --profile checks run --rm --no-deps -T \
  -e PGDATABASE=investalo_credentials_checks \
  -e PAPER_TEST_PASSWORD_FILE=/run/secrets/paper_test_password \
  -v "$paper_root/infra/local/paper_test_password:/run/secrets/paper_test_password:ro" \
  -v "$paper_root/services/workers/src:/app/services/workers/src:ro" \
  -v "$paper_root/packages/trading/src:/app/packages/trading/src:ro" \
  -v "$paper_root/packages/marketdata/src:/app/packages/marketdata/src:ro" \
  -v "$paper_root/tests/trading:/app/tests/trading:ro" \
  -v "$paper_root/tests/marketdata:/app/tests/marketdata:ro" \
  -v "$paper_root/tests/paper:/app/tests/paper:ro" \
  api-checks python -m pytest /app/tests/paper /app/tests/trading /app/tests/marketdata \
  /app/tests/workers/test_computation.py -q --tb=short -p no:cacheprovider
