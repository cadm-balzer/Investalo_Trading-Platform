# AGENTS.md

see `docs/project-info.md` for projekt details

Working Project Folder: /opt/Investalo_Trading-Platform

## Project state and navigation

- Current phase: local M1 implementation, approved in Q31.
- PR60 merged: 0bda3e4 ancestor of main7cc6848, GH/fetch verified.
  IP-090 funding-only checkpoint on feat/m1-futures-paper-funding:
  own settlement command with independent exact-time marks/native rates,
  bounded delayed knowledge, same-mark midnight basis before funding,
  preserved real quote clock/no fills. Durable full-command receipt permits
  scoped source continuation; missing/revised/earlier/next funding still stops.
  Liquidation cannot be erased by newer recovered quotes; reconciliation
  remains separate. Old genesis/state/command identity golden receipt retained.
  18 new/93 focused pinned cases/57 subtests pass after forecast fixture fix.
  Actual Classic source has NO settlement mark; independent valuation is
  injected only, no real valuation collector or complete funding service yet.
  Source cursor/archive/launcher/state publication/013 settings/profit epochs/
  manual recovery remain open. No DB/dependency/performance/public/live/AI
  change. See docs/futures-paper-settlement.md.
- PR59 merged: b6890eb ancestor of main29f6661, GH/fetch verified.
  Q48/IP-090 own selected-asset dashboard on feat/m1-futures-asset-dashboard:
  acknowledged own Paper state -> pure scoped projection -> authenticated
  read-only API -> strict TS contract -> overview/portfolio table.
  H1/Wilder RSI14 with close time, real open quantity/average/2x/stage,
  tick-floored95% last actual fill ceiling, next H1 check and truthful
  rearm/confirmation/price/window/blockers; no forecast purchase.
  9 new domain/4 actual PG+HTTP/6 Cockpit cases;76 distinct focused pinned
  Paper/API cases, final13 new cases rerun;32 Cockpit cases/typecheck and
  pinned Cockpit build pass. Running services unchanged.
  15s visible-tab refresh. API/BFF opt-ins default off; normal launcher has
  no state reader yet. Funding valuation/durable worker publication remain
  necessary before running dashboard acceptance. No migration/dependency/
  performance/public/live/AI changes. See docs/futures-paper-assets.md.
- PR58 merged: cd79977 ancestor of main2cdb9b7, GH/fetch verified.
  IP-090 next local checkpoint on feat/m1-futures-public-feed:
  unsigned Classic25-GET source, five BITGET-prefixed candidates,
  separate exact closed H1 trade/mark axes, individual native quote clocks,
  full bounded history page plus separate funding forecast.
  Guarded own Paper handoff binds the last acknowledged source receipt;
  open exposure stops before unvalued funding, including publication lag.
  Classic history has no settlement mark; no omitted/shifted/fake funding.
  15 new cases;111 focused pinned cases/100 subtests pass, including source/
  journal full restore. Actual current source capture complete:
  infra/local/futures-paper-source/20261114-current-1,25 create-only0600
  canonical responses/58h per axis/580 candles/5 quotes/40 funding/5 forecasts.
  Receiptsha dabfaf047fc545357e095670190c1b1df28dcb300375417639c351ee9cfebfeb.
  No market performance/DB/dependencies/public/live/AI activation.
  Complete funding valuation, durable source cursor/archive/launcher,
  instrument/status/013 settings adapter, profit epochs/recovery/Cockpit
  remain IP-090. See docs/futures-paper-feed.md.
- PR57 merged: c196093 ancestor of mainf8a2217, GH/fetch verified.
  IP-090 first local checkpoint on feat/m1-futures-paper-runtime:
  own candidate pool3–7/initial funded3–5, immutable six-stage ranges,
  H1-RSI/H1 protection/fixed2×, native funding IDs and declared Paper fills.
  Own fsync journal/full replay/CAS/exclusive writer/unknown-write stop;
  injected feed worker only.139 focused pinned cases/76 subtests passed;
  final20 Paper cases rerun pinned after midnight/clock/thread fixes.
  No imports/market performance/DB/dependencies/public/live/AI changes.
  Actual feed/funding coverage, launcher/archive,013 settings/status adapter,
  Q36 profit epochs, manual recovery and Cockpit remain IP-090/IP-088.
  Raising the3–7 ceiling alone does not expand initial funded capacity.
  Historical artifacts/protocols preserved; old journal decoder unchanged.
  See docs/futures-paper-runtime.md.
- Q47 prioritizes Futures trading implementation after the leverage comparison:
 2× first Paper baseline; dashboard basket limit and actual-capital recommendation.
 IP-089 persists own USDT-Paper planning3–7, owner/trader CAS + atomic audit,
 default-off API/BFF/portfolio. Additive013 ONLY in fixture after rollback
 preflight, sha78f1c339f6ff8b5bf6827d7eae3d987b6ed6a8bd32b69dcfcc45a88a94753645;
 fixture001–012 and development migration set unchanged. Capacity helper
 retains all remaining regular/manual/fee reserves, acknowledged profit
 capacity and eligible asset count; future/stale cash or shortage rejects.
 Fixed acknowledged range amount cannot grow just because free cash grows.
 28 new/56 focused pinned cases/18 subtests, nine Cockpit tests, typecheck
 and pinned build passed. Runtime Futures cash/minimum-range adapter absent: recommendation=null,
 runtime_ready=false. Next IP-090: durable dedicated Futures Paper runtime,
 H1-RSI/stages/H1 protection/mark/funding, journal/restart, own dashboard
 and IP-088 recovery; then calibrated Bitget demo orders. More simultaneous
 coins do not guarantee greater stable returns; initial3–5, phased profits
 to7 retained. No live/public/AI activation. PR56 merged into PR55 branch
 8ffafea; PR55 now merged into main51c2f68 (GH/fetch ancestry verified). Current branch
 feat/m1-futures-paper-runtime. See docs/futures-paper-settings.md.
- IP-087 fully complete; no active job.3×106752/4×102760 commands,
  209512 total, eight final artifacts/13 unchanged completion hashes;
  eleven original native files still matchada2029. Original4× exit137
  preserved without receipt; readonly full restore completed without new
  market job. Twelve previous reference artifacts and15 sources verified.
  Final receiptsha
  0b382391c2fedb92d1c32a3094992a976f049c77b5dd09d769381066d8ad1b7c.
  3×+8523.18/DD23.54%/two liquidations/stages209/100/51/23/14;
  4×+9464.20/DD29.65%/three liquidations/stages164/76/38/17/10.
  3/2 eligible end slots, one BTC end-open each; no account halt or recovery.
  4× unrecorded admission counters absent, not zero.2× remains best reference.
  Recommend2× baseline/3×–4× regime research only; no changed approved range
  or active AI. Five recovery cases/13 subtests and five Cockpit cases pass;
  typecheck/build pass. IP-088 runtime/persistence/API integration remains open;
  UI/BFF default off, no public or broker activation.
  See docs/futures-moderate-results-20261113.md.
- PR55 was OPEN when IP-087 branched from4ad9a4e on
  feat/m1-futures-moderate-leverage. User requests3×/4× on same model axis
  and Q46 manual liquidation recovery with visible dashboard blockers.
  Separate moderate scenario/explicit flag/protocol; old constructor and
  2×/5×/10× identities retained. Protocolsha
  79308ab0b727f848ec1c446b096a1c501392ab8592ae6d67fbbc39a0669b760e.
  Three new/38 focused pinned cases/66 subtests pass. Only3×/4× new native
  jobs; twelve reference artifacts rehash before/after. Keep eleven grid
  implementation files frozen during fold. No automatic recovery in this
  leverage comparison. Q46 manual action retains losses/history and needs
  actual flat/order reconciliation and full new own budget; new RSI/leverage
  cycle afterwards. Native Futures are offline research, not runtime yet.
  IP-088 UI/core workflow separate, no live/public/AI activation.
  See docs/futures-moderate-leverage.md.
- IP-087 original3×106752-command restore complete (+8523.18/DD23.54%,
  two liquidations). Original4× native journal/26305 curve points complete,
  but process exited137 during restore; cause unconfirmed. Preserve original
  directory without receipt. Read-only futures_journal_metrics observer and
  complete-futures-moderate.py retain eleven original hashes atada2029,
  verify all sources/references/original bytes, then complete only4× restore
  in new20261113-h1-grid-moderate-completed output. No repeated market job.
  Normal/gap metric parity and five manual recovery cases pass (13 subtests).
  4× unrecorded admission/filter counters omitted, never reported as zero.
  IP-088 candidate + default-off dashboard/BFF implemented and tested;
  durable own Futures runtime/API/CAS reconciliation remains open.
  No production enablement or historical journal codec changes.
  See docs/futures-manual-recovery.md.
- PR54 merged: head0bcdcd2 ancestor of main9999671 (GH/fetch verified).
  IP-086 on feat/m1-futures-grid-leverage follows user's requested direct
  leverage comparison: same declared grid/cash/margin/price-guard economics,
  fixed whole-basket2×/5×/10×, no simultaneous Classic recalibration.
  Separate explicit grid_leverage_comparison flag and plan/profile protocol
  binding; original2× default digest/restrictions retained. Reuse verified
  IP-0852× receipt/four artifacts; only5×/10× new native jobs, one at a time.
  Frozen protocolsha
  c2d458f9a62331e94c96865fa7bc4a78039a3996e7de89180abc716edc2a2ac3.
  Six new/35 focused pinned cases/58 subtests pass; two strengthened
  synthetic restore cases additionally check foreign genesis rejection.
  Full native fold/restore complete:
  infra/local/futures-capital-research/20261113-h1-grid-leverage,
  implementation checkpoint8e440e2. Native5×96344/10×34545 commands,
  total130889; eight new artifacts/eleven unchanged start-end hashes.
  Receiptsha a1c7c03a0e6487f22024edf586d5a0378e88fe16beed764e4af4de1e00786dde.
  All252 new entries/126 normal exits/nine liquidations verified on grids;
  actual entry/decision leverage always equals frozen whole-basket scenario.
  2× reference+9596.82/DD18.01%/zero liquidations retained;
  5×+6434.15/DD29.44%/four liquidations, stages117/60/28/11/7;
  10×−1151.95/DD18.15%/five liquidations, stages19/7/3/0/0.
  No account halt, but stopped slots remain terminal:5× only BTC after
  2024-08-05;10× last real entry2022-10-11/last liquidation2022-10-13.
  10× is not three years active trading. Own unused stage capital remains.
  Further selective leverage needs frozen causal regime criteria;
  liquidation reentry requires separate reconciliation/recovery and real
  capital admission, no implicit reset. No active job.
  Full Classic mapping/historical broker acceptance remain
  separate; no AI/live/holdout/public/DB/dependency change.
  See docs/futures-grid-leverage-results-20261113.md.
- PR53 merged: headfa993f5 ancestor of main174ac6f (GH/fetch verified).
  IP-085 on feat/m1-futures-grid-comparison adds separate current-grid/5:
  current quantity/minimum/market bounds, adverse tick ceiling for buys/
  floor for exits, all six own-capital amounts and frozen2× unchanged.
  Fees/maintenance/funding/exact margin and old price guard retained;
  no public-tariff substitution or complete Classic order-freeze claim.
  Frozen protocolsha8f24a3f0d9a7ba0af3daf497bf5ed2925a5478db35da138ed96a2b95afe84a8d
  before performance; source metadata remains2026 Bitget on2022–2025 native
  Binance prices, no historical broker acceptance. Old profile digest matches
  frozen IP-082; all four old output artifacts rehashed unchanged.
  Thirteen new/122 distinct focused pinned cases/88 subtests pass across
  targeted runs. Corrected new genesis whitelist and funding test fixtures
  (same-time marks);109 legacy cases passed,24 affected cases rerun.
  Native job/full restore complete:
  infra/local/futures-capital-research/20261113-h1-current-grid,
  108427 commands/122675 retained IDs/four artifacts/eleven unchanged
  start-end implementation hashes. Exported receiptsha
  727911a2f49e9814c9aa488ad365a4e451dc7ae86bd933d0d522acb9f95debfd.
  Net+9596.82/DD18.01%,273 closures/233 positive/40 negative;
  no liquidation/account halt/margin rejection. Stages275/128/72/37/24;
  all536 actual entries/273 exits verified on frozen grids.
  Compared with IP-082: net+16.90, DD+0.40 percentage points, margin
  denials29→0;28 old price guards remain uncalibrated. Two end-open baskets
  valued at mark, last actual entry2025-07-29. No active job.
  Next: separate full Classic order-freeze/margin/price-guard calibration
  before further leverage comparison. No AI/live/holdout/public/DB/dependency
  change. See docs/futures-current-grid-results-20261113.md.
- PR52 merged: head8d71aeb ancestor of main5a89712 (GH/fetch verified).
  IP-084 on feat/m1-futures-broker-calibration captures one unsigned public
  Classic USDT contract GET (2026-11-13); five selected original objects
  and source hashes saved. Current quantity steps BNB.01/BTC.0001/ETH.01/
  SOL.1/XRP1; these are current Bitget rules, not historical Binance rules.
  Sixteen focused pinned cases/twenty subtests pass. Static probes of all51
  frozen IP-083 rows: no proposed quantity on current grid; floor alone
  covers all19 margin-only XRP residuals under unchanged old margin arithmetic,
  headroom.00377589–1.10892819 USDT. No price-grid/fee-freeze/acceptance/PNL claim.
  Exact USDT money quantum/rounding remain unknown, no epsilon introduced.
  Classic long opening loss applies order>mark, not mark>order;
  old price guard remains uncalibrated. No UTA formula transfer.
  Metadata receiptsha61c50ac6bc85b86ee176f1c7d926153d899f16c4b4cbeec35437a1a1a37d6e5c;
  probe receiptshad95eb94d18a46e67f67fd6e0f31de59cfd6186905715028de4be5cba64a22ab1.
  Ten baseline implementation hashes unchanged; no full fold/new performance/
  economic policy/runtime/DB/dependency change. Failed local captures/probes
  preserved without success receipt. Next IP-085: separate grid-aware frozen
  research assumptions before leverage comparison. See docs/futures-broker-calibration.md.
- PR51 merged by user; head7c239a2 is ancestor of main165c5f4
  (GH/fetch verified). IP-083 on feat/m1-futures-admission-audit adds a
  read-only reconstruction of remaining native admission rejections.
  Nine focused pinned cases/ten subtests pass; actual funding depletion
  and overlapping mark/margin denials verified synthetically.
  Full baseline fold/export complete after daemon interruption and a corrected
  JSON export (shallow dict primitive/text-byte mismatch); three affected
  pinned cases pass. Final output:
  infra/local/futures-admission-audit/20261113-native-export-corrected,
  109440 commands/530 entries/581 candidates/exact final receipt.
  Four original artifact and ten start/end implementation hashes verified.
  Audit receiptsha4e4b5bf91f13cd8771c0f18b051d28b79305a34e4e8695ea90f3d0faa8d5c86b.
  51 denied attempts/34 cycle-stages; 50 attempts/33 cycle-stages filled later.
  19 margin-only attempts are XRP rounding residuals below1E-8 with7.77–14.01
  USDT own restoration capacity; all filled later. One additional XRP attempt
  combines that residual with price bound. Other nine margin denials are
  first-fill mark premium, up to0.90 USDT; all filled later.
  32 price bounds are a model guard, not proven historical broker rejection.
  One XRP cycle49/stage5 price denial never fills. Next: money precision and
  broker/cost calibration, retain frozen reference and real cash constraints.
  Interrupted/failed earlier directories preserved without success receipt.
  No active job, new performance/risk rule/source or AI/live/holdout/public/
  DB/dependency change. See docs/futures-admission-results-20261113.md.
- PR50 merged by user; head6dfde31 ancestor of mainbde1cee verified via
  GH/fetch. IP-082 on feat/m1-futures-reserved-budget implements Q45's own
  reserved-budget instruction: separate reserved-cash/4. Funding debits
  own isolated cash, no additional global net-funding-quota halt. Only actual
  entry/exit fees and paid restoration consume wallet cost reserve.
  Restoration retains declared remaining regular entry/full exit fee backing;
  unused regular/manual capital never funds restoration. Actual cash,
  initialmargin and liquidation remain hard; full five fills are not promised
  after funding depletion. Q44 own profitable full closing exception persists.
  Frozen protocolsha
  b1892df1eac4a66f157b0576b1efef7017f0e62bccc10c2bedb110441316be21.
  183 distinct focused pinned checks/108 subtests passed (nine new).
  Native H1 job/full restore complete:
  infra/local/futures-capital-research/20261113-h1-reserved-cash,
  109440 commands/four artifacts/eight unchanged start/end implementation
  hashes verified before export. Receiptsha
  4e7d902c7127b317932c75e3b3878ffcaa3971c7863f077f477d2ca490713cec.
  Net+9579.93/DD17.62%,269 closures/no liquidations/no account halt,
  stages271/126/72/37/24; last real entry2025-07-29. Two end-open baskets
  valued at mark; no forced profit exits.29 declared-initialmargin and32
  fill-bound rejections remain; no budget/cash rejection. No active job.
  Historical policies1–3 frozen.
  No AI/live/holdout/public/DB/dependency changes.
  See docs/futures-reserved-budget.md and
  docs/futures-reserved-budget-results-20261113.md. User reviews/merges PRs.
- User confirmed PR49 merged; head0cd45d5 is ancestor of main0c0c7ce
  (verified). All ten corrected native jobs and full restores now complete:
  666180 commands/40 hashes; receiptsha
  979880a5b9fdcadc1a8aa8f11f23e7e1af158c86b68d4ea3d27c2b282470476e.
  Exported and rehashed BEFORE further implementation edits.
  Base2× H1/H4 protection nets+2507.71/+2410.79, no budgethaltes;
  5× and stress cases can exhaust real cost reserve; 10× loses all five
  slots to terminal liquidations. See docs/futures-cash-results-20261112.md.
  IP-080 now implements the already-authorized actual H1-RSI entry comparison
  on new feat/m1-futures-h1-entries: distinct signal policy/journal schema,
  old H4 identities unchanged, same full CashPlan/H1 protection and2×.
  Protocolsha23aefed3d96ff6cb9eb6b404209fc67f227529904131463941ec0c2fb7cb39f1
  was frozen before performance.85 distinct focused pinned tests/57 subtests
  passed (seven new). Native H1 job/full restore complete:46212 commands/
  four rehashed artifacts, receiptsha
  3c6fdfb5b1c5ec6129f9bc7e4c4f1368ec19761f06e0d628707f8b72f12ed130.
  Net+2643.89, DD17.62%,43 closures, no liquidations, stages43/23/15/9/7.
  Real trading stops2023-01-16: profitable BTC cycle4 (+446.84 net)
  costs22.09714550 exceed19.80198020 reserve at full exit, latching global
  budgethalt (command17473). This is not a three-year active H1 result.
  Q44 now explicitly CONFIRMED: only own completed basketprofit covers
  closing overrun. IP-081 separate CapitalRealizedCashPlan realized-cash/3:
  complete normal exit only, same symbol/cycle, net positive after all costs
  and at least entire overrun; never extra cash/profit credit. Open budgets,
  partial exits, other/unrealized profit, liquidations and existing halts
  receive no exception. All six-stage capital/manual reserves unchanged.
  174 distinct focused pinned checks/103 subtests pass (14 new across080/081).
  Frozen protocolsha719716bcc813c1fa22de769c2b86ed43d72b4e0d29a9d133065c06cf0cbf339a.
  Native Q44 job/restore complete after daemon restart, rehashed2026-11-13:
  infra/local/futures-capital-research/20261112-h1-realized-costs;
  64277 commands/four artifact/eight implementation hashes verified,
  receiptsha893bfedeb260b9f4b44589c2719a9135e4876ceda72c87f6285a5294b0c952db.
  Net+3928.28/DD17.62%,98 closures/no liquidations; stages98/48/30/16/13.
  Stops2023-10-02 at XRP cycle21 fundingbatch (command43858):
  open cost19.94101471 exceeds19.80198020 by0.13903451. Q44 does NOT
  exempt this open breach. Existing global halt remains terminal.
  This historical IP-081 remains frozen; Q45 now authorizes the separate
  IP-082 own-reserved-budget interpretation above.
  No AI/live/holdout/public/DB/dependency change. See
  docs/futures-h1-entry-results-20261112.md and docs/futures-realized-cost-results-20261112.md.
- IP-077 `ca98561` merged into main `ab3b4ab` (verified). IP-078 implements
  the complete ten-scenario native market job, explicit Open+1s exits/
  Open+2s same-price valuation/restoration/entries, funding/native offsets,
  terminal liquidation, event drawdown and end-MTM without forced profit exits.
  Seven new/115 distinct focused pinned tests and166 subtests passed;
  byte-identical cached capital JSON plus original335-command journal restore.
  One source cohort/scenario at a time on the2-GB host; failed/terminated
  output directories preserved without successreceipt. Current full native job:
  infra/local/futures-capital-research/20261112-market-canonical.
  All ten native reports/full restores complete:451193 journalcommands and
  40 hashed artifacts. Receiptsha9e7802ecbc7d99bb44d8430ae4b9200c37633cfab5d276c0f8ec5c3e31bc5897.
  Base H1 net2×+687.70/5×+1670.50/10×−625.65 USDT; H4−7.28/−213.35/−725.44.
  Findings are model-only: gross funding cap despite credits, and all-empty-slot
  range reservation halt trading early. Next IP-079: separate corrected cash/
  active-range profile before performance tuning; retain funded six stages,
  manual reserve, real capital/margin/liquidation constraints and frozen baseline.
  No public/DB/dependency/holdout/broker/AI activation.
  See `docs/futures-market-backtest.md` and `docs/futures-market-results-20261112.md`.
- IP-076 `29d76d9` merged into main `ef2aa9b` (verified). IP-077 freezes
  own economic protocol shaeb9a278513facb4f7560413c6ae269dc2fd44adf917eec00ebec9925ddcc8c06:
  five native BINANCE-prefixed slots,2×/5×/10× and H1/H4 protection plus
  predefined2× cost/path sensitivities (ten total). Fees/maintenance/lot/
  insurance are declared assumptions, not historical broker acceptance.
  Native funding reference uses settlement mark or explicit H1-open approximation;
  no timestamp shifts. valued_hour freezes exact boundary marks before day basis;
  atomic funding_batch keeps per-settlement IDs and full journal restore.
  Current liquidation checked before restoration/new price; no phantom recovery.
  Native preflight verified15 artifact hashes/263040 prices/16515 settlements,
  10937 exact-hour events/3363 groups;9595 native marks/6920 approximations.
  Successful receipt2252c6f78054a482a2eb67ecdc344d517aeb46083ce518141ccf0c00b549064c.
  27 new/56 distinct focused pinned cases passed. First failed/killed preflights
  have no receipt; preserve their directories. Cache datasetdigest per stream.
  No market performance, DB/migrations/dependencies or runtime activation.
  Next IP-074/IP-069: implement complete native market job and metrics/journal
  with all frozen scenarios, then report net results; no more source import needed.
  See `docs/futures-economic-profile.md`.
- IP-075 `fd99018` merged into main `d0fa375` (verified); user approves
  continuing and PR creation with working GH CLI. IP-076 adds own
  `futures_capital_journal.py` plus versioned larger capital identity policy:
  full genesis replay of H4-RSI/five stages/H1 or H4 protection, fixed
  leverage cycles, funding, day bases and terminal liquidation losses.
  Default250000 retained IDs, explicit max1000000; legacy max100000 unchanged.
  23 new/99 distinct focused pinned cases passed; synthetic five-coin1200h/
  6000-command/6050-ID full restore and all100005 retained IDs verified.
  Owned0600 create-only/exclusive file,512MiB/250000-command bound,
  acknowledged minimum receipt and unknownwrite stop/readback, no retries.
  No existing module/codec/dependency/DB/runtime mutation or market job.
  Next IP-074/IP-069: freeze economic costs/funding nominal/margin/liquidation/
  intrabar assumptions, then native net comparison on shared IP-075 source.
  See `docs/futures-capital-journal.md`.
- IP-074 `2d7878f` merged into main `507cb87` (verified). IP-075 adds own
  native H1 source/import for BNB/BTC/ETH/SOL/XRP,2022-08-01..2025-08-01:
  263040 trade/mark candles,16515 fundingevents,295 unsigned GETs. All fifteen
  saved hashes/digests and ten axes verified. SOL has75 additional unique
  settlements within8h diagnostic buckets in November2022; preserve them.
  BTC/ETH funding unchanged, six H1-aggregated versus native-H4 differences
  recorded; do not silently repair old sources or mix comparison axes.
  22 new cases/50 distinct focused pinned cases passed. No holdout, market
  performance or runtime activation. Next: frozen economic assumptions and
  full new-profile journal/identity capacity before net study. See
  `docs/futures-hourly-history.md`.
- IP-073 `b9a9c0e` merged into main `452c9d8` (verified). IP-074 adds
  `futures_capital_signals.py`: closed H4 RSI/rearm, five own-capital buys,
  frozen basket leverage and separate closed H1/H4 Supertrend protection.
  Explicit finer trade/mark observations, latched liquidation before new
  entries, truthful funding/partial-exit net floor; genesis-only start.
  27 new cases and105 focused pinned cases/46 subtests passed. Capital-only
  full-fill research, no broker/AI/runtime authority. Native H1 cohort,
  frozen market assumptions and new-profile full journal restore remain
  IP-074/IP-069 before market performance. See `docs/futures-capital-signals.md`.
- IP-073 implements Q41–Q43 in separate `futures_capital_research.py`:
  own-capital stages, frozen per-cycle leverage, account/stress diagnostics,
  reconciled own-basket liquidation and unused-reserve accounting. Capital
  admission/full synthetic fills only, not RSI or broker authority. Legacy
  pending/signal wrappers explicitly reject the new plan. No active AI,
  journal restore, native-market net result or runtime activation. Next IP-074:
  RSI/H1-Supertrend integration and frozen native Futures research profile.
  See `docs/futures-capital-research.md`.
- Q41,2026-11-12 supersedes earlier mandatory6%/8% account-admission guidance
  for the next Futures research variant: user requires the approved full
  six-stage budget, without account-loss/correlated-stress gates preventing
  its use. Record6%/8% as warnings and−50% correlated account stress as
  diagnostics in the new profile, not hard gates. Preserve actual budget,
  signal/manual-reserve, execution-integrity and liquidation constraints,
  and−55% emergency exit. Old frozen research/Paper profiles remain historical.
  Q42 resolves the table amounts as own entry capital; position purchase
  notional is that amount times leverage. User accepts liquidation before all
  five regular buys at higher leverage; no mandatory−50% survival gate for the
  new variant. Initialmargin/current liquidation/budget/order integrity still
  apply. Q43 confirms later AI regime/risk evaluation before the first buy
  freezes leverage for that entire basket, including all subsequent buys.
  No reassessment changes an open basket's leverage. Exact AI criteria remain
  unvalidated; no active AI or live/public activation.
  See Q41–Q43 in `docs/interview.md` and `docs/futures-capital-ladder.md`.
- Confirmed Q1–Q5: private invitation pilot, cockpit/backtests/paper before live,
  independent hard risk limits, controlled AI promotion, and free external
  tools/accounts first. TradingView Essentials is the existing paid subscription.
  Do not book additional paid services without a new concrete decision.
- Confirmed Q6–Q8: plan both Bitget and MT5 for the first release; modular
  monolith with separate workers, Python/FastAPI, Next.js/TypeScript and PostgreSQL;
  separate cockpit login with MFA.
- Confirmed Q9–Q14: BTC/USDT and ETH/USDT spot without leverage on H4;
  XAUUSD trend/pullback with H1 regime and M15 entries after validation;
  written crypto prompt over older images; 25% growing quote amounts, 5% drop
  from the last actual entry, -50% stress from the first entry; Docker Compose
  from the start; local Authelia OIDC/MFA with administratively provisioned users.
  Do not infer approval for systemd deployment.
- Confirmed Q15–Q22: RSI14/Wilder closed-H4 signals; Supertrend ATR10/Wilder ×3
  protection with net-breakeven floor and no further buys; crypto paper 10,000 USDT,
  each basket 500 principal +5 costs, 6% daily/8% initial loss and -55% first-fill
  exit; independent MT5 broker demo, 0.25% idea risk, one idea, 1% daily/5% initial loss.
  The sixth tranche is a reserved manual entry as clarified by Q23.
  Plan a public central HTTPS entry for the invitation-only pilot and existing free
  SMTP. Public rollout still needs approval.
- Confirmed Q23–Q28: keep the buffer exclusively for a manual entry and inform
  the user; no automatic -40% trigger. Administrative MFA reset after email
  confirmation; MT5 is on a separate home-network server, using an outbound
  authenticated HTTPS bridge. Research targets: 3 years crypto/2 years gold,
  positive independent net holdout, PF >=1.2 and 30 baskets per crypto asset/
  100 gold trades in holdout. Pilot backup targets RPO 24h/RTO 4h with encrypted
  external and protected offline copies. M1 scope is confirmed; actual AI,
  full news/calendar feeds, live/FTMO/customer decisions follow later gates.
  Q29–Q30 confirmed: buffer after five regular stages, one manually confirmed
  entry, no RSI required but price <=95% last regular fill; preview/MFA and all
  risk/protection gates. Once-only cockpit notice plus optional user-enabled email.
  Do not simulate hindsight-selected manual fills as automated performance.
- M1 substantive interview decisions Q1–Q30 and Q31 final shared understanding
  are confirmed. The user explicitly instructed implementation to begin.
  Reviewable summary: `docs/implementation-brief.md`.
- Original requirements: `docs/project-info.md`; complete draft: `docs/concept.md`.
- Architecture/stack proposals: `docs/architecture.md`; trading: `docs/trading.md`.
- Track work in `docs/tasks/board.md`, milestones in `docs/roadmap.md`,
  deferred work in `docs/backlog.md`, and user decisions in `docs/interview.md`.
- Read `docs/memories/decision-log.md` and `docs/memories/gotchas.md` before
  implementation; consult `docs/inventory.md` before reusing legacy code.
- Preserve the original project prompt. Label unresolved requirements and
  proposed defaults explicitly; an unanswered interview question is not approval.
- Local bootstrap and M1 implementation are authorized. Keep live trading and
  public/production rollout behind their separate approvals.
- The user explicitly authorized autonomous local commands and asks for concrete
  interim acceptance notices. Continue routine local implementation without
  repeating permission questions; tool sandbox escalations still apply.
  Reconfirmed2026-11-08: execute local commands independently, without renewed
  routine approval questions. Production deployment remains separately gated.
- The user explicitly authorized intermediate commits and GitHub pushes.
  Push reviewed feature checkpoints with the existing repository deploy identity;
  this does not authorize production deployment, history rewrite or force-push.
- 2026-11-12: user also authorizes creating Pull Requests; they review/approve
  them themselves. No merge authorization inferred. Existing deploy SSH identity
  supports pushes; PR creation still requires an authenticated GitHub API/plugin.
- User provisioned GH CLI2.46.0 on host; authenticated cadm-balzer with
  repo/read:org verified. Use `gh pr create --body-file` for reviewed checkpoints.
  Network sandbox can falsely report an invalid token on `gh auth status`;
  retry outside it before changing authentication. Never print `gh auth token`.
- Default foundation: `infra/README.md` starts five services behind loopback and
  the optional offline research worker. Immutable H4 snapshots, frozen jobs and
  persisted net results/equity charts are implemented. A real 90-day BTC import
  tests the workflow; it does not satisfy the three-year/holdout validation gate.
  Broker execution, recovery and pilot operation remain unfinished.
  Generated `infra/local/` is ignored and never a build context.
- Existing reference repositories: `/opt/investalo-trading-system` and
  `/opt/investalo-autotrader`. Treat them as read-only references unless work there
  is explicitly authorized. Their strategies need independent net-cost validation.
- Bitget account clarification after Q31: the user's funded account is Classic
  with separate spot/futures wallets. Each platform user creates a dedicated key
  in their own Bitget account (API key, secret and passphrase). Initial private
  adapter is Classic V2. Keep wallet capital separate; do not infer permission
  for futures trading, transfers or real-money activation from funded balances.
  Connection/onboarding scope: `docs/bitget-connection.md`.
  Isolated stdlib Classic read core: `integrations/bitget/README.md`, 24 offline
  tests in `tests/bitget`. Private store/onboarding integration exists below;
  actual user keys, HTTP/UI and broker calls remain IP-009/IP-015.
  Only three fixed GET paths.
  User accepted checkpoint `3052560` and will merge it themselves.
  GitHub default branch is `main`; verify merge state before changing branches.
  Main now contains accepted checkpoint and acceptance note (`3fd95b1`), verified
  at `d3b31e2`; envelope checkpoint `7f83b33` merged into main, verified at
  `71e57f1`; store checkpoint `46860ab` merged into main, verified at `b3030de`;
  onboarding checkpoint `69a1f8b` merged into main, verified at `56070ba`;
  step-up checkpoint `d57bd56` merged into main, verified at `b6198f7`;
  registry checkpoint `6a18102` merged into main, verified at `f422a90`;
  current work branch: `feat/m1-paper-preview-integration`.
  Isolated AEAD core: `packages/credentials/README.md`, 20 offline tests with
  pinned cryptography and a separate hardened Compose check.
  Credential store: `services/credentials/README.md`; migration003 and current
  AAD/CAS/rotation/revocation verified with 19 client +18 actual PostgreSQL tests,
  four provisioning tests and a rolled-back role-drift probe. Both local DBs
  `investalo` and `investalo_credentials_checks` now have001–007 applied.
  Applied migrations are immutable in either database.
  Credential LOGINs are bound through SESSION_USER to one active tenant/user;
  runtime/research cannot read tables or execute credential functions.
  The administrative check profile mounts migration credentials; it is not a
  restricted runtime service.
  Private `BitgetOnboarding` connects the existing Classic probe, canonical
  triple codec, store and dedicated request-bound one-use assertions.
  Migration004 commits a globally unique JTI before probing, rechecks actor/
  epoch/reauth/account/versions/time and finishes write/audit in one transaction.
  SQL trusts Python signature verification; direct003 functions remain trusted
  primitives, without a universal MFA guarantee. The007 proof remains separate
  from003/004 credential execution.
  `DevelopmentKeyFileProvider` explicitly requires development mode and fixed
  trusted fingerprints, ownership/modes and 32-byte KEKs; no production provider.
  Tests use synthetic assertions/keys/broker responses with actual PG.
  120 checkcontainer tests passed: 19 client, 41 onboarding units, 60 actual PG
  (18 store, 30 authorization, 12 synthetic Bitget/AEAD flows). IP-030 complete.
  Credential HTTP/UI, physical browser step-up and actual user credentials remain unfinished.
  Additive005 exposes only authenticated own account/connection metadata to
  the runtime LOGIN; no UID/envelope/key material or direct private-table rights.
  112 API/worker and120 credential regression tests passed after005.
  Prepared BFF state binds session/CSRF/actor/tenant/epoch/target/CAS and an
  opaque preview token against stale tabs. All sensitive HTTP/UI steps stay off.
  Authelia4.39.28 password reauth preserves old second-factor state; auth_time
  plus amr=mfa proves no fresh second factor. Do not weaken this release gate.
  User explicitly approved additional free Cockpit passkeys for account changes.
  SimpleWebAuthn14.1.0 checks UV/UP/exactRP/origin/challenge/owner/key/counter.
  Additive006 implements durable FORCE-RLS registry, one factor per tenant/user/
  RP and RP-wide credential uniqueness including revoked rows. Administrative
  enrollment uses manually attested email approval plus opaque confirmation UUID;
  32-byte bearer ticket is stored only as hash, max600s, with claim committed
  before crypto and max120s enrollment. Local BFF/UI enrollment binds current
  actor/epoch/session/CSRF/Origin and consumes each attempt once.
  ES256/UV/UP/fmt=none registration is a candidate, not first-use private-key
  proof; a fresh assertion remains mandatory before sensitive actions.
  Admin revocation advances global user auth_epoch/reauth_after and invalidates
  all tenant sessions. Terminal tombstones prevent recovery/re-enrollment;
  BL-025 remains open. SQL assertion CAS is a trusted primitive without challenge
  replay proof; no unbound HTTP CAS endpoint. Physical browser acceptance and
  credential integration remain IP-033; account changes stay disabled.
  Migration006 passed293 API/worker checks including67 actual registry/API PG
  cases;120 credential regressions and115 cockpit tests passed. Typecheck,
  builds and48 real HTTPS checks passed; two independent reviews found no blockers.
  A complete synthetic BFF enrollment is now verified in IP-037; physical device
  proof remains IP-033.
  Applied001–007 are immutable.
  Session TTL store holds enrollment attempts only;
  preserve original OIDC claims. See `docs/passkey-step-up.md`.
- User explicitly approved the public development preview on2026-11-07 after
  adding auth DNS. Both cockpit.investalo.de and auth.cockpit.investalo.de now
  resolve to5.45.96.83 and serve valid Let's Encrypt certificates through Caddy.
  Active opt-in `--file infra/compose.public-preview.yaml` exposes only edge80/443;
  default Compose remains local and must not accidentally replace the overlay.
  Twelve preparation/provisioning tests and48 real public HTTPS checks passed;
  certificate persistence after restart and original identity/data bindings verified.
  The separate public-issuer synthetic user explicitly shares the existing
  development tenant; old user, worker, keys and factors remain unchanged.
  RP/credential ownership is not migrated. IP-035 complete; BL-026 TLS operations
  and full pilot/production acceptance remain open. Account changes/live remain off.
  See `docs/https-entry.md`.
- HTTPS checkpoint `35960f3` is merged into main `e741c6b` (verified).
  User confirmed successful public browser login and Google Authenticator setup,
  accepted the visible progress, and instructed continued M1 work.
  IP-036 implements the internal durable target-bound passkey proof in additive007:
  committed one-use claim before crypto, RP-wide unique challenge, immutable
  actor/session/CSRF/origin/old OIDC time/metadata/factor bindings, atomic
  counter/version CAS plus grant, and own-preview confirmation consumed once.
  API/SQL trust the authenticated BFF crypto verdict; original OIDC claims stay
  unchanged and checked_at is separate. Confirm reports execution_enabled=false;
  no account-action browser routes or003/004 credential execution enabled.
  Full regression:461 API/worker (70 new actual PG),143 cockpit (28 new crypto),
  120 credential checks, typecheck and pinned builds passed; independent reviews
  found no blockers. Both DBs001–007 immutable. Running preview containers were
  not recreated. Hardware/browser acceptance and credential integration remain
  IP-033; retention/rate operation BL-017, recovery BL-025.
  See `docs/passkey-action-proofs.md`.
  Implementation checkpoint `9b47ae1` and acceptance note `4c9f63f` are merged
  into main `2c996d5` (verified). If the inherited SSH agent stalls, use the existing deploy identity
  with IdentityAgent=none and strict host-key checking (see `TOOLS.md`).
- IP-037 connects007 to gated proof-only `/security/passkeys/verify` and four
  `/api/passkeys/actions/` POST routes. Explicit
  `COCKPIT_PASSKEY_PROOF_PREVIEW=1` is required; default and public Compose keep
  it off. Pass the immutable session that authorized HTTP CSRF to the adapter;
  recheck identity/epoch/original OIDC time/expiry/CSRF/origin after awaits.
  Browser receives only safe preview/options/grant fields; tokens remain in
  page memory. Enrollment preserves original expiry and requires authoritative
  factor readback after write. 265 Cockpit tests, typecheck and pinned build,
  90 isolated HTTPS/BFF/API/PG checks, nine disabled checks and eight fixture
  preparation security tests passed; independent review has no remaining blocker.
  Test services use dedicated synthetic keys, fixed protected `/tmp` state and
  the fixture DB, no host ports; all are stopped. Running public services were
  unchanged and remain healthy (HTTPS200). No migrations/dependencies changed.
  These checks use synthetic P256/approval, not physical devices or real email
  attestation. Public activation, physical acceptance,003/004 integration,
  recovery and pilot operation remain open. See `docs/passkey-browser-proof.md`.
- IP-037 checkpoint `84f7633` is merged into main `512c096` (verified).
  IP-038 adds an isolated versioned TS/Python passkey credential assertion
  contract: distinct audience/kind, purpose receipt, actor/session/target/CAS,
  metadata digest and exact body bytes. Preserve original OIDC time; fresh
  passkey check and credential consent times are separate. Do not fabricate AMR.
  The receipt parser accepts trusted server inputs; it cannot prove durable
  issuance. Signing and verification are repeatable, with no DB consumer.
  A007 proof-only confirmation is not credential consent. Explicit purpose
  authority and global consumption are implemented by IP-039 below; final
  credential writer integration remains open.
  New signer/verifier have no HTTP/runtime caller; old contracts and001–007
  remain unchanged. Optional `credential-assertion-checks` runs offline tests
  without network, secrets, mounts, ports or DB dependencies; existing services
  are unchanged. Physical acceptance, integration and recovery remain IP-033.
  333 Cockpit tests,77 offline onboarding tests on host and pinned Python3.14.10,
  109 actual TS/Jose/Python checks, typecheck and pinned Cockpit build passed.
  Independent review has no remaining blocker. Historical461 API/worker,
  120 credential and99 HTTPS fixture cases were not rerun. Public services
  remain unchanged/healthy/TLS200, proof flag off.
  Contract and validation: `docs/passkey-credential-assertions.md`.
- IP-038 checkpoint `8bb64db` is merged into main `13ba2e2` (verified).
  IP-039 adds explicit purpose authority in008: purpose/origin/body digest
  frozen at prepare, explicit consent only from a still-granted007 proof,
  global one-use consume and a separate final transaction lock.
  A proof-only007 confirmation cannot be converted into credential consent.
  The private client verifies the dedicated30-claim assertion before DB access
  and returns a client-bound handle only after acknowledged consume commit.
  Unknown commits never trigger automatic retries. SQL trusts authenticated
  Python/BFF crypto; it is not a signature verifier. Current SESSION_USER actor,
  epoch/reauth/original OIDC, factor, metadata/CAS and clock are checked at both
  boundaries. Final lock is terminal across commits, repeatable within its TX.
  No003/004 executor, HTTP route, broker or runtime activation is connected.
  Reviewed008 was preflighted in a fully rolled-back transaction, including
  actual runtime preparation, then applied ONLY to investalo_credentials_checks.
  Its immutable checksum is9328008652ad697a306093301d9488fe3e0b184a3ffd8333f7beda5924712c57.
  Development DB investalo remains001–007; never blindly run default migrate/up.
  271 credential tests (19 client,95 offline,157 actual PG,97 new PG cases),
  rerun461 API/worker checks and pinned migrate/storage/API-check builds passed.
  Independent review has no blocker. Public services unchanged/healthy/TLS200.
  Historical333 Cockpit/109 interop checks were not rerun; TS signer unchanged.
  Validation and remaining integration: `docs/passkey-credential-authorizations.md`.
- IP-039 checkpoint `389082a` is merged into main `be13145` (verified).
  IP-040 connects the private `PasskeyBitgetOnboarding` executor:
  committed008 consume before any read/probe, separate008 lock +003 AEAD
  mutation +009 terminal completion in one final transaction. Exact verified
  claims/SESSION_USER/current lock XID and permitted postmutation CAS state
  are required; actor/factor/account/time remain current. Clock is checked
  after audit/FK waits. Failures roll back final write/lock/completion while
  consume remains; unknown commits never retry or overwrite completed audit.
  Revoke needs no key read/decryption/probe and permits paused accounts.
  009 passed fully rolled-back DDL and actual failed-completion preflight,
  then applied ONLY to investalo_credentials_checks. Its immutable checksum:
  435d658458c6be7359ab19ad575421fb843c8756975710cc651eff41c4d62b75.
  Old001–008 unchanged; development investalo remains001–007. No HTTP caller,
  real broker transport/key intake or public flag activation. 356 pinned
  credential tests passed (19 client,116 offline,221 actual PG;64 new PG),
  including real signed receipts, AEAD writes, audit-wait expiry and unknown
  commit cases. Pinned builds and independent review passed. Public services
  unchanged/healthy/TLS200. Rerun461 API/worker tests passed against fixture009.
  Contract: `docs/passkey-credential-execution.md`.
- IP-040 checkpoint `3476f74` is merged into main `0fd25b6` (verified).
  IP-041 implements private BFF orchestration and default-off008 API
  prepare/authorize routes, preserving the original session and explicit
  credential consent. Integration checks use synthetic keys and the isolated
  fixture database. No browser credential intake, runtime credential service,
  public flag or migration activation is included in this checkpoint.
  Original session/CSRF/Origin/OIDC and current actor/factor/metadata remain
  bound after awaits; explicit credential consent cannot reuse007 proof-only
  confirmation. Exact private body stays solely in trusted caller memory.
  572 API/worker tests (111 new:87 unit,24 actual PG),385 Cockpit tests
  (52 new),299 real synthetic TS/WebAuthn/HTTPS/API/PG/Jose/Python/AEAD/009
  checks, typecheck, pinned builds and independent reviews passed.
  Existing001–009 immutable; investalo001–007, fixture001–009 verified.
  Historical356 credential tests were not rerun; private Python/SQL unchanged.
  User restarted host; protected synthetic /tmp state regenerated by the
  existing preparation script, then fixture completed. Fixture APIs stopped;
  six public services healthy, regular TLS HTTPS200. See
  `docs/passkey-credential-cockpit.md` for remaining browser/runtime gates.

- IP-041 checkpoint `cd66c3a` is merged into main `c573ab3` (verified).
  IP-042 implements an injected private development HTTPS transport with mutual
  TLS, a dedicated CA and pinned BFF client certificate. Trusted original
  session context is separate from the opaque credential JWT; actor/role/DSN
  selection remains fixed server configuration. Only synthetic fixture checks;
  no production launcher, runtime key provider, browser intake or public flag.
  The stdlib HTTP server is development-only, never a production acceptance.
  User reconfirmed continuing M1 and the need for longer BTC backtests:
  three-year BTC/ETH research and independent holdout remain IP-011/IP-013/BL-018;
  the current90-day snapshot is only workflow proof.
  376 pinned credential tests (20 new HTTP/mTLS),440 Cockpit tests (55 new),
  typecheck and346 real mTLS/HTTPS/WebAuthn/API/PG/AEAD checks passed.
  Existing pipe flow306 checks rerun/passed; overlapping runs are not additive.
  Independent review has no remaining blocker; prior572 API/worker tests
  were not rerun (API/migrations unchanged). Fixture APIs stopped, six public
  services healthy, regular TLS HTTPS200; DB007/fixture009 verified.
  Pinned Python/Node fixture and Cockpit builds passed; running preview
  containers were not recreated. No new dependencies or migrations.
  Contract: `docs/passkey-credential-https.md`.

- IP-042 checkpoint `94fb73b` is merged into main `6300971` (verified).
  IP-043 adds an explicit synthetic-only development credential launcher and
  isolated container. Fixed fixture DB/LOGIN, actor and008/009 capabilities
  are verified before listening; ambient PG options are rejected. Owned0400
  files pin separate signing/KEK identities and the mTLS client certificate.
  Exact synthetic canaries are required before verifier/consume; broker is
  synthetic. Runtime mounts no migration/API/research password or BFF client
  private key. Administrative setup/audit mode mounts no credential LOGIN
  password and never calls the executor. New per-run UUID state is create-only;
  no new dependencies or migrations. Stdlib HTTPS/file provider remain
  development-only; production server/provider, physical/browser acceptance
  and real keys/broker remain open. See `docs/credential-development-service.md`.
  401 pinned credential tests with52 subtests (25 new launcher cases),10 host
  preparation tests and440 integrated restricted-service/mTLS checks passed.
  Default image without development opt-in rejects before network startup.
  Pinned runtime/Python/Node builds and independent review passed.
  Historical injected HTTPS387 and pipe329 checks rerun/passed; overlap is
  not additive. Prior440 Cockpit/572 API-worker suites not rerun; app code
  unchanged. All migration checksums normal007/fixture009 verified.
  Fixture containers stopped, six public services unchanged/healthy,
  cockpit/auth regular TLS HTTP200.

- IP-043 checkpoint `998bb90` is merged into main `9f2a9a5` (verified).
  IP-044 replaces the synthetic service's stdlib HTTP engine with the existing
  pinned Uvicorn/h11 stack. Controlled accepted sockets bound TLS handshake
  and absolute deadlines; peer fingerprint and raw framing are checked before
  parsing. Socket and executor work capacity remain separate across disconnects.
  The launcher remains synthetic-only; no production/provider/broker/public
  activation or migration changes. See `docs/credential-asgi-transport.md`.
  419 pinned credential tests and52 subtests passed, including18 new actual
  TLS/ASGI cases and221 existing actual PG cases. 451 restricted-service/mTLS
  integration points, both Python builds and independent review passed.
  Default image rejects startup without --development. Historical440 Cockpit/
  572 API-worker and older HTTPS/pipe integrations not rerun; code unchanged.
  All migration checksums normal007/fixture009 verified, testcontainers stopped,
  six public services unchanged/healthy and cockpit/auth regular TLS HTTP200.

- IP-044 checkpoint `9555624` is merged into main `dcb9feb` (verified).
  IP-045 implements an isolated browser credential flow: bounded
  session-bound continuations, three strict HTTP phases, browser memory only
  and explicit credential consent after the passkey. Runtime providers and
  public activation remain separate gates; fixtures use synthetic keys.
  540 Cockpit tests (100 new), typecheck, pinned Cockpit/Node fixture builds,
  481 actual controller/HTTPS/restricted-service checks and six actual Next
  default-off route checks passed. Existing service regression460 checks
  passed; overlapping runs are not additive. Final independent review has
  no blocker. Python/SQL suites419/572 not rerun; no dependency/migration
  changes. Normal007/fixture009 checksums verified, testcontainers stopped,
  six public services unchanged/healthy, cockpit/auth regular TLS HTTP200.
  The runtime browser provider deliberately returns unavailable until its
  signing/mTLS identity is provisioned; no flags enable arbitrary key intake.
  The activated fixture uses an injected synthetic cookie resolver, not actual
  Next session storage, browser SameSite or physical authenticators.
  Real provider/key operation, Next/device acceptance, quotas/worker routing,
  reconciliation/recovery and real broker/egress remain open.
  See `docs/credential-browser-flow.md`.
- User confirmed IP-045 merged; checkpoint0a0751b is ancestor of main073c474
  (verified). The user explicitly asks to prioritize the actual trading and
  backtesting system. Continue IP-011/012/013 with multi-year BTC/ETH research
  and then Paper; defer further credential runtime activation. Public-data
  backtests need no private keys. IP-046 technical protocol is recorded before
  performance: fetch2022-08-01..2026-08-01, research first3y, reserve last1y
  solely as holdout. These explicit checkpoint windows are not an approved
  economic validation split or altered strategy. Previously evaluated90-day
  BTC demo is excluded; no ordinary holdout job/worker access.
  See `docs/long-history-backtests.md`.


- IP-046 complete: public BTC/ETH sources8766 H4 bars each, research6576 and
  reserved holdout2190, all gap-free. Exact immutable window CLI; operator
  holdout staging uses existing administrative rights, no new API/SQL grant.
  Both actual public-development research jobs succeeded and their net metrics
  match deterministic core replay exactly. Only research simulated; read-only
  audit confirms four window datasets, no full source import, zero holdoutjobs.
  66 pinned core tests/33 subtests,5 metadata fixturetests,572 API/worker and
  48 actual HTTPS checks per asset passed; independent review has no blocker.
  NormalDB007/fixture009 immutable; public six services unchanged/TLS200.
  Full api-checks MUST use -e PGDATABASE=investalo_credentials_checks, because
  its default normalDB lacks008; never migrate normalDB to repair tests.
  ETH HTTP fixture reads bounded pinned Next JSON clientprops, not browser
  hydration. Economic validation/costcalibration remain open. Next is IP-047:
  persistent simulated paper orders/fills/risk/journal, same core, no keys/live.
  Frozen protocol: docs/research-protocols/crypto-h4-20261108.json.


- 2026-11-09: IP-046eb62176 merged into maindd1903b (verified). User explicitly
  requests lower LLM/API costs: small scoped reads/outputs, bounded checkpoints,
  no repeated broad tests or extra agent calls for routine work. Persist this
  preference; never claim a numeric cost reduction without billing evidence.
  IP-048 adds incremental PaperRunner/checkpoint/journal contract inside IP-047.
  84 pinned focused tests/48 subtests pass,14 new Runner cases. Existing defaults
  and dependencies unchanged. Restore binds actor/account/config/cost/mode;
  no DB writer/feed daemon/HTTP activation yet. Next: PostgreSQL CAS and atomic
  append-only journal, then worker/Cockpit. See docs/paper-runner.md.

- IP-048 checkpoint `fe6309a` merged into main `dc60c19` (verified).
  IP-049 implements private PaperStore and atomic010 checkpoint/journal CAS.
  Dedicated paper LOGIN uses SESSION_USER account binding; no direct tables,
  credential access or new runtime/research rights. SQL trusts Python economic
  calculations. Require fresh non-autocommit connections; unknown commits
  require readback, never automatic retry. 78 pinned tests/15 subtests passed,
  including29 actual PG cases; independent review has no remaining blocker.
  Reviewed010 applied ONLY to investalo_credentials_checks after rolled-back
  DDL/worker/failure preflight. Immutable SHA256:
  812a0a1f1702f09ef3b9410640eae7b60498320326888a86c494a83f8f3f5797.
  Development investalo remains001–007; fixture001–010 verified.
  NEVER default migrate/up to repair tests. Fixture-only TLS/SCRAM HBA added;
  PG config reloaded, public containers not recreated, cockpit TLS200.
  Synthetic fixture password rotated after a connection trace; factory errors
  now sanitized. No real credentials affected. No builds/dependencies added.
  IP-047 next: public market feed, running Paperworker and Cockpit status.
  See docs/paper-postgres-store.md.

- IP-049 checkpoint e0cfb45 merged into main1a805e5 (verified). IP-050 connects
  fixed unsigned Bitget SPOT ticker/current-candle GETs to PaperRunner/Store.
  BTC/ETH,40 closed-H4 warmup, complete coverage/revised overlap/fresh real
  bid/ask, no historical fills or manual approval. Every input commits atomically;
  unknown commit stops process, next process reads state before new inputs.
  Only explicit --once or --cycles1..100 accepted. Continuous operation gated:
  REST polling cannot reliably supply exact midnight baseline required by core;
  daily_baseline_required stays enforced, no current-equity substitution.
  Isolated fixture overlay has own Paper LOGIN/CA only, no ports/admin keys,
  separate development egress bridge, existing pinned image/readonly source.
  Real public feed40bars each; actual cycles82/84/86 then restart88, zero fills.
  151 pinned tests/48 subtests,30 actual PG; independent bounded review green.
  Normal007/fixture010/checksums unchanged, no migrations/dependencies/builds.
- IP-050 checkpoint af65c51 merged into mainb9d4b41 (verified). IP-051 adds
  read-only own-tenant Paper status/journal API and gated Cockpit panel.
  API_PAPER_STATUS_PREVIEW and COCKPIT_PAPER_STATUS_PREVIEW default off;
  Default Compose/public preview unchanged. Stored inputs do not prove a
  running worker; historical/missing valuation and absent daily baseline
  are explicit. No strategy, risk, writer or execution change.
  Reviewed011 preflight fully rolled back, then applied ONLY to
  investalo_credentials_checks; normal001–007/fixture001–011 and all applied
  checksums verified. Applied011 immutable SHA256:
  8065031b7eb57486013282e84b91bd6fb3c205155f9aec1ca81b5470b9430f72.
  Restricted runtime function rechecks active user/member, original OIDC and
  epoch; SQL trusts authenticated API and transaction-local identity GUCs.
  No direct Paper table/writer rights. 170 pinned targeted tests/48 subtests
  (37 actual PG/API),16 Cockpit contract/SSR panel tests, typecheck/pinned build
  and scoped independent review passed. No new dependencies/broad credential
  repeats. Existing public containers unchanged/healthy, cockpit TLS200.
  Q32 was pending at this checkpoint; approved and implemented by IP-052 below.
  IP-047/BL-028 continuous operation/activation still open.
  Contract: docs/paper-status-readmodel.md.
- IP-051 checkpoint05ea009 merged into main5d5c61e (verified).
  User explicitly approved Q32 H4-close midnight Paper model valuation and
  reminded RSI relevance. IP-052 adds day input paper-h4-close/1 before any
  new-day quote/fill. Prior persisted cash/inventory, exact BTC/ETH midnight
  bars, committed evidence and replay-stable baseline; no retroactive repair
  of already changed post-midnight inventory. Missing evidence blocks buys.
  RSI14/Wilder closed-H4 automatic entry/rearm rules,6%/8%, real quote fills,
  protection and latched halts unchanged. Manual sixth-stage Q29 unchanged.
  Historical simulator/frozen Research results unchanged. No competing Paper
  quote-driven day reset.012 guards frozen midnight candle digests across
  restart and exposes model label through default-off status API/Cockpit.
  Fully rolled-back actual writer/replay preflight and scoped review passed;
  012 applied ONLY to fixture, now immutable SHA256:
  b79857a01fa9eba1dbac5d9d46a10432723b4bd97e2b9ad89ca47c1198b2fa0a.
  Normal007/fixture012; no new dependencies/normal migration/public activation.
  190 distinct targeted Python/PG cases/48subtests passed (43 actual PG/API):
  full189 plus corrected invalid test OHLC/targeted3;17 Cockpit SSR/contracts
  and typecheck/pinned Cockpitbuild passed. Normal007/fixture012/all hashes
  verified; existing public containers unchanged/healthy/cockpit TLS200.
  Continuous service still gated on operational
  acceptance; bounded once/cycles remain. Contract: docs/paper-midnight-basis.md.
  Public six services unchanged/Cockpit TLS200; one-off fixtures stopped.
  Tests rebind fixed investalo_paper_tests LOGIN: prepare a new fixture/env after tests,
  never blindly reuse older account configuration. Next IP-047: safe daily
  baseline operation, dedicated persistent development identity and Cockpit.
  See docs/paper-market-worker.md; cost preference remains scoped work.


- IP-052 checkpointc1703c1 merged into maina996bf2 (verified).
  IP-053 adds fixed local fixture LOGIN investalo_paper_development and stable
  protected prepared/bound manifest; never rebind/rotate/unpause automatically.
  Repeated provisioning and four rolled-back privilege/binding drift probes pass.
  Explicit paper-development profile: no ports, own password/CA, readonly code,
  bounded resources/logs and restart:no. Strict development-loop fixes PG
  identity/config and rejects extra PG variables. Separate autocommit advisory
  singleton session with guards before writes/health; lost session/unknown
  commit terminal. CAS remains authoritative across cooperative check/write gap.
  Six consecutive failures stop; max24h for new cycle starts, not hard wall
  for already-running work.44 targeted pinned worker cases/3 provisioning units
  and actual restricted TLS/duplicate/release/session-loss/normal-DB denial pass.
  Real feed revisions82/84/86, fresh process88; no fills. Local service healthy,
  duplicate process rejected, controlled restart continued102+ after100.
  Synthetic account separate from rebinding tests; RSI/Q32/risk unchanged.
  No migration/dependency/public activation; normal007/fixture012 hashes verified.
  Public six services unchanged/TLS200, status flags off, fixture has no public
  user. Retention/quota/Egress/monitoring/recovery and actual midnight observation
  remain BL-028; next IP-047 user/status integration. Keep scoped checks for cost.
  Contract: docs/paper-development-runtime.md.


- IP-053 checkpoint03fee1e merged into mainb0827ba (verified).
  IP-054 activates read-only own Paper display within the already approved
  public DEVELOPMENT preview. Normal investalo and fixture now001–012;
  reviewed008–012 applied atomically only after full rolled-back DDL and actual
  own/foreign/epoch/old-OIDC/revoked-membership runtime preflight. Immutable files
  unchanged.008/009 expand private capabilities; actual sensitive flags/routes
  remain off, no credential launcher or key/broker/live activation.
  Stable investalo_paper_preview LOGIN/account under protected existing public
  owner tenant; prepared recovery verifies existing grants before mutation.
  No fixture copying/rebinding, no original user/tenant/research/factor changes.
  Exact normal TLS/SCRAM HBA, fixture/direct-table/other-definer denial tested.
  Strict paper_preview_once --once fixed normal DB/role/CA/secret; no retry or
  listener. Real run revision82/zero fills; RSI/Q32/risk/costs unchanged.
  Only API/Cockpit rebuilt/recreated. For future preview updates use BOTH
  --file infra/compose.public-preview.yaml and --file infra/compose.paper-preview.yaml
  with --env-file infra/local/paper_preview.env. Naked public overlay keeps
  display off and is its fallback; default Compose unchanged. Caddy/Auth/PG/
  Research and separate healthy fixture observation were not recreated.
  34 targeted pinned Pythoncases,5 stdlib provisions,17 Cockpit SSR/contracts,
  pinned builds and scoped review passed.29 real HTTPS/OIDC/MFA/BFF checkpoints
  show own state on overview/portfolio/journal, no cache, sensitive routes503,
  logout only test session/no research job. Both012 hashes and original stable
  fixture identity verified. This is a saved bounded-run state, not a confirmed
  continuously running preview worker or profitability proof. Next IP-047:
  own bounded preview observation; BL-028 midnight/Egress/quota/retention/recovery.
  Contract: docs/paper-preview-integration.md. Keep cost-sensitive scoped work.

- IP-054 checkpoint b48be7d merged into main 2a9efe0 (verified).
  User accepts the visible Cockpit progress and asks to prioritize planned
  strategy fine-tuning because absolute returns are small. IP-013 first
  diagnoses exposure/capital use, RSI entries, exits, costs and a comparable
  benchmark, then bounded chronological candidate validation. Stored IP-046
  research spans three years: BTC +132.63 / ETH +96.09 USDT per separate
  10,000-USDT account (~1.33% /0.96% total). No invested-capital return or
  independent profitability proof inferred. Holdout stays sealed until frozen
  selection; this request does not approve changing strategy/budgets/risk.
  Plan: docs/long-history-backtests.md#geplantes-feintuning.

- Q33 (2026-11-09): user plans 3–5 different crypto baskets concurrently,
  full account capital allocation and later AI evaluation after RSI signals.
  On explicit follow-up user confirms daily6% / initial8% remain binding.
  Allocation is not full investment authority; shared equity/reservations/
  portfolio risk can prevent stages or close baskets early. IP-055 prepares
  joint portfolio research, not an addition of separate asset simulations.
  Additional assets, exact budgets/reservation/priority rules remain to be
  specified. Current BTC/ETH500+5 spot profile and immutable results unchanged.
  AI market phase/Fear & Greed/news/halving context first in shadow mode with
  as-of information, versioned decisions and bounded token costs. Variable
  leverage/fewer stages are future candidates needing separate validated
  strategy/margin rules; no AI override of limits or delay of protection.
  Plan: docs/multi-basket-ai-plan.md; D-059 / BL-029 / IP-021/022/055.

- Plan9455bfe merged into mainef18d74 (verified). IP-056 prepares IP-055
  with separate offline
  joint BTC/ETH research on unchanged500+5 budgets/10k equity, not the expanded
  allocator. Complete atomic on_quotes validates all prices before shared risk;
  explicit historical midnight close checks previous6% before baseline reset.
  Single-quote/Paper/worker paths unchanged. Canonical aligned H4 and separate
  frozen policy digest; passive benchmark shares max budgets/costs/rounding/bid
  terminal valuation, without strategy risk exits or exposure matching.
  Actual6576 researchbars/asset: net228.716909USDT, maxDD0.6143546%,
  held principal time-average72.5594567USDT (0.7255946% initial). Benchmark
  net2577.902525, peakDD12.1144932%, initial loss3.4806339%/daily3.1920850%.
  Peak DD is NOT loss against8% INITIAL limit.56 baskets (BTC24/ETH32) do not
  prove per-asset holdout targets. Fixed file/hash/window replay uses research
  ONLY, no DB/broker/holdout access, migrations/dependencies/public changes.
  New coins requested; expanded budgets/stress/reservations/priority remain
  IP-055. Contract: docs/portfolio-reference.md.
  65 targeted pinned cases/26subtests +4 host inputguards, exact real research
  replay including benchmark loss bases and read-only final review passed.
  No new holdout/selection/physical-browser/public activation claim.

- IP-056 checkpoint698146f merged into main3bb0d0c (verified).
  IP-057 adds an unconnected stdlib proposal
  for equal3–5 slots, explicit cost reserve and bound immutable buy reservations.
  Shared cash/lifetime budget/min6%/8% headroom; proposed correlated50% stress
  counts holdings/pending/candidate plus unused fees once. Further-buy price
  caps <=first fill; no gain offset/silent clipping. Unknown/cancel-requested
  buys stay reserved and deny new purchases. No release/retry/reset or durable
  CAS/execution/authentication claim; caller supplies complete authoritative
  account evidence.10k/1% reserve permits~1002 initial aggregate principal;
  five first stages fit, later buys can fail. Larger budget/stress profile
  explicitly asked before research integration; no answer inferred, coins also
  undecided. Budgets do not renew on sale; cycle reuse/priority/research adapter
  remain IP-055.85 pinned targeted tests/65subtests,81 host tests/review passed.
  Existing strategy/DB/holdout/broker/public runtime unchanged.
  Contract: docs/portfolio-allocation.md; D-061.

- IP-057 checkpointd31dcf3 merged into main1f44b7f (verified). Q34:
  user explicitly accepts equal3–5 slots/1% principal cost reserve/additional
  correlated50% stress for offline research, retaining6%/8%. Reminds staged
  buys lower average cost.
  IP-058 connects the allocator to existing deterministic RSI/fill/portfolio
  core with its own allocated-rsi-research/1 config/state/report. Two closed
  RSI<30 bars first; further buys rearm>30 then<30 and >=5% below last actual
  regular fill;25% growing stages, five regular plus explicit manual sixth.
  Complete intent/dispatch assessment; own pending buy excluded at dispatch.
  Actual buy principal/all fees retained across partial/closed sales and
  duplicate fills. No cycles replenished yet; one full cycle per synthetic
  slot until its next contract. User explicitly asked now for coin selection
  and same nominal slot reuse after normal fully reconciled exits, no budget
  growth/partial-release/risk-stop automatic resume. Answers still pending;
  do not infer them from profile approval.97 targeted pinned cases/65subtests,
  93 host cases,12 final adapter cases repeated pinned/host and scoped review
  passed. No extra-market assets, profitability/MFAhardware proof, new
  dependencies, DB/holdout/broker/normal runtime or snapshot activation.
  docs/staged-portfolio-research.md; D-062.

- IP-058 checkpoint4f56024 merged into main7ec9b41 (verified). Current branch:
  feat/m1-portfolio-history-preflight at IP-059. User asked clarification of
  coin and reuse questions; answers subsequently confirmed in Q35 below. IP-059 public
  metadata/readiness only: five proposed SPOT USDT instruments online, exact
  first two2022-08-01 H4 bars/asset parsed (10 total). No complete three-year
  history/performance/holdout/market approval inferred. Current ETH minimum
  quantity0.0005 needs a separate future research constraint; don't add fields
  to frozen v1 rules/digests or treat current metadata as historical facts.
  Actual responses/timestamps/hashes in docs/research-protocols/
  portfolio-candidates-preflight-20261110.json. No runtime/DB/private/broker/
  strategy change. docs/portfolio-history-preflight.md; D-063.

- Q35 confirmed2026-11-10: BTC/ETH/SOL/BNB/XRP plus ZEC/HYPE/XMR/LINK/XLM/
  NEAR/BCH/LTC/UNI are candidates, not14 funded baskets. Capacity stays3–5;
  fixed nominal slots reusable after fully reconciled normal profit/trailing
  exits with fresh RSI/gates, no profit-based budget growth or risk auto-resume.
  IP-060 on feat/m1-candidate-pool-reuse extends unmerged IP-059b944be1;
  origin/main still7ec9b41 at start. Separate candidate-pool-rsi-research/1,
  slot assignment before first fill, current-cycle budgets versus lifetime
  audit, closed-cycle receipts and risk quarantine. Existing staged/v1 files,
  versions/digests, default symbols and runtime remain unchanged.
  PoolPlan accepts bounded technical symbols for fixtures/frozen cohorts;
  APPROVED_CANDIDATES separately records approved14. Canonical simultaneous
  signal priority is a frozen research default. Complete simultaneous marks
  required. Slot-projected unchanged allocation gates at prepare/dispatch.
  PoolInstrumentRules adds minimum quantity separately, rechecks rounded
  quote/quantity after slippage. Own report uses capacity for planned capital;
  benchmark_status=not_computed rather than overspending14 old full budgets.
  Public metadata13 online; XMRUSDT40034 at metadata/history. ZEC/HYPE/XLM
  have no two-bar sample at2022-08-01, launchTime is current provider metadata,
  not historical listing proof.20 sample candles total for10 candidates;
  no full-history/performance/holdout proof. Old record unchanged/new record
  docs/research-protocols/portfolio-candidate-pool-preflight-20261110.json.
  114 pinned targeted Trading/Paper/worker cases/65subtests,17 new pool
  cases and independent review passed. Natural synthetic OHLC creates15
  first-stage buys over3 RSI cycles,10 normal exits/releases, same fixed
  five-slot budgets. No manual fabrication. Final sell fee crossing daily
  limit directly tested. Extended data schema/full histories/frozen cohorts/
  comparable benchmark/actual net run and durable Paper integration remain
  IP-055/BL-029. No dependency/DB/runtime/public/broker activation.
  docs/candidate-pool-research.md; D-064.

## Trading and implementation invariants

- IP-06022534b7 merged into mainab928ee (verified2026-11-10).
  Q36 supersedes the no-growth planning preference: user wants staged reuse
  of realized closed-basket profits once a full basket range is fundable,
  confirmed option1: add funded slots from initial3–5 up to7, then increase
  future cycle budgets. At least3 additional reconciled closes per grant,
  net all costs/losses and already earmarked profit, one original full slot
  incl manual/cost reserve per grant. Open cycles keep frozen budgets.
  IP-061 adds separate seven-slot-profit-rsi-research/1 and variable per-slot
  research allocator; immutable epochs bind closure prefix/cash/equity.
  Earmarked future increases remain reserved while older cycles occupy slots.
  Original6% daily/8% initial loss bases, cash/equity/stress/reconciliation
  gates stay unchanged; no runtime/live activation. Existing pool v1 remains
  fixed comparison baseline. Actual expanded historical net comparison,
  durable reservation/reconciliation and Paper integration remain IP-055.
  docs/profit-etapes.md; D-066. Branch feat/m1-seven-slot-profit-research.

- Q37 explicitly changes the later trading target to Futures, with
  phase-dependent2x–10x only on strong causally evidenced uptrend signals.
  User confirmed isolated USDT-M long-only; each basket's budget is actual
  capital incl entries/costs/explicit margin buffer, no automatic contributions
  from other baskets. Keep−50% stress and6% daily/8% original account limits;
  reduce leverage or block entry if collateral/liquidation gates fail.
  Stress is50% of first actual fill at every stage, including no RSI/rearm.
  Unposted reserved margin does not protect an immediate gap.
  No guaranteed minimum leverage or live/account settings activation.
  AVAX/HBAR/TRX/BGB/BAT/RENDER are optional substitutes for XMR/ZEC/HYPE/XLM;
  final replacement cohort not frozen. IP-062 public ClassicV2 check found20
  normal perpetuals and52 early trade/mark bars across13 contracts.
  AVAX/TRX early2022 samples available, other four alternatives not; XLM
  futures has samples despite prior Spot absence. RENDER current funding4h,
  others8h; do not treat current metadata as historical.
  Existing Spot strategy/data/results/runtime whitelist remain unchanged.
  Futures need separate nominal/margin/free collateral/funding/maintenance/
  liquidation model, contracts/price-type snapshots and net research.
  Exact regime/leverage mapping, budget split and open-cycle regime-change
  rules still unresolved; AI cannot relax independent risk gates.
  IP-063/BL-030; docs/futures-research.md; D-067.
  IP-06154d2a7d and IP-062f6617b6 merged into main168219f, verified.
  IP-0630cf8a2b merged into main6d06ec5, verified.
  IP-0647007e90 merged into mainab2b6bb, verified.
  IP-06512c2b6c merged into mainffd4211, verified.
  IP-06640d8ba6 merged into main1d06dd3, verified.
  IP-067f18188d merged into mainf844b66, verified.
  IP-06891a1547 merged into main56877b0, verified.
  IP-06957b2858 merged into mainf37be4b, verified.
  IP-0700ebb98b merged into main629901b, verified.
  Current branch feat/m1-futures-long-replay-journal.
- IP-063 first checkpoint adds pure isolated-usdt-long-economics/1 and
  isolated-usdt-long-stress/1. Signed funding/full close PnL/netbreakeven,
  conservative whole-tier maintenance (explicit research assumption, not
  exact historical broker liquidation), and3–7 mixed funded slot assessment.
  Project one worst-price full fill; move collateral once, debit entryfee
  once, reserve all remaining slot margin/costs/remainder against cash.
  Current account and isolated liquidation gates run before projection.
  First-fill50% stress and original6%/8% bases unchanged; missing tier
  coverage, all unresolved orders and fill bound below mark reject.
  Unposted buffers do not protect gaps. First fill needs >50% nominal posted,
  so effective entry leverage is below2x regardless of broker10x setting.
  Frozen plan binds assumptions/precision/fees/budgets; actor inputs trusted,
  no proof of funded profit epochs, persistent reservation, regime or dispatch.
  execution_enabled always false; no default/running module changed.
  44 new tests,187 host and191 pinned tests/135 subtests passed; independent
  economic review has no remaining blocker. No old actual baseline rerun
  because existing modules unchanged. No DB/dependency/runtime/public/broker/
  holdout change. IP-063 event ledger/partialfills/funding/gap sequencing and
  IP-064 separate futures price-type histories are implemented below.
  docs/futures-economics.md; D-068.
- IP-064 adds separate futures-h4-snapshot/1 and funding/1 contracts with
  explicit Classic-V2 USDT-M perpetual/price-kind identity and bounded
  immutable Decimal/UTC/coverage/digests. Candle suffix prevents old Spot
  conversion/execution; old schemas/exports/worker defaults unchanged.
  Public H4 importer: fixed trade/mark/index paths,200/page,52 pages,
  10k bars,256KiB/response,10s timeout, paced, no redirect/retry.
  Frozen protocol and198 public pages prove three-year BTC/ETH histories
  2022-08-01 inclusive to2025-08-01 exclusive: six6576-bar streams,
  39,456 bars with exact common axis/roundtrip/file+data hashes.
  Ignored infra/local/futures-research-data/20261110-network has originals;
  committed protocol/receipt has perpage canonical decoded-response hashes.
  Create-only importer; no successful final receipt on incomplete execution.
  Signed funding events deliberately have no cadence/completeness proof.
  Funding transport/archives, other candidates and historical fee/precision/
  maintenance assumptions remain BL-030/IP-055. No holdout requested.
  23 new host tests and81 pinned tests/147 subtests passed; independent
  review no blocker. Checkhelper adds two readonly script/protocol mounts;
  no dependency/DB/worker/runtime/production/broker change.
  User asks about2x first entry/higher later: no automatic leverage ladder
  approved; whole enlarged position/account must pass independent gates.
  IP-063 ledger/funding/partialfills/gaps and exact regime/budget rules open.
  docs/futures-marketdata.md; D-069.
- IP-065 adds pure isolated-usdt-long-ledger/1 for caller-reconciled evidence,
  three to seven baskets, partial entry/exit fills, signed funding, declared
  own margin posting, fresh complete marks and explicit pre-mutation midnight
  basis. Tenant/account/plan/revision and hashchain bind each transition.
  Gross committed own capital differs from signed isolated funding balance;
  credits do not mint budget, charges do not reset between cycles.
  Partial close uses explicitly assumed proportional research margin release.
  Full close reports complete price/fee/funding net PnL; no profitgrant authority.
  Gaps never invent stop/liquidation fills; deficits and known post-halt fills
  remain recorded. Actual loss/unsafe margin/budget breaches latch; no reset
  on margin posting, recovery or day change. Reserve shortfall separately
  blocks future funding without inventing a permanent halt after normal loss.
  Equal-time research order mark/day/funding/margin/entry/exit; each symbol's
  funding timestamp consumed once even under new event ID/revision.
  Exact command replay fails stale revision; globally durable broker-fill
  deduplication/persistence/unknown orders and commits are NOT implemented.
  No purchase/strategy/dispatch authority; execution_enabled false. Existing
  IP-063 purchase stress remains separate; IP-066 pending/riskbridge must
  retain gross vs net collateral and paid costs before future intent/dispatch.
  31 new cases,218 host/222 pinned tests with157 subtests passed. Root economic
  review including3/5/7-slot exact existing-assessor match; no new delegated
  reviewer or broad unchanged credentials/DB/public regressions.
  User clarifies2x minimum: retain approved broker research range2–10, no
  automatic per-stage ladder. Effective initial leverage may be below2 with
  posted own buffer; actual broker timing/atomicity before first-fill gap
  must be proven before corresponding execution. Current minLever metadata
  is not a proof of chosen effective leverage or public/live authorization.
  Official V3 funding history is currently90days/page cursor; public download
  docs list candles/trades/depth, not a complete public funding archive.
  No substituted rates, data downloads/holdout reads, dependency/migration/
  runtime/broker/public activation. IP-063 remains open; IP-066/BL-030 next.
  docs/futures-event-ledger.md; D-070.
- IP-066 adds pure isolated-usdt-long-pending/1 above unchanged ledger/risk-v1.
  Ledger-based assessment separates gross own margin budget from signed net
  collateral, charges and outstanding principal-cost restoration. Original
  6%/8%/first-fill50% stress and 3–7 funded slots stay unchanged.
  One pending purchase per research account; immutable request/revision/hash,
  no cash movement at reservation. Unknown attempted order never times out,
  retries or locally cancels; exact terminal cumulative quantity/margin/fees
  required. Real partial fills book once, including zero extra margin.
  Unexpected/out-of-envelope fills book truthfully and latch wrapper quarantine;
  ledger-v1 audit/hash unchanged. Broker fill/order IDs consumed across cycles
  within retained state lineage; 1024 per identity list, never evict.
  Not persistent/global broker dedupe, DB-CAS, restore or dispatch authority.
  Start wrapper assumes trusted reconciled ledger, not unknown-order recovery.
  All timestamps chronological; authentic broker evidence remains caller duty.
  A max-price full-fill projection does not prove all fragment price paths:
  cheaper actual first fragment can lower the stress floor for the remaining
  order. Regression records this and blocks a later purchase; IP-067 must
  assess causal remaining-fill envelope/gaps before continuation/replay.
  Original evidence cannot authorize remaining fills or brokerbuffer timing.
  28 new tests;246 distinct host/250 distinct pinned Trading/Worker tests with
  167 subtests passed (full245/249 then new boundary case focused). Root review,
  no delegation/broad unchanged credential/DB/public repeats. No original
  module/export/data/holdout/dependency/migration/runtime/broker/public changes.
  IP-066 bounded checkpoint done; IP-067/063/BL-030 remain. Contract:
  docs/futures-pending-research.md; D-071.
- IP-067 adds pure isolated-usdt-long-continuation/1, unchanged old modules.
  Tenant/account/plan/revision/intent/order + complete downward gap floors.
  Actual first-fill anchor, signed already-posted collateral only; pending
  margin/restoration/crossbasket topups never assumed. Existing and full
  remaining quantity endpoint bounds cover affine prefixes with fixed first
  fill, capped prices, full conservative tier and full remaining entry fee.
  Free costs must remain covered at BOTH gap endpoints: hypothetical cheap
  remainder profit cannot heal zero-remainder cost shortfall.
  Current/prior-gap/post-fill isolation, 6%/8% aggregate stress, original gross
  budgets/funding restoration/costs, original leverage and fresh day/marks
  remain checked. Missing first-fill position blocks without inventing timing.
  Shows required collateral/deficit, never automatically posts or clears halt.
  risk_covered is economic research only; requires_reconciliation=true and
  execution_enabled=false. Unknown order/reservations unchanged. Not a proof
  of future funding, upper mark paths, broker timing, durable IDs or exact
  original strategy-cycle authority. Pending guard cannot replace that binding.
  31 new cases;277 distinct host/281 pinned Trading/Worker tests219 subtests
  passed (full276/280 then all31 updated module cases focused). Root economic
  review, no new delegation or unchanged credential/DB/public repeats.
  No old exports/versions/data/holdout/dependencies/migrations/runtime changes.
  IP-067 done; IP-068 causal RSI/staffel/intent-cycle replay adapter next with
  explicitly frozen research costs/margin/regime and first-fill assumptions.
  Fundingarchives/historical rules remain IP-055/063/BL-030. Contract:
  docs/futures-continuation-stress.md; D-072.

- Profitability is a measurable research objective, never a guarantee.
- Use one versioned deterministic strategy core for backtest, paper, and live.
- Risk limits are enforced independently of strategy/AI and before order dispatch.
- Model quote budget, position notional, usable margin, and account equity separately.
- Never retry an uncertain broker order blindly; reconcile before resubmission.
- Require authenticated tenant context for requests, jobs, files, caches, and streams.
- Broker credentials must never reach browser storage, research workers, AI, or logs.
- Research workers use a dedicated LOGIN role bound to one tenant through
  `SESSION_USER`, bounded fenced leases and restricted database functions.
  Never give them API/migration credentials or evaluate protected holdout datasets.
  Snapshots, frozen job inputs and terminal results are immutable. Applied SQL
  migrations are checksum-protected; extend them with a new numbered migration.
- Default to a private user base and disabled live execution. Q20 permits planning
  a public central HTTPS pilot entry; databases/workers stay internal. Real-money activation
  requires explicit account/strategy/risk approval in addition to deployment approval.
- Never inherit loose dependency ranges or floating images from the legacy systems.
  Verify supported versions, pin exact releases/digests, and commit lockfiles.
- Keep original strategy images in `strategies/`; executable rules belong in a
  reviewed specification and immutable strategy versions.
- `secrets/` is ignored. Removing a file from tracking does not remove its history;
  potential credentials need rotation and separately authorized history remediation.

## Boundaries

Always do

- Keep security defaults: private deployment, encryption, and least privilege.
- Use exact version pins
- Keep docs concise and update them when architecture or process changes.
- Keep all general documentation up to date including all AGENTS.md files
- Document significant design decisions in `docs/memories/decision-log.md` and
  technical pitfalls in `docs/memories/gotchas.md` — both are committed to Git so
  colleagues (not just the current agent session) benefit from them.
- Add deferred follow-ups to `docs/backlog.md` and remove items once done.
- Follow best practice. If a requirement goes against best practice, point this out. Consult official documentation to verify best practice.
- use SKILLS to get more specialist skills, if you need more SKILLs get the right one from https://www.skills.sh/
- work with git and save your work. you can also push your feature branches and main branch to github.com by yourself.
- Make sure you work efficiently and avoid unnecessary long-running LLM tasks. Keep the LLM context efficient and save on token costs.

Ask first

- Change key structures and strategy.
- Introduce new CI/CD tooling dependencies.
- Execute external-facing actions outside this repository (publishing, posting, messaging).
- before deploying to production ask for approval

Never do

- Never commit hardcoded secrets, access keys, or tokens.
- Do not expose resources directly to the public without a central entry point.
- Do not expose sensible resources such as databases to the public internet.
- Do not run destructive commands without explicit user approval.
- Don't exfiltrate private data. Ever.
- Don't run destructive commands without asking.
- `trash` > `rm` (recoverable beats gone forever)
- When in doubt, ask.

## Memory

You wake up fresh each session. These files are your continuity:

- **Daily notes:** `memory/YYYY-MM-DD.md` (create `memory/` if needed) — raw logs of what happened
- **Long-term:** `MEMORY.md` — your curated memories, like a human's long-term memory

Capture what matters. Decisions, context, things to remember. Skip the secrets unless asked to keep them.

### 🧠 MEMORY.md - Your Long-Term Memory

- **ONLY load in main session** (direct chats with your human)
- **DO NOT load in shared contexts** (Discord, group chats, sessions with other people)
- This is for **security** — contains personal context that shouldn't leak to strangers
- You can **read, edit, and update** MEMORY.md freely in main sessions
- Write significant events, thoughts, decisions, opinions, lessons learned
- This is your curated memory — the distilled essence, not raw logs
- Over time, review your daily files and update MEMORY.md with what's worth keeping


### 📝 Write It Down - No "Mental Notes"!

- **Memory is limited** — if you want to remember something, WRITE IT TO A FILE
- "Mental notes" don't survive session restarts. Files do.
- When someone says "remember this" → update `memory/YYYY-MM-DD.md` or relevant file
- When you learn a lesson → update AGENTS.md, TOOLS.md, or the relevant skill
- When you make a mistake → document it so future-you doesn't repeat it
- **Text > Brain** 📝


## Tools

Skills provide your tools. When you need one, check its `SKILL.md`. Keep local notes (SSH details, commands, jobs, etc.) in `TOOLS.md`.

- IP-068 adds pure isolated-usdt-long-signals/1 over unchanged indicator/risk/
  ledger/pending/continuation cores. Canonical complete native trade/mark H4
  frames; RSI14/Wilder, actual-stage VWAP -5% reentry, five regular stages,
  manual sixth and explicit own buffer separate. Constant2x bounded research
  baseline, no inferred regime or stage leverage ladder. Profile requires
  declared-full-intent-margin-with-first-fragment/research-only: every first
  order fragment reports full own intent margin, no broker atomicity proof.
  Bind profile/symbol/cycle/stage/intent/causal signal/quantity/price/margins.
  Completed stages require exact terminal reconciliation; last-fill resets
  RSI, terminal preserves genuine rearm since that fill. Known outside-cycle/
  after-protection fills book truth and latch global quarantine. Normal flat
  cycles preserve indicator history; unknown orders never timeout or retry.
  +5% trade-close protection uses whole-cycle fee/funding/partial-exit netfloor;
  no pre-fill close reused as profit, no fictional stop fills. Insolvent gap
  marks continue without fabricated positive midnight basis. Existing1024
  ID limits remain; not persistence/restore/dispatch or a performance job.
  36newcases,313distincthost/317pinned228subtests passed; focused eigenreview,
  no delegation/data/holdout/dependency/migration/runtime/public changes.
  Next IP-069 actual funding provenance and frozen long-replay protocol;
  economic regime/budget/buffer choices and archives remain IP-055/063/BL-030.
  docs/futures-signal-replay.md; D-073.

- IP-069 first checkpoint adds bounded unsigned Classic-V2 funding importer,
  explicit calendar diagnostics and create-only checksum-pinned protocol CLI.
  Exact fixed GET URL/no keys/cookies/redirects/retry,100 rows/page,100 pages,
 256KiB/10s; strict descending advancing pages, identical overlaps deduped,
  revised/future/foreign/bad rows or capacity exhaustion fail. Native BTC/ETH
  each270 events2026-08-13T16Z..2026-11-11T08Z,8GETs,540 observations;
  actual requested2022-08-01..2025-08-01 has0 events each. Declared8h calendar
  expects3288 each; missing never0 rates, calendar not historical attestation.
  Separate requested/recent funding/1 snapshots,4 artifacts/8 page hashes
  verified; official V3 current docs explicitly90d, old legacy wording differs.
  Failed sandbox DNS run retains no receipt; authorized network run separate
  infra/local/futures-funding-data/20261111-native-network. Tracked receipt:
  docs/research-protocols/futures-funding-receipt-20261111.json.
 25newhostcases/102distinctpinnedmarketdata187subtests passed (101full, final25
  modulechecks). Eigenreview, no delegation/trading/DB/credentials repeats.
  Only2readonly fixturemounts; no dependencies/migrations/holdout jobs/runtime/
  publicactivation. Existing formats/cores/exports unchanged. IP-069 still
  open: full native historical provenance/economic profile/long journal.
  Optional userpreference for separate free Binance research comparison asked;
  no answer yet, no venue substitution or new data/job enabled. Bitget target
  unchanged. docs/futures-funding-availability.md; D-074.

- Q38 explicitly approved separate free Binance futures research comparison.
  Bitget remains trading target; no account/private key/live approval.
  IP-070 own immutable binance-usdt-futures-research/1 + frozen create-only
  unsigned importer: BTC/ETH each6576 trade/mark/index H4 bars and3288 signed
  funding events2022-08-01..2025-08-01 exclusive.52 GETs/8 artifacts/digests
  verified, all price axes complete; declared8h bucket missing/duplicate/
  unexpected0. Original funding offsets up to29ms preserved, not rounded.
  Each1369 native funding settlement markprices absent; remain None.
  H4 markbars do not prove exact settlement price; later economic protocol
  must declare reference/cost envelope. Calendar not historical schedule/
  tier/fee/liquidation proof; no netperformance/holdout requested.
  28newcases,130distinctpinnedmarketdata passed (127full then28focused).
  Eigenreview; two readonly testmounts only, no dependencies/migrations/
  credentials/DB/runtime/public activation or unchanged broad repeats.
  Raw data infra/local/binance-futures-research-data/20261111-native-network;
  committed protocol/receipt docs/research-protocols/binance-futures-history*.
  Initial sandbox DNS failure retained no receipt; authorized new network run.
  IP-069 remains economic profile + long journal without dropping1024 IDs,
  then actual netresearch. Never mix Binance funding into native Bitget claims.
  docs/binance-futures-research-data.md; D-075.

- IP-071 adds explicit Pending/2 immutable identity histories, default50000
  bounded1..100000, no eviction; original Pending/1 tuple1024 remains default.
  Four own namespaces/count/root receipts; compact snapshot primitive only for
  this new type. Rootreceipt alone cannot restore. Fresh longstart requires
  flat ledgerrevision0, never reset an existing evidence ledger.
  Local JSONL journal genesis/profile/actor/plan/protocol/dataset/policies bound;
  full typed input replay restores indicators/unknownorders/partialfills/
  terminalstate/globalIDs/latched quarantine. No broker authority.
  Owned0600/no leafsymlink/hardlink/exclusive lock; write+fsync before stateack.
  Unknownwrite closes/readbacks, no retry/tailrepair;256KiB/128MiB/100000commands.
  minimum_receipt external retained acknowledged anchor detects even whole
  tail loss; pass it for recovery. Unanchored inspection cannot detect valid
  prefix rollback. Local hashchain not sourceauthenticity/admin resistance.
  Full synthetic6576H4/1096midnights/7672retainedIDs exact restored,9.544.108
  bytes; firstID/indicators retained.59.228s write/62.707s originalrestore,
  additional full anchored restore passed. No real market netperformance.
  25newcases/342distinctpinnedTrading+worker green (337full,25focused,final
  53Pending/Journal37subtests after halt-type guard);
  eigenreview/noagents/dependencies/PG/migrations/runtime/public changes.
  Source contracts/strategy/risk unchanged; existing cores shared with explicit
  new identity type. IP-069 needs economic fundingprice/cost/cohort protocol.
  Native Binance assets BTC/ETH only;3–7-symbol portfolio requires genuine
  suitable cohort, never add synthetic third coin as native performance.
  docs/futures-long-replay-journal.md; D-076.

- 2026-11-11: user explicitly requests H1 research plus H4 with correct larger
  basket capital. IP-07132fd13c merged into maind749081 verified.
  Q39/IP-072 offline Spot comparison: same native Binance BNB/BTC/ETH/SOL/XRP
  H1 source, H4 aggregated from identical hours, shared10000USDT,3/5 fixed
  reusable slots,1% principal costs; no profit etapes or leverage in this study.
  RSI14/rearm/5%/25%/manual sixth and6%/8%/minus50% remain unchanged.
  Native2023-03-24 missing13h/shortened12h explicitly excludes same12–16h block
  for both variants before market performance. Cancel pending buys/restart
  Wilder confirmations; retain holdings/stops/halts/all bar evidence.
  Four base cases plus two predefined doubled-cost cases; holdout untouched.
  New H1 engine is offline only; default Candle/engine/runtime stay H4.
  Source/price/config/policy manifests and artifacts:
  docs/h1-h4-basket-comparison.md. Futures net study remains separate IP-069.
  All six real3y runs complete: H1/H4 three slots net725.04/1251.79USDT;
  five slots985.30/1064.30; more H1five averaging fills66/47 but higherDD.
  Doubled-cost five slots1015.72/1554.99; altered fill/stop path, not evidence
  higher costs beneficial. Isolated fill test confirms real0.2% costs.
  H4 remains reference; fine-execution/stop sensitivity and holdout before
  promotion.135 public GETs; each26303 native H1,26300 evaluatedH1/6575H4,
  all evidence retained, all six full curves checked.18new/356distinctpinned
  cases (355full,64targeted,1newcostcase overlap), legacy228.7169/56 exact.
  No dependencies/migrations/services/public changes. Results/monthly CSV
  tracked; raw source/curves ignored. No independent economic validation.
