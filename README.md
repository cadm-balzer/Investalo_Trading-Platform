# Investalo Trading Platform

Mandantenfähiges Trading-Cockpit mit Portfolio, Journal, Backtests und
automatisiertem Handel über Bitget und MetaTrader 5.

**Stand: 2026-11-08 — M1-Implementierung gestartet, Q31 bestätigt.**
Das lokale Fundament läuft über Docker Compose: Cockpit, FastAPI, PostgreSQL,
Authelia und zentraler HTTPS-Proxy. Versionen, Imagedigests und Paketlocks sind
festgelegt. Der deterministische Crypto-Kern und ein isolierter Offline-
Researchworker sind implementiert. Backtests verwenden unveränderliche H4-
Snapshots und zeigen gespeicherte Nettoergebnisse, Kosten und Equitykurven.
IP-046 erweitert die verfügbare Forschung auf drei Jahre BTC/ETH-H4
(2022-08-01–2025-08-01); ein weiteres Jahr ist separat als Holdout reserviert.
Nächster Schwerpunkt ist die Paperausführung mit demselben Handels-/Risikokern.
[Protokoll, Bedienung und Aussagegrenzen](docs/long-history-backtests.md).
Der vollständige erste Release mit beiden Brokerpfaden bleibt in Umsetzung.
Crypto startet mit BTC/ETH Spot ohne Hebel auf H4; MT5 mit XAUUSD Trend/Pullback.
RSI-/Supertrend-Regeln sowie Paper-/Demolimits sind bestätigt.
Die sechste Crypto-Tranche bleibt ausschließlich für einen manuellen Einstieg
reserviert: nach fünf Stufen, 5%-Preisabstand, Vorschau/MFA/Risk Gate;
Cockpitmeldung mit optionaler E-Mail. MT5 läuft laut Nutzer
auf einem separaten Heimnetzserver und wird über eine ausgehende HTTPS-Bridge
angebunden. Öffentlicher zentraler HTTPS-Einstieg für private Nutzer und
administratives E-Mail-Recovery sind bestätigt, ebenso Validierungsmaßstab,
Pilotbackupziele und M1-Umfang.
Alle Entscheidungen Q1–Q31 sind bestätigt.
Bestätigt sind privater Start, Cockpit/Backtests/Paper vor Echtgeld,
verbindliche Risikolimits, kontrollierte KI und zunächst kostenlose externe Dienste.

## Einstieg

- [Originaler Projektauftrag](docs/project-info.md)
- [Gesamtkonzept](docs/concept.md)
- [Bestätigter M1-Umfang und Umsetzung](docs/implementation-brief.md)
- [Lokaler Start](infra/README.md) und [Runtimepins](docs/runtime-pins.md)
- [Architektur und Technologieauswahl](docs/architecture.md)
- [Handelslogik und Validierung](docs/trading.md)
- [Sicherheit](docs/security.md) und [Betrieb](docs/operations.md)
- [Compose-/Authelia-Plan für den Privatpilot](docs/deployment-plan.md)
- [MT5-Bridge zum Heimnetzserver](docs/mt5-bridge.md)
- [Bitget-Kontoverbindung mit eigenem API-Key](docs/bitget-connection.md)
- [Roadmap](docs/roadmap.md), [Ticketboard](docs/tasks/board.md) und
  [Backlog](docs/backlog.md)
- [Interview und offene Entscheidungen](docs/interview.md)
- [Bestandsaufnahme](docs/inventory.md) und [offizielle Quellen](docs/sources.md)

## Projektstruktur

| Pfad | Verantwortung |
|---|---|
| `apps/cockpit/` | Dashboard und Bedienoberfläche |
| `services/api/` | Autorisierte API und fachliche Anwendungsfälle |
| `services/credentials/` | Gebundener Credentialstore und privater Bitget-Einrichtungsablauf |
| `services/workers/` | Datenimport, Backtests, Execution und Abgleich |
| `packages/trading/` | Gemeinsamer deterministischer Strategie- und Risikokern |
| `packages/marketdata/` | Validierte H4-Snapshots, öffentlicher Bitget-Import und CSV |
| `packages/credentials/` | AES-GCM-Envelopes und authentifizierte Kontobindung |
| `packages/contracts/` | Versionierte API-, Ereignis- und Bridgeverträge |
| `integrations/` | Bitget-Adapter und nutzereigene MT5-Bridge |
| `infra/` | Lokale Composeumgebung, TLS, Bootstrap und Werkzeugprofile |
| `tests/` | Fachliche, Integrations-, Isolations- und Recoverytests |
| `strategies/` | Bereits vorhandene Strategieabbildungen |
| `docs/`, `memory/` | Planung, Tickets, Entscheidungen und Arbeitsnotizen |

Cockpit zeigt tatsächlich gespeicherte Konten, Positionen, Journal und
Backtestaufträge und deren Ergebnisse; fehlende Daten bleiben leer. Die API
prüft signierte Identität, Mitgliedschaft und RLS und friert Daten-/Kostenstand
bei idempotenter Jobannahme ein. Ein echter 90-Tage-BTC-Import prüft den lokalen
Researchablauf; wirtschaftliche Validierung bleibt offen. Der isolierte
[Classic-Bitget-Readadapter](integrations/bitget/README.md) ist mit 24 Offline-Tests
geprüft. Der isolierte [Credential-Envelopekern](packages/credentials/README.md)
verschlüsselt gebundene Daten und ist mit 20 Manipulations-/Rotations-/Restoretests
geprüft. Der [Credentialstore](services/credentials/README.md) ergänzt persistente
Nutzer-/Kontobindung, Versionsprüfung, Rotation und Widerruf. Der private
Einrichtungsablauf verbindet Classic-Identitätsprüfung, verschlüsseltes Keytriple
und einmalige Freigaben für Einrichtung, Keywechsel und Widerruf. Die Prüfung
nutzt synthetische Freigaben und Brokerantworten gegen echte PostgreSQL-Tabellen:
120 Tests bestanden, davon 60 tatsächliche PostgreSQL-Fälle.
Ein Dateischlüsselprovider ist ausschließlich für Entwicklung verfügbar.
Das Cockpit zeigt jetzt geschützte Bitget-Kontometadaten. Kontoänderungen bleiben
gesperrt: Authelia-Reauth belegt keinen neu verwendeten zweiten Faktor.
Die zusätzliche Passkey-Bestätigung ist bestätigt. Dauerhafte Publickey-
Registry, administratives Einmalticket, Widerruf und lokales Browser-Enrollment
sind implementiert. Physische Geräteabnahme und Browser-Credentialfreigabe folgen;
registrierte Passkeys öffnen noch keine Kontoänderungen.
[Passkeyplan und Abnahmegrenzen](docs/passkey-step-up.md).
Der interne zielgebundene Passkey-Aktionsnachweis verbindet jetzt dauerhaften
Einmalclaim, Signaturprüfung, Counter/CAS und Vorschau-Bestätigung.
Der Adapter erhält die ursprünglichen OIDC-Claims. IP-037 ergänzt eine ausdrücklich
aktivierbare Browservorschau unter `/security/passkeys/verify`; Standardprofil und
öffentliche Vorschau lassen sie ausgeschaltet. Der vollständige BFF-Enrollment-
und Nachweisablauf ist mit synthetischen P256-Daten über echtes HTTPS/API/PG
geprüft. Das Ergebnis bleibt `execution_enabled:false`; physische Geräteabnahme,
öffentliche Aktivierung und Cockpit-Credentialausführung folgen separat.
[Ablauf und Grenzen](docs/passkey-action-proofs.md).
[Browservorschau und Prüfbelege](docs/passkey-browser-proof.md).
IP-038 ergänzt einen isolierten TypeScript-/Python-Vertrag für spätere
Passkey-Credentialassertions mit eigener Audience und unveränderter OIDC-Zeit.
Die bestehende007-Funktionsbestätigung ist keine zweckgebundene Credentialfreigabe.
[Vertrag und offene Integration](docs/passkey-credential-assertions.md).
IP-039 ergänzt additive008 und einen privaten Pythonclient: Zweck/Body werden
bei Prepare eingefroren, ein noch erteilter007-Grant ausdrücklich autorisiert,
die Freigabe global einmalig konsumiert und in einer getrennten Transaktion
vor dem künftigen Write erneut geprüft. Die geprüfte008 ist ausschließlich in
der Fixture-DB angewendet; `investalo` bleibt001–007. Die 271 Credentialtests
(157 mit tatsächlichem PostgreSQL) und 461 API-/Workerchecks bestanden.
Cockpit-Credentialausführung und Browseraktivierung bleiben gesperrt.
[Dauerhafte Autorisierung und Grenzen](docs/passkey-credential-authorizations.md).
IP-040 verbindet diese Freigabe im privaten `PasskeyBitgetOnboarding` mit
Classic-Probe,003-AEAD-Store und neuem009-Abschlussaudit. Consume committed
vor Probe;008-Lock, Credentialänderung und terminaler Abschluss teilen eine
finale Transaktion. 817 Tests bestanden: 356 Credentialtests, darunter 221
tatsächliche PostgreSQL-Fälle, und 461 API-/Workerchecks. Zurückgerollter009-
Preflight und gepinnte Prüfbuilds bestanden.
009 ist ausschließlich in der Fixture-DB angewendet.
IP-040 aktivierte keine HTTP-/Echtkey-/Brokeranbindung.
[Private Ausführung und Abnahme](docs/passkey-credential-execution.md).
IP-041 ergänzt die private Cockpit-Orchestrierung und eine standardmäßig
ausgeschaltete interne API für008-Prepare und ausdrückliche Zustimmung.
Der Ablauf bindet unveränderte Bodybytes, ursprüngliche OIDC-Sitzung und
Passkeynachweis an den privaten Executor. Es gibt weiterhin keine
aktivierte Credentialeingabe-/Ausführungsroute im Browser, keine Betriebsschlüssel oder
echte Brokerverbindung. Die öffentliche Vorschau bleibt unverändert.
[Private Cockpit-Anbindung und Gates](docs/passkey-credential-cockpit.md).
572 API-/Worker- und385 Cockpittests sowie299 integrierte Prüfpunkte bestanden;
Typecheck, gepinnte Builds und unabhängige Reviews grün.
Die ausdrücklich freigegebene Entwicklungsvorschau ist unter
[cockpit.investalo.de](https://cockpit.investalo.de) aktiv. Beide Domains haben
gültige Let’s-Encrypt-Zertifikate; 48 öffentliche HTTPS-/MFA-/Backtestprüfpunkte
bestanden. [Zugang und Betrieb](docs/https-entry.md).
Geschützte Cockpiteingabe mit echter MFA-Schrittbestätigung, Schlüsselbetrieb
und tatsächliche Brokeranbindung, manuelle MFA-Reservefreigabe
und Pilotbetrieb sind weitere M1-Aufgaben.
IP-042 ergänzt einen lokal injizierten Entwicklungs-HTTPS-Transport mit
gegenseitigem TLS und unabhängigem ursprünglichem Sitzungskontext.
[Dienstgrenze und verbleibender Betrieb](docs/passkey-credential-https.md).
IP-043 trennt den synthetischen Credentialexecutor in einen eigenen
Entwicklungscontainer mit ausschließlich gebundener Credentialrolle und
eigenen Schlüsseldateien. Der administrative Checker prüft danach das Ergebnis;
echte Schlüssel werden vor Verbrauch der Freigabe abgewiesen.
[Isolierter Dienst und Startbedingungen](docs/credential-development-service.md).
IP-044 übernimmt dafür den bestehenden gepinnten ASGI-Stack. mTLS vor dem
HTTP-Parser, strikte Rawheader sowie getrennte Verbindungs-/Arbeitsslots
erhalten die bisherigen Grenzen auch bei Disconnects.
[ASGI-Transport und Betriebsgrenzen](docs/credential-asgi-transport.md).
IP-045 ergänzt den isolierten Browserablauf mit Schlüsseleingabe, Passkeyprüfung
und separater Änderungsbestätigung. Der Controller wird über interne HTTPS-
Requests bis zum verschlüsselten Dienst geprüft; die Next-Routen bleiben ohne
provisionierte Betriebsprovider gesperrt.
[Browserablauf und verbleibende Abnahmen](docs/credential-browser-flow.md).
Vollständiger Privatpilot, Produktion und Echtgeld benötigen eigene
Abnahmen. Das lokale Standardprofil bindet ausschließlich `127.0.0.1:8443`;
die aktive Vorschau veröffentlicht nur den zentralen Proxy auf80/443.

## Arbeitsregeln

Siehe [AGENTS.md](AGENTS.md). Geheimnisse und private Kontodaten gehören nicht in
Git. Neue externe Dienste, wesentliche Architekturentscheidungen und
Produktionsdeployments brauchen die dort festgelegte Abstimmung.

Dauerhafte Profitabilität und absolute Sicherheit sind Zielvorstellungen, keine
garantierbaren Eigenschaften. Abnahmen prüfen nachvollziehbare Nettoergebnisse,
Risikobegrenzung und konkrete Sicherheitskontrollen.
