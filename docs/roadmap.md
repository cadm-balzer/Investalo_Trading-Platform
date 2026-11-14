# Roadmap

Q47 priorisiert jetzt die Handelsimplementierung mit2×. IP-089 verbindet eine
gespeicherte eigene Basket-Obergrenze3–7 mit Default-off-Portfolio/API/BFF;
initial3–5, spätere zusätzliche Slots weiterhin nur über Q36-Gewinnetappen.
Kapazitätsvorschlag erhält alle offenen regulären/manuellen/Kostenreserven;
echte Futureskontodaten und Mindest-Rangeadapter fehlen noch ausdrücklich.
**IP-090 läuft:** Kandidatenpool, H1-RSI/Nachkäufe/H1-Schutz/Mark/Funding,
Budgetbindung, fsync-Journal/CAS/Restore und eingespeister2×-Paperworker geprüft.
Aktueller Classic-Collector mit25 gehashten GETs/fünf Kandidaten und
Quellen-/Journalrestore geprüft; reale58h-Quellenprobe erfolgreich.
Offene Baskets stoppen vor unbewerteten Fundingterminen.
Q48-Assetanzeige zeigt eigene RSI-/Positions-/Nachkaufstände und nächste
H1-Checks, Default-off; [Vertrag](futures-paper-assets.md).
Funding-only-Journal/Quellenfortsetzung mit eingespeister exakter Bewertung
und erhaltenen Quoteuhren geprüft; [Vertrag](futures-paper-settlement.md).
Nächster Schritt: tatsächliche Settlementmarkquelle/-erfassung, dauerhafter Feedcursor,
lokaler Launcher/Archivierung, Status-/Settingsadapter, Q36-Gewinnetappen und
Q46-Recovery/IP-088 samt laufender Cockpitanbindung. [Paperkern](futures-paper-runtime.md),
[aktueller Feed](futures-paper-feed.md).
Danach Bitget-Demoausführung und separate Echtgeldabnahme. Keine neuen
Hebelstudien davor. [Vertrag](futures-paper-settings.md).

IP-087 abgeschlossen: gleiche Modellachse2×/3×/4×/5×/10×;2× bleibt beste
Referenz.3×+85,23%/DD23,54%/zwei Liquidationen,4×+94,64%/DD29,65%/drei
Liquidationen. Unterbrochener4×-Export per vollständigem readonly Restore
abgeschlossen, kein wiederholter Marktjob. [Ergebnisse](futures-moderate-results-20261113.md).
Q46/IP-088 manuelle Wiederbelebung: Prüf-/Auditkandidat und Default-off-
Startseiten-/Portfolio-UI vorhanden; dauerhafte eigene Futurespersistenz,
Reconciliation/API/CAS und tatsächliche Browseranbindung bleiben offen.
Kausale AI-Regimevalidierung folgt getrennt, ohne geänderte Hebelfreigabe.
[Recoveryvertrag](futures-manual-recovery.md).

IP-079: alle zehn korrigierten nativen Jobs und Restores abgeschlossen;
666180 Commands/40 Artefakthashes belegt.2× H1/H4-Schutz liefert
+2507,71/+2410,79 USDT ohne Budgethaltes.5×/Stress kann echte Kostenreserve
erschöpfen;10× verliert die fünf Slots durch terminale Liquidationen.
[Vollständige Ergebnisse](futures-cash-results-20261112.md).

IP-080 implementiert echte H1-RSI-Einstiege mit gleicher Cashstaffel,
zunächst gleichem H1-Schutz und2×. Neue Signal-/Journalidentität und
Referenzbindung vor Leistung eingefroren;85 gezielte gepinnte Fälle/
57 Subtests grün. Nativer Vergleich/Restore abgeschlossen: +2643,89 USDT,
DD17,62%, sieben volle Fünfstufen-Baskets. Halt bereits2023-01-16 durch
2,30 USDT Kostenüberhang beim profitablen BTC-Abschluss.
[Ergebnisse und Auslöser](futures-h1-entry-results-20261112.md).

Q44 bestätigt ausschließlich eigene vollständig realisierte Abschlussgewinne
als Deckung des Kostenüberhangs. Separate IP-081-Policy implementiert,
174 gezielte gepinnte Fälle/103 Subtests grün. Neuer H1-/2×-Vergleich
vollständig restauriert: +3928,28 USDT,98 Abschlüsse,13 volle Fünfstufen-
Baskets, DD17,62%, keine Liquidationen. Neuer Halt2023-10-02 durch offenes
XRP-Fundingbudget; diese Grenze bleibt im eingefrorenen IP-081 hart.
Q45 beauftragt nun IP-082: das fest reservierte Budget vollständig verwenden,
Funding innerhalb der eigenen isolierten Margin statt zusätzlichem globalem
Quotenhalt. Neue reserved-cash/4 zählt tatsächliche Walletzahlungen, behält
Gebührenbacking und alle sechs Kapitalstufen. 183 gezielte gepinnte Fälle/
108 Subtests grün; nativer H1-/2×-Vergleich vollständig restauriert:
109440 Commands/vier Artefakte/acht unveränderte Start-End-Hashes.
Netto+9579,93 USDT/DD17,62%,269 Abschlüsse/24 volle Fünfstufen-Baskets,
keine Liquidationen oder Kontohaltes. Tatsächlicher letzter Einstieg
2025-07-29, zwei offene Endpositionen zum Markkurs. IP-083 hat die verbleibenden
Ablehnungen vollständig diagnostiziert:51 Versuche/34 Zyklusstufen,33 später
ausgeführt.19 reine XRP-Marginablehnungen sind Rundungsreste unter1E−8 trotz
verfügbarer eigener Restoration;32 Preisgrenzen sind deklarierte Modellguards.
Nächster Schritt: Geldquantisierung und Broker-/Kosten-/Preisregelkalibrierung
mit eigenem Referenzanker vor weiterem Hebelvergleich und unabhängigem Holdout.
IP-084 sichert aktuelle Classic-Bitget-Verträge und51 statische Rasterproben:
19 reine XRP-Marginreste durch Mengenfloor unter alter Formel gedeckt.
USDT-Geldrundung und historische Brokerregeln bleiben unbekannt.
IP-086 priorisiert nach Nutzerauftrag den direkten festen2×/5×/10×-Vergleich
auf derselben deklarierten Rasterökonomie.2×-Referenz bleibt unverändert;
nur5×/10× neue native Jobs/Restores, vollständige Classic-Kalibrierung
weiterhin separat. Sechs neue/35 gepinnte Fälle/58 Subtests grün.
Beide vollen Restores abgeschlossen:130889 Commands/acht neue Artefakte/
elf Start-End-Hashes.5×+64,34%/DD29,44%/vier Liquidationen,
10×−11,52%/DD18,15%/alle fünf Slots bis Oktober2022 terminal.
2× erzielt im festen Vergleich das höchste Netto. Für selektiven höheren
Hebel kausale Regimekriterien einfrieren; Slotwiederbelegung nach Liquidation
braucht eine eigene Recovery-/Reconciliation-/Kapitaldeckungsregel.
[Ergebnisse](futures-grid-leverage-results-20261113.md).
[Hebelvergleich](futures-grid-leverage-comparison.md).

IP-085 friert einen eigenen rastergerechten Forschungsvergleich ein;
Referenz/Staffel/Cash-/Liquidationsgrenzen bleiben erhalten.
Protokollsha8f24a3f0d9a7ba0af3daf497bf5ed2925a5478db35da138ed96a2b95afe84a8d
vor Performance gefroren; eigene current-grid/5-Policy,109 Legacy- und
dreizehn neue gezielte gepinnte Fälle grün. Nativer2×-H1-Lauf und voller
Restore abgeschlossen:108427 Commands/vier Artefakte/elf Start-End-Hashes,
netto+9596,82/DD18,01%,273 Abschlüsse/keine Liquidationen oder Kontohaltes.
Alle29 bisherigen Marginablehnungen entfallen;28 Modellpreisguards bleiben.
Mehrnetto16,90 USDT bei0,40 Prozentpunkten mehr Drawdown ist kein großer
Optimierungsgewinn. Vollständige Classic-Orderfreeze-/Marginabbildung und
Preisguard-Kalibrierung folgen separat vor weiterem Hebelvergleich.
[Rasterergebnisse](futures-current-grid-results-20261113.md).
[Rastervergleich](futures-current-grid-comparison.md).
[Aktuelle Brokerkalibrierung](futures-broker-calibration.md).
[Diagnoseergebnisse](futures-admission-results-20261113.md).
[Neuer Budgetvertrag](futures-reserved-budget.md).
[Vollständige Ergebnisse](futures-reserved-budget-results-20261113.md).
[Ergebnisse](futures-realized-cost-results-20261112.md).

IP-078 implementiert den vollständigen nativen Futures-Nettojob für alle zehn
vorab eingefrorenen Varianten, mit tatsächlichen RSI-Kaufstufen, Gebühren/
Funding, Gapexits/Liquidation, End-MTM und vollständigem Journalrestore.
Alle zehn tatsächlichen Marktjobs und vollständigen Restores sind abgeschlossen,
451193 Commands/40 Artefakthashes belegt. Zwei Modellbremsen verhindern
durchgehenden Handel: Brutto-Fundingbudget und Reservierung sämtlicher leerer Slots.
IP-079 prüft als Nächstes separate korrigierte Cash-/aktive Rangebindung.
Historische Brokerregeln, Holdout, AI und echte Ausführung bleiben offen.
[Ergebnisse](futures-market-results-20261112.md).
[Marktvergleich](futures-market-backtest.md).

IP-077 friert zehn Futures-Vergleichsfälle vor Auswertung ein und ergänzt
native exakte Fundinggrenzen: fünf feste Slots,2×/5×/10×, beide Schutzintervalle,
Kosten- und Preisreihenfolgetests. Nativer Quellen-/Profilpreflight vollständig.
Nächstes IP-074/IP-069: den vollständigen Marktjob mit Funding/Costs/Exits/
Liquidation/Endbewertung und Journal fortsetzen, dann alle Fälle netto berichten.
[Eingefrorenes Profil](futures-economic-profile.md).

IP-076 ergänzt den vollständigen neuen Kapital-/Signaljournalrestore und
größere behaltene Ereignishistorien. Fünf Nachkäufe, Funding, Tagesbasen,
feste Hebelzyklen und terminale Liquidationsverluste bleiben beim Wiederanlauf
identisch. Nächstes: wirtschaftliches Profil vor Leistungsauswertung einfrieren,
anschließend native Futures-Nettobacktests mit gleichem H1-/H4-Schutzvergleich.
[Wiederanlaufvertrag](futures-capital-journal.md).

IP-075 ergänzt die gemeinsame native H1-Futures-/Fundingquelle für
BNB/BTC/ETH/SOL/XRP im unveränderten Dreijahres-Forschungsfenster.
Eigener neuer Restore inzwischen IP-076; anschließend wirtschaftliche Annahmen
einfrieren und H1-/H4-Schutz mit gleichen Markt-/Kosteneingaben vergleichen.
[H1-Quellenvertrag](futures-hourly-history.md).

IP-074: Kapitalkern mit tatsächlichen H4-RSI-/Nachkaufsignalen und separatem
geschlossenem H1/H4-Supertrend verbunden. Feinere Preisbeobachtungen,
Liquidationsvorrang und Funding-/Teilverkaufs-Nettofloor geprüft.
Native H1-Kohorte IP-075 und voller Restore IP-076 vorhanden. Als Nächstes
wirtschaftliche Annahmen einfrieren, anschließend gleicher Futures-Nettovergleich.
[Signaladapter](futures-capital-signals.md).

IP-073: bestätigtes Eigenkapital-/Warnungs-/Liquidationsprofil als
eigenständiger Kapitalkern umgesetzt; Legacy unverändert. Nächstes IP-074:
RSI/Nachkäufe/H1-Supertrend verbinden und native Futureskohorte samt
Kosten/Funding/Journalrestore vor echtem Nettovergleich einfrieren.
[Implementierung](futures-capital-research.md).

Q43: Späterer AI-Agent bewertet Marktphase/Risiko vor dem ersten Kauf und
friert den Hebel für den kompletten Basket ein. Nachkäufe/manuelle Stufe6
verwenden denselben Hebel; neue Bewertung erst für neue Baskets.
Exakte kausale AI-Kriterien/Modellvalidierung weiterhin offen.
[Bestätigtes Kapital-/Hebelprofil](futures-capital-ladder.md).

Q42: Tabellenbeträge sind Eigenkapital, Kaufnominal=Kapital×Hebel.
Nutzer akzeptiert Liquidation vor Abschluss der regulären Staffel;
neue Variante ohne verpflichtende−50%-Überlebensgarantie.
Tatsächliche Initialmargin/Budgets/Liquidation verbuchen. Spätere kausale
AI-Regimewahl2×–10×; Startfixierung für gesamten Basket inzwischen Q43 bestätigt.
[Kapitalprofil und mechanischer Vergleich](futures-capital-ladder.md).

Q41,2026-11-12: Nutzer bestätigt volle Staffelbudgets und hebt für die neue
Futuresvariante die sperrende Rolle der6%/8%-Kontolimits und des gemeinsamen
−50%-Kontostresstests auf. Als Warnungen/Diagnose berichten; Budget,
tatsächliche Liquidationsdeckung, Signale und−55%-Notausstieg erhalten.
Eigenkapitalfrage inzwischen durch Q42 geklärt. Bestehende Rechenkerne/Paper
und eingefrorene Ergebnisse unverändert.
[Entscheidung](interview.md#q41-vollständige-kaufstaffel-statt-begrenzendem-kontostressprofil).

Q40: nächste Leistungsforschung auf Futures fokussieren; Spot-Investing
ist eine spätere separate Strategie. H4-RSI-Einstiege mit H1-Supertrend
als Forschungsvariante vergleichen, beide Stopvarianten auf derselben
feineren Preisachse. Geschlossene Kerzen, Nachkäufe,+5%/Nettofloor,
−55%/−50%/6%/8% erhalten. IP-069 braucht zuerst passende native Futures-H1-
Kohorte und eingefrorene Kosten-/Funding-/Marginannahmen. Kein Runtimewechsel.
[Entscheidung](interview.md#q40-futures-priorisieren-und-h4-einstiege-mit-h1-schutz-vergleichen).

Q39/IP-072: Nutzer priorisiert tatsächlichen H1/H4-Nettovergleich mit
vollständiger bestätigter Basket-Kapitalplanung. Eigener Spotvergleich auf
gleicher nativer Fünf-Coin-Quelle mit drei/fünf Slots und Kostenstress.
H4-Runtime bleibt unverändert; Futuresökonomie/Nettovergleich IP-069 bleibt
eine separate nächste Auswertung. [Vergleich](h1-h4-basket-comparison.md).

IP-071: vollständiges Langlaufjournal/ID-Historien und synthetischer
Dreijahresmechanik-/Wiederanlaufbeleg vorhanden. IP-069 als Nächstes
wirtschaftliches Profil/Fundingpreisbezug/passende native Kohorte und
tatsächlicher Nettovergleich. [Vertrag](futures-long-replay-journal.md).

Q38/IP-070: separater Binancevergleich bestätigt, native Dreijahresdaten
vollständig importiert. Bitget bleibt Handelsziel. Als Nächstes IP-069:
wirtschaftliches Profil einschließlich Funding-Markpreisbezug und Langlaufjournal
vor dem tatsächlichen Nettovergleich. [Datenbasis](binance-futures-research-data.md).

IP-069 erster Checkpoint: native Fundingbeobachtungen/Lückenprüfung belegt.
Für2022–2025 keine Abrechnungen aus aktueller Bitget-API; vollständige Quelle,
wirtschaftliches Protokoll und Langlaufjournal weiter offen.
[Befund](futures-funding-availability.md).

IP-068: begrenzter Futures-RSI-/Staffel-/Zyklusadapter vorhanden,
36 neue Fälle/317 gepinnte Fälle grün. IP-069 prüft Fundingprovenienz und
langes Replayprotokoll mit expliziten wirtschaftlichen Annahmen.
[Vertrag](futures-signal-replay.md).

IP-067: kausale Restfill-/Gapdeckung implementiert,31 neue Fälle;
281 unterschiedliche gepinnte Fälle/219 Subtests grün. IP-068 ergänzt RSI-/Staffel-/Zyklus-
autorität mit begrenztem Futures-Replay unter expliziten Forschungsannahmen.
[Vertrag](futures-continuation-stress.md).

IP-066 verbindet ledgerbasierte Kaufprüfung, begrenzte Pendingreservierung,
Teilfill-Dedupe und terminalen Abgleich. Dauerhafter Abgleich und echte
Fundingarchive bleiben offen. [Vertrag](futures-pending-research.md).

IP-065: Futures-Buchungsledger für Teilfills/Funding/Gaps vorhanden.
Fundingarchive/historische Regeln vor Nettoläufen offen. [Vertrag](futures-event-ledger.md).

IP-064 ergänzt eigene Futures-H4-/Fundingverträge mit Markt-/Preisartbindung
und begrenztem öffentlichen Import; danach Funding-/Maintenanceannahmen und
IP-063-Ereignisledger vervollständigen. [Datenvertrag](futures-marketdata.md).

IP-063: Offlineökonomie/Kaufstress mit44 neuen Fällen implementiert;
191 gepinnte Fälle/135 Subtests grün. Ereignisledger, Teilfills und Funding-
buchungen folgen; IP-064 zuerst eigene Futures-/Preisart gebundene
Historienverträge vor längerem Nettovergleich. [Rechenvertrag](futures-economics.md).

Q37/IP-062: Futures-Grundprofil bestätigt,20 aktuelle USDT-M-Kontrakte und
52 frühe Trade-/Markkerzen öffentlich geprüft. Alternativen AVAX/HBAR/TRX/
BGB/BAT/RENDER; volle Historien noch offen. IP-063: eigene Margin-/Funding-/
Liquidationsökonomie mit erhaltenem−50%- und6%/8%-Risk Gate, vor Futuresnettolauf.
[Vertrag und Grenzen](futures-research.md).

Q36/IP-061: bestätigte Gewinnetappen im separaten Offlinekern implementiert.
Zuerst Slots bis sieben, danach höhere neue Budgets; offene Budgets und
ursprüngliche6%/8%-Risikobasen erhalten.147 gepinnte Fälle/87 Subtests grün,
alte Dreijahresbaseline exakt reproduziert. Erweiterte Historien und
vergleichbare Nettoleistungsläufe folgen IP-055. [Vertrag](profit-etapes.md).

IP-047 ist aktiv: eigener gespeicherter Paperstand jetzt im Entwicklungscockpit sichtbar. IP-054 umfasst eigene Kontoprovisionierung, begrenzten Kurslauf und lesende Aktivierung. Als Nächstes eigener begrenzter Preview-Beobachtungsworker und längerfristige Betriebsabnahme. [Anzeige](paper-preview-integration.md).

IP-013 berücksichtigt die Nutzerpriorität2026-11-09 zum Feintuning: zuerst
geringe Kontorendite/Kapitalnutzung erklären, dann begrenzte chronologische
Kandidatenprüfung vor eingefrorener Auswahl und Holdout.
[Forschungsplan](long-history-backtests.md#geplantes-feintuning).

Q33/IP-055 erweitert die Forschungsplanung auf3–5 Coinbaskets mit gemeinsamer
Kapitalzuordnung und weiterhin bindenden6%/8%-Kontolimits. Spätere RSI-
Signalprüfung durch KI bleibt IP-021/022; Hebel/variable Stufen benötigen
eigene validierte Varianten. [Portfolio- und KI-Plan](multi-basket-ai-plan.md).

IP-056 bereitet IP-055 mit einer realen gemeinsamen BTC-/ETH-Baseline und
Kapitalnutzungsdiagnose vor. Erweiterte Coins/Budget-/Stressablehnungsregeln
vor größerem Leistungslauf festlegen. [Offline-Referenz](portfolio-reference.md).

IP-057 konkretisiert gleiche größere Slots und gemeinsame Kaufreservierungen.
Profilentscheidung ist mit Q34 bestätigt; Wiederbelegung/Signalpriorität und
erweiterte Leistungsläufe folgen.
[Kapital- und Stressprüfung](portfolio-allocation.md).

IP-058 nutzt das bestätigte Forschungsprofil mit unveränderter RSI-/Nachkauf-
und Filllogik. Zunächst synthetische Zyklen; neue Marktassets/Wiederbelegung
und eingefrorene erweiterte Leistungsläufe folgen.
[Nachkaufadapter](staged-portfolio-research.md).

Q35/IP-060 bestätigt14 Kandidaten und setzt3–5 feste wiederbelegbare Slots
mit unverändertem RSI-/Nachkaufkern um.114 gepinnte Fälle/65 Subtests grün.
XMR aktuell nicht gefunden, ZEC/HYPE/XLM ohne2022-Sample. Eigene erweiterte
Datenverträge, vollständige Historien, eingefrorener Benchmark und echter
größerer Leistungslauf folgen. [Pool und Vorcheck](candidate-pool-research.md).

Stand 2026-11-10. Q1–Q5 bestätigen privaten Pilot, Paper zuerst, feste
Risikolimits, kontrollierte KI und kostenlose externe Dienste.
Q6–Q8 bestätigen beide Handelsintegrationen im MVP, Grundstack und eigene MFA.
Q9–Q14 bestätigen BTC/ETH Spot H4, XAUUSD Trend/Pullback H1/M15,
schriftliche Crypto-Vorlage, Quote-/Preisbezüge, Docker Compose und Authelia.
Q15/Q17–Q19 bestätigen RSI-/Supertrend-Regeln und Paper-/Demolimits.
Q23 reserviert die sechste Tranche ausschließlich für manuellen Einstieg;
Freigaberegeln und Cockpit-/optionalem Mailkanal in Q29/Q30 bestätigt.
Q20 plant öffentlichen HTTPS-Einstieg für privaten Nutzerkreis, Q21 vorhandenen
SMTP; Q24 bestätigt administratives E-Mail-Recovery. Q25 MT5-Heimnetzhost,
Q26 Forschungsfilter, Q27 Pilotbackupziele und Q28 Releasegrenze bestätigt.
Keine festen Termine ohne Umfangs- und Kapazitätsentscheidung.

| Phase | Ergebnis | Abnahmekriterium / Gate |
|---|---|---|
| P0 Planung | Struktur, Inventur, Konzept, Interview, Ticketboard | Gemeinsames Verständnis bestätigt; zentrale Entscheidungen und offene Forschungsfragen dokumentiert |
| P1 Fundament | Gepinnte Laufzeiten, private Entwicklungsumgebung, Auth/Tenants, DB | Reproduzierbarer Start; Isolationstests; keine Secrets im Repository; keine ausführenden Echtgeldrechte |
| P2 Daten und Tradingkern | Crypto Basket und XAUUSD Trend/Pullback, Historienimport, Risiko-/Kostenmodelle | Datenqualität; deterministische Regeln; konsistente Budget-/Lotrechnung |
| P3 Backtest und Cockpit | Konto-/Portfoliosicht, Journal, Backtestworkflow und Charts | End-to-End-Backtest mit immutable Ergebnis, Provenienz und negativen Risikofällen |
| P4 Paper/Demo | Bitget und MT5, Dispatch, Reconciliation und Schutz | Beide Adapter mit Crash/Timeout/Teilfill/Replay geprüft; Paperkriterien vorher festgelegt |
| P5 Begrenzter Livepilot | Separat freigegebenes Konto/Strategie/Budget | Nettonachweis, Limits, Backuprestore, Alarmierung und ausdrückliche Produktions-/Livefreigabe |
| P6 Stabilisierung | Breiter validierte Assets/Strategien und Portfoliorisiko | Pro neuer Variante Netto-/Stressnachweis, gleiche Risikoverträge und geprüfte Kontoregeln |
| P7 Information und KI | News/Makro/Kalender, Signalprüfung, Researchpromotion | Lizenz-/Quotenfreigabe; messbarer Zusatznutzen; keine AI-Risikoerhöhung |
| P8 Kundenbetrieb | Erweiterte Isolation, Datenschutz, Skalierung und Produktbetrieb | Neue Produktentscheidung, Rechts-/Lizenzprüfung und belastbarer Betrieb |

Die Phasen können lesende Markt-/Kontoinformation parallel ergänzen.
Kritische Execution und Risikoprüfungen werden nicht zugunsten vieler
gleichzeitig implementierter Features verkürzt.

IP-041 verbindet den privaten Cockpitkern mit Passkey-Zweckfreigabe
und verschlüsselter Credentialausführung. Standardmäßig deaktivierte API-Routen
und die isolierte Fixtureprüfung erweitern das Fundament. Browser-Keyeingabe,
physische Geräteabnahme und der tatsächliche Credentialdienst bleiben gesonderte
Arbeit vor echter Kontoverbindung. [Ablauf](passkey-credential-cockpit.md).
IP-042 ergänzt die [private Entwicklungs-HTTPS-Grenze](passkey-credential-https.md)
mit gegenseitigem TLS. Produktionslauncher, Betriebsschlüssel und
Browser-Keyeinrichtung bleiben vor der tatsächlichen Kontoverbindung offen.
IP-043 prüft den [getrennten synthetischen Credentialdienst](credential-development-service.md)
mit eigener gebundener DB-Rolle und eigenen Schlüsseldateien. Damit ist die
Entwicklungs-Containergrenze konkret; Produktionsserver und Schlüsselbetrieb
bleiben gesonderte Abnahmen.
IP-044 übernimmt dafür den bereits gepinnten [ASGI-Unterbau](credential-asgi-transport.md)
mit TLS-/Rawframingprüfung und unabhängigen Grenzen für Verbindungen und
laufende Schreibarbeit. Echter Schlüsselbetrieb und Kontoverbindung folgen.
IP-045 ergänzt den [isolierten Browserablauf](credential-browser-flow.md):
Schlüsseleingabe, Passkey und ausdrücklicher Änderungsconsent mit synthetischer
Controller-/HTTPS-/Dienstprüfung. Öffentliche Aktivierung, Betriebsprovider
und tatsächliche Next-/Geräteabnahme bleiben separate Gates.
Aktueller Schwerpunkt nach Nutzeranweisung2026-11-08: Trading und Backtesting.
IP-046 liefert drei Jahre BTC/ETH-Forschungsdaten und reserviert ein weiteres
Jahr außerhalb des schon ausgewerteten90-Tage-Demos. Der vorhandene Cockpit-/
Workerablauf berechnet die längere Forschung; wirtschaftliche Holdoutabnahme
und Kostenkalibrierung bleiben IP-013. Danach folgt IP-047: persistente
Paperausführung, Risikoprüfung und Journal mit dem bestehenden Kern. Private
Brokerkeys sind dafür keine Voraussetzung. Weitere Credentialaktivierung
wird zurückgestellt; Echtgeld bleibt nach P4/P5 separat freizugeben.
[Mehrjahresprotokoll](long-history-backtests.md).

## Meilenstein M1: privates Cockpit mit Backtests und Paper

Enthält: MFA-Anmeldung nach ausgewähltem Identitykonzept, Tenant-/Kontobindung,
Portfolio und offene Positionen mit Datenalter, Journal, eine Strategie je Brokerpfad,
Backteststart/-abbruch und grafische Auswertung, Paperstatus und Riskanzeigen.
Bitget und MT5 gehören beide zum MVP: BTC/ETH Spot H4 und XAUUSD Trend/Pullback
H1/M15 sind bestätigt, ebenso reguläre Crypto-Signale, Schutz und Risikoprofile.
Q23/Q29/Q30 bestätigen manuellen Puffer mit Nutzerinformation und Schutzgates.
Q24 bestätigt administratives E-Mail-Recovery; Q25 den separaten Heimnetzhost.
Q28 bestätigt vollständige KI-/News-/Kalenderfeeds als späteren Ausbau.

Abnahme:

- Ein frischer Checkout kann mit dokumentiertem Lockstand privat gestartet werden.
- Zwei Testmandanten können keine Daten, Jobs, Dateien oder Streams voneinander sehen.
- Ein Backtest wird identisch reproduziert; Kosten-/Fillannahmen sind sichtbar.
- Paper verarbeitet doppelte Zustellung und unklare Ausführung ohne Blind-Resend.
- Budget-, Drawdown- und Datenfrischeverletzungen sperren neue Exposition.
- Kontostände, Cashflows und PnL werden nachvollziehbar getrennt.
- Manueller Paperpuffer mit Vorschau/Bestätigung durchläuft dieselben Risiko-
  und Ausführungsgrenzen; Benachrichtigungen lösen keine Orders aus.
- Q27: externe/offline verschlüsselte Sicherung, getrennte Schlüssel,
  RPO 24 Stunden/RTO vier Stunden im Restoretest nachgewiesen.

Kein neuer kostenpflichtiger Dienst ist Voraussetzung ohne eigene Abstimmung.
Wenn Free-Quoten oder Hostkapazität nicht ausreichen, wird Umfang/Rechenfenster
angepasst und die Lücke als Entscheidung sichtbar gemacht.

## Gate vor Live

Wirtschaftliche Schwellen und Mindeststichprobe vor Optimierung definieren.
Ausreichende Out-of-Sample-/Stressnachweise, kleine freigegebene Kapitalgrenze,
kontinuierliche Equityüberwachung, brokerseitiger Schutz soweit möglich,
Restore mit Brokerabgleich und nachvollziehbare Abbruchpolicy.

Privater Produktionsrollout und erste echte Order benötigen jeweils die
festgelegte explizite Freigabe. Eine Freigabe des Konzepts erfüllt diese Gates
nicht automatisch.

## Laufender Betrieb

Pro Release: Versionen, Quellen, Migrationen, Risiken und Rückfallplan.
Regelmäßig: Datenqualität, echte Fillkosten, Riskprofiländerungen,
Drift, Restore und Anbieter-/API-/Securityänderungen prüfen.
Optimierung erzeugt Kandidaten und Nachweise; sie ersetzt keine Risikopolicy.

Tickets stehen in [tasks/board.md](tasks/board.md), zurückgestellte Arbeit in
[backlog.md](backlog.md). Erledigte Backlogpunkte werden ins Ticket-/Entscheidungs-
archiv überführt und aus der offenen Liste entfernt.
