# Bestandsaufnahme

IP-009/IP-015: gemeinsamer isolierter Demo-Abnahmepfad über eigene HTTPS-BFF-
HTTPadapter, tatsächliche API/PG015/016/017 und separaten eingeschränkten
Python-mTLS-Executor ergänzt. Frische private Testidentitäten, tatsächliche
P256-/AEAD-/Consume-/Lock-/Completionprüfung und Prozessneustart.
Testservices ohne Hostports; normale Dienste und feste Browsersperre bleiben.
Sitzung/Key-/UID-/Parent-/IP-Provenienz synthetisch, native Abnahme folgt.
[Vertrag und Prüfbeleg](bitget-demo-local-acceptance.md).

IP-009/IP-015: eigene private Demo-Dateiidentität und explizite Serverfactory
ergänzt. Originalpfad/inode/UID/0700/0400/Fingerprints, CA/Client-EKU/
Keyzugehörigkeit/Gültigkeit bei jedem Zugriff geprüft.33 neue/914 gepinnte
Cockpitfälle, Typecheck/Build grün. Tatsächliche lokale Dateien/Loopback-mTLS/
P256/Jose geprüft; API/DB-Receipt/Executorantworten weiter synthetisch.
Provider nicht global installiert, Browserruntime fest aus. Kombinierte
laufende API/PG/Python-Executorabnahme folgt. [Vertrag](bitget-demo-private-identity.md).

IP-009/IP-015: eigener geschützter Demo-Browserablauf/HTTPadapter/Controller/
Formular sowie getrennte Next-Routen und authentifizierte Demoseite ergänzt.
101 neue/881 gesamte gepinnte Cockpitfälle, Typecheck/Build grün.
Echte P256-Signaturen in In-Process-Request/Responseprüfung; Executor und
Konten synthetisch, React-SSR statt physischem Browser. Runtime fest aus;
private Identitätsverdrahtung/kombinierte laufende/native Abnahme folgen.
Keine DB-/Service-/Dependencyänderung. [Vertrag](bitget-demo-browser-flow.md).

IP-009/IP-015: eigene Default-off-Demo-Metadaten-API/Fixture017 und gebundener
Cockpit-Serveradapter mit tatsächlicher Sitzungs-/APIanbindung ergänzt.
Nur sichere Konto-/Connectionmetadaten, aktueller Owner/Trader/Actor/Scope;
keine privaten UID/IP/Provenienz/Envelopereads oder Freigabe.
348 unterschiedliche gepinnte Fälle,54 neu; final36 betroffene APIfälle grün.
001–016/Entwicklungs-DB unverändert. Private Signing-/Executoridentität,
geschützter Dashboard-Keyeingang/kombinierte lokale/native Abnahme folgen.
[Vertrag](bitget-demo-metadata-provider.md).

IP-009/IP-015: eigener privater Demo-BFF-/Signer-/mTLS-Executorvertrag verbindet
015-APIreceipt mit tatsächlicher P256/UVprüfung, Demo-Consent und aktuellen
Readbacks. Keine Normalfreigabekonversion; exakter serverseitiger App-Typ
begrenzt gemeinsame Pythonlistener auf feste getrennte Pfade.434 verschiedene
gepinnt grüne Fälle/57 Subtests,194 neu;111 eigene TS/Python-Interopprüfungen.
Injizierte Adapter, kein operativer Provider/Dashboard- oder kombinierter
End-to-End-Betrieb. [Vertrag](bitget-demo-bff-flow.md).

IP-009/IP-015: eigene interne Default-off-Demo-API ergänzt fünf Proof-/Consent-
Routen über unverändertem015. Aktuelle Scope-/Sitzungs-/Factor-/Metadatenchecks,
committed einmaliger Claim und expliziter Consent; exakte eigene Projektion,
Expiryprüfung nach Commitack.52 neue/163 unterschiedliche gepinnte Fälle grün,
final52 erneut; keine Migration oder Dienstaktivierung. Eigener BFF folgt.
[Vertrag](bitget-demo-passkey-api.md).

IP-009/IP-015: DemoPasskeyOnboarding/Fixture016 verbinden committed Consume,
injektierten vertrauenswürdigen Provisioning-/KEKadapter und tatsächlichen
014-AEADwrite/keylosen Widerruf mit atomarem eigenem Post-Write-Abschluss.
Normal003/008/009 und014/015 byteidentisch; kein nativer Provenienzbeweis,
HTTP-Keyeingang oder aktiver Dienst.27 neue/157 unterschiedliche gepinnte
Fälle grün, final62 eigene Executor-/Demo-Purposefälle erneut.
[Vertrag](bitget-demo-passkey-executor.md).

IP-009/IP-015: additive015/eigene Demo-Passkey-Assertion-/Authorizationmodule
verbinden bestehende Registry/Counter-CAS mit eigenem Consentledger.
Feste Demo-Domains/exakte Bodybindung, committed Consume/separater finaler
Lock mit aktueller Berechtigung; originale Normalledger/014 unverändert.
35 neue/199 unterschiedliche gepinnte Fälle grün; final66 eigene
Demo-Passkey-/Storefälle erneut grün. Fixture/synthetische Verifikationsurteile,
Executor inzwischen separat ergänzt; kein HTTP-Keyeingang.
[Vertrag und Abnahme](bitget-demo-passkey-purpose.md).

IP-009/IP-015: demo_store.py/additive014 ergänzen eigenes bitget_demo-Konto,
immutable Ciphertextmetadaten/atomaren Audit und aktuellen tatsächlichen
LOGIN-/Tenant-/Owner-/Epoch-/Reauth-/Ready-/Expiryreader. Registrieren,
KEK-Rewrap und terminaler UUID-Widerruf mit CAS;31 neue/229 gepinnte Fälle/
204 Subtests grün. Nur Fixture-DDL/Synthetik, keine operative Keyannahme.
Demo-Passkey-Purpose inzwischen separat vorhanden; Dashboard-/Executoranschluss
folgt. [Vertrag](bitget-demo-credential-store.md).

IP-009/IP-015/IP-016: eigener DemoSecretSpec/AES-GCM-Purposekern und
SealedDemoReadProvider in demo_secret_provider.py. Demo/Normal-Ciphertexte
nicht austauschbar; aktueller trusted Snapshot/Storage/Purpose/Ciphertext
vor/nach Decrypt geprüft. 18 neue Fälle;180 gepinnte Fälle/204 Subtests grün.
Eigene tatsächliche DB-/Passkey-Purposeeinrichtung und geschützte Dashboard-
Demo-Eingabe/native Abnahme folgen. [Vertrag](bitget-demo-secret-provider.md).

IP-015/IP-016: futures_demo_read.py verbindet registered scope/CAS mit eigenem
signierten identity+14-Achsen-GET-Transport und provider-/key-/UID-/Parent-/IP-
Gates. Explicit HTTPS ohne Proxy/Redirect; alte drei Readpfade unverändert.
22 neue synthetische Provider-/Mock-HTTPS-Fälle/143 Gesamtfälle grün.
Geschützter tatsächlicher Demo-Provider und native Abnahme fehlen weiter;
keine Brokerrequests/Services/Orderautorität. [Vertrag](bitget-demo-read-transport.md).

IP-015/IP-016: futures_demo_registry.py ergänzt ursprüngliche private UID-/
Kontopfadregistry und RegisteredDemoOutbox. Create-only Claim vor Genesis,
Katalog-/UID-/Outboxlocks und erneute Root-/Claim-/Inodeprüfung; keine zweite
Kontobindung/Keyrotation/Originalinitialisierungsreset. 29 neue tatsächliche
Filesystem-/Prozessfälle/121 Gesamtfälle grün. Kein nativer UID-/Keynachweis
oder Dispatcher. [Vertrag](bitget-demo-account-registry.md).

IP-015/IP-016: futures_demo_account.py ergänzt feste14 Readachsen,
bounded Pendingpagination, sieben native Configchecks und einen readonly
Wallet-/Positions-/Order-/Triggerabgleich unter der eigenen Outboxrevision.
Eigene Cash-/ursprüngliche Positionsbasis bleibt explizit; keine implizite
Paperübernahme. 22 neue/92 gesamte synthetische Fälle grün, tatsächlicher
privater Outboxrestore inklusive. Native ältere Orderabdeckung/Kontoprovenienz/
Kosten/Funding/Transport bleiben offen; keine Aktivierung.
[Vertrag](bitget-demo-account-check.md).

IP-016: futures_demo_outbox.py ergänzt eigenes privates append-only
Journal mit Kontobindung/Commanddigest, exklusivem Pfadwriter/CAS,
Unknown-before-send, fsync/readback und atomarem Mindestreceipt.
Vollrestore erhält bestätigte sowie unklare Suffixe ohne Resend/Reset.
22 neue tatsächliche Filesystemfälle/70 Gesamtfälle einschließlich
Kindprozessabbruch grün. Keine Broker-/Finanz-/Dienstaktivierung.
Kontoregistry, vollständiger nativer Account-/Order-/Cash-/Kostenabgleich
und gebundener Transport folgen. [Vertrag](bitget-demo-outbox.md).

IP-015/IP-016: futures_demo.py/futures_demo_reconcile.py ergänzen einen
separaten Offline-Classic-Demovertrag mit eigenen unsignierten IOC-Plänen,
stabiler Commandkennung, Unknown-/Ack-/Teilfill-/Stornozuständen und
Positionsmengenvergleich. 24 neue/48 gesamte synthetische Fälle grün.
Keine Schlüssel/HTTP-Dispatch/Outbox/Finanzbuchung oder Dienstaktivierung.
Demo-Keynachweis, dauerhafter Executionpfad und volle Account-/Order-/
Kostenreconciliation folgen. [Vertrag](bitget-futures-demo.md).

IP-088: futures_paper_recovery.py/futures_recovery_executor.py ergänzen eigene
gebuchte Paperliquidationen, vollständiges cashgedecktes Neubudget, Ziel-RSIreset
und additive manuelle Journal-CAS-Aktion/Vollrestore. Alte Verluste/Peerreserven/
Quellenbasis bleiben erhalten. Optionale gemeinsame Status/3-Publikation,
normale scoped GET-/POST-API und create-only Allocation-/Journalregistry verbinden
bestehende Cockpit-/BFF-Komponenten. Aktiver Feedwriter bleibt exklusiv.
Default-off;42 tatsächliche HTTPS/PG/SSR-Prüfungen mit synthetischer Quelle,
bounded Launcher-/APIübergabe und vollem Restore bestanden. Physische
Browserabnahme/große Journale/Dauerbetrieb und Demoabgleich folgen.
[Vertrag](futures-manual-recovery.md).

IP-090: futures_paper_universe.py/local_seven_profit_config ergänzen ausdrücklich
AVAX/LINK zu sieben echten Classic-Kandidaten. Quellen35 GETs/Settlement14,
eigene /2-Records, privater Archivvollrestore, journalgebundene Launcher und
eigene Kapazitäts-/Assets-API; anfänglich weiterhin drei finanzierte Ranges.
Sieben neue Fälle und native Abnahme mit null Entries/Closures grün.
Fünf-Coin-Defaults/alte Journale unverändert.
[Vertrag und Receipt](futures-seven-candidates.md).

IP-090/Q36: futures_paper_profit_plan.py/futures_paper_profit.py führen eine
eigene profit/2-Policy mit tatsächlichem Abschluss-/Nettopräfix, once-only
Budgetepochen,3→7-Plätzen und anschließend zukünftiger Volumenerhöhung ein.
Offene alte Ranges bleiben eingefroren; Gewinne werden nicht nochmals gebucht.
Eigener Journal-CAS/Full-restore, gebundener Quellen-/Kontoworker und normaler
Kapazitätsreader sind verbunden. Zwölf neue Fälle;224 breiter gepinnter Lauf/
118 Subtests und final37 gezielte Fälle/11 Subtests grün.
Native Kandidaten bleiben fünf; Erweiterung für6/7 als Nächstes.
[Vertrag](futures-paper-profit-epochs.md).

IP-090: futures_paper_capacity.py/futures_capacity_source.py verbinden eigenes
bestätigtes Cash, offene reguläre/manuelle/Kosten-/Restorationreserven, feste
finanzierte Ranges und archivierte aktuelle Quotes mit einem zusätzlichen
unsigned Classic-Contracts-GET. Gemeinsame Statuspublikation/2 mit /1-Kompatibilität,
scoped Planungs-API und Portfolio zeigen Empfehlung oder konkrete Blocker.
Nur Beratung, keine neuen finanziellen Gates oder Kapitalfreigaben.
89 gezielte gepinnte Fälle/18 Subtests,574 Cockpitfälle/Typecheck grün.
[Vertrag](futures-paper-capacity.md).

IP-090: futures_local_profile.py erklärt ein eigenes10k/3-Ranges/5-Kandidaten/
2×-Laufprofil mit originalem aktuellen Classic-Raster-SHA. Das neue explizite
lokale Composeoverlay/geschützte Fixturemount und der native HTTP-Cockpittest
verbinden echte Quellen mit gebundenem CLI, Journal, Status, HTTPS/BFF/API/PG
und tatsächlichem Next-SSR. Keine öffentliche Aktivierung oder neue Migration.
[Lokale Abnahme](futures-local-cockpit-acceptance.md).

IP-090: futures_paper_account.py/futures_paper_bootstrap.py binden eine eigene
explizite private Allokation/Actor-/Genesisdatei an vorhandene Konto-UUIDs.
futures_account_reader.py liest aktuelles eigenes ready/USDT/Paperkonto und
013-Einstellungen per restricted LOGIN/readonly RLS. futures_account_worker.py
übernimmt echte neueste Revisionen und prüft vor Commits erneut;
futures_account_main.py bietet einmalige Initialisierung/gebundenen Restore.
22 neue Fälle/nach Gesamtrun und gezieltem Schlusslauf162 verschiedene grün;
114 Subtests. Noch kein dauerhafter Dienst; Paperkapazitätsreader separat ergänzt.
[Vertrag](futures-paper-account-binding.md).

IP-090: futures_paper_archive.py sichert native25-/10-GET-Kohorten vor
Verwendung und revalidiert Originalantworten beim Laden offline.
futures_paper_source.py/futures_paper_journal.py binden Cursor und ausstehendes
Funding an den eigenen Journalcommit; futures_source_worker.py setzt mit
frischen Quotes fort. futures_paper_main.py ist ein default-off begrenzter
Launcher für vorhandene eigene UUID-/Genesisjournale. Zwölf neue/140 gezielte
gepinnt grüne Fälle/109 Subtests; eigene Konto-/Kapital-/013-Anbindung separat
implementiert, noch keine laufende Dienst-/Cockpitaktivierung.
[Vertrag](futures-paper-source-worker.md).

IP-090: futures_paper_status.py veröffentlicht nach bestätigtem Workerjournal
einen kompakten eigenen FuturesAssetState mit Receipt in privaten atomaren
owned0600-Dateien. Optionaler normaler API-Reader über privaten Statusroot;
Frische/RSI-Fenster/Kontosperren bei jedem Lesen neu berechnet. Full-restore-
Minimumreceipt bindet Neustart/Reparatur; Unknown-write stoppt Weiterarbeit.
Begrenzter Launcher separat implementiert, kein laufender Feeddienst;
[Vertrag](futures-paper-publication.md).

IP-090/Q49: futures_paper_minute.py ergänzt die bestätigte native Minuten-Open-
Paperreferenz mit vollem OHLC-/Quellen-/Wissenszeitvertrag und eigenem
minute_settlement-Journalbefehl. Quellenübergabe vergleicht native Fundingraten/
IDs beider Belege; bestehender Worker kann explizit abrechnen. Vollrestore,
Cash/Mitternacht/Liquidationslatch und alte exakte Goldenidentität geprüft.
Begrenzter Launcher und Statusreader separat implementiert, Betrieb noch offen.
[Vertrag](futures-paper-minute-funding.md).

IP-090: futures_settlement_source.py und capture-futures-settlement-source.py
erfassen zehn native GETs/fünf Fundingraten/fünf Mark-Minutenkerzen mit
geschütztem Archiv/Roundtrip. Reale16:00Z-Probe erfolgreich. Minuten-Open
ist die bestätigte Q49-Paperreferenz; kein exakter Broker-Settlementmark.
Archivbytes/-flags bleiben unverändert; Aufnahme startet keinen Worker.
[Vertrag](futures-settlement-source.md).

IP-090: futures_paper_settlement.py ergänzt einen Funding-only-Journalbefehl
mit unabhängiger exakter Settlementbewertung, nativen Raten und getrennten
Ereignis-/Wissenszeiten. Worker settle_once und bestätigter Quellenfortgang
inklusive vollständigem Restore; Handelsquoteuhr bleibt unverändert.
Ein exakter Broker-Settlementmark fehlt weiterhin; Q49 ergänzt dafür einen
eigenen deklarierten Modellvertrag, ohne den exakten Vertrag umzudeuten.
[Vertrag](futures-paper-settlement.md).

Q48/IP-090: futures_paper_view.py liefert die eigene Asset-/RSI-/Positions-/
Nachkaufprojektion; futures_paper_assets.py und GET/v1/futures-paper-assets
binden authenticated own IDs an einen privaten bestätigten State-Reader.
FuturesAssetsPanel/TS-Vertrag/15s-Refresh auf Übersicht und Portfolio,
Default-off. RSI-Kerzenschluss, echte Fills,95%-Tickgrenze, H1-Check und
Warte-/Sperrgründe; optionaler privater Dateireader jetzt implementiert,
laufende Quellen-/Dienstanbindung bleibt offen.
[Vertrag](futures-paper-assets.md).

IP-090 aktueller Classic-Collector: futures_paper_feed.py sammelt25 öffentliche
GETs für fünf Futureskandidaten mit getrennten H1-Trade/Markachsen, nativen
Quoteuhren, Fundinghistorie/Forecast und gehashter Quellenbindung.
capture-futures-paper-feed.py sichert25 owned0600/create-only Antworten und
typisierten Observation-Roundtrip vor Receipt; echte58h-Probe grün.
Paperübergabe benötigt den bestätigten Vorgängerbeleg und sperrt offene
Positionen vor unbewertetem Funding. Archivierter begrenzter Quellenworker
separat implementiert; kein laufender Feed-/Fundingdienst.
[Vertrag](futures-paper-feed.md).

IP-090 erster Schritt: futures_paper_plan.py trennt Kandidaten von finanzierten
Plätzen; futures_paper.py verbindet den H1-/Cashkern mit2×-Paperfills.
futures_paper_journal.py speichert eigene Genesis/Batches/Settings per fsync
und vollem Restore; futures_paper_worker.py nutzt einen eingespeisten Feed.
Provider-/DB-/Cockpitanbindung, Gewinnetappen und Recovery bleiben offen.
[Vertrag und Prüfbeleg](futures-paper-runtime.md).

IP-089: futures_paper_settings.py/API/BFF/FuturesPaperSettingsPanel speichern
eigene USDT-Paper-Planung3–7 mit Revision und atomarem Audit. Additive013
nur in investalo_credentials_checks, sha78f1c339f6ff8b5bf6827d7eae3d987b6ed6a8bd32b69dcfcc45a88a94753645.
futures_capacity.py berechnet aus vertrauenswürdigen Cash-/Reserve-/Range-/
Gewinnetappen-/Kandidatenbelegen einen technischen Kapazitätsvorschlag.
Own-Paper-Cash-/Mindestorderadapter ist inzwischen separat angebunden;
ohne frische Belege weiterhin recommendation=null/runtime_ready=false.
Default-off; Q36-Gewinnetappen und eigener dauerhafter Dienst bleiben IP-090.
Kein Spotkontostand-/historischer End-MTM-Ersatz. [Vertrag](futures-paper-settings.md).

IP-087: eigene ModerateEconomicScenario-Flagachse auf unverändertem Grid-/Cashkern.
Für unterbrochene Exporte existiert readonly futures_journal_metrics.py plus
complete-futures-moderate.py, keine Wiederholung nativer Jobs nötig.
IP-088: futures_capital_recovery.py liefert reinen Kandidaten/Auditreceipt;
FuturesRecoveryPanel/BFF Default-off. Kein dauerhafter Futuresruntimeadapter.
Siehe docs/futures-manual-recovery.md und docs/futures-moderate-results-20261113.md.

IP-086: explizite `grid_leverage_comparison`-Achse im vorhandenen
Rasterprofil/Marktjob. Gleicher Gridplan-/Journaldecoder mit zusätzlicher
Protokollbindung im Policydigest, alte2×-Defaultidentität unverändert.
`--h1-grid-leverage` faltet5×/10× vollständig und bindet die wiederverwendete
2×-Referenz an deren vier unveränderte Ausgabeartefakte. Beide vollen
nativen Restores130889 Commands/acht neue Artefakte/elf Start-End-Hashes
und252 neue Käufe mit konstantem Hebel auf Raster geprüft.
[Ergebnisse](futures-grid-leverage-results-20261113.md).
Keine neue Abhängigkeit oder Laufzeitaktivierung.
[Vergleich](futures-grid-leverage-comparison.md).

IP-085: eigener `futures_capital_grid.py` und bytegebundener
`futures_grid_profile.py`; expliziter `--h1-current-grids`-Job verwendet
bestehenden Kapital-/Ledger-/Signal-/Funding-/Journalablauf.
Plan-/Profilidentity enthält Mengen-/Preisraster/Marketgrenzen/Quellendigest,
alte Defaultdigests bleiben gleich. Nur zwei zusätzliche read-only
Testmounts, kein Runtime-/Dependencywechsel. Vollständiger nativer Job/Restore
und alle536 Entry-/273 Exitrasternachweise abgeschlossen; vier Artefakte
und elf unveränderte Start-End-Implementationshashes gesichert.
[Ergebnisse](futures-current-grid-results-20261113.md).
[Vergleichsvertrag](futures-current-grid-comparison.md).

IP-084: isolierter `futures_broker_calibration.py`, create-only
`capture-futures-broker-rules.py` und lokale `probe-futures-broker-grids.py`.
Ein fixer öffentlicher Classic-GET; strikte fünf USDT-Perpetualverträge,
genaue Decimalraster und begrenzte Auditpräzision. Keine Runtimecaller oder
Änderung an zehn Referenzmodulen. 16 gepinnte Tests/20 Subtests,
hashgebundene aktuelle Metadaten und51 statische Proben.
[Vertrag und Grenzen](futures-broker-calibration.md).

IP-083: eigener nur lesender `futures_admission_audit.py` und fester
`audit-futures-admissions.py`-CLI. Der bestehende Journaldecoder/Reducer,
Signalassessment und Kapitalplan werden unverändert wiederverwendet.
Vollständige Kette/Endreceipt und Originalhashes verifiziert; abgelehnte
Assessments verändern keinen Zustand. Evidence enthält exakte Dezimalstrings,
Kettenanker und Cash-/Margin-/Preiswerte. Kein neuer Marktjob oder Runtimecaller.
[Ergebnisse](futures-admission-results-20261113.md).

IP-082: separates `CapitalReservedCashPlan`; tatsächliche Walletkosten und
eigenes isoliertes Funding sind getrennt. Kapitalkern, Ledgerbuchungen,
Signalrearm, normaler Q44-Abschluss und Full-Genesis-Journal wiederverwendet.
Restoration lässt Gebühren für reguläre Restkäufe/deklarierten vollständigen
Ausstieg in der eigenen Barreserve; nur der neue Trigger verwendet diese
gleiche Kapazität. `--h1-reserved-cash` bindet ein neues Protokoll an den
vollständigen IP-081-Receipt. Keine neue Broker-/Runtimeautorität.
[Reserviertes Budget](futures-reserved-budget.md).

IP-081: separates `CapitalRealizedCashPlan` mit default-striktem
Ledgerabschluss-Hook. Q44 erlaubt ausschließlich positiven eigenen
vollständigen Abschlussgewinn als Kostendeckung; keine neue Cashbuchung.
`--h1-realized-costs` bindet ein separates Protokoll an IP-080-Receipt.
[Abschlusskosten](futures-realized-exit-costs.md).

IP-080: explizites `CapitalH1SignalProfile` und eigene H1-Journaldomäne.
Geschlossener H1-RSI aus demselben nativen Input; bestehender Signal-/Ledger-/
Fundingschutz und Replay wiederverwendet. `--h1-entries` bindet vorab
eingefrorenen 2×-Vergleich an vollständig geprüfte H4-Einstiegsreferenz.
Keine neue Abhängigkeit, Broker- oder Runtimeautorität.
[H1-Einstiegsvergleich](futures-h1-entry-comparison.md).

IP-079: separates `CapitalCashPlan` im bestehenden Kapitalkern, expliziter
`--cash-budgets`-Marktjob und bytegebundenes neues Protokoll. Wiederverwendet
Ledger/Signal/Funding/Journal mit unverändertem Legacydefault; volle aktive
Ranges und eigene tatsächliche Kosten statt unbeanspruchter Leerslot-/Bruttolimits.
[Cashbudgets](futures-cash-budgets.md).

IP-078: vollständiger `futures_capital_backtest.py` und create-only
`backtest-futures-capital.py` für zehn eingefrorene native Dreijahresvarianten.
Wiederverwendet den bestehenden Kapitalkern, Signaladapter und vollständigen
Journalrestore. Eigene byteidentische `capital_digest.py`-Beschleunigung;
begrenzte feste Snapshot-Schemata gecacht. Keine Broker-/Runtimeautorität.
[Marktvergleich](futures-market-backtest.md).

IP-077: eingefrorenes `futures_research_profile.py`, create-only
`preflight-futures-capital.py` und explizite valued-hour/Fundingbatch-
Journalcommands. Native Quellenidentität/Settlementzeiten bleiben erhalten,
Kosten und Versicherungsdeckung sind erklärte Modellannahmen.
Keine vollständige Marktjob-/Performance- oder Runtimeaktivierung.
[Wirtschaftsprofil](futures-economic-profile.md).

IP-076: eigener `futures_capital_journal.py` und versionierte größere
`capital_identity_history.py`. Vollständiger Restore des neuen Q41–Q43-
Kapital-/H4-RSI-/H1/H4-Schutzprofils, eigene Genesis, bestätigter Mindestanker
und Unknownwrite ohne Retry. Legacy-Module/Exporte unverändert.
[Wiederanlauf](futures-capital-journal.md).

IP-075: eigener `binance_futures_hourly.py` und create-only
`import-futures-h1-history.py`. Fünf bekannte Coins, native H1-Trade-/Mark-
und Fundingquellen; Legacy-H4-/Bitgetformate unverändert. Wiederverwendet
geprüfte Fundingzeilen/Canonical-/UTC-/Preis-/NoRedirect-Helfer und neutrales
ResearchCandle. Kein wirtschaftlicher Replayjob oder Brokerzugriff.
[Quelle](futures-hourly-history.md).

IP-074: `futures_capital_signals.py` verbindet den eigenen Kapitalkern mit
geschlossenem H4-RSI und getrenntem H1/H4-Supertrend. Wiederverwendet Wilder-
Indikatoren und neutrale ResearchCandle/H4-Aggregation; Defaults unverändert.
Volle tatsächliche fünf Stufen, genaue Fundingbewertung und Liquidationsvorrang.
Kein Brokerpending, neuer Journalrestore oder nativer Nettojob.
[Vertrag](futures-capital-signals.md).

IP-073: eigener `futures_capital_research.py` und deklarierte vollständige
`LiquidationSettlement`-Buchung. Legacyprofile behalten ihre Identität/Gates.
Eigenkapitalstaffel/fester Zyklushebel, Warnungen statt Kontostresssperren,
Restmargin/Versicherungsbeleg und ungestellte Reserven getrennt.
Kapitalmodell ohne RSI-/Broker-/Persistenzautorität.
[Vertrag](futures-capital-research.md).

IP-072: `timeframe_spot.py`, `timeframe_research.py` und create-only
`research-timeframes.py` für den beauftragten echten H1/H4-Basketvergleich.
Eigene Offlineversion verwendet bestehenden RSI-/Pool-/Fill-/Risikokern,
volle Drei-/Fünf-Slotbudgets und fünf bestätigte Coins. Standard weiterhin H4.
[Vertrag und Ergebnisse](h1-h4-basket-comparison.md).

IP-071: `identity_history.py`/`futures_replay_journal.py`, ausdrücklicher
Pending/2-Modus; bestehender Standard1024 unverändert. Vollständiger
6576-Frame-Synthetiklauf mit7672 erhaltenen IDs/Restore.25 neue Fälle/
342 unterschiedliche gepinnte Trading-/Workerprüfungen.
[Vertrag](futures-long-replay-journal.md).

IP-070: eigenes `binance_futures.py`, gefrorene create-only ImportCLI und
belegter separater Binance-Dreijahresdatensatz: je BTC/ETH6576 H4-Kerzen pro
Trade/Mark/Index und3288 Fundingraten.28 neue Fälle/130 unterschiedliche
gepinnt grün. Kein Nettoleistungslauf. [Vertrag](binance-futures-research-data.md).

IP-069: neues `futures_funding.py`, create-only ImportCLI, gefrorenes
Quellenprüfprotokoll und echte Receipt.25 neue Fälle/102 gepinnte Marktdatafälle
grün. Bestehende Snapshots/Tradingkerne unverändert. [Vertrag](futures-funding-availability.md).

IP-068: neues `futures_signals.py`,36 synthetische Fälle für RSI/Wilder,
Nachkäufe, tatsächliche Teilfill-VWAPs, Zyklen und Nettofloor.313 unterschiedliche
Host-/317 gepinnte Trading-/Workerfälle/228 Subtests grün; alte Module und
Exporte unverändert. [Vertrag](futures-signal-replay.md).

IP-067: neues `futures_continuation.py` und31 Fälle für vorhandene/volle
Restmenge, signed Nettostand und korrelierte Gapstresshülle. Keine bestehenden
Module/Exports geändert;277 unterschiedliche Host-/281 gepinnte Fälle/219 Subtests grün.
[Vertrag](futures-continuation-stress.md).

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
