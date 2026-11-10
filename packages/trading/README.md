# Deterministischer Crypto-Paperkern

IP-057 ergänzt `investalo_trading.allocation` als unverbundenen Offlinevorschlag:
gleiche3–5 Slots, gemeinsame Kosten-/Cash-/Stressprüfung und immutable
Kaufreservierungen. Keine Aktivierung eines größeren Strategieprofils.
[Konkrete Budgets und Grenzen](../../docs/portfolio-allocation.md).

IP-056 ergänzt den separaten Offline-`PortfolioSimulator` für gemeinsame
vollständige BTC-/ETH-Historien. Ein Konto, atomare Quote-Batches, Kapital-
kennzahlen und passive kostenvergleichbare Referenz; ursprüngliche
Einzelasset-/Paperpfade unverändert. [Vertrag/Ergebnisse](../../docs/portfolio-reference.md).

Stdlib-Python, immutable Dataclasses, Decimal und UTC. Version
`crypto-basket/1.0.0`; Konfiguration und Instrumentpräzision zusätzlich per
Digest an Snapshots gebunden. Kein Broker-I/O, kein Secretzugriff und kein
XAUUSD-/Live-Ausführungsadapter. Fachliche Quelle: [trading.md](../../docs/trading.md).

Import über `PYTHONPATH=packages/trading/src`; keine Runtimeabhängigkeiten.
Prüfung vom Repositoryroot:

```sh
PYTHONPATH=packages/trading/src python3 -m unittest discover -s tests/trading -v
```

## API

```python
from datetime import datetime, timezone
from investalo_trading import CryptoEngine, PaperSimulator, dump_state, load_state

engine = CryptoEngine()
state = engine.start("tenant-id", "paper-account-id", datetime.now(timezone.utc))
# state = engine.on_quote(state, quote).state
# transition = engine.on_bar(state, completed_h4_bar)
# state = transition.state             # order intent is NOT a fill
# state = engine.apply_fill(state, confirmed_fill).state
restored = load_state(dump_state(state))
```

- `on_quote` überwacht −55%-Exit, Kontolimits und +5%-Gewinnschutz laufend.
- `on_bar` akzeptiert kausale, lückenlose geschlossene UTC-H4-Kerzen.
  RSI14/Wilder, ATR10/Wilder ×3; fünf automatische Stufen. Alte identische
  Kerzen und Fill-IDs sind auch nach Snapshotrestore idempotent.
- `validate_dispatch` prüft unmittelbar vor Ausführung erneut. Unklare Orders
  mit `mark_order_unknown` sperren Blind-Resend; `reconcile_cancelled` verlangt
  einen bereits erfolgten autoritativen Fill-/Stornoabgleich.
- `reset_day(state, midnight_utc)` übernimmt die aktuelle Equity als Tagesbasis.
  Historischer Simulator: vorher Mitternachtsquotes liefern.
  Inkrementelles Paper nutzt seit Q32/IP-052 stattdessen `PaperRunner.day`
  mit exakten H4-Mitternachtscloses und Cash/Mengen vor Mitternacht, eigener
  Policy `paper-h4-close/1`, ohne Quote-/RSI-/Fillmutation.
  [Vertrag](../../docs/paper-midnight-basis.md). Fehlt eine Tagesbaseline, blockieren neue
  Käufe; Gesamtlimit und Preisexit bleiben aktiv. Finanzielle Halts sind
  gelatcht; `resume` ist ein expliziter autorisierter Bedienvorgang.
  Der −55%-Preisexit ist ebenfalls ein Risk-Stop: der betroffene Basket bleibt
  nach dem Schließen gesperrt bis `resume_basket(state, symbol, now)`, mit
  Anwendungsauthorisierung/MFA und abgeglichenen Orders. Gewinn-/Trailingexits
  erlauben einen neuen normalen Zyklus. Das ist eine Stopklassifikation,
  keine automatische Reserve- oder Notfalleinstiegsregel.
- `preview_manual` nach fünf bestätigten Stufen, `confirm_manual` höchstens einmal:
  ursprüngliche Reserve, 5%-Preislimit, Vorschauablauf und neue Riskprüfung.
  Die Anwendung MUSS Tenant, Owner/Trader, frische MFA und einmalige gebundene
  Freigabe verifizieren. `authorization_reference` ist nur deren Auditbeleg.
  Der Domainkern authentifiziert keine Nutzer.
  Auch eine vor dem ersten Fill stornierte manuelle Freigabe bleibt zunächst
  reserviert. Ein späterer Retry desselben logischen Intents benötigt einen
  eigenen autorisierten Reconciliationablauf; dieser erste Kern bietet ihn
  noch nicht an.
- `PaperSimulator.settle(state, at)` führt vorhandene Paperintents mit aktuellen
  Quotes aus; Rückgabe `(state, fills, events)`. Es erzeugt keine manuelle Order.
- `PaperSimulator.run(candles)` liefert `BacktestResult` mit Provenienz,
  Fills/Events, Equitykurve, Netto-PnL, Drawdown und geschlossenen Baskets.
  `primitive(result)` liefert JSON-kompatible Records mit Dezimalstrings.

## Grenzen des Referenzmodells

Fünf reguläre Stufen plus unangetastete Reserve; keine erfundenen manuellen
Fills. Historische Käufe frühestens am nächsten bekannten Kerzenopen;
nicht erfüllbare Preislimits werden storniert. OHLC-Reihenfolge konservativ
`Open → Low → High → Close`; Stopfills zu verfügbaren ungünstigen Quotes,
kein garantierter Stoppreis und kein künstliches Schließen am Historienende.
Für wirtschaftliche Nachweise sind brokerpassende feinere Daten erforderlich.

`SimulationCosts` verwendet explizite Forschungsannahmen (je 0,1 % Fee, Spread
und Slippage). Diese sind keine Bitget-Tarife oder gemessene Liquidität.
Exitfee und Exit-Slippage in `StrategyConfig` müssen zum Modell passen.
Der Nettobreakeven bezieht sich auf den verkaufbaren Bid und berücksichtigt
beide Exitannahmen; Spread steckt bereits im Bid. `InstrumentRules`-Defaults
sind Simulatorpräzision; echte Mindestmengen/Ticks müssen aus Venues kommen.
Quote-/Previewfrische standardmäßig 30 Sekunden ist eine technische
Fail-closed-Grundeinstellung, kein getestetes Betriebs-SLO.

Kostenreserve 5 USDT für den gesamten Basket, Principal 500 USDT. Quote- und
Mengenrundung immer nach unten; Rest bleibt Cash. Echte unerwartete bekannte
Kauffills werden verbucht und bei Limitverstoß gelatcht/geschlossen. Unbekannte
oder überverkaufende Fills verlangen Reconciliation statt erfundener Positionen.
MT5/FTMO, Datenfeeds, Outbox-/DB-Transaktionen und MFA gehören in Adapter/Anwendung.

## Incremental PaperRunner (IP-048)

`PaperRunner(tenant_id, account_id)` consumes `quote(checkpoint, quote, now=...)`
and `bar(checkpoint, candle, now=...)`, returning immutable checkpoint plus
journal entry. `start(at)`, `dump(checkpoint)` and `restore(payload)` provide
bound restart snapshots. Buys wait for a later fresh quote for their asset;
known duplicates cannot fill twice. No automatic manual approval/resume.
The caller must CAS and atomically commit checkpoint and append-only journal
before ACK. A PostgreSQL writer/feed daemon is still IP-047, not provided by
this class. [Contract and limits](../../docs/paper-runner.md).
