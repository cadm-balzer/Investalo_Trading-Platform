# Git-basiertes Ticketboard

Stand 2026-11-10. Dieses Board ist das initiale Task-/Ticketsystem ohne
zusätzliche Tools oder externe Veröffentlichung.

Status: `READY` ausführbar, `IN_PROGRESS` aktiv, `WAITING_DECISION` benötigt
konkrete Nutzerentscheidung, `BLOCKED` benötigt Voraussetzung, `DONE` geprüft.
Ein Ticket wird mit Ergebnis, Prüfbeleg und gegebenenfalls Commit abgeschlossen.
Priorität `P0` ist kritisch, `P1` Kernumfang, `P2` Ausbau.

| ID | Prio / Phase | Status | Aufgabe | Abhängigkeit / Abnahme |
|---|---|---|---|---|
| IP-001 | P0 / P0 | DONE | Originalauftrag, Skills, Host und Referenzrepos inventarisieren | Vollständig gelesen; read-only Quellenstände in inventory.md |
| IP-002 | P0 / P0 | DONE | grill-me-Interview und gemeinsames Verständnis | Q1–Q31 bestätigt, Nutzer beauftragt Umsetzung |
| IP-003 | P0 / P0 | DONE | Struktur, Konzept und Projektdokumentation | Vollständiger Entwurf; Links/Tickets/Beispiele/Diff geprüft, im Planungsbranch gesichert |
| IP-004 | P0 / P0 | DONE | Git-Containment für Credentialpfad | Ignore + aus Tracking entfernt, lokale Datei erhalten; Resthistory dokumentiert |
| IP-005 | P0 / P0 | WAITING_DECISION | Credentialrotation und Historyremediation koordinieren | Inhalte nicht ausgeben; Rotation falls echte Keys; Rewrite/Force-Push nur explizit |
| IP-006 | P0 / P1 | IN_PROGRESS | Runtimepins und bestätigten Betriebsentwurf konkretisieren | Pins/Locks/Digests und lokaler Lauf geprüft; SMTP/Recovery/Backup/Pilot noch offen |
| IP-007 | P1 / P1 | IN_PROGRESS | Gepinntes Bootstrap und reproduzierbarer privater Start | Fünf Basisdienste plus Researchprofil aufgebaut; unabhängiger Clean-Checkout-Nachweis vor Pilot |
| IP-008 | P0 / P1 | IN_PROGRESS | Auth, Tenants, RBAC und DB-Isolation | OIDC/MFA, BFF, Einladungsprovisionierung und FORCE RLS getestet; Recovery/Registrierung/Streams folgen |
| IP-009 | P0 / P1 | IN_PROGRESS | Credentialverschlüsselung und minimale Serviceidentitäten | AEAD, gebundener Store und einmalig autorisierter privater Probe-/Writeablauf geprüft; Betriebsprovider, HTTP/BFF-MFA und echte Keyannahme folgen |
| IP-010 | P1 / P2 | IN_PROGRESS | Crypto- und MT5-Strategien vollständig spezifizieren | Sachentscheidungen bestätigt; Regeln dokumentiert, technische Kern-/Broker-/Kausalitätsabnahme folgt |
| IP-011 | P1 / P2 | IN_PROGRESS | Marktdatenimport, Instrumentmetadaten und Snapshots | Strikte H4-Snapshots/CSV/Bitgetpagination und IP-046-Dreijahresfenster BTC/ETH mit reserviertem Jahres-Holdout; Datenrechte und historische Instrumentregeln offen |
| IP-012 | P0 / P2 | IN_PROGRESS | Tradingkern und unabhängige Risk Engine | Crypto-Core: 31 Tests; Offlineworker nutzt denselben Kern; MT5, Broker-/Paper-Riskintegration folgen |
| IP-013 | P1 / P3 | IN_PROGRESS | Kosten-/Fillmodell, reproduzierbare Backtests und kontrolliertes Feintuning | Gefrorene Dreijahresresultate IP-046; Nutzerpriorität2026-11-09: geringe Kontorendite anhand Kapitalnutzung, RSI-Einstiegen, Ausstiegen, Kosten und Benchmark erklären. Danach begrenzte Kandidatenprüfung mit chronologischer Validierung; Regeländerungen separat abstimmen, Auswahl vor unabhängiger Holdoutabnahme einfrieren. [Forschungsplan](../long-history-backtests.md#geplantes-feintuning) |
| IP-014 | P1 / P3 | IN_PROGRESS | Cockpit, Portfolio und Journal | MFA/Portfolio/Journal plus Datasetwahl, tatsächliche Nettoergebnisse und Equitykurven; visuelle Browserabnahme und Paperbedienung folgen |
| IP-015 | P0 / P4 | BLOCKED | Bitget-Anbindung für Paper/Demo | IP-009/012; Capabilityvertrag, Modustrennung und Kontobindung |
| IP-016 | P0 / P4 | BLOCKED | Outbox, Executionjournal und Reconciliation | IP-015; Crash/Timeout/Doppelzustellung/Teilfill ohne Blind-Resend |
| IP-017 | P0 / P4 | BLOCKED | Kill-Switch, Schutz und Fachalarmierung | IP-016; neue Exposition, Cancel und Flatten getrennt nachweisen |
| IP-018 | P0 / P4 | BLOCKED | Backup/Restore und Betriebsabnahme | IP-007/016; extern/offline verschlüsselt, Schlüssel getrennt, RPO 24h/RTO 4h, Restore isoliert mit Brokerabgleich |
| IP-019 | P0 / P5 | BLOCKED | Livepilot vorbereiten und Freigabe einholen | IP-013/017/018; vorher vereinbarte Nettonachweise, Konto/Budget/Production konkret |
| IP-020 | P0 / P4 | BLOCKED | MT5-Heimnetzbridge und Legacyportierung im MVP | Ausgehendes HTTPS, Demo-/Gerätebindung; Auth/Risk/Lotsizing/Zeitkausalität, ein Writer/Konto |
| IP-021 | P2 / P7 | BLOCKED | Makro, Kalender und News integrieren | Rechte/Quoten/Provider geklärt; Point-in-time und Datenalter |
| IP-022 | P2 / P7 | BLOCKED | KI-Prüfung von RSI-Signalen im Shadow Mode und Kandidatenpromotion | Q33/IP-013/021/055; Marktphase/Fear & Greed/News/Halving-Kontext, historischer Wissensstand und prospektiver Vergleich. Provider/Datenschutz/Aufrufbudget und Variante festlegen;6%/8% bleiben außerhalb der KI bindend. Hebel/variable Stufen separat validieren |
| IP-023 | P2 / P8 | WAITING_DECISION | Öffentliches Kundenprodukt definieren | Privatpilot; neue Scope-, Rechts-, Lizenz- und Betriebsentscheidung |
| IP-024 | P0 / P3–P4 | IN_PROGRESS | Manuellen Crypto-Paperpuffer und Nutzerinformation umsetzen | Domainvorschau/Bestätigung/Risk implementiert; echte MFA-Schrittbestätigung, UI/Worker/optionale E-Mail folgen |
| IP-025 | P1 / P1–P3 | DONE | Lokales Fundament zur Zwischenabnahme bereitstellen | Gepinnte Builds, 82 automatisierte Tests und 28 reale HTTPS-/MFA-/BFF-Prüfpunkte bestanden; kein fertiger M1-Pilot |
| IP-026 | P1 / P2–P3 | DONE | Lokalen Daten-/Research-/Ergebnisablauf schließen | 540 reale BTC-H4-Kerzen importiert; 132 Tests und 32 reale HTTPS-Prüfpunkte bestanden, einschließlich Offlineworker und Equitykurve |
| IP-027 | P0 / P4 | DONE | Classic-Bitget-Verbindungsplan und isolierten Readkern prüfen | Eigene Nutzerkeys und Classic bestätigt; 24 Offline-Tests plus unabhängiger Review; echte Keyeingabe und Serviceanbindung bleiben IP-009/IP-015 |
| IP-028 | P0 / P1 | DONE | Isolierten Credential-Envelopekern prüfen | 20 AES-GCM-Tests mit gepinnten Wheels, unabhängiger Review und gehärteter Offline-Checkcontainer; echte Keyannahme und persistente Integration bleiben IP-009 |
| IP-029 | P0 / P1 | DONE | Gebundene persistente Credential-Speicherung prüfen | 19 Client +18 echte PG-Tests, vier Provisionierungstests und Rollen-Driftprobe; damals003 nur Fixture-DB, inzwischen001–005 beide DBs; Betriebsprovider/HTTP/MFA bleiben IP-009 |
| IP-030 | P0 / P1–P4 | DONE | Bitget-Prüfung, Triple-Speicherung und einmalige Actionfreigabe verbinden | 120 Tests inkl. 60 echte PG-Fälle bestanden; synthetische Freigaben/Broker, damals004 nur Fixture-DB; HTTP/BFF-MFA und Pilotprovider bleiben IP-009 |
| IP-031 | P0 / P1 | DONE | Geschützte Kontometadaten und vorbereitete Actionzustände prüfen | Additive005, 36 reine +20 PG-Metadatenfälle, 25 Actionzustandsfälle; 40 reale HTTPS-Prüfpunkte einschließlich gesperrtem Step-up und IdP-Faktorfrischebefund |
| IP-032 | P0 / P1 | DONE | Bestätigten zusätzlichen Passkey-Assertionkern prüfen | SimpleWebAuthn14.1.0, 19 echte synthetische Signaturtests, voller Cockpitlauf78/Typecheck/Containerbuild grün; unabhängiger Review, kein aktiver HTTP-Verifier |
| IP-033 | P0 / P1 | IN_PROGRESS | Dauerhafte Passkeyverwaltung und Browser-Schrittflow integrieren | Registry/Enrollment IP-034, Nachweis007 IP-036, synthetischer BFF-Durchlauf IP-037, Vertrag IP-038, Zweckfreigabe008 IP-039, privater Executor IP-040, Cockpitablauf IP-041 und Entwicklungs-HTTPS IP-042 vorhanden; IP-043/044 prüfen den getrennten ASGI-Dienst, IP-045 den isolierten Browsercontroller. Tatsächliche Next-/physische Geräteabnahme, Betriebsschlüssel und öffentliche Aktivierung folgen; BL-020/021/025 |
| IP-034 | P0 / P1 | DONE | Dauerhafte Passkeyregistry und lokales Browser-Enrollment implementieren | Additive006, Einmalticket, FORCE RLS, Counter-/Versions-CAS, terminaler Widerruf/Audit und BFF-Enrollment; 528 Tests und48 HTTPS-Prüfpunkte grün, unabhängige Reviews, keine Actionfreigabe |
| IP-035 | P0 / P1 | DONE | Freigegebene HTTPS-Entwicklungsvorschau aktivieren | Nutzerfreigabe und beide DNS-Namen vorhanden; zwei gültige LE-Zertifikate, zwölf Helpertests und48 öffentliche HTTPS-/MFA-/Backtestprüfpunkte grün. Separate öffentliche Identität im bestehenden Entwicklungstenant; nur Edge80/443, Zertifikate nach Neustart erhalten. BL-026/Pilotabnahme bleiben offen |
| IP-036 | P0 / P1 | DONE | Dauerhaften zielgebundenen Passkey-Aktionsnachweis implementieren | Additive007, Claim vor Kryptoprüfung, Counter-/Versions-CAS und einmalige Vorschau-Bestätigung; 724 Prüfungen grün, unabhängige Reviews. Originale OIDC-Claims erhalten; Browseraktivierung und Credentialausführung bleiben separate Gates |
| IP-037 | P0 / P1 | DONE | Passkey-Prüfseite und vollständigen BFF-Ablauf integrieren | Gated Vorschau/Assertion/Bestätigung, positiver synthetischer BFF-Enrollmentablauf;265 Cockpittests,99 isolierte HTTPS/BFF/PG-Prüfpunkte,8 Vorbereitungstests, Typecheck/Build und Review grün. Öffentliche Aktivierung/physische Geräteabnahme separat; keine Credentialausführung |
| IP-038 | P0 / P1 | DONE | Getrennten Passkey-Credential-Assertionvertrag vorbereiten | Eigener Zweck-/Actor-/Sitzungs-/Ziel-/Bodyvertrag, originale OIDC-Zeit und frische Passkeyzeit getrennt;333 Cockpittests,77 Offline-Onboardingtests auch im gepinnten Container,109 Interopprüfpunkte, Typecheck/Build und Review grün. Dauerhafte Ausgabe/Consume und004-Integration folgen |
| IP-039 | P0 / P1 | DONE | Zweckgebundene Passkey-Credentialfreigabe dauerhaft ausstellen und konsumieren | Additive008 mit explizitem Zweck ab Vorbereitung, Consentreceipt, globalem Einmalverbrauch und separatem finalem Lock; privater Client.271 Credential-/461 API-Workertests und gepinnte Builds bestanden;008 nur Fixture-DB, keine HTTP-/Broker-/Runtimeaktivierung |
| IP-040 | P0 / P1 | DONE | Private Passkeyfreigabe mit Credentialmutation und Abschlussaudit verbinden | Merge389082a in Mainbe13145 verifiziert;008 Consume vor Probe,008 Lock+003 AEADwrite+009 Abschlussaudit gleiche finale TX.356 Credential-/461 API-Workertests und gepinnte Builds bestanden;009 nur Fixture-DB. HTTP, echte Schlüssel und öffentliche Aktivierung bleiben gesondert |
| IP-041 | P0 / P1 | DONE | Privaten Cockpit-Zweckablauf mit API und Credentialexecutor verbinden | Merge3476f74 in Main0fd25b6 verifiziert; standardmäßig deaktivierte008 API-Brücke und injizierter BFF-Ablauf mit ursprünglicher Session, expliziter Credentialzustimmung und exaktem Body.572 API-/385 Cockpittests,299 integrierte Prüfpunkte, Typecheck/Builds/Review grün; Browser-Keyannahme und öffentlicher Betrieb bleiben gesondert |
| IP-042 | P0 / P1 | DONE | Privaten Entwicklungs-HTTPS-Transport zum Credentialexecutor prüfen | Mergecd66c3a in Mainc573ab3 verifiziert; gegenseitiges TLS, eigene BFF-Zertifikatsbindung, unabhängiger Sitzungskontext und unveränderte Bodybytes; ausschließlich synthetische Fixture, 376 Credential-/440 Cockpittests,346 mTLS-Prüfpunkte und gepinnte Builds/Review grün; kein Produktionslauncher oder öffentlicher Keyeingang |
| IP-043 | P0 / P1 | DONE | Synthetischen Credentialdienst mit eigener DB-/Schlüsselidentität starten | Merge94fb73b in Main6300971 verifiziert; getrennte Runtime/Admincontainer, feste Fixture-DB/LOGIN, Startprüfung und synthetische Guard vor008-Verbrauch.401 Credential-/10 Vorbereitungstests,440 tatsächliche Dienstprüfpunkte und gepinnte Builds/Review bestanden; Produktionsserver/Schlüsselbetrieb und Browser-Keyannahme folgen |
| IP-044 | P0 / P1 | DONE | Isolierten Credentialdienst mit gepinntem ASGI-HTTP-Unterbau prüfen | Merge998bb90 in Main9f2a9a5 verifiziert; bestehende Uvicorn-/h11-Pins, mTLS vor Parser, Rawframing und getrennte Verbindungs-/Arbeitsslots.419 Credentialtests/52 Subtests,451 Dienstprüfpunkte und gepinnte Pythonbuilds/Review bestanden; nur synthetischer lokaler Dienst |
| IP-045 | P0 / P1 | DONE | Isolierten Browserablauf für Passkey-Credentialaktionen integrieren | Merge9555624 in Maindcb9feb verifiziert; begrenzte Fortsetzungen, Vorschau/Passkey/ausdrücklicher Consent und privater Seitenspeicher.540 Cockpittests,481 Controller-/HTTPS-/Dienstprüfpunkte,6 tatsächliche gesperrte Next-Routenchecks,460 bestehende Dienstprüfpunkte und gepinnte Builds/Review grün. Next-Betriebsprovider/physische Abnahme und öffentliche Aktivierung bleiben separat |
| IP-046 | P1 / P2–P3 | DONE | Mehrjährige BTC/ETH-Forschung und echte lange Cockpitbacktests bereitstellen | Merge0a0751b in Main073c474 verifiziert; je8766 Quellkerzen,6576 Forschung/2190 reservierter Holdout.66 gepinnte Coretests/33 Subtests,5 Metadatenfälle,572 API-/Workerfälle,je48 reale HTTPS-Prüfpunkte,exakter Replay und null Holdoutjobs; Review grün, keine Migration/Serviceaktivierung |
| IP-047 | P1 / P3–P4 | IN_PROGRESS | Persistenten Crypto-Paperablauf mit Risk Gate und Journal umsetzen | Nutzerpriorität Trading; IP-012/046. Derselbe Strategiekern, getrennte simulierte Konten/Orders/Fills, geschlossene H4-Signale, Crash/Replay ohne Doppelfill und sichtbarer Paperstatus; keine privaten Brokerkeys oder Echtgeld |
| IP-048 | P1 / P3–P4 | DONE | Schrittweisen wiederherstellbaren Paperkern mit Journalvertrag ergänzen | Mainmergeeb62176/dd1903b geprüft;14 neue Runnerfälle,84 gepinnte gezielte Tests/48 Subtests. Frische spätere Quotes, keine doppelten Fills/automatischen manuellen Einstiege. PostgreSQL-Writer und laufender Feed/Cockpit bleiben IP-047 |
| IP-049 | P1 / P3–P4 | DONE | Paperzustand und Journal atomar in PostgreSQL speichern | Mergefe6309a in Maindc60c19 verifiziert; eigene SESSION_USER-Kontobindung, CAS und gemeinsamer Commit/Readback.78 gepinnte Tests/15 Subtests,29 tatsächliche PG-Fälle und Review grün;010 nur Fixture-DB. Feedworker/Cockpit bleiben IP-047 |
| IP-050 | P1 / P3–P4 | DONE | Öffentlichen Spotfeed und begrenzten Paperworker verbinden | Mergee0cfb45 in Main1a805e5 verifiziert; BTC/ETH-H4 plus echte Bid/Ask, persistierte Zyklen82/84/86 und Neustart88.151 Tests/48 Subtests,30 echte PG-Fälle; begrenzte Fixtureabnahme/Review grün. Tageswechsel/Dauerbetrieb und Cockpit bleiben IP-047 |
| IP-051 | P1 / P3–P4 | DONE | Tenantgebundenen Paperstatus und Journal im Cockpit bereitstellen | Mergeaf65c51 in Mainb9d4b41 verifiziert; lesende011/API und default-off Panel.170 gezielte Tests/48 Subtests inkl37 echte PG/API,16 Cockpit-Vertrags-/SSR-Fälle, Typecheck/Build/Review grün.011 nur Fixture; Q32/Tageswechsel/Dauerbetrieb/Anzeigeaktivierung bleiben offen |
| IP-052 | P1 / P3–P4 | DONE | Freigegebene H4-Mitternachtsbasis vor Paperfills speichern | Merge05ea009 in Main5d5c61e verifiziert; Q32 bestätigt. Eigener Tagesinput/Beleg/CAS, RSI unverändert.190 unterschiedliche gezielte Fälle/48 Subtests inkl43 PG/API,17 Cockpitfälle/Typecheck/Review grün.012 nur Fixture; Dauerbetrieb/Anzeigeaktivierung bleiben IP-047/BL-028 |
| IP-053 | P1 / P3–P4 | DONE | Stabile lokale Paperidentität und begrenzten Beobachtungsdienst ergänzen | Mergec1703c1 in Maina996bf2 verifiziert; Fixture-LOGIN/Manifest/Singleton,24h-Zyklusstartbudget/sechs Fehler/Unknowncommit terminal.44 Workerfälle/3 Dateischutztests und echte Drift-/TLS-/Sessionabnahme grün. Feed82/84/86/Neustart88 ohne Fills; lokaler Dienst gesund. Nutzer-/Anzeigeintegration und längerfristiger Betrieb bleiben IP-047/BL-028 |
| IP-054 | P1 / P3–P4 | DONE | Eigenen gespeicherten Paperstand in der Entwicklungsvorschau anzeigen | Merge03fee1e in Mainb0827ba verifiziert; normales012 nach zurückgerolltem Preflight, stabile eigene Paperidentität/ein begrenzter Kurslauf82 ohne Fills.34 Python/5 stdlib/17 Cockpit/29 HTTPS-MFA grün, Builds/Review. Lesende Anzeige aktiv, sensitive Routen503; laufender Previewworker/Betrieb bleiben IP-047/BL-028 |
| IP-055 | P1 / P3 | IN_PROGRESS | Gemeinsamen Multi-Basket-Researchlauf vorbereiten | Q33/Q34:3–5 Coins, volle Planung, bindende6%/8%; gleiche Slots/1% Reserve/Stressprofil bestätigt. IP-056 Baseline, IP-057 Allokator, IP-058 Nachkaufadapter. Coins und feste Wiederbelegung erfragt; Historiendaten/Metadaten, Zyklusvertrag und eingefrorener größerer Lauf offen. [Plan](../multi-basket-ai-plan.md) |
| IP-056 | P1 / P3 | DONE | Gemeinsame deterministische BTC-/ETH-Referenz und Kapitaldiagnose ergänzen | Mainef18d74 enthält9455bfe; separater Offlinekern, atomare H4-Batches/Tagesbasis und passive kostenvergleichbare Referenz.65 gepinnte Fälle/26 Subtests, vier Inputguards und Ergebnisreplay/Review grün. Reale Forschungnet228,72 USDT, zeitgewichtetes Kaufprincipal72,56. Erweiterter Allokator bleibt IP-055. [Vertrag](../portfolio-reference.md) |
| IP-057 | P1 / P3 | DONE | Prüffähigen Offlinevorschlag für größere Slots und Kaufreservierung ergänzen | 698146f in Main3bb0d0c verifiziert; gleiche3–5 Slots, Kostenreserve, gebundene immutable Views/Revision und Kauf-/Cash-/Budget-/Stressdiagnose.85 gepinnte Fälle/65 Subtests,81 Hostfälle und Review grün. Profilentscheidung/Coins und Researchadapter bleiben IP-055. [Vorschlag](../portfolio-allocation.md) |
| IP-058 | P1 / P3 | DONE | Bestätigtes Forschungsprofil mit vorhandener RSI-Nachkaufstaffel verbinden | d31dcf3 in Main1f44b7f verifiziert; eigene Researchversion, vollständige Staffel, Lifetime-Fillkosten und Allokation vor Intent/Dispatch.97 gepinnte Fälle/65 Subtests,93 Hostfälle;12 Adapterfälle nach manueller Fillergänzung erneut grün. Review ohne Blocker; bisher nur synthetische Zyklen, Marktassets/Wiederbelegung/Leistungslauf offen. [Vertrag](../staged-portfolio-research.md) |
| IP-059 | P1 / P3 | DONE | Öffentliche Verfügbarkeit und Instrumentregeln der vorgeschlagenen Coins prüfen | 4f56024 in Main7ec9b41 verifiziert; fünf echte Spot-Metadatenantworten und zehn H4-Kerzen am Forschungsbeginn geprüft, Record/JSON konsistent. ETH-Mindestmenge separat zu modellieren. Coinauswahl/Wiederbelegung weiter offen; kein vollständiger Dreijahres- oder Leistungsnachweis. [Vorcheck](../portfolio-history-preflight.md) |

## Abschlussbelege

IP-058:97 unterschiedliche gezielte gepinnte Fälle/65 Subtests (93 Trading/
Paper, vier Worker) und93 Hostfälle grün. Zwölf neue Adapterfälle anschließend
auf Host und gepinnt nochmals mit tatsächlichem manuellem Fill/Ledger geprüft.
Unabhängiger fokussierter Review ohne Blocker. Alle fünf regulären Stufen
senken im kontrollierten Test mit vorhandenem synthetischem Gewinn den
Durchschnitt; konkurrierende Reservierungen können Nachkauf sperren.
Keine neue Rendite-/Holdout-/Browser-/Brokerabnahme oder Runtimeänderung.

IP-057:85 gezielte gepinnte Fälle/65 Subtests (81 Trading/Paper, vier Worker),
81 Hostfälle und unabhängiger gezielter Abschlussreview ohne Blocker.
20 neue Allokationsfälle einschließlich Reviewkorrekturen; keine DB-/Broker-/
Holdout-/Runtimeänderung. Größeres Profil vor Integration ausdrücklich erfragt;
vorhandene gefrorene Baseline-/Leistungsbelege bleiben unverändert.

IP-056:65 gezielte gepinnte Fälle/26 Subtests (61 Trading/Paper und vier
Worker-Compute), vier Host-Inputguards; 16 neue Batch-/Portfoliotests und
vier neue Protokollguards. Reale Forschungsreplays exakt gegen gespeicherte
Netto-/Kapital-/Benchmarkkennzahlen und Digests. Abschlussreview ohne Blocker,
Syntax/JSON/Dokumentlinks/Diff geprüft. Kein DB-/Holdout-/Brokerzugriff oder
öffentlicher Containerwechsel; ursprüngliche gefrorene Jobs unverändert.

IP-054:34 gepinnte gezielte Pythonfälle, fünf stdlib-Provisionierungsfälle,
17 Cockpit-Vertrags-/SSR-Fälle, gepinnte Builds/Review und29 echte HTTPS-/OIDC-/
MFA-/BFF-Prüfpunkte bestanden.008–012 vollständig zurückgerollt mit eigenen/
fremden/revokten/alten Epoch-/OIDC-Kontexten; danach atomar normal angewendet,
beide012-Hashes bestätigt. Neue feste eigene Kontobindung, vier Driftprobes
zurückgerollt, TLS/Fixture-/Tabellensperre und Readback geprüft. Reale Revision82
ohne Fills; eigener Stand auf Übersicht/Portfolio/Journal sichtbar. Nur API/
Cockpit neu erstellt; andere Dienste/Fixtureruntime gesund, sensitive Flags
und Routen gesperrt. Kein dauerhafter Previewworker/Profitabilitätsbeleg.
[Bedienung und Rückfall](../paper-preview-integration.md).

IP-053:44 gezielte gepinnte Runtime-/Workerfälle und drei stdlib-Dateischutztests
bestanden. Wiederholte Provisionierung erhält IDs/Dateien/Zeilenzahlen; vier echte
Driftprobes zurückgerollt. Eigener TLS-LOGIN, Doppelstart, Sessionverlust/-freigabe,
normale DB verweigert und Readback geprüft. Feed82/84/86, neuer Prozess88 ohne
Fills; gleicher RSI/Q32-Kern. Lokaler Dienst gesund, Doppelprozess abgewiesen,
Neustart nach100 fortgesetzt102+. Scoped Review ohne Blocker. Keine neue
Dependency/Migration/Build, normal007/Fixture012/Ledger bestätigt; öffentliche
Dienste unverändert/gesund/TLS200. Max24h für neue Zyklusstarts, restart:no.
[Bedienung/Grenzen](../paper-development-runtime.md).

IP-052: Q32 ausdrücklich bestätigt; H4-Modellbasis vor Quotes/Verkäufen
gespeichert, RSI-Zustand/6%/8%/gelatchte Halts unverändert.
190 unterschiedliche Python-/PG-Fälle/48 Subtests grün (43 tatsächliche PG/API);
Vollauf189 grün, fehlerhafte OHLC-Testdaten korrigiert und betroffener
Neustart-/CLI-Lauf3 grün.17 Cockpit-Vertrags-/SSR-Fälle, Typecheck und gepinnter
Cockpitbuild grün. Normal007/Fixture012/alle Ledgerprüfsummen bestätigt;
öffentliche Dienste unverändert/gesund, Cockpit TLS200.
012 nach vollständig zurückgerolltem tatsächlichem Writer-/Replaypreflight
und unabhängigem Review nur Fixture angewendet. Keine neuen Dependencies,
keine normale Migration oder öffentliche Aktivierung. Dauerbetrieb bleibt
bis Betriebsabnahme begrenzt. [Vertrag](../paper-midnight-basis.md).

IP-051:170 gepinnte gezielte Tests/48 Subtests, davon37 tatsächliche
PostgreSQL-/API-Fälle;16 Cockpit-Vertrags-/SSR-Paneltests, Typecheck und
gepinnter Cockpitbuild bestanden. Eigener/fremder Tenant, entzogene
Mitgliedschaft, Replay und fehlender Kontext geprüft; Runtime ohne
Tabellen-/Writerrechte. Review ohne Blocker.011 nach vollständig
zurückgerolltem Preflight ausschließlich Fixture-DB; normal007/Fixture011
und sämtliche Ledgerprüfsummen verifiziert. Keine neuen Dependencies;
keine breite Credential-/HTTP-Wiederholung. Öffentliche Container
unverändert/gesund, Cockpit TLS200. Beide Anzeigeflags ausgeschaltet.
Q32 zur Preisbasis der Mitternachtsbewertung offen; Risikoregeln unverändert.
[Vertrag und verbleibende Gates](../paper-status-readmodel.md).

IP-050:151 gepinnte Tests/48 Subtests,30 echte PostgreSQL-Fälle bestanden.
Öffentlicher Feedcheck je40 geschlossene H4 und frische echte Quotes.
Isolierter Worker committed drei Zyklen82/84/86, Prozessneustart88;
keine historischen Fills. Synthetischer Signal-/Fill-/Restartfall über
Feedparser/SQL erzeugt genau einen Fill. Review grün für begrenzte Abnahme.
CLI sperrt Dauerbetrieb bis sichere Tagesbaseline geklärt ist.
Keine Migration/Build/Dependency, normal007/Fixture010 unverändert.
Alle Einmalcontainer beendet, bestehende Dienste/Cockpit TLS200.
[Vertrag und verbleibende Betriebsgates](../paper-market-worker.md).

IP-049:78 gezielte gepinnte Tests/15 Subtests bestanden, davon29 tatsächliche
PostgreSQL-Fälle. Konkurrenz, atomarer Rollback, verlorene Commitantwort und
Restart mit genau einem simulierten Fill geprüft; Review ohne Blocker.
010 nach vollständig zurückgerolltem Preflight nur Fixture-DB angewendet:
normal007/Fixture010 und sämtliche Ledgerprüfsummen geprüft.
HBA nur um Fixture-TLS/SCRAM ergänzt und PostgreSQL-Konfiguration neu geladen.
Öffentliche Dienste nicht neu erstellt, Cockpit TLS/HTTP200. Keine neue
Dependency/Build oder breite HTTP-/Credentialregression.
[Vertrag und nächste Feed-/Cockpitintegration](../paper-postgres-store.md).

IP-048:84 gezielte gepinnte Trading-/Marktdata-/Workerberechnungstests mit
48 Subtests bestanden. Paper-Snapshot-Restore und Journaleintrag geprüft;
PostgreSQL-Writer/Feed/Cockpit bleiben IP-047. Kein neuer Dienst/DB-Grant/
Migration oder Imagebuild; kein breiter Auth-/Credential-Regressionslauf.
[Vertrag und genaue Grenzen](../paper-runner.md).

IP-046: je drei Jahre BTC/ETH-H4 im echten Cockpit-/Workerpfad und ein
separat reserviertes Jahr.66 gepinnte Coretests/33 Subtests, fünf Metadaten-
Fixturetests,572 API-/Workerfälle und je48 tatsächliche HTTPS-Prüfpunkte grün.
Deterministischer Replay reproduziert beide repräsentativen Nettowerte exakt;
Read-only-Audit bestätigt null Holdoutjobs/keinen importierten Vollquellensatz.
Review ohne Blocker. Keine Migration/öffentliche Dienstneuerstellung;
normal007/Fixture009 unverändert, beide TLS-Einstiege HTTP200.
[Protokoll, Ergebnisse und Grenzen](../long-history-backtests.md).

IP-045:540 Cockpittests mit100 neuen Fällen, Typecheck und gepinnte Cockpit-/
Nodebuilds bestanden.481 synthetische Controller-/HTTPS-/Dienstprüfpunkte und
sechs tatsächliche gesperrte Next-Routenchecks grün; bestehender Dienstablauf
mit460 Prüfpunkten erneut bestanden. Überlappende Prüfläufe nicht addieren.
Review ohne Restblocker. Keine Migration/Dependency/öffentliche Aktivierung;
normal007/Fixture009-Prüfsummen unverändert, Testcontainer beendet,
öffentliche sechs Dienste gesund und reguläres TLS HTTP200.
[Browservertrag und genaue Belege](../credential-browser-flow.md).

IP-044:419 gepinnte Credentialtests/52 Subtests und451 tatsächliche
Prüfpunkte im getrennten mTLS-Dienstablauf bestanden. 18 neue TLS-/ASGI-Fälle
prüfen Handshake, Rawframing, absolute Fristen und die getrennte Begrenzung
laufender Arbeit nach Disconnect. Beide Pythonbuilds und unabhängiger Review
grün. Keine neue Migration oder öffentliche Aktivierung; aktuelle Prüfsummen
normal007/Fixture009 stimmen überein, Testcontainer beendet, öffentliche
Dienste unverändert/gesund und Cockpit/Auth mit regulärem TLS HTTP200.
[ASGI-Vertrag und genaue Belege](../credential-asgi-transport.md).

IP-043:401 gepinnte Credentialtests mit52 Subtests, zehn Host-
Vorbereitungstests und440 integrierte Prüfpunkte im getrennten
Credentialdienst bestanden. Image ohne Entwicklungsoption beendet sich
vor dem Netzwerkstart. Unabhängiger Review ohne offene Blocker.
[Dienstgrenze und Betrieb](../credential-development-service.md).
Der bestehende injizierte HTTPS-Ablauf387 und Pipeablauf329 Prüfpunkte erneut bestanden;
überlappende Integrationsläufe nicht addieren. Alle gespeicherten
Migrationsprüfsummen normal007/Fixture009 stimmen mit den SQL-Dateien überein.
Fixturecontainer beendet, sechs öffentliche Dienste unverändert und beide
Domains mit regulärem TLS HTTP200.

Nutzerhinweis2026-11-08 zu kurzen Bitcoin-Backtests ist mit IP-046 praktisch
adressiert: je drei Jahre BTC/ETH und reservierter Jahres-Holdout. Der alte
90-Tage-Snapshot bleibt Funktionsnachweis. Kostenkalibrierung, eingefrorene
Auswahl und wirtschaftliche Holdoutabnahme bleiben IP-013/BL-018 offen.

IP-042:376 gepinnte Credentialtests,440 Cockpittests/Typecheck und346 reale
mTLS-/WebAuthn-/HTTPS-/API-/PG-/AEAD-Prüfpunkte bestanden. Pipevariante306
erneut geprüft; überlappende Läufe nicht addieren. Frühere572 API-/Workerfälle
nicht neu gezählt. Unabhängiger Review ohne verbleibenden Blocker;003–009
unverändert. [Vertrag und Grenzen](../passkey-credential-https.md).

- **IP-001:** [inventory.md](../inventory.md), [sources.md](../sources.md);
  Auftrag und beide lokalen Skills vollständig gelesen, Referenzrepos unverändert.
- **IP-002:** [interview.md](../interview.md) ist die alleinige Übersicht der
  bestätigten und noch offenen Nutzerentscheidungen.
- **IP-004:** `git rm --cached` entfernt den Credentialpfad aus dem Index,
  die lokale Datei bleibt erhalten und ist ignoriert. Inhalte wurden nicht gelesen.
  Historien-/Rotationsarbeit bleibt IP-005.
- **IP-003:** 28 Projekt-Markdown-Dateien und 23 Tickets geprüft:
  keine defekten lokalen Links oder unbekannten Ticketreferenzen.
  Basketanteile, Durchschnitt, +5%-Marke und −50%-Stress unabhängig nachgerechnet.
  Architektur-/Tradingreview eingearbeitet; `git diff --check` sauber.
  Lokaler Planungsbranch: `docs/project-foundation`.
- **IP-006, 2026-11-07:** [deployment-plan.md](../deployment-plan.md)
  konkretisiert Compose/Authelia. Offizieller Quellenabgleich und Architekturreview
  ohne weitere Befunde; keine Installation oder Laufzeitabnahme.
  Aktueller Check: 32 Projekt-Markdown-Dateien inklusive Agentpointer,
  keine defekten Links/Ticketreferenzen; damaliger Stand Q9–Q14 bestätigt,
  Q15–Q22 offen, inzwischen durch Runde 4 beantwortet.
- **Runde 4, 2026-11-07:** Signale/Schutz und Risikoprofile übernommen;
  Notfallreserve, öffentlicher HTTPS-Pilot und E-Mail-Recoverypräferenz ausdrücklich
  als Abweichungen dokumentiert. Offizieller Authelia-Abgleich: administrative
  Faktorresets möglich, Mail-only-Selbstservice/Logout nicht pauschal zusagen.
  Q23–Q28 bleiben Vorschläge; keine Dienste, Orders oder Nachrichten ausgeführt.
  Architektur-/Tradingreview eingearbeitet; 32 Markdown-Dateien/23 Tickets ohne
  defekte Links/Referenzen. Antwortstatus und Notfallbudget-/Stress-/Cashvergleich
  unabhängig geprüft, `git diff --check` sauber.
- **Runde 5, 2026-11-07:** Q23 ersetzt automatischen Puffer durch manuellen
  Einstieg mit Nutzerinformation. Q24/Q26–Q28 bestätigt, Q25 Heimnetzhost
  laut Nutzer; [mt5-bridge.md](../mt5-bridge.md) konkretisiert ausgehendes HTTPS,
  Demo-/Gerätebindung und Fehlerszenarien. Q29/Q30 bleiben offen.
  Die bisherigen Offenstatus in den historischen Rundennotizen sind überholt.
- **Runde 6, 2026-11-07:** Q29/Q30 bestätigt. M1-Sachentscheidungen vollständig,
  [implementation-brief.md](../implementation-brief.md) bündelt den Reviewstand.
  Q31 Abschlussbestätigung ausstehend; keine Implementierung freigegeben.
  Architektur-/Tradingreview ohne weitere Befunde. 34 Markdown-Dateien/24
  eindeutige Tickets, lokale Links, Antwortstatus und Fünferstaffel-/Cashstress
  geprüft; `git diff --check` sauber. Keine Anwendungs-Laufzeitabnahme.

- **Runde 7 / IP-025, 2026-11-07:** Q31 und autonome lokale Umsetzung bestätigt.
  Branch `feat/m1-foundation`. Docker/Compose exakt gepinnt installiert;
  API/Cockpit mit Locks gebaut, Migration/IdP-Provisionierung ausgeführt.
  Alle fünf Dienste laufen; Anwendungsgesundheit geprüft und ausschließlich
  `127.0.0.1:8443` veröffentlicht. Momentaufnahme nach Login: rund 408 MiB
  Container-RAM insgesamt, keine Last-/Produktionsabnahme.
  31 Crypto-, 39 API-/echte PG-Isolations- und 12 Cockpit-Sicherheitstests
  bestanden. 28 zusätzliche reale HTTPS-Prüfpunkte einschließlich
  Passwort/TOTP, frischem OIDC, BFF/Mandant, Callback-Replay, CSRF,
  idempotenter Jobannahme und Logout bestanden.
  Unabhängige Architektur-/Tradingreviews eingearbeitet. Lokale Tests erzeugen
  ausschließlich `.invalid`-Identität; Erstregistrierung/Recovery bleiben offen.
  [Startanleitung](../../infra/README.md), [Tests](../../tests/README.md).
  Queued bedeutet persistiert, nicht verarbeitet; Worker/Daten/Broker fehlen.
  Foundationcommit `5fe3a2e` auf GitHub-Branch `feat/m1-foundation` gesichert.
  Zwischenstand-Pushes ausdrücklich autorisiert; Remote-Historie vor Push
  abgeglichen. Credential-Historienarbeit bleibt IP-005, kein Force-Push.

- **IP-026, 2026-11-07:** Öffentlicher Bitget-V3-SPOT-Import für
  2026-08-09 08:00 bis 2026-11-07 08:00 UTC: 540 abgeschlossene H4-Kerzen,
  ohne Lücken im gewählten Fenster. Dataset immutable, Daten-/Contenthash
  getrennt; Job friert Strategie und Kosten bei Annahme ein.
  Eigener Researchworker mit `SESSION_USER`-Tenantbindung, begrenzten
  DB-Funktionen und Lease/Attempttoken; Testfixtures nutzen eine separate Rolle.
  Migration 002 angewendet, 001 unverändert. Broker- und BFF-Secrets bleiben
  unerreichbar. Sechs lokale Dienste geprüft, nur `127.0.0.1:8443` veröffentlicht.
  31 Trading-, 20 Marktdaten-, 56 API-/Worker-, 21 Cockpit- und 4
  Provisionierungstests bestanden; Typecheck und gepinnte Containerbuilds grün.
  32 reale HTTPS-Prüfpunkte umfassen MFA, Datasetwahl, idempotente Annahme,
  tatsächliche Berechnung, persistierten Datenhash und Equitydarstellung.
  Ergebnis bleibt ausdrücklich nicht wirtschaftlich validiert; Dreijahresziel,
  Kostenkalibrierung und unabhängiger Holdout nicht erfüllt.
  Implementierungscommit `3a73c12` auf `origin/feat/m1-foundation` gepusht.
  [Startanleitung](../../infra/README.md), [Tests](../../tests/README.md).

- **IP-027, 2026-11-07:** [Verbindungsplan](../bitget-connection.md) und
  [Classic-Readadapter](../../integrations/bitget/README.md) umgesetzt.
  Ausschließlich drei signierte GET-Pfade, TLS ohne Redirect/Umgebungsproxy,
  begrenzte Antworten, statische redigierte Fehler und getrennte Walletmodelle.
  Kontoinfoprobe lernt UID; Walletzugriff verlangt feste Nutzer-/UID-/Parentbindung,
  bekannte Leserechte und erwartete IP in der gemeldeten Whitelist.
  24 Offline-Tests bestanden, unabhängiger Review ohne kritische Restbefunde.
  Keine neuen Abhängigkeiten, echten Nutzerkeys oder Brokeraufrufe.
  Vault, tatsächliche Egress-/Kontoabnahme, atomare DB-Bindung, globale UID-Quota
  und API-/Cockpiteinbindung bleiben IP-009/IP-015.
  Implementierungscommit `3052560` auf `origin/feat/m1-foundation` gepusht;
  Nutzer hat die Zwischenabnahme ausdrücklich akzeptiert und übernimmt den
  Merge in den Hauptbranch selbst. Keine Produktions-/Echtgeldfreigabe.

- **IP-028, 2026-11-07:** [Credentialkern](../../packages/credentials/README.md)
  implementiert. Versionierte AES-256-GCM-Envelopes mit zufälligen DEKs,
  getrennten Payload-/Wrap-AAD-Domänen und authentifizierter Tenant-/Nutzer-/
  Konto-/UID-/Profil-/Revisionsbindung. KEK-Rewrap authentifiziert beide
  bestehenden AEAD-Schichten; ursprüngliche Ciphertexte bleiben unverändert.
  20 Tests mit erfundenen Schlüsseln bestanden, einschließlich Referenzvektor,
  Manipulationsabwehr, Rotation und lokaler Wiederherstellung.
  Unabhängiger Review ohne verbleibende Blocker. Offizielle Version-/Wheelhashpins;
  tatsächlicher Python-3.14.10-Checkcontainer Nonroot, ohne Netzwerk/Secrets,
  schreibgeschütztes Rootdateisystem und keine Capabilities.
  API-/Researchlocks und angewendete Migrationen unverändert.
  Kein Vaultdienst, Runtime-Schlüsselprovider, DB/API/UI oder echte Keyannahme.
  Root-of-Trust, Serviceidentitäten, Revisions-/Usagegates und externer Restore
  bleiben IP-009/BL-022. Hauptbranchmerge bis `3fd95b1` verifiziert;
  neue Arbeit auf `feat/m1-credential-envelope`.

**IP-029, 2026-11-07:** Hauptbranch enthält `7f83b33`, verifiziert bei
`71e57f1`; neuer Branch `feat/m1-credential-storage`. Migration003 ergänzt
private FORCE-RLS-Tabellen und feste Security-Definer-Funktionen, tatsächliche
SESSION_USER-Tenant-/Userbindung und aktive owner/trader-Gates. API und Research
haben keinen Credentialzugriff. Pythonstore verwendet aktuelle persistierte
AEAD-Bindung, CAS für Credential-/Speicherversion, authentifizierte Rotation und
terminalen Widerruf; pausiertes Konto und fehlender alter KEK verhindern
den schützenden Widerruf nicht.
37 Tests im gepinnten Python3.14.10-/PG18.6-Prüfablauf bestanden, zusätzlich vier
Provisionierungstests und eine erfolgreiche SQLSTATE42501-Driftprobe mit Baseline
und überprüftem Rollback. Unabhängiger Architekturreview eingearbeitet.
003 ausschließlich in `investalo_credentials_checks` angewendet;001/002
unverändert, gewöhnliche Entwicklungsdatenbank bleibt002. Checkprofil ist bewusst
administrativ und enthält die Migrationsidentität. Keine echte Keyannahme,
Schlüsselprovider, HTTP/UI oder Brokerkontakte.
Anleitung: [Credentialstore](../../services/credentials/README.md),
[Fixtureprüfung](../../infra/README.md).

**IP-030, 2026-11-07:** Hauptbranch enthält Storecheckpoint `46860ab`,
verifiziert bei `b3030de`; neuer Branch `feat/m1-bitget-onboarding`.
Private Einrichtung verbindet Classic-Probe und kanonisches Triple mit dem
gebundenen AEAD-Store. Gesonderte Assertion bindet Aktion/POST-Ziel/Bodyhash,
frische Authzeit ab Schrittstart und aktuelle Identität. Migration004 konsumiert
JTI vor der Probe; aktueller Actor/Epoch/Reauth/Konto/Zeit/Versionen und
transaktionsgebundener Write-/Auditabschluss werden erneut geprüft.
Keywechsel hält UID/Parent fest, Widerruf benötigt keine Probe oder alten KEK.
Expliziter Entwicklungsdateiprovider hält KEK-ID/Material mit festen Fingerprints
über Neustarts stabil und prüft Dateityp/Eigentümer/Modi.

120 Tests im gepinnten Python3.14.10-/PG18.6-Ablauf bestanden: 19 Client,
41 Onboarding-Offline, 60 tatsächliche PG-Fälle (18 Store, 30 Autorisierung,
12 synthetische Bitget-/AEAD-Flows). Replay, Sperrwartezeiten/Expiry, Epoch,
Brokeridentität/-rechte/IP, CAS und atomarer Rollback geprüft; unabhängige
Python-/SQL-/Dokumentationsreviews ohne Restblocker. Keine Brokerkontakte
oder echten Nutzerkeys. 001/002/003 unverändert; 004 ausschließlich Fixture-DB,
gewöhnliche Entwicklungsdatenbank nachweislich weiter 002. Migrationschecksummen
und Composekonfiguration geprüft. 40 Projekt-Markdown-Dateien: lokale Links und
54 Ticket-IDs gültig; `git diff --check` sauber.
SQL vertraut der Python-Signaturprüfung; direkte 003-Funktionen sind Server-
primitiven ohne universelle MFA-Garantie. Echter HTTP/BFF-MFA-Schrittflow,
Signaturidentität, CSRF und Betriebsschlüsselprovider bleiben IP-009/BL-021/022.
Retention-/Crash-/Commitausgangabgleich folgt BL-024.
Anleitung: [Credentialstore](../../services/credentials/README.md).

**IP-031/IP-032, 2026-11-07:** Onboardingmerge69a1f8b auf main56070ba
verifiziert; Branch `feat/m1-credential-step-up`. Additive005 veröffentlicht
nur aktuelle autorisierte eigene Konto-/Verbindungsmetadaten. Keine UID-/Parent-/
Envelope-/KEK-Abfrage; andere Tenantnutzer können keine fremde Verbindung als
freien Registrierungsslot sehen. Alle001–005 jetzt in beiden lokalen DBs
angewendet, Prüfsummen/idempotenter Lauf geprüft; vorherige SQL-Dateien unverändert.

Vorbereitete Actionzustände binden Session/CSRF/Actor/Tenant/Epoch/frozenTarget/
CAS und eigenen Previewtoken. Der unabhängige Review stellte fest:
Authelia-Reauth erhält alte MFA; normaler Login ist keine frische
Zweitfaktorfreigabe. Sensitive Server und UI bleiben geschlossen, auch mit
gültiger Sitzung/CSRF. Nutzer bestätigt zusätzlichen Cockpit-Passkey; dessen
isolierter Verifier mit exakt gepinnter Standardbibliothek ist umgesetzt.
Dauerhafte Registrierung/Counter-CAS/Widerruf/Audit, einmalige gebundene
Challenges und Browser-/Gerätetest folgen IP-033.

310 automatisierte Prüfungen bestanden:112 API/Worker,120 Credentialregression,
78 Cockpit einschließlich19 echten synthetischen P256-Passkeyfällen.
Typecheck, gepinnte Builds und40 tatsächliche HTTPS-Prüfpunkte grün.
Letztere bestätigen normalen Login/CSRF/Replay/Research/Logout, gesperrte
Credentialrouten und Reauth-Wiederverwendung des alten Faktors.
Sechs lokale Dienste gesund, nur127.0.0.1:8443 veröffentlicht.
Keine echte Keyannahme, Brokerkontakte oder öffentliche/Produktionsänderung.
Entwurf und verbleibende Gates: [Passkeys](../passkey-step-up.md).

**IP-034, 2026-11-07:** Hauptbranch enthält Schrittflowcheckpoint `d57bd56`,
verifiziert bei `b6198f7`; Branch `feat/m1-passkey-registry`.
Additive006 speichert gebundene Publickeys, Counter, Backupzustand, Versionen
und Audit unter FORCE RLS. Administrativ E-Mail-bestätigtes Einmalticket,
committed Claim vor Kryptoprüfung und einmaliger session-/CSRF-/Actor-/Epoch-/
RP-gebundener BFF-Versuch. Widerruf erhöht die globale Nutzerepoch und sperrt
alle Tenant-Sitzungen; terminaler Ersatz-/Recoveryweg bleibt BL-025.

528 automatisierte Tests bestanden:293 API/Worker einschließlich67 echter
Registry-/API-PG-Fälle,120 Credentialregressionen und115 Cockpitprüfungen.
Typecheck, gepinnte Builds, Migrationsprüfsummen/idempotente Läufe in beiden DBs
und48 tatsächliche HTTPS-Prüfpunkte grün. Zwei unabhängige Reviews ohne
Restblocker. Sechs lokale Dienste gesund; nur127.0.0.1:8443 veröffentlicht.
001–006 jetzt in beiden DBs angewendet und immutable.

`fmt=none`-Registrierung bleibt Kandidat ohne privaten Besitznachweis.
SQL-Counter-CAS ist kein Challenge-Replayschutz; kein HTTP-CAS.
Erfolgreicher vollständiger BFF-Enrollmentablauf, echte Browser-/Geräteabnahme
und frische zielgebundene Assertions/Grants folgen IP-033.
Kontoänderungen bleiben gesperrt; keine echten Brokerkeys, Brokerkontakte,
E-Mails, öffentliche Bereitstellung oder Echtgeldaktionen.
Anleitung und Abnahmegrenzen: [Passkeys](../passkey-step-up.md).

## Zwischenabnahme: öffentliche Entwicklungsvorschau

2026-11-07: Nutzer hat auth-DNS eingerichtet und die Vorschau ausdrücklich
freigegeben. Beide Domains zeigen auf5.45.96.83; gültige Let’s-Encrypt-
Zertifikate bis2027-02-05, HTTP308 und Zertifikatsvertrauen nach Proxyneustart
bestätigt. Nur Caddy veröffentlicht80/443; eingeschränkte Containerrechte bleiben.

Öffentliche Issueridentität als weiterer Owner im konkret ermittelten vorhandenen
Entwicklungstenant provisioniert. Lesende Prüfung bestätigt ursprünglichen Nutzer,
geteilte Mitgliedschaft, unveränderte Researchworkerbindung und vorhandene Datasets.
Zwölf Helpertests und48 tatsächliche öffentliche HTTPS-Prüfpunkte bestanden,
einschließlich TOTP/OIDC, Workerberechnung, Nettobericht/SVG und Logout.
Unabhängiger Abschlussreview ohne Blocker. Keine Broker- oder Echtgeldfreigabe;
IP-033 und BL-026 bleiben nächste Arbeitsbereiche.
[Zugang und Betrieb](../https-entry.md).

## Zwischenabnahme: interner Passkey-Aktionsnachweis

2026-11-07: HTTPS-Checkpoint `35960f3` ist in Main `e741c6b` gemerged;
Nutzer bestätigt Browserlogin und Google Authenticator und beauftragt Fortsetzung.
Branch `feat/m1-passkey-action-proof` ergänzt den dauerhaften Nachweis007:
konkrete Kontoaktion, eingefrorene Metadaten/CAS, aktuelle Faktorversion,
Sitzung/CSRF/Origin, originale OIDC-Zeit und eigene Vorschaukennung.
Claim wird vor Kryptoprüfung committed; Counter und Grant entstehen atomar,
Bestätigung verbraucht genau den eigenen Grant einmal.

724 Tests bestanden: 461 API/Worker einschließlich 70 neuer tatsächlicher
PG-Fälle, 143 Cockpit einschließlich 28 neuer synthetischer P256-Abläufe und
120 Credentialregressionen. Reviews von SQL, API und BFF ohne Restblocker.
Die drei vorhandenen Auth-Zeittests berechnen ihre Zukunftsgrenzen jetzt beim
Testaufruf, damit längere Suiten deren Aussage erhalten.
Browserrouten für Kontoänderungen, reale Keyannahme und003/004-Ausführung
bleiben gesperrt. Vollständiges BFF-Enrollment und reale Geräteabnahme folgen
IP-033. [Ablauf und Prüfbelege](../passkey-action-proofs.md).

## Zwischenabnahme: Passkey-Prüfseite und vollständiger BFF-Durchlauf

2026-11-08: Aktionsnachweis `9b47ae1` und Abnahmenotiz `4c9f63f` sind in
Main `2c996d5` gemerged und verifiziert. Branch `feat/m1-passkey-browser-proof`
verbindet007 mit einer ausdrücklich aktivierbaren Prüfseite: Konto/Aktion
ansehen, frische Passkey-Assertion und die eigene Vorschau einmalig bestätigen.
Die HTTP-autorisierten Sitzung/CSRF bleiben bis zum Ergebnis unverändert
gebunden. Enrollment behält die ursprüngliche Sitzungsfrist und verlangt
nach Speicherung eine autoritative Faktorlesebestätigung.

265 Cockpittests, Typecheck und gepinnter Build bestanden.90 tatsächliche
isolierte HTTPS/BFF/API/PG-Prüfpunkte einschließlich vollständiger Einrichtung,
P256-Assertions, drei Aktionen, Replay und Konkurrenz sowie9 Prüfungen mit
deaktivierter Oberfläche sind grün. Acht Vorbereitungstests prüfen Dateirechte,
Symlinks/Hardlinks und ersetzte Elternpfade. Reviewhinweise zur Sitzungsbindung
und zur privilegierten Dateivorbereitung sind behoben; keine Restblocker.

Testdienste verwendeten eigene synthetische Schlüssel/Tickets und die
Fixture-DB, veröffentlichten keine Ports und sind angehalten.001–007 bleiben
unverändert; API-/Credentialregressionen aus IP-036 wurden nicht erneut gezählt.
Öffentliche Dienste unverändert und gesund, Cockpit mit regulärem TLS200.
Default und öffentliche Vorschau behalten die Prüfseite ausgeschaltet.
`execution_enabled:false`, alte Credentialrouten503, keine003/004-Ausführung.
Physisches Gerät, tatsächliche E-Mail-Attestierung, öffentliche Aktivierung,
Credentialintegration, Recovery und Betrieb bleiben offene Abnahmen.
[Ablauf und Grenzen](../passkey-browser-proof.md).

## Zwischenabnahme: isolierter Passkey-Credential-Assertionvertrag

2026-11-08: Checkpoint84f7633 in Main512c096 verifiziert; neuer Branch
`feat/m1-passkey-credential-handoff`. IP-038 bereitet einen eigenen Zweckvertrag
zwischen TS/Jose und Python vor. Originale OIDC-Zeit bleibt erhalten, frische
Passkey-/Autorisierungszeiten separat; Actor/Sitzung/Origin/RP/Ziel/CAS/
Metadatendigest und exakte Bodybytes gebunden. Alter Signer/Verifier/004
unverändert,007-Prüfbestätigung keine Credentialzustimmung.

333 Cockpittests,77 Offline-Onboardingtests auf Host und gepinntem
Python3.14.10,109 tatsächliche sprachübergreifende Offlineprüfpunkte,
Typecheck und gepinnter Cockpitbuild bestanden. Unabhängiger Review ohne
Restblocker. Optionales gehärtetes Testprofil ohne Netzwerk/Secrets/Mounts/
Ports/DB-Abhängigkeiten; bestehende sechs öffentliche Dienste unverändert/
gesund, TLS200, Nachweisflag off. Historische461/120/99 Suiten nicht erneut
ausgeführt.

Kein dauerhafter Aussteller/Einmalverbrauch oder HTTP-/Brokerexecutor.
Künftige additive Integration benötigt ausdrücklich bestätigte Zweckfreigabe,
globalen Consume vor Probe und erneute aktuelle Bindungsprüfung bei Annahme/
Write. Physische Abnahme, tatsächliche E-Mail, Recovery und Betrieb bleiben
IP-033 und eigene Gates. [Vertrag/Grenzen](../passkey-credential-assertions.md).

## Zwischenabnahme IP-039 — dauerhafte Credentialfreigabe

Merge8bb64db in Main13ba2e2 verifiziert; neuer Branch
`feat/m1-passkey-credential-authorization`. Zweck, Origin und Bodydigest
werden vor dem Passkeynachweis eingefroren. Explizite Zustimmung erzeugt ein
dauerhaftes Receipt; der private Client prüft die Signatur, konsumiert vor
einer künftigen Probe einmalig und prüft aktuelle Bindungen im finalen Lock.

271 Credentialtests (19 Client,95 Offline,157 tatsächliche PG;97 neue PG)
und461 API-/Workertests bestanden. Gepinnte Builds und unabhängiger Review
ohne Blocker.008 nach zurückgerollter DDL-/Runtime-Vorprüfung nur in der
Fixture-DB angewendet; investalo bleibt001–007. Sechs öffentliche Dienste
unverändert/gesund, reguläres TLS HTTPS200.

Kein HTTP-/Broker-/003/004-Executor verbunden. Physische Geräteabnahme,
öffentliche Aktivierung, echte E-Mail/Keyeingabe und abschließende Integration
bleiben eigene Gates. [Ablauf/Grenzen](../passkey-credential-authorizations.md).

## Zwischenabnahme IP-040 — private Credentialausführung

Merge `389082a` in Main `be13145` verifiziert; Branch
`feat/m1-passkey-credential-execution`. Der private Executor verbindet committed
008-Consume vor Read/Probe mit einer separaten finalen Transaktion aus008-Lock,
003-Credentialmutation und009-Terminalaudit. Alle drei Aktionen durchlaufen
diesen Ablauf. Revoke benötigt keine Entschlüsselung/Probe.

356 Credentialtests (19 Client,116 Offline,221 tatsächliche PG) und461
API-/Workertests bestanden.64 neue PG-Fälle (48 Abschluss,16 Executor)
prüfen auch Sperrwartezeit/Ablauf nach Mutation, Concurrent-Replay, aktuelle
Authority/CAS, finale Rollbacks und verlorene Commitantworten.21 neue
Offlinefälle, gepinnte Builds und unabhängiger Review ohne Restblocker.

009 nach vollständig zurückgerollter DDL-/echter Failure-Abschlussvorprüfung
ausschließlich in Fixture-DB angewendet/immutable;001–008 unverändert,
investalo bleibt001–007. Öffentliche Dienste unverändert/gesund/TLS200.
Keine HTTP-/echte Key-/Brokeraktivierung; physische Geräteabnahme, tatsächliche
E-Mail, Browserintegration, Betrieb/Recovery bleiben separate Gates.
[Ablauf/Prüfbelege](../passkey-credential-execution.md).

## Zwischenabnahme IP-041 — privater Cockpit-Credentialablauf

Merge `3476f74` in Main `0fd25b6` verifiziert; Branch
`feat/m1-passkey-credential-cockpit`. Default-off008-API-Brücke und privater
BFF-Kern verbinden Zweckvorbereitung, echte Passkeyprüfung, ausdrückliche
Credentialzustimmung, separate Signatur und privaten Executor.
Ursprüngliche Session/CSRF/Origin/OIDC bleiben nach Await gebunden;
Bodybytes liegen nur beim vertrauenswürdigen Aufrufer im Speicher.

572 API-/Workertests (111 neue:87 Unit,24 tatsächliche PG),385 Cockpittests
(52 neue),299 integrierte TS/WebAuthn/HTTPS/API/PG/Jose/Python/AEAD/009-Prüfpunkte
und Typecheck/gepinnte Builds/Reviews bestanden. Alle drei Aktionen, Bodydrift,
Replay und unveränderte OIDC-Zeit geprüft. Ein bestehender Zeitparametertest
berechnet relative Werte beim Testaufruf; Produktionsregeln unverändert.

Keine neue Migration: investalo001–007, Fixture001–009 verifiziert/immutable.
Nach Nutzerneustart nur geschützte synthetische Fixtureablage neu vorbereitet.
Fixture-APIs gestoppt; sechs öffentliche Dienste gesund, reguläres TLS HTTPS200.
Browser-Keyannahme, physische Geräteabnahme, Betriebsidentität/-provider und
realer Credential-/Brokertransport bleiben gesonderte Arbeit.
[Ablauf und Belege](../passkey-credential-cockpit.md).

## Zwischenabnahme IP-043 — isolierter Entwicklungs-Credentialdienst

Register, Austausch und Widerruf laufen über mTLS in einem eigenen Container
mit gebundenem Fixture-LOGIN und eigenen Schlüsseldateien. Der administrative
Checker hat kein Credential-LOGIN-Passwort und prüft lediglich Setup/Ergebnisse.
Feste Startbedingungen, exakte Mounts und fehlende Zusatzgruppen sind geprüft.
Echte Keys werden vor Consentverbrauch abgewiesen; keine öffentlichen Ports,
neuen Abhängigkeiten oder Migrationen.

401 Credentialtests/52 Subtests, zehn Vorbereitungstests und440 reale
Dienstprüfpunkte bestanden; gepinnte Runtime-/Python-/Nodebuilds und unabhängiger
Review ohne offene Blocker. Historische HTTPS-/Pipeabläufe387/329 erneut bestanden;
überlappende Läufe nicht addieren. Fixturecontainer beendet, öffentliche
sechs Dienste gesund, Cockpit/Auth mit regulärem TLS200.
Produktionsserver, Schlüsselbetrieb, Browser-Keyeingabe/physische Geräteabnahme
und tatsächlicher Broker bleiben weitere M1-Arbeit.
[Vertrag und genaue Abnahme](../credential-development-service.md).

## Zwischenabnahme IP-044 — gepinnter ASGI-Transport

Merge `998bb90` in Main `9f2a9a5` verifiziert; Branch
`feat/m1-credential-asgi-transport`. Kontrollierte Socketübergabe an Uvicorn/h11,
Peerfingerprint vor HTTP, Rawheaderprüfung vor Parsernormalisierung und eine
absolute 20-Sekunden-Frist. Vier Verbindungen einschließlich Handshakes und
vier tatsächliche Executorarbeiten sind getrennt begrenzt; Disconnect oder
Timeout geben noch laufende Arbeit nicht frei und lösen keinen Retry aus.

419 Credentialtests/52 Subtests in154,35s und451 integrierte Dienstprüfpunkte
bestanden; Hashlockbuilds und Review ohne Restblocker. Nur synthetischer
Entwicklungslauncher, keine öffentliche oder echte Brokeraktivierung.
Uvicorn-Protokollkopplung bei Upgrades erneut prüfen; Betriebsidentitäten,
Schlüsselprovider, Quoten/Recovery und Browser-/Geräteabnahme bleiben offen.
[Vertrag und Abnahme](../credential-asgi-transport.md).

## Zwischenabnahme IP-045 — isolierter Credential-Browserablauf

Merge `9555624` in Main `dcb9feb` verifiziert; Branch
`feat/m1-credential-browser-flow`. Gemeinsame exakte Bodybildung,
prozessgebundene begrenzte Fortsetzungen und drei geschlossene HTTP-Phasen
verbinden Controller, Passkey und ausdrückliche Änderungszustimmung.
Private Bytes bleiben im Seitenspeicher; Abort/Ablauf/Identitätswechsel
verwerfen Referenzen und ignorieren verspätete Antworten. Unbekannte
Schreibergebnisse lösen kein Retry aus.

540 Cockpittests, Typecheck, gepinnte Builds und Review bestanden;
481 synthetische Browsercontroller-/HTTPS-/Dienstprüfpunkte,460 bestehende
Dienstprüfpunkte und sechs tatsächliche gesperrte Next-Routenchecks grün.
Öffentliche Dienste unverändert/gesund, Testcontainer beendet und DB-
Prüfsummen normal007/Fixture009 bestätigt. Tatsächliche aktivierte Next-
Sitzungen/physische Geräte, provisionierte BFF-/Dienstprovider, Schlüssel-/
Quota-/Recoverybetrieb und echte Brokerabnahme bleiben offen.
[Vertrag und Abnahme](../credential-browser-flow.md).

## Zwischenabnahme IP-046 — Dreijahresbacktests und nächste Paperausführung

Main073c474 enthält IP-0450a0751b (verifiziert). Nutzer priorisiert ausdrücklich
Trading und Backtesting; weitere Credentialaktivierung wird zurückgestellt.
Branch `feat/m1-long-history-backtests` stellt beide realen6576-Kerzenläufe
in der bestehenden Entwicklungsansicht bereit. Forschungsfenster/Strategie/
Kosten wurden vor Leistungsläufen im Protokoll eingefroren. Die reservierten
2190-Kerzen-Holdouts bleiben gesperrt und haben null Jobs. Positive
Forschungszahlen ersetzen keine unabhängige Validierung.
Abschlussbelege oben und [vollständiger Vertrag](../long-history-backtests.md).
IP-047 ist der nächste konkrete Papercheckpoint mit demselben Handelskern,
Journal und Crash-/Replay-/Riskprüfung; privater Brokerzugang dafür nicht nötig.

## Routine

Vor Beginn Status setzen, relevante Entscheidungs-/Pitfallnotizen lesen.
Nach fachlichem Abschluss passende Prüfungen einmal ausführen, Ergebnis
dokumentieren, betroffene Generaldocs aktualisieren und Arbeit in Git sichern.
Neue Findungen als Backlogpunkt erfassen; kritische Punkte sofort als Ticket.
