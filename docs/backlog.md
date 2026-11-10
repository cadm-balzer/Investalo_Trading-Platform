# Offenes Backlog

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
| BL-030 | Futuresökonomie, Regime und Hebelvalidierung | Q37/IP-062–063: isolierte USDT-M-Long-Baskets mit eigenem echten Kapital/Marginpuffer bestätigt;−50%/6%/8% erhalten, gewünschte2×–10× nur nach Risiko-/Regimeprüfung. AVAX/HBAR/TRX/BGB/BAT/RENDER alternativ, volle Futures-/Mark-/Fundinghistorien und historische Maintenance-Stufen offen. Exakte Uptrend-/Hebelregeln, Budgetaufteilung, Verhalten bei Regimewechsel, eigene Frozen-Daten-/Kosten-/Nettoverträge und spätere Executionidentität fehlen. [Vertrag](futures-research.md) |

RSI-/Supertrend-/Budget-/Exitentscheidungen Q1–Q31 sind bestätigt.
Q32 zur H4-Modellpreis-Basis ist ebenfalls bestätigt. Offen bleiben die
genannten Umsetzungen und Betriebs-/Wirtschaftlichkeitsnachweise.
Q33 bestätigt das Multi-Basket-/KI-Planungsziel und weiterhin6%/8% Kontolimits;
konkrete größere Kaufbudgets, zusätzliche Coins und Varianten bleiben offen.
