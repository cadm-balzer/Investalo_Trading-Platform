# H4 research snapshots

IP-050 adds `paper_feed.py`: fixed unsigned SPOT ticker/current-candle GETs,
real bid/ask, closed UTC H4 coverage and freshness. Existing research history
contract unchanged. Actual public BTC/ETH check passed; only bounded fixture
Paperworker accepted. [Feed/worker contract](../../docs/paper-market-worker.md).

Stdlib-only package. Add `packages/marketdata/src` and `packages/trading/src`
to `PYTHONPATH`. No exchange account, key, paid feed, strategy optimization or
automatic holdout evaluation is included.

```python
from investalo_marketdata import load_snapshot, to_trading_candles
from investalo_trading import PaperSimulator, primitive

snapshot = load_snapshot(json_bytes)
result = PaperSimulator().run(
    to_trading_candles(snapshot), tenant_id=tenant_id, account_id=research_account_id
)
record = primitive(result)
# Preserve both: snapshot.data_digest and result.data_digest.
# The latter is the existing simulator's simulation_data_digest.
```

`DatasetSnapshot` is a frozen dataclass. Its `candles` are a tuple of existing
`Candle` records. Schema `marketdata-snapshot/1` stores public symbols
`BTC/USDT` or `ETH/USDT`, timeframe `4h`, source, synthetic flag, OHLC Decimal
strings, exact UTC opening/exclusive closing times, coverage and optional
provenanced instrument metadata. The core still uses `BTCUSDT` and `ETHUSDT`:
`to_trading_candles` changes only that notation, preserving all prices/times.
The immutable strategy version and configuration digest remain unchanged.

`dump_snapshot(snapshot) -> str` emits canonical JSON; `load_snapshot(str|bytes)`
validates the schema, coverage and digest. `snapshot.source.record()` and
`snapshot.coverage.record()` expose JSON records with UTC ISO strings.
`snapshot.coverage.complete` is `True` only for the exact requested interval,
`False` for leading/trailing shortfall, and `None` without an explicit request.
No coverage result is a strategy-performance validation.

The SHA256 `data_digest` covers schema, symbol, timeframe, source venue/version/
clean URL, synthetic label, instrument metadata and canonical candles.
Retrieval time and requested coverage are excluded so repeated retrieval or a
different requested window cannot change an identical dataset's identity.
Keep the complete immutable snapshot bytes as the separate audit artifact.
Changing provenance, precision metadata, labels or any OHLC value changes the
digest. Optional precision metadata distinguishes historical/current/assumed
rules; it is never implicitly applied to historical execution.

Validation rejects empty history, interior gaps, duplicates, unsorted snapshots,
inconsistent OHLC, nonpositive/nonfinite prices, unclosed/future bars, non-UTC
or misaligned H4 timestamps, unsupported symbols and unexpected fields.
Limits are 10,000 bars and 16 MiB per input; Decimal text is bounded to 64
characters, 36 digits, exponent ±24 and magnitude `1e-24..1e24`.
No interpolation, inferred volume or reconstructed bid/ask data is added.

```bash
PYTHONPATH=packages/marketdata/src:packages/trading/src python -m investalo_marketdata \
  bitget --symbol BTC/USDT --start 2023-11-07T00:00:00Z \
  --end 2026-11-07T00:00:00Z --output history.json
PYTHONPATH=packages/marketdata/src:packages/trading/src python -m investalo_marketdata \
  synthetic --symbol BTC/USDT --bars 240 --output fixture.json
PYTHONPATH=packages/marketdata/src:packages/trading/src python -m investalo_marketdata \
  csv candles.csv --symbol BTC/USDT --real --output imported.json
PYTHONPATH=packages/marketdata/src:packages/trading/src python -m investalo_marketdata \
  validate imported.json
```

Requested endpoints must already be closed at retrieval; the example dates
must be adjusted to available closed history. Output is create-only and never
overwrites an existing snapshot. CSV has the exact header
`symbol,open_time,close_time,open,high,low,close`; explicit `--real` or
`--synthetic` is required. `--real` is the importing operator's assertion,
not venue verification. CSV source is `csv/csv-v1`, with optional clean HTTPS
source URL; public metadata may conservatively display its URL as null.
Synthetic fixtures always use `synthetic/fixture-v1`, null URL and
`synthetic=true`, and demonstrate integration only.

The adapter uses the [current official Bitget V3 public history API](
https://www.bitget.com/docs/catalog/market/market-data#get-klinecandlestick-history):
`category=SPOT`, `interval=4H`, `type=market`, at most 100 rows per page and
at most 90 days per request. Older history may be queried, but availability
is measured, not promised. There is no documented `4Hutc` value in this API;
returned Unix-millisecond timestamps must actually align to UTC H4.
Bitget documents possible extra earlier intervals when `endTime` crosses
an interval boundary. Backward queries use exact UTC interval boundaries;
public V3 probes on 2026-11-07 verified that subtracting 1 ms instead rounds
down and skips candles between pages. The exact exclusive cursor and start
avoid that truncation. Queries
normalize provider transport order, reject duplicate/nonprogressing pages
and preserve precision from the documented string OHLC fields.
Requests are paced below 20/sec/IP (other host users can still share that quota),
timeouts and response sizes are bounded, redirects and blind retries are denied.
An injected `fetch_json(url)` supports deterministic tests without networking.

## Exact research windows

`window_snapshot(snapshot, start=..., end=...)` selects an explicit UTC-H4
interval only when every requested candle exists. Prices and source metadata
are preserved; the new immutable snapshot has its own digest and exact
coverage. A complete subwindow does not establish complete parent coverage.

```bash
PYTHONPATH=packages/marketdata/src:packages/trading/src python -m investalo_marketdata \
  window history.json --start 2022-08-01T00:00:00Z \
  --end 2025-08-01T00:00:00Z --output research.json
```

IP-046 verified public four-year BTC/ETH histories (8,766 H4 bars each),
partitioned into three research years (6,576) and a reserved year (2,190).
The 90-day provider limit applies per request, not to the total dataset.
Only research is simulated; purpose assignment and holdout access remain
operator/database responsibilities. See [the frozen protocol](../../docs/long-history-backtests.md).
