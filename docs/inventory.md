# Bestandsaufnahme

Read-only erhoben am 2026-11-06. Keine Credentials, privaten Kontodaten oder
Ergebnisprotokolle gelesen; die beiden Referenzrepos wurden nicht verändert.

## Host und Werkzeuge

| Merkmal | Befund |
|---|---|
| Betriebssystem | Ubuntu 26.04.1 LTS, x86_64/KVM |
| CPU/RAM | 2 vCPU, etwa 1,9 GiB RAM, kein Swap |
| Speicher | Rootdisk etwa 76 GiB, etwa 68 GiB frei zur Inventur |
| Python | 3.14.4 |
| Node.js | 26.13.0 |
| Git | 2.53.0 |
| Codex / Gemini CLI | 0.167.0 / 0.67.0 |
| Docker / GitHub CLI | Nicht im PATH auffindbar |
| Aktuelles Projekt | Dokumentation, lokale Skills und Strategieabbildungen; keine Anwendung |

Installierte Versionen sind Fakten, keine freigegebenen Runtimepins.
Der lokale Ubuntu-Adminskill bezieht sich auf 24.04 und muss gegen 26.04
validiert werden. Der große Zielstack passt nicht ohne Ressourcenplanung auf
die vorhandene kleine VM.

## Referenzrepositories

| Repository | Inventurierter Stand |
|---|---|
| `/opt/investalo-trading-system` | `main`, sauber; `f3771a8908eb64a87b9d89f1d4834c832908cb6e` |
| `/opt/investalo-autotrader` | `main`, sauber; `7ccfbd907a0bda53019024f725eba9428b389bf2` |

Trading-System: Python/FastAPI, Next.js/React, PostgreSQL/TimescaleDB, Redis,
Compose und MT5-Bridge. StrategyPlugins für Trend/Pullback, RSI,
Channel Breakout, Order Block, Asia/Opening Range.
Kontosnapshots/Deal-Sync, Bar-Push, Dashboard/Journal, Historienexport und
Backtest-/Kostenkalibrierungswerkzeuge sind vorhanden.

MT5-Referenzen: `AccountReporter.mq5`, `AccountDeals.mqh`, `MarketBars.mqh`,
`HistoryExport.mq5`. Autotrader liefert Webhook → persistente JSON-Queue →
Polling/Ack und Order-EA mit lokalem Idempotenzjournal.
Keine Bitget-Integration in den inventarisierten Komponenten.

## Übernahmegrenzen

| Befund | Konsequenz |
|---|---|
| Keine vollständige Tenant-/User-/Org-Zuordnung | Neues Auth-/RBAC-/Tenantmodell erforderlich |
| Ausgewählte Dashboard-/Signalrouten ohne sichtbare Authdependency | Für Multiuser nicht ungeprüft übernehmen |
| RiskGuard vergleicht mit `max(configured_risk, 1.0)` | Konfigurierte Werte unter 1 % werden nicht strikt eingehalten; im neuen Kern beheben |
| Kosten teils nachträglich auf unveränderte Fills gerechnet | Kein gleichwertiger kostenbehafteter Ausführungssimulator |
| Swap/Slippage und identisches Brokerlotsizing fehlen im geprüften Runner | Nettoergebnisse neu validieren |
| H1-Index im Trend/Pullback um −1 Stunde verschoben bei Bar-Startzeitquelle | Möglicher Look-ahead; Timestampsemantik und Kausalität vor Übernahme nachweisen |
| Python ohne vollständigen Lockstand, floating Images | Neue exakte Pins/Locks nötig |
| Frontendbuild mit `npm install || true`, Lock nicht vor Installation kopiert | Fehlerverdeckung und nicht reproduzierbarer Build |
| Keine vollständigen versionierten Reproduktionspakete inventarisiert | Behauptete erfolgreiche Backtests sind noch kein belastbarer Nachweis |

RiskGuard-Referenz: `backend/app/core/risk/guard.py:109` im Trading-System.
Der Befund ist auf die gelesenen Komponenten begrenzt, kein umfassendes
Sicherheitsaudit des produktiven Altsystems.

Frontend-Lockstände im Referenzrepo: Next.js 15.5.24, React/DOM 19.2.8,
TypeScript 5.9.3. Diese Werte werden nicht automatisch als neue Pins übernommen.
API-/EA-Verträge, Brokerwährung, Symbolmapping und Kontoprofile müssen
vor jeder Übernahme getestet werden.

## Konkrete Strategiezuordnung

Der Registrycode schaltet XAUUSD mit `trend_pullback` frei, H1-Trendregime plus
M15-Einstieg/ATR. EURUSD, USDJPY und USDCAD besitzen leere Ensembles;
GBPUSD/USDCHF zusätzlich keine Validated-Symbol-Freigabe.
Dies beschreibt den inventarisierten Code, nicht aktuelle Trades oder Gewinne.

Die Goldbilder zeigen andere CBS-Basketvarianten: H1 mit einer RSI-Kerze,
−1%-Abstand, vier Einstiegen und +1%-Exit; H4 mit zwei RSI-Kerzen,
−2%-Abstand, drei Einstiegen und +5%-Exit. Im Code existiert kein entsprechendes
CBS-/Basket- oder H4-Plugin. Ein nutzereigener Terminalhost ist aus den erlaubten
technischen README-Fakten nicht identifizierbar und muss noch zugeordnet werden.

## Vorhandene Strategieabbildungen

`strategies/` enthält Crypto Basket, Gold H1/H4 CBS, Coffee CBS und Öl Swing.
Sie bleiben Originalreferenzen. Text-/Codeformalisation, Parameter und
Widersprüche werden gesondert mit dem Nutzer geklärt; Bildtitel allein
definieren keine ausführbare Strategie.

## Git und Sicherheit

Zu Beginn liegen Nutzeränderungen in `AGENTS.md` und `docs/project-info.md`
sowie `GEMINI.md` vor. Sie werden bei den angeforderten Dokumentationserweiterungen
erhalten. Die vorhandene Schlüsseldatei ist bereits getrackt.
Containment und verbleibender Historienbefund: [security.md](security.md).
