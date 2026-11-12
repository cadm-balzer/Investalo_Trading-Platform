#!/usr/bin/env bash
set -euo pipefail
paper_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$paper_root/infra/scripts/compose.sh" --profile checks run --rm --no-deps -T \
  -e PGDATABASE=investalo_credentials_checks \
  -e PAPER_TEST_PASSWORD_FILE=/run/secrets/paper_test_password \
  -v "$paper_root/infra/local/paper_test_password:/run/secrets/paper_test_password:ro" \
  -v "$paper_root/services/workers/src:/app/services/workers/src:ro" \
  -v "$paper_root/services/api/src:/app/services/api/src:ro" \
  -v "$paper_root/packages/trading/src:/app/packages/trading/src:ro" \
  -v "$paper_root/packages/marketdata/src:/app/packages/marketdata/src:ro" \
  -v "$paper_root/tests/trading:/app/tests/trading:ro" \
  -v "$paper_root/tests/marketdata:/app/tests/marketdata:ro" \
  -v "$paper_root/infra/scripts/import-futures-history.py:/app/infra/scripts/import-futures-history.py:ro" \
  -v "$paper_root/docs/research-protocols/futures-history-20261110.json:/app/docs/research-protocols/futures-history-20261110.json:ro" \
  -v "$paper_root/infra/scripts/import-futures-funding.py:/app/infra/scripts/import-futures-funding.py:ro" \
  -v "$paper_root/docs/research-protocols/futures-funding-20261111.json:/app/docs/research-protocols/futures-funding-20261111.json:ro" \
  -v "$paper_root/infra/scripts/import-binance-futures-history.py:/app/infra/scripts/import-binance-futures-history.py:ro" \
  -v "$paper_root/docs/research-protocols/binance-futures-history-20261111.json:/app/docs/research-protocols/binance-futures-history-20261111.json:ro" \
  -v "$paper_root/infra/scripts/import-futures-h1-history.py:/app/infra/scripts/import-futures-h1-history.py:ro" \
  -v "$paper_root/docs/research-protocols/futures-h1-history-20261112.json:/app/docs/research-protocols/futures-h1-history-20261112.json:ro" \
  -v "$paper_root/infra/scripts/preflight-futures-capital.py:/app/infra/scripts/preflight-futures-capital.py:ro" \
  -v "$paper_root/docs/research-protocols/futures-capital-economics-20261112.json:/app/docs/research-protocols/futures-capital-economics-20261112.json:ro" \
  -v "$paper_root/tests/paper:/app/tests/paper:ro" \
  api-checks python -m pytest /app/tests/paper /app/tests/trading /app/tests/marketdata \
  /app/tests/workers/test_computation.py -q --tb=short -p no:cacheprovider "$@"
