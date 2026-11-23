# Offenes Backlog

IP-009: [Admin-SMTP/E-Mail-Bestätigung](admin-email-settings.md) ist ausgerollt.
SMTP-Login/Codeprüfung abgeschlossen; erstes Ticket tatsächlich ausgestellt
und SMTP-Handoff bestätigt. Nutzer bestätigt erfolgreiche Passkeyregistrierung.
Authelia-Testadresse/Dateinotifier noch separat auf reale Wiederherstellung
umstellen; keine bestehende E-Mail-Freigabe behaupten.

IP-009/IP-015: [Demo-Einrichtung](bitget-demo-dashboard-setup.md) sichtbar
vorbereitet. Futures-/Spot-Demo-Read-Write bestätigt; eigener nativer
[Handelskey-/AEAD-Vertrag](bitget-demo-trading-profile.md) geprüft.
Dauerhafter Trading-Store/gemeinsame Demo-UID-/Kontoregistry und aktuelle
Metadatengrundlage in [Fixture018](bitget-demo-trading-store.md) geprüft.
Eigener Trading-Passkey-/Consent-/Consume-/Executorpfad in
[Fixture019](bitget-demo-trading-passkey.md) geprüft. Eigene Default-off
[Handelskey-API](bitget-demo-trading-api.md) mit sicheren Metadaten/Rechten
ergänzt. Eigener [BFF-/Browser-/privater Transportablauf](bitget-demo-trading-dashboard.md)
geprüft. [Gemeinsame isolierte Tradingabnahme](bitget-demo-trading-acceptance.md)
mit449 Prüfungen bestanden. [Operative Runtime/private Benutzerkonfiguration](bitget-demo-trading-runtime.md)
ausgerollt; Passkey und erste tatsächliche Demo-Keyregistrierung abgeschlossen.
Native Account-/Order-/Kosten-/Latenz-/
Quotaabnahme und Demo-Dispatcher folgen. Synthetische Guards bleiben erhalten.

Stand 2026-11-10. Aktive Aufgaben stehen im [Ticketboard](tasks/board.md).
Keine erledigten Punkte in dieser Liste halten.

| ID | Thema | Auslöser / spätere Aufgabe |
|---|---|---|
| BL-001 | Geheimnisse in bestehender Git-Historie | IP-005: mögliche Keys rotieren, Rewrite-/Remotekoordination abstimmen |
| BL-002 | Hostkapazität und kritischer Handel | Vor P4 messen; RAMerweiterung oder getrennte Researchkapazität entscheiden |
| BL-003 | Free-only Secrets-/Backup- und Laufzeitnachweise | Authelia/SMTP/administratives Recovery/Backupziele bestätigt; vor P1/P4 Zustellung, Schlüssel, externes Ziel und Restore prüfen |
| BL-004 | Rechtliche Zulässigkeit von FTMO-Multiuserausführung | Vor MT5-Demo-/Livefreigabe beziehungsweise P8 Kontovertrag, Personal Use und mögliche Zustimmung prüfen |
| BL-005 | Datenrechte für News, Kalender und Mehrnutzeranzeige | Vor IP-021 Lizenz/Quota/Anbieter festlegen |
| BL-006 | Legacy-RiskGuard, Kosten und mögliche Zeit-Leaks | Bei IP-012/020 strikte Limits, Fillkosten und historische Kausalität nachweisen |
| BL-007 | Strategieabbildungen für Gold/Coffee/Öl formalisieren | Nach erster Strategie mit Nutzerpriorität; keine Titel als Codeinterpretation |
| BL-008 | SSO mit investalo.de | Nach initialer Identityentscheidung und privatem Pilot |
| BL-009 | Weitere Broker/Märkte/Strategien | Nach Zwei-Adapter-Abnahme und separater Hypothesenprüfung |
| BL-010 | Hochverfügbarkeit und Regionen | Nach bestätigtem SLA/Lastbedarf; zusätzliche Infrastruktur separat planen |
| BL-011 | Höhere Mandantenisolation | Bei Kunden-/Vertragsbedarf separate Rollen/DBs bewerten |
| BL-012 | TimescaleDB, Cache oder zusätzlicher Jobbroker | Nur nach Lastmessung und konkretem Betriebsnutzen |
| BL-013 | Freigegebene CI/CD-Automatisierung | Konkretes Tool/Abhängigkeiten vor Einführung abstimmen |
| BL-014 | Erweiterte automatische Strategiepromotion | Erst nach validiertem Researchprozess, expliziter Governanceentscheidung |
| BL-015 | Kundenbetrieb, Abrechnung und Compliance | IP-023; neue Product-/Rechts-/Privacyphase |
| BL-016 | Brandtokens und bestehendes UX-System | Vor IP-014 Websitevorgaben erfassen und Logoverwendung/Design abstimmen |
| BL-017 | Auth-Retention und Ratenbegrenzung | Nonce-/Sitzungsbereinigung, begrenzte Jobannahme und Recoveryoperator vor Pilot nachweisen |
| BL-018 | Researchdaten, Feintuning und Executionidentitäten | IP-046 reale Dreijahresforschung BTC/ETH und reservierter Jahres-Holdout; Paperkern/Store/Feed und eigene Anzeige IP-048–054. Nutzerpriorität2026-11-09: geringe Kontorendite diagnostizieren, Kapitalbindung/RSI/Ausstiege/Kosten und vergleichbaren Benchmark auswerten. Begrenzte chronologische Kandidatenprüfung ohne Holdoutnutzung; Regeländerungen abstimmen und Auswahl einfrieren. Reale Fees/Spread/Instrumentregeln und unabhängige Holdoutabnahme offen; separate Live-Executionrollen bei IP-016 |
| BL-019 | Manueller Auftrag ohne Fill | Bei IP-024 expliziten abgeglichenen Wiederholungsweg für reservierte manuelle Intents ergänzen; keine blinde neue Order |
| BL-020 | Tatsächliche MFA-Schrittbestätigung | Registry, Enrollment, zielgebundener Nachweis007 und ausdrücklich aktivierbare Browservorschau implementiert; vollständiger synthetischer BFF-Ablauf über echtes isoliertes HTTPS/API/PG geprüft. Physische Browser-/Geräteabnahme, reale E-Mail-Attestierung, öffentliche Aktivierung und Rate-/Speicher-/Retentionbetrieb bleiben IP-033/BL-017; Authelia-Reauth und Counter-CAS allein beweisen keinen frischen zweiten Faktor |
| BL-021 | Bitget-Keyeinrichtung und Walletgrenzen | IP-040 verbindet008 mit PostgreSQL-geprüfter privater Classic-Probe/003-Mutation und009-Abschlussaudit; IP-041 ergänzt private Cockpit-Orchestrierung und standardmäßig abgeschaltete008-API; IP-042/043/044 prüfen Entwicklungs-mTLS, getrennten synthetischen Credentialcontainer und ASGI-Unterbau. IP-045 ergänzt isolierte Browserkomponente/Controller mit synthetischer HTTPS-Prüfung.008/009 ausschließlich in der Fixture-DB. Tatsächliche Next-Sitzungs-/physische MFA-Abnahme, provisionierte BFF-/Dienstidentitäten und Schlüsselprovider, produktiver HTTP-/Egress-/Brokerbetrieb und gemeinsame UID-Quota vor echter Verbindung abnehmen.007-Confirm ist keine Credentialeinwilligung; UTA/Futuresausführung später gesondert |
| BL-022 | Credential-Schlüsselbetrieb und Rollbackschutz | Aktuelle DB-Revision, CAS und getrennte Credentialrollen geprüft, expliziter Entwicklungs-Dateiprovider mit stabilen Fingerprints vorhanden; IP-043 konkretisiert synthetischen Dienstcontainer, IP-044 seinen gepinnten ASGI-Unterbau. Externe Betriebsschlüsselgrenze, provisionierte Identitäten, gemeinsame Nutzungs-/Noncebudgets, Schutz gegen vollständigen DB-Rollback und verschlüsselter externer Restore vor echter Keyannahme nachweisen |
| BL-023 | Wiederanbindung nach Credentialwiderruf | UID und Plattformkonto bleiben terminal reserviert; kontrollierten admin-/MFA-/Brokerprüfweg für erneute Einrichtung oder Übertragung entwerfen, keine automatische Reaktivierung oder Löschung |
| BL-024 | Credential-Freigaben im Betrieb | Annahme-/Speicherlimits und Retention ohne Replayöffnung festlegen; IP-045-Prozessfortsetzungen brauchen vor Betrieb abgenommene Workerzuordnung und Quoten. Autorisierte, aber nach Crash unvollständige JTIs und unbekannte Commits abgleichen, keine automatische Probe-/Writewiederholung |
| BL-025 | Passkey-Recovery nach terminalem Widerruf | Administrativer Widerruf sperrt den Faktor und erhöht die globale Nutzer-Epoch; kontrollierten E-Mail-bestätigten Ersatz-/Recoveryweg mit eigener Migration und Sitzungsbindung abnehmen. Keine Reaktivierung, Löschung oder erneute Registrierung in reservierte Slots |
| BL-026 | Öffentlicher TLS-Betrieb | IP-035 bestätigt persistente ACME-Daten nach Neustart und ausschließlich Edge-Hostports; tatsächliche Erneuerung, Ablaufüberwachung, unabhängig externe Portprüfung und geschützten Wiederherstellungsweg noch nachweisen; Zertifikat ersetzt keine Pilotabnahme |
| BL-027 | Testclient-Abhängigkeit | Starlette meldet im grünen API-Lauf die Ablösung von `httpx` durch `httpx2`; beim nächsten geprüften Dependencycheckpoint FastAPI-/Starlette-Kompatibilität, exakte Pins und Lockstände gemeinsam prüfen |
| BL-028 | Paper-Dauerbetrieb | Q32/IP-052 H4-Tagesmodell, IP-053 Fixturebeobachtung und IP-054 eigener bestätigter Stand aus begrenztem Kurslauf im Cockpit vorhanden. Noch eigener begrenzter Preview-Beobachtungsworker, echte Mitternachtsbeobachtung, Egress/Quoten/Retention und längerfristige Monitoring-/Recoveryabnahme; ca34.560 Quotejournalinputs/Tag bei5s. Keine automatische Löschung oder unangekündigte Frequenzänderung |
| BL-029 | Multi-Basketportfolio und KI-Signalprüfung | Q33–36/IP-055:14 Kandidaten,3–5 Anfangsslots, Wiederbelegung und6%/8% bestätigt. IP-060 offline Poolzyklen/Mindestmengen; IP-061 separate Gewinnetappen zuerst bis7 Slots, danach höhere neue Budgets implementiert. Vollständige erweiterte Datenverträge/Historien, eingefrorene Kohorten/Benchmark und echter Nettovergleich fest/Gewinnprofil offen. XMR Spot aktuell nicht gefunden, ZEC/HYPE/XLM ohne2022-Sample. Dauerhafte Reservierung/Brokerabgleich/Paperintegration folgen. KI zuerst Shadow Mode mit damaligem Wissen/Kostenbudget; Hebel/Stufen separat validieren. [Plan](multi-basket-ai-plan.md) |
| BL-030 | Futuresökonomie, Regime und Hebelvalidierung | Alte Q37-Profile behalten−50%/6%/8%; im neuen Q41–45-Kapitalprofil sind sie Diagnostik/Warnungen, tatsächliches Kapital/Margin/Liquidation bleiben verbindlich. Native Kohorte und volle Nettovergleiche IP-075–086 abgeschlossen; IP-087 ergänzt3×/4×. Kausale damalige Regime-/AI-Kriterien und unabhängiger Holdout, vollständige Classic-/historische Brokerkalibrierung bleiben offen. Q46/IP-088: eigene dauerhafte Paper-CAS-/Status-/API-Recovery implementiert; lokale HTTPS/PG/SSR-Abnahme mit synthetischer Quelle und bounded Zyklus-/APIübergabe bestanden. Physischer Browser, große Journale/Dauerbetrieb und tatsächlicher Demo-Positions-/Orderabgleich folgen. Keine automatische Wiederbelebung oder rückwirkende Verlustlöschung. [Recovery](futures-manual-recovery.md), [Vergleich](futures-moderate-leverage.md) |
| BL-031 | Wechselnde native Fundingtermine im erweiterten Paperpool | Der explizite Sieben-Coin-Collector und14-GET-Replay sind nativ geprüft. Q49 verlangt je Abrechnung vollständige echte Funding-/Minutenbelege. Bei künftig verschiedenen Terminen gilt Reconciliationstop; vor kontinuierlichem Betrieb einen eigenen Vertrag für tatsächlich fällige Teilkohorten, erhaltene IDs/Quotecursor und Vollrestore prüfen. Keine Ersatzraten oder still weggelassenen fälligen Ereignisse. [Vertrag](futures-seven-candidates.md) |
| BL-032 | Classic-Demo-Ausführung und Kostenquelle | IP-015/016: Offline-Auftrags-/Teilfillvertrag, private Outbox/CAS/fsync/Crashrestore und14-Achsen-Snapshotcheck gegen eigene Outbox-/Cash-/Positionsbasis vorhanden. Ursprüngliche private shared-root UID-/Kontopfadregistry mit bound Zugriff vorhanden; keine automatische Adoption/Rotation/Reset. Getrennter signierter Demo-Readtransport, eigener AEAD-/SealedProviderkern, dauerhafter Demo-Store/DB-Reader in Fixture014 und eigene Demo-Passkey-Zweckfreigabe/Consume-/Lockclient in Fixture015 vorhanden. Eigener privater Demo-Executor/Post-Write-Completionvertrag in Fixture016 und eigene Default-off-Proof-/Consent-API über015 ergänzt; eigener privater BFF-Verifikations-/Consent-/Signingflow und mTLS-Executortransport geprüft. Eigener scoped Metadatenzugriff/Fixture017 und Cockpit-Serveradapter ergänzt. Eigener geschützter Demo-Browserablauf mit Formular/Next-Routen ergänzt, Runtime fest aus ([Browserablauf](bitget-demo-browser-flow.md)). Eigener privater Dateiprovider/Serverfactory mit tatsächlicher mTLS-Prüfung ergänzt ([Private Identität](bitget-demo-private-identity.md)); gemeinsame isolierte laufende HTTPS/BFF/API/PG/Executorabnahme mit438 Prüfungen bestanden ([Abnahme](bitget-demo-local-acceptance.md)); private MAC-gebundene Herkunftsfreigabe und nativer Registrierungsprüfer mit synthetischen Replies vorhanden ([Provisioning](bitget-demo-native-provisioning.md)); privater einmaliger TTY-Prüfaufruf mit tatsächlicher Echoabnahme vorbereitet ([Prüfaufruf](bitget-demo-private-probe.md)); reale Metadaten-/Keyeinrichtung und operative Installation/Provisioning ([Metadaten](bitget-demo-metadata-provider.md), [BFF](bitget-demo-bff-flow.md)), native Endpoint-/Latenz-/UID-Quota-/Keyprovenienz, Root-/Backupbetriebsabnahme und ältere Normal-/Triggerorder-/Cashabdeckung fehlen. [Executor](bitget-demo-passkey-executor.md), [Freigabe](bitget-demo-passkey-purpose.md), [Readtransport](bitget-demo-read-transport.md), [Registry](bitget-demo-account-registry.md). Classic fill-history laut Anbieter nicht im Demo verfügbar: tatsächliche Fill/Funding/Kostenquelle vor Nettoledger/Recovery kalibrieren; Paperwerte nicht übernehmen. [Abgleich](bitget-demo-account-check.md), [Outbox](bitget-demo-outbox.md) |

BL-032 ergänzt2026-11-22: tatsächlicher Demo-Key/Provider und10k-Kontoanzeige
aktiv; manuelle [Startprüfung](bitget-demo-startup-check.md) implementiert.
Ältere offene Standard-/Triggeraufträge außerhalb des dokumentierten
3-Monats-Fensters, tatsächliche Kosten/Funding, native5s-Latenz und ursprüngliche
operative Outboxbasis vor Orderdispatcher/Testfreigabe nachweisen.

BL-032 fortgesetzt: Startprüfungsrollout genehmigt/erledigt, erster nativer
Nutzerbericht noch unbestätigt; technische Diagnose aktiv. Privater
[Orderkern und öffentliche BTC-Vorschau](bitget-demo-order-dispatch.md)
implementiert. Eigener realer dauerhafter Orderconsumer und Konto-/Budgetguard
sowie tatsächliche ursprüngliche Registryeinrichtung vor Aktivierung fehlen.
Native Demo-Maximalmengenquelle klären; Public `maxOrderQty` ist leer.
Startdiagnose jetzt konkret: zehn native200/00000 in5265ms; begrenzt
überlappende Lesegruppen implementiert/geprüft; zweite native Diagnose
belegt null/null-Pending-Leerantwort, eigener Startupadapter ergänzt.
Originaler nativer Startabruf vollständig erfolgreich:15 GETs/4551ms/200/00000.
Browserbericht bestätigt: Cross/Hedge/10× weicht vom geplanten Profil ab;
gezielte Demo-Konfigurationsvorbereitung und ältere Scope-/Kostenabnahme offen.
Nutzer meldet BTC vorbereitet; [BTC-Testvorschau](bitget-demo-btc-test-preview.md)
mit gezielter Konfiguration und gesamter Kontoprüfung ausgerollt;
originaler privater BTC-Abruf/Browseranzeige bestätigt. BTC isoliert/
einseitig/2× passt. Grant-Quellenabgleich aus bestehendem BTC-GET mit176
Pythonfällen/Executorbuild geprüft; PR111 gemergt und Rollout erledigt,
nativer Grant-Nachweis folgt. [Dauerhafter Orderconsumer](bitget-demo-order-consumer.md)
mit185 Pythonfällen/Executorbuild geprüft; operative Zustimmungs-/Accountguard-/
Registry-/Routeanbindung weiterhin offen.
Native maximale Limitmenge/Kosten/ältere Scopefreigabe weiterhin offen.
Frontend-Optimierung auf kleinem Host sehr langsam (gemeldete432,8min);
Builderauslastung und externen Buildpfad vor größeren Frontendblöcken prüfen.

RSI-/Supertrend-/Budget-/Exitentscheidungen Q1–Q31 sind bestätigt.
Q32 zur H4-Modellpreis-Basis ist ebenfalls bestätigt. Offen bleiben die
genannten Umsetzungen und Betriebs-/Wirtschaftlichkeitsnachweise.
Q33 bestätigt das Multi-Basket-/KI-Planungsziel und weiterhin6%/8% Kontolimits;
konkrete größere Kaufbudgets, zusätzliche Coins und Varianten bleiben offen.
