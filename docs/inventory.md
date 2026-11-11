# Bestandsaufnahme

IP-066: neues `futures_pending.py`,28 synthetische Fälle; gebundene
Kaufreservierungen, vollständiger Terminalabgleich, begrenzte Broker-ID-Dedupe
und Kaufstress direkt aus Bruttozuordnung/signed Ledgernettostand.
Keine alten Kerne/Exports geändert. [Vertrag](futures-pending-research.md).

IP-065: neues `futures_ledger.py` und31 Fälle für abgeglichene Teilfills,
Funding/Close-PnL/Gaps.218 Host-/222 gepinnte Trading-/Workerfälle mit157
Subtests bestanden. Bestehende Module/Exporte unverändert. [Vertrag](futures-event-ledger.md).

IP-064: neue separate `futures_snapshot.py`/`futures_bitget.py`, unsigned
Classic-V2-H4-Importer und eigenes Fundingformat. Spotmodule/-Exports
unverändert; Testhelper bindet nur neues Importscript/Protokoll readonly ein.
[Vertrag und echte Datenabnahme](futures-marketdata.md).

IP-063: neue pure `futures_economics.py`/`futures_risk.py`,44 neue Fälle,
191 gezielte gepinnte Tests/135 Subtests. Keine alten Module geändert;
keine Runtime-/Broker-/DB-/Dependencyaktivierung. Funding-/Fee-/Breakeven-
ökonomie und isolierter/gemeinsamer Kaufstress, kein Ledger/Orderadapter.
[Vertrag](futures-economics.md).

IP-062: öffentliche Classic-V2-Futuresinventur20 Kontrakte,40 Historienproben
und52 frühe geprüfte Trade-/Markkerzen in neuem Messrecord. Alle sechs
Alternativen aktuell normal; AVAX/TRX mit frühen Proben. Keine Futuresökonomie,
neue Runtimewhitelist oder Hebelaktivierung implementiert.
[Futuresvorcheck](futures-research.md).

IP-061: `profit_research.py` ergänzt eigenständige immutable Gewinn-/Budgetepochen,
`variable_budget.py` prüft3–7 unterschiedliche Slotbudgets mit ursprünglicher
Risikobasis. Gemeinsamer RSI-/Fillkern erhält defaultneutrale Budgethooks.
147 gezielte gepinnte Fälle/87 Subtests,143 Hostfälle; dreijährige BTC-/ETH-
Baseline exakt reproduziert. Keine Runtime-/DB-/Dependencyänderung.
[Vertrag](profit-etapes.md).

IP-060: neuer Offlinepool mit unabhängig3–5 Slots, vollständigen RSI-Stufen,
fixer Wiederbelegung nach normalen abgeglichenen Exits, quarantänisierten
Riskexits und eigener Mindestmenge.114 gepinnte Fälle/65 Subtests.
13 der14 Kandidaten liefern Spotmetadaten; XMR nicht gefunden.
Keine Runtime-/DB-/Dependencyänderung. [Vertrag](candidate-pool-research.md).

IP-059: öffentlicher Kandidatenvorcheck bestätigt fünf Spotpaare/Metadaten
und zehn H4-Kerzen am2022-08-01. Keine Assetaktivierung/Performanceauswertung;
vollständige Dreijahreshistorie noch ungeprüft.
[Belege](portfolio-history-preflight.md).

IP-058 (2026-11-10): neuer eigener Offline-Forschungsadapter verbindet
bestätigte Allokation und vorhandene deterministische RSI-Nachkauf-/Filllogik.
Keine Legacyübernahme, neue Abhängigkeit oder DB-/Runtimeaktivierung.
[Vertrag](staged-portfolio-research.md).

IP-056 (2026-11-09): neuer separater gemeinsamer Offline-BTC-/ETH-Referenzkern,
atomare H4-Bewertung, Kapitalnutzung und passive Kostenreferenz auf unverändertem
500+5-Profil. Keine Legacyübernahme/zusätzliche Abhängigkeit, DB-/Runtime-
änderung oder erweiterte Coinaktivierung. [Befund](portfolio-reference.md).

Read-only erhoben am 2026-11-06. Keine Credentials, privaten Kontodaten oder
Ergebnisprotokolle gelesen; die beiden Referenzrepos wurden nicht verändert.
Die folgenden Tabellen beschreiben den Ausgangsstand. Der aktuelle lokale
Umsetzungsstand vom 2026-11-08 steht am Ende dieser Datei.

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

**Ergänzung 2026-11-07, Nutzerangabe Q25:** MT5 läuft auf einem separaten
Server im Heimnetz. Betriebssystem, Terminalbuild und konkrete Demo-Instanz
sind damit noch nicht technisch geprüft. Der neue Verbindungsplan steht in
[mt5-bridge.md](mt5-bridge.md); keine Remoteänderungen erfolgt.

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

## Lokale Umsetzung 2026-11-07

Q31 bestätigt; Branch `feat/m1-foundation`. Docker Engine 29.9.3,
Compose 5.7.0 und gepinnte Runtimeimages installiert. Fünf lokale Basisdienste
PostgreSQL/Authelia/API/Cockpit/Caddy plus optionaler Offline-Researchworker;
ausschließlich Caddy veröffentlicht
`127.0.0.1:8443`. TLS/CA, separate DB-Rollen und Service-UIDs eingerichtet.
Strategie-/API-/Worker-/Daten-/Cockpittests vorhanden. Öffentliche BTC-H4-Daten
wurden als unveränderlicher 90-Tage-Snapshot importiert. Kostenkalibrierung,
Dreijahresdaten und Holdoutnachweis bleiben offen; keine Brokerkonten verbunden.
Die Referenzrepos blieben unverändert.
Runtimepins: [runtime-pins.md](runtime-pins.md); Start: [infra/README.md](../infra/README.md).

**Fortgeschriebener Stand:** Der Defaultstart bleibt lokal. Die ausdrücklich
freigegebene [Entwicklungsvorschau](https-entry.md) verwendet ein separates
öffentliches HTTPS-Overlay mit gültigen Zertifikaten und zentralem Caddy80/443;
DB/API/Worker besitzen keine öffentlichen Hostports.
Credentialfundament, Registry und der interne
[Aktionsnachweis007](passkey-action-proofs.md) sowie IP-037–040 sind auf main
`0fd25b6` enthalten; Merge des Checkpoints `3476f74` ist verifiziert.
IP-037 ergänzt die ausdrücklich aktivierbare
[BFF-Browservorschau](passkey-browser-proof.md) und den vollständig synthetisch
geprüften Enrollmentablauf. Angewendete001–007 bleiben immutable.
IP-036: 724 Tests und gepinnte Builds grün. IP-037: 265 Cockpittests, Typecheck,
gepinnter Cockpitbuild, 90 isolierte HTTPS/BFF/API/PG-Prüfpunkte, neun Prüfungen
mit ausgeschalteter Vorschau und acht Helper-Sicherheitsfälle bestanden;
die 461 API-/Worker- und 120 Credentialregressionen wurden nicht erneut ausgeführt.
Standard-/öffentliches Composeprofil lassen die Vorschau ausgeschaltet;
laufende öffentliche Container blieben unverändert. Brokerkeyeingabe,
physische Geräteabnahme, echte E-Mail-Attestierung, öffentliche Aktivierung und
Cockpit-Credentialausführung bleiben offen.
IP-038 ergänzt den isolierten
[TS-/Python-Assertionvertrag](passkey-credential-assertions.md), ohne dauerhaften
Aussteller/Consumer oder Änderungen an004, DB, HTTP und Runtime.
333 Cockpittests (265 plus 68 neue), 77 Offline-Onboardingtests (41 plus 36 neue)
und 109 tatsächliche Offline-Interopprüfungen sowie Typecheck bestanden.
Gepinnter Cockpitbuild und77 Tests im isolierten Python3.14.10-Container bestanden;
461 API-/Worker-, 120 Credential- und 99 HTTPS-Prüfungen wurden nicht erneut
ausgeführt. Öffentliche Dienste und ausgeschaltetes Nachweisflag bleiben erhalten.
IP-039 ergänzt additive008 und
den privaten [Autorisierungsclient](passkey-credential-authorizations.md):
Zweck beim Prepare einfrieren, ausdrücklich autorisieren, global einmalig
konsumieren und in getrennter finaler Transaktion aktuelle Bindungen sperren.
Geprüfte008-DDL und tatsächliches Runtime-Prepare im vollständig zurückgerollten
Preflight bestanden;008 ist ausschließlich in `investalo_credentials_checks`
angewendet. `investalo` bleibt001–007. Gepinnte Migrate-/Storage-/API-Prüfbuilds
und 461 erneut ausgeführte tatsächliche API-/Workerchecks bestanden.
271 Credentialtests: 19 Client-, 95 Offline- (18 neue Clientfälle) und 157
tatsächliche PostgreSQL-Fälle (97 neue008-Fälle) bestanden. Die 333 Cockpit-/
109 Interopprüfungen und der Cockpitbuild stammen aus IP-038 und wurden
für IP-039 nicht erneut ausgeführt; TS-Signer unverändert. Kein003/004-Writer,
HTTP-/Brokeranschluss oder
öffentliche Aktivierung; die sechs öffentlichen Container bleiben unverändert
und gesund. Öffentlicher HTTPS-Lesecheck200 mit regulärer TLS-Prüfung bestanden.
IP-040 verbindet den privaten
[Passkeyexecutor](passkey-credential-execution.md) mit008, Classic-Probe,003-AEAD-
Write und009-Abschlussaudit in derselben finalen Transaktion.116 Host-
Offlinefälle einschließlich 21 neuer Executorfälle bestanden.009-DDL und
tatsächlicher failed-Abschluss bestanden einen vollständig zurückgerollten
Preflight; gepinnte Migrate-/Storage-/API-Prüfbuilds bestanden.009 ist nur in
`investalo_credentials_checks` angewendet. Im gepinnten Container bestanden 356
Tests: 19 Client-, 116 Offline- (21 neue Executor-) und 221 tatsächliche PG-Fälle
(64 neue: 48 Completion/16 Executor). Erneuter API-/Workerlauf mit 461 Tests
gegen Fixture009 bestanden: 817 aktuelle Prüfungen insgesamt;
historische Cockpit-/Interop-/Buildbelege stammen aus IP-038.
001–008 bleiben unverändert; `investalo` bleibt001–007.
Keine HTTP-/Echtkey-/Echtbroker-/öffentliche Aktivierung, Nachweisflag weiterhin
aus. Sechs öffentliche Dienste unverändert/gesund, HTTPS200-Lesecheck mit
regulärer TLS-Prüfung bestanden.
Auf `feat/m1-passkey-credential-cockpit` ergänzt IP-041 die
[private Cockpit-Orchestrierung](passkey-credential-cockpit.md) mit injiziertem
Executor und eine standardmäßig ausgeschaltete008-Prepare-/Authorize-API.
Bodybytes bleiben beim vertrauenswürdigen Aufrufer; die API erhält Digests
und bewahrt die ursprüngliche OIDC-Zeit. Das explizite API-Gate und ein
konfigurierter kanonischer HTTPS-Origin/RP gelten nur für interne Zweckfreigabe.
Keine Browser-Keyeingabe-/Credentialexecutor-HTTP-Anbindung, keine
Betriebsschlüssel oder echte Brokerverbindung;001–009 bleiben unverändert,
008/009 fixture-only. Referenzrepositories weiterhin unverändert.
572 API-/Worker- und385 Cockpittests,299 integrierte Prüfpunkte,
Typecheck/gepinnte Builds und Reviews bestanden. Nach Nutzerneustart nur
synthetische Fixtureablage/Secretmounts neu vorbereitet; Fixture-APIs gestoppt,
sechs öffentliche Dienste gesund, reguläres TLS HTTPS200.
IP-042 ergänzt auf `feat/m1-credential-private-transport` einen injizierten
Entwicklungs-HTTPS-Adapter, eigenen TS-Client und tatsächliche mTLS-Fixture.
Eigene CA/Clientpin, unabhängiger Sitzungskontext und unveränderte Bodybytes;
keine Legacyübernahme, Abhängigkeiten, Migrationen oder öffentliche Aktivierung.
Die administrative Fixture ist kein eingeschränkter Runtime-Dienst.
[HTTPS-Vertrag](passkey-credential-https.md).
