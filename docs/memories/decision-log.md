# Entscheidungsprotokoll

Entscheidungen erhalten Status und Begründung. Ein dokumentierter Vorschlag ist
keine Nutzerfreigabe. Quellen: [Interview](../interview.md), [Auftrag](../project-info.md).

## 2026-11-06 — D-001: Planung vor Implementierung

**Status: beauftragt.** Originalauftrag vollständig gelesen. Zuerst
Projektstruktur, Konzept, Roadmap, Tickets und grill-me-Interview.
Alle vorgeschlagenen Technologie-/Strategiedetails ausdrücklich kennzeichnen.

## 2026-11-06 — D-002: MVP und Nutzerkreis

**Status: bestätigt, Q1/Q2.** Privates Cockpit mit Backtests und Paper zuerst.
Mandantenmodell von Beginn an, späteres Kundenangebot als eigener Ausbau.
Echte Ausführung und Produktionsdeployment bleiben separate Freigaben.

## 2026-11-06 — D-003: Unabhängige Risikopolicy

**Status: bestätigt, Q3.** Verbindliche Risikogrenzen werden außerhalb von
Strategie/AI durchgesetzt. Konkrete Zahlen nach Markt-/Kontotypwahl.
Die −50%-Assetanforderung ersetzt keinen Kontodrawdownlimit.

## 2026-11-06 — D-004: Kontrollierte Selbstoptimierung

**Status: bestätigt, Q4.** AI bewertet und schlägt vor; Strategie-/Parameteränderung
nach Backtest, unabhängiger Validierung und Freigabe. Keine AI-Risikoerhöhung.

## 2026-11-06 — D-005: Vorhandener Host und Free-Angebote

**Status: bestätigt, Q5.** Vorhandenen Server verwenden; externe Tools/Accounts
zunächst kostenlos. TradingView Essentials bereits bezahlt.
Gratisstatus ersetzt weder Nutzungsrechte noch ausreichende Betriebsqualität.

## 2026-11-06 — D-006: Architekturvorschlag

**Status: bestätigt, Q7.** Modularer Monolith, getrennte Worker,
Python/FastAPI, Next.js/TypeScript, PostgreSQL samt persistenten Jobs.
Begründung: vorhandene Bausteine, gemeinsame Transaktionen und kleiner Betriebsumfang.
Konkrete Pins und Prozess-/Identitywahl bleiben gesonderte Detailentscheidungen.

## 2026-11-06 — D-007: Erster Strategiepfad

**Status: bestätigt, Q6.** Nutzer wählt Bitget und MT5 gemeinsam für den ersten
Release. Die Empfehlung einer nacheinander erfolgenden Brokerintegration ist
damit verworfen. Konkrete Assets, Spot/Derivate und Strategievarianten folgen.

## 2026-11-06 — D-009: Eigene Anmeldung

**Status: bestätigt, Q8.** Eigene MFA-Anmeldung für das Cockpit.
Website-SSO ist späterer Ausbau; kostenloser Provider/Eigenbetrieb noch offen.

Provider konkretisiert durch Q14/D-012, Deployment durch Q13/D-011.

## 2026-11-06 — D-008: Secretcontainment

**Status: Sicherheitsmaßnahme im beauftragten Repository.** Vorhandener
Credentialpfad wird ignoriert und aus neuen Snapshots entfernt, lokale Datei
erhalten. Keine Inhalte gelesen. Rotation falls echte Keys und Historyrewrite
sind getrennte Arbeit; keine ungeprüfte Veröffentlichung.

## 2026-11-07 — D-010: Startstrategien und Crypto-Vorlage

**Status: bestätigt, Q9–Q12.** BTC/ETH USDT Spot ohne Hebel auf H4.
MT5 startet mit vorhandenem XAUUSD Trend/Pullback H1-Regime/M15-Entry nach
Risk-/Kosten-/Kausalitätsprüfung. Schriftlicher Crypto-Prompt maßgeblich:
Quote-Beträge wachsen 25 %, 5%-Preisabstand zum letzten tatsächlichen Fill,
−50%-Stress zum ersten Fill. Bildabweichungen werden nicht übernommen.

## 2026-11-07 — D-011: Compose statt systemd

**Status: bestätigt, Q13.** Docker Compose von Beginn an.
Der systemd-Vorschlag ist verworfen. Nonroot, interne Ports, exakte Pins
und gemessene Ressourcen bleiben Anforderungen; keine Installation erfolgt.

## 2026-11-07 — D-012: Lokales Authelia

**Status: bestätigt, Q14.** Lokale MFA der angebotenen Authelia-OIDC-Variante
mit administrierten Privatnutzern und Passwort plus TOTP/WebAuthn.
Kein Cloud-Identityprovider zum Start. Damals offene Zugangs-/SMTP-/
Recoveryentscheidungen werden durch D-015 und D-016 konkretisiert.

## 2026-11-07 — D-013: Signale, Gewinnschutz und gesonderte Notfallreserve

**Status: bestätigt, Q15–Q17.** RSI14/Wilder aus geschlossenen H4-Kerzen,
zwei `<30`-Kerzen erster Kauf, anschließend Rearm `>30` und eine `<30`-Kerze
plus 5%-Preisabstand. Genau 30 kein Trigger; höchstens eine Stufe je Kerzenereignis.
Supertrend ATR10/Wilder ×3, Schutz ab +5 % verkaufbarem Kurs zum Einstand,
Netto-Untergrenze und monotones Trailing, keine Käufe nach Schutz, kein Flipexit.

Q16 verwirft den regulär ausgelösten sechsten Kauf: ausschließlich Notfallreserve.
Der damalige −40%-Vorschlag war nicht bestätigt und wird in Q23/D-017
durch die manuelle Reserve ersetzt.

## 2026-11-07 — D-014: Paper-/Demoprofile

**Status: bestätigt, Q18/Q19.** Crypto 10.000 virtuelle USDT, BTC/ETH je
500 Kaufprincipal +5 Kostenreserve, 6 % Tagesverlust gegen Equity 00:00 UTC,
8 % Verlust gegen Startkapital; offene Ergebnisse/Kosten inklusive.
Zusätzlicher −55%-Exit relativ zum ersten Fill; Limits schließen simulierte
Positionen und sperren neue Käufe bis bewusster Wiederaufnahme.

MT5 getrenntes Brokerdemo, 0,25 % modelliertes Risiko je Idee einschließlich
Kosten, maximal eine offene Idee; 1 % Tagesverlust gegen Equity 00:00
Europe/Prague und 5 % gegen Startdemoequity. Lots abrunden, unter Mindestlot
auslassen. Keine Echtgeldfreigabe und keine Garantie gegen Gapüberschreitungen.

## 2026-11-07 — D-015: Öffentlicher Einstieg für den Privatpilot

**Status: bestätigt, Q20/Q21.** Nutzer verwirft tunnel-only Pilotzugang:
öffentlichen zentralen HTTPS-Einstieg bereits im Privatpilot planen.
Nutzerkreis bleibt eingeladen, DB/Worker intern. Vorhandenen kostenlosen
SMTP mit TLS vorsehen. Keine öffentliche Selbstregistrierung, tatsächliche
Veröffentlichung und Mailversand bleiben gesondert geprüfte Aktionen.

## 2026-11-07 — D-016: E-Mail als gewünschter Recoverynachweis

**Status: Präferenz bestätigt, Q22; Ablauf später in Q24/D-018 bestätigt.** Nutzer möchte
E-Mail als ausreichenden Nachweis statt verpflichtendem unabhängigem Ersatzfaktor.
Best-Practice-Abweichung festhalten: Die Postfachübernahme könnte dann den
MFA-Reset ermöglichen. Authelia erlaubt kontobezogene administrative Faktorresets;
bei normaler Pflicht zum vorhandenen Faktor kein fertiger Mail-only-Selbstservice.
Der zunächst vorgeschlagene Ablauf wird durch D-018 konkretisiert.

## 2026-11-07 — D-017: Puffer ausschließlich manuell

**Status: bestätigt, Q23.** Nutzer behält den Puffer für einen manuellen
Einstieg und möchte darüber informiert werden. Kein automatischer −40%-Kauf
und keine daraus abgeleitete Alarmgrenze. Ursprüngliches Quote-Budget und
unabhängige Risk-/Schutzgates bleiben verbindlich.

Freigaberegeln und Meldekanal später in Q29/Q30/D-023 bestätigt.
Der deterministische Referenzbacktest lässt den Puffer Cash; tatsächliche
diskretionäre Entscheidungen separat journalisieren und auswerten.

## 2026-11-07 — D-018: Administratives E-Mail-Recovery

**Status: bestätigt, Q24.** Kurze Einmalchallenge an bestehende Adresse,
kein gleichzeitiger Adresswechsel; administrativer kontobezogener Faktorreset,
Sitzungs-/Tokenentzug, erneute Passwortanmeldung und MFA-Neuregistrierung.
Normale Faktoränderungen weiterhin mit MFA. Postfachabhängiges Restrisiko
aus D-016 bleibt bestehen; Laufzeitabnahme vor Pilotbetrieb.

## 2026-11-07 — D-019: MT5 auf separatem Heimnetzserver

**Status: Nutzerangabe und Integrationsauftrag, Q25.** MT5 läuft auf einem
anderen Server im Heimnetz. Neue Bridge ausgehend per authentifiziertem HTTPS
zu diesem System, keine eingehenden Routerports. Getrenntes Brokerdemo,
Tenant-/Geräte-/Kontobindung, ein Writer und persistentes lokales Journal.
Konkretes OS/Terminalbuild/Instanz nicht remote geprüft. Keine Hoständerung erfolgt.
Plan: [mt5-bridge.md](../mt5-bridge.md).

## 2026-11-07 — D-020: Validierungsmaßstab

**Status: bestätigt, Q26.** Mindestens drei Jahre Crypto und zwei Jahre
brokerpassendes Gold als Datenziel; chronologische getrennte Fenster und
ungeöffneter unabhängiger Holdout. Wirtschaftlicher Filter im Holdout:
positiver Nettoertrag, PF ≥1,2, mindestens 30 geschlossene Baskets je
Crypto-Asset beziehungsweise 100 Goldtrades. Historienlücken und zu geringe
Stichprobe sind kein bestandener Nachweis; technische Paperbeobachtung möglich.
Verfahren vor Optimierung einfrieren. Kein statistischer Gewinnbeweis.

## 2026-11-07 — D-021: Pilotbackupziele

**Status: bestätigt, Q27.** RPO 24 Stunden/RTO vier Stunden; tägliche
verschlüsselte externe Sicherung auf kostenloses kontrolliertes Ziel,
zusätzliche geschützte Offlinekopie und getrennte Schlüsselaufbewahrung.
Konkretes Ziel und Restoretest vor Pilotfreigabe; noch kein Laufzeitnachweis.
Echtgeldanforderungen an späterem Gate gesondert entscheiden.

## 2026-11-07 — D-022: Erster Release und Ausbaugrenzen

**Status: bestätigt, Q28.** M1 Cockpit/MFA/Tenants/Portfolio/Journal/Backtests
und beide Paper-/Demopfade. Echte KI-Bewertung und vollständige News-/
Kalenderfeeds folgen als Ausbau, Schnittstellen vorsehen.
Echtgeldbudgets, FTMO-Kontoregeln, externe AI-Provider und Kundenbetrieb
ausdrücklich erst vor ihrem späteren Gate entscheiden.

## 2026-11-07 — D-023: Manuelle Pufferfreigabe und Nutzerinformation

**Status: bestätigt, Q29/Q30.** Nach fünf abgeschlossenen regulären Stufen
maximal eine manuell bestätigte zusätzliche Stufe innerhalb ursprünglicher
Reserve; kein RSI-Signal erforderlich, Kaufpreis höchstens 95 % des letzten
regulären Fill-VWAP. Vorschau und frische MFA; Kontolimits, −55%-Exit,
Gewinnschutz, Datenfehler und ungeklärte Orders können den Kauf sperren.
135,53 USDT gerundete Reserve im 500-USDT-Kaufprincipal, 5 USDT Kostenreserve
für den ganzen Basket. Einmalige Cockpitmeldung plus einschaltbare E-Mail;
keine automatische Order oder −40%-Alarmgrenze.

Alle M1-Sachentscheidungen sind damit geklärt. Q31 bestätigt anschließend das
gemeinsame Verständnis und den Übergang zur lokalen Implementierung (D-024).

## 2026-11-07 — D-024: M1-Umsetzung und lokale Autonomie

**Status: bestätigt, Q31 und anschließende Nutzeranweisung.** Implementierung
beginnen und lokale Tasks/Kommandos selbstständig ausführen; konkrete
Zwischenabnahmen melden. Kein erneutes Warten auf Routinegenehmigungen.
Produktionsrollout, externe Nachrichten und Echtgeld behalten ihre eigenen
Grenzen. Lokaler Featurebranch `feat/m1-foundation`; vollständiger M1-Pilot
und erstes überprüfbares Fundament sind unterschiedliche Abnahmen.

## 2026-11-07 — D-025: Reproduzierbares privates Fundament

**Status: umgesetzt innerhalb bestätigter Architektur.** Fünf gepinnte
Compose-Dienste mit Nonroot, Ressourcenlimits und dienstbezogenen Secrets.
Nur Caddy veröffentlicht Loopback-HTTPS; interne API/DB/IdP-Verbindungen
mit CA-Prüfung/TLS. PostgreSQL trennt Migration, Runtime und IdP, FORCE RLS
und zusammengesetzte Fremdschlüssel begrenzen Mandantenzugriffe.
Cockpit verwendet OIDC-Codeflow/PKCE und verschlüsselte serverseitige
Sitzungen; Browser erhält keine Broker-/IdP-Tokens. Pins:
[runtime-pins.md](../runtime-pins.md). Testidentitäten und CA sind lokale,
ignorierte Entwicklungsdaten, keine Produktionscredentials.

## 2026-11-07 — D-026: Crypto-Riskstop und Referenzsimulation

**Status: implementierte Auslegung bestätigter Schutzregeln.** Der −55%-Exit
sperrt den betroffenen Basket bis zu bewusster Wiederaufnahme nach Flat/
Abgleich; gewöhnlicher Gewinnexit setzt diese Risikosperre nicht.
Kostenannahmen der Referenzsimulation sind explizite Forschungsparameter,
noch keine kalibrierten Bitget-Gebühren/Spreadwerte. Manuelle Reserve bleibt
im automatischen Referenzlauf Cash; Domainvorschau ersetzt keine reale
MFA-Schrittbestätigung und keinen brokerseitigen Fill.

## 2026-11-07 — D-027: Frischer OIDC-Login mit Authelia

**Status: Kompatibilitätsfix im bestätigten MFA-Ablauf.** Authelia 4.39.28
behandelt `max_age=0` im Consentformular dauerhaft als erneuten Loginbedarf.
Das laut OIDC Core gleichwertige `prompt=login` wird verwendet; zusätzlich
muss die signierte `auth_time` mindestens dem gespeicherten Flowstart
entsprechen. Frühere Authentifizierung wird auch innerhalb der Uhrtoleranz
abgewiesen; `amr=mfa`, Nonce, PKCE und Signatur bleiben verpflichtend.
Quellen: [OIDC Core](https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest),
[Authelia util.go](https://github.com/authelia/authelia/blob/v4.39.28/internal/oidc/util.go).

Späterer Befund D-036: Dies beweist eine frische Anmeldung, keine erneute
Verwendung des zweiten Faktors. Sensitive Actionfreigaben bleiben zusätzlich
an den bestätigten Cockpit-Passkey gebunden.

## 2026-11-07 — D-028: GitHub-Zwischenstände

**Status: ausdrücklich beauftragt.** Geprüfte Zwischenstände committen und
auf GitHub pushen, bestehende Host-Deploy-Identität verwenden. Foundation
`5fe3a2e` auf `feat/m1-foundation` gesichert. Remote-Historie vor Push live
abgeglichen; der historische Credentialpfad war bereits auf remote main.
Neue lokale Testsecrets sind ausgeschlossen. Rotation/Historyremediation
bleibt IP-005; keine daraus abgeleitete Rewrite-/Force-Push-Freigabe.

## 2026-11-07 — D-029: Eingefrorene Daten und tenantgebundener Researchworker

**Status: umgesetzt im bestätigten PostgreSQL-/Workerentwurf.** Streng validierte
`marketdata-snapshot/1`-Artefakte speichern Datenhash und vollständigen
Contenthash. Jobs frieren Dataset, Strategie und Kosten bei Annahme ein;
Snapshot und terminales Ergebnis bleiben immutable. Operatorimport nutzt die
Migrationsidentität, der Offlineworker eine eigene LOGIN-Rolle je Tenant.
`SESSION_USER`-Bindung, eingeschränkte Security-Definer-Funktionen und
Attempttoken/Lease/Heartbeat verhindern fremde Tenantwahl und veraltete
Abschlüsse. Keine API-/BFF-/Brokersecrets, kein Internetimport im Worker.
Bestehende Jobs ohne Snapshot sind ausdrücklich `dataset_missing` fehlgeschlagen.

## 2026-11-07 — D-030: Forschungsresultat und Validierungsstatus

**Status: konservative Anzeige innerhalb bestätigter Nachweisregeln.**
`backtest-result/1` enthält Netto-PnL, Drawdown, geschlossene Baskets, nullable
Profitfaktor, Equitykurve sowie Daten-/Simulations-/Konfigurations-/Kostenhash.
Kostenannahmen und synthetische Daten sind sichtbar; automatische Referenzläufe
lassen den manuellen Puffer als Cash. Keine künstliche Schließung am Datenende.
Öffentliche 90-Tage-BTC-Daten dienen dem Funktionsnachweis, nicht dem
Dreijahres-/Holdoutgate. `validation=not_evaluated` bleibt verpflichtend;
Holdouts sind im gewöhnlichen Researchpfad weder lesbar noch ausführbar.

## 2026-11-07 — D-031: Nutzergebundener Bitget-Key und Classic-Konto

**Status: ausdrücklich präzisiert nach Q31.** Nutzer besitzt finanziertes Spot-
und Futureskapital; Folgefrage bestätigt Classic mit getrennten Wallets.
Jeder Plattformnutzer erstellt einen eigenen dedizierten API-Key im eigenen
Bitget-Konto. Erste private Integration nutzt Classic V2 mit UID-/Parentbindung
und strikt getrennten Walletgrößen. M1 liest echte Konten und handelt Paper;
Futures-/Echtgeldaktivierung wird aus Guthaben oder Keyeinrichtung nicht abgeleitet.
Keine automatischen Transfers oder UTA-Migration. Geschützte Triple-Eingabe und
Credentialverschlüsselung sind vor echter Keyannahme erforderlich.
Plan und Quellen: [bitget-connection.md](../bitget-connection.md).

## 2026-11-07 — D-032: Isolierter Classic-Readkern vor echter Keyannahme

**Status: umgesetzt innerhalb der bestätigten M1-Lesegrenze.** Stdlib-Adapter
erlaubt ausschließlich Kontoinfo, Spotassets und Futureskonten als feste
signierte GET-Pfade. Eine Kontoinfoprobe prüft Rechte und erwartete IP, lernt UID
und ermöglicht die anschließende feste Nutzer-/UID-/Parentbindung.
Walletdaten benötigen diese Bindung und frische Kontoinfo; getrennte Modelle
erzeugen kein gemeinsames Handelsbudget. 24 erfundene Offline-Tests und
unabhängiger Review bestanden. Kein echter Key angenommen oder Konto verbunden.
Vault, API/UI, tatsächliche Egress-IP, atomare DB-Bindung und gemeinsame UID-Quota
bleiben Integrationsvoraussetzungen. Keine neue Paketabhängigkeit.

## 2026-11-07 — D-033: Isolierte AEAD-Envelopes im Credentialentwurf

**Status: umgesetzt innerhalb des bestätigten AEAD-/Tenant-/Kontoplans.**
AES-256-GCM aus exakt/hashgepinntem `cryptography==50.0.2`, eigene zufällige
DEKs pro Credentialpayload und versionierte KEKs. Getrennte AAD-Domänen binden
Tenant/Nutzer/Konto/Verbindung/Broker-UID/Parent/Classic-Leseprofil/Revision;
die KEK-ID gehört zusätzlich zur Wrap-AAD. Rewrap prüft beide alten AEAD-Schichten
und erhält Payloadciphertext/-nonce. Nur explizite Ciphertextserialisierung;
keine eigene Kryptografie und keine Entschlüsselung in Research.
20 Tests und unabhängiger Review bestanden. Separater Hashlock/Offline-
Checkcontainer; keine API-/Researchdependencyänderung. Betriebsschlüsselprovider,
DB-/Serviceautorisierung, Antirollback und externer Restore sind noch offen.

## 2026-11-07 — D-034: Persistenter Credentialstore mit gebundener DB-Identität

**Status: umgesetzt im bestätigten Credential-/PostgreSQL-Entwurf.**
Migration003 trennt Credentialtabellen von API und Research; FORCE RLS und feste
Security-Definer-Funktionen mit `pg_catalog`-Suchpfad. Eine schmale LOGIN-Rolle
bindet tatsächlichen SESSION_USER an einen aktiven Tenant/Nutzer mit owner/trader-
Mitgliedschaft. Gefährliche Rollenflags, fremde Mitgliedschaften und
Delegationsrechte sperren den Zugriff. Caller-GUCs begründen keine Rechte.
Pythonstore authentifiziert aktuelle persistierte Bindung; Revision und
Speicherversion verhindern veraltete Änderungen. KEK-Rewrap erhält Payloaddaten.
Widerruf ist terminal, auch bei pausiertem Konto oder fehlendem alten KEK möglich.
Globale Broker-UID- und Kontoeindeutigkeit bleibt nach Widerruf erhalten;
kontrollierte Wiederanbindung folgt BL-023.

37 Client-/PG-Tests, vier Provisionierungstests und eine tatsächliche
zurückgerollte Driftprobe bestanden; unabhängiger Review eingearbeitet.
Migration003 nur in separater Fixture-DB angewendet,001/002 unverändert.
Das administrative Prüfprofil besitzt Migrationscredentials; nur die drei
Credential-Testlogins sind auf die Fixture-DB begrenzt. Keine neuen Paketversionen,
CI/CD-Tools, Betriebskeys oder Brokerkontakte. KEK-Provider, HTTP/MFA-Anbindung,
vollständiger DB-Rollbackschutz und externer Restore bleiben IP-009/BL-022.
Grundlagen: [PG18 Definerfunktionen](https://www.postgresql.org/docs/18/sql-createfunction.html),
[RLS](https://www.postgresql.org/docs/18/ddl-rowsecurity.html),
[Zeilensperren](https://www.postgresql.org/docs/18/explicit-locking.html).

## 2026-11-07 — D-035: Einmalig autorisierte private Bitget-Einrichtung

**Status: umgesetzt innerhalb des bestätigten Credential-/Classic-Entwurfs.**
Der private Python-Ablauf verbindet die bestehende Classic-Probe mit einem
kanonischen verschlüsselten Keytriple und dem gebundenen Store. Eine gesonderte
BFF-to-Credential-Assertion bindet Aktion, POST-Ziel und unveränderten Bodyhash;
feste Claims verlangen MFA und Authzeit ab Schrittflowstart. Migration004
konsumiert die globale JTI vor der Probe und hält einen statischen privaten Audit.
Aktuelle Identität/Auth-Epoch, Reauth, Konto, Ablaufzeit und beide Versionen
werden nach der Probe erneut geprüft. Finaler Write und Abschlussaudit teilen
eine Transaktion; auch nach Sperrwartezeiten wird die tatsächliche Uhr geprüft.
Fehler oder Crash öffnen keinen Replayweg; unbekannte Commits werden abgeglichen.
Keywechsel erhält UID/Parent; Widerruf braucht weder Probe noch alten KEK.

SQL verifiziert keine JWT-Signaturen und beweist keine Browser-MFA; direkte
003-Funktionen bleiben vertrauenswürdige Serverprimitiven. Der bestehende
BFF-Login ist keine solche Actionfreigabe. Echter Schrittflow, eigene
Signaturidentität/CSRF, HTTP-Keyeingang und Betriebsschlüsselprovider folgen
BL-021/BL-022. Explizite Entwicklungsdateien prüfen Eigentümer, Modus, Größe und
unabhängig vertrauenswürdige feste Fingerprints; VM-root bleibt außerhalb dieser
Grenze. Annahme-/Retention-/Crashabgleich folgt BL-024. Keine neue Abhängigkeit,
echte Keys, Brokerkontakte oder Produktionsänderung.

120 Tests im gepinnten Python3.14.10-/PG18.6-Prüfablauf bestanden (19 Client,
41 Units, 60 echte PG-Fälle), unabhängige Reviews ohne Restblocker.
004 nur Fixture-DB, gewöhnliche Entwicklungsdatenbank nachweislich weiter002;
001/002/003 unverändert und Migrationschecksummen/idempotenter Lauf geprüft.

Grundlagen: [OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html),
[PG18 Uhrfunktionen](https://www.postgresql.org/docs/18/functions-datetime.html),
[OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

## 2026-11-07 — D-036: Metadaten und Faktorfrische getrennt prüfen

**Status: implementierter Schutzbefund.** Additive005 erlaubt nur dem geprüften
Runtime-LOGIN eine feste Konto-/Verbindungsmetadatenprojektion für aktive
owner/trader mit aktueller Identität/Epoch. Andere Nutzerverbindungen bleiben
auch im selben Tenant403; private Credentialtabellen/-funktionen bleiben gesperrt.
001–005 sind jetzt in beiden lokalen Datenbanken angewendet und immutable.
Vorbereitete Actionzustände binden Sitzung/CSRF/Actor/Tenant/Epoch und eingefrorene
Ziele/Versionen; eigene Bestätigungskennung verhindert Mehrtabverwechslung.

D-027 gilt für frische Anmeldung, nicht für frische Zweitfaktorverwendung:
Authelia4.39.28 erhält beim Passwort-Reauth den alten zweiten Faktor und nutzt
die letzte Faktorzeit für `auth_time`. OIDC-`prompt=login` plus `amr=mfa` reicht
für sensitive Actionfreigaben nicht. Der tatsächliche lokale HTTPS-Test prüft
diese Wiederverwendung. Server und UI bleiben für solche Änderungen gesperrt.
Quellen und Gates: [Passkeys](../passkey-step-up.md).

## 2026-11-07 — D-037: Zusätzlicher Cockpit-Passkey

**Status: ausdrücklich vom Nutzer bestätigt nach D-036.** Kostenlose zusätzliche
Passkey-Bestätigung für Kontoänderungen mit einmaliger Registrierung je Nutzer.
Authelia bleibt der Loginprovider; lokale Prüfzeit ersetzt keine IdP-Claims.
Der isolierte Assertionkern nutzt SimpleWebAuthn14.1.0 mit UV/UP, festem
HTTPS-Origin/RP und serverseitiger Challenge. Aktivierung erst mit dauerhafter
gebundener Registrierung, administrativem Erstzugang, CAS/Counter/Widerruf,
Audit und echtem Browsernachweis. Diese technischen Gates folgen IP-033.
Keine echte Keyannahme, Brokerkontakte oder Pilotveröffentlichung.

## 2026-11-07 — D-038: Dauerhafte Registry und administrativer Erstzugang

**Status: lokale Umsetzung der bestätigten Passkeyergänzung.** Additive006
speichert einen unveränderlich gebundenen Publickey je Tenant/Nutzer/RP unter
FORCE RLS; Credential-ID bleibt RP-weit auch nach Widerruf reserviert.
Ein manuell E-Mail-bestätigter Operator stellt ein32-Byte-Einmalticket aus;
DB speichert nur Hash, CLI nur geschützte neue Datei. Ticket maximal600s,
Claim/Enrollment maximal120s. Claim committed vor Browser-/Kryptoprüfung;
Fehler, Crash oder unbekannter Commit geben ihn nicht frei.
Registry-/Versions-/Counterupdate und Audit bleiben atomar. Sperrfolge
Actor → Tenant/Nutzer/RP-Slot → Ticket/Key vermeidet fehlende-Zeilen-Races.
Adminwiderruf sperrt den Nutzer zuerst exklusiv und erhöht seine globale
Auth-Epoch/`reauth_after`; damit sind alle Tenant-Sitzungen ungültig.
Terminaler Ersatz-/Recoveryweg bleibt BL-025.

Lokales BFF-Enrollment bindet Sitzung/CSRF, Identität/Epoch, RP und aktuellen
HTTPS-Origin. ES256/UV/UP/`fmt=none`-Registrierung ist ein Kandidat ohne
Attestierungssignatur. Erst eine separate frische Assertion darf später
eine sensitive Freigabe ermöglichen. SQL-CAS allein beweist bei Counter0
keinen Challenge-Replayschutz; kein HTTP-CAS, Actiongate bleibt geschlossen.
Browser-/Geräteabnahme und zielgebundene Grants bleiben IP-033.
Abschlussbelege:528 automatisierte Tests,48 tatsächliche HTTPS-Prüfpunkte,
Typecheck, gepinnte Builds und beide idempotenten Migrationsläufe grün.
Unabhängige SQL/API- und Cockpitreviews ohne Restblocker. Positiver vollständiger
BFF-Enrollmentablauf und reale Geräteabnahme bleiben ausdrücklich offen.
[W3C](https://www.w3.org/TR/webauthn-3/#sctn-registering-a-new-credential),
[PG18-Sperren](https://www.postgresql.org/docs/18/explicit-locking.html),
[Definerfunktionen](https://www.postgresql.org/docs/18/sql-createfunction.html).

## 2026-11-07 — D-039: Öffentliche TLS-Konfiguration getrennt vorbereiten

**Status: geprüfter Vorschlag, Aktivierung nicht freigegeben.** Nutzer meldet
Browserzugang mit SSL-Fehler. Tatsächliche Prüfung zeigt DNS auf diesem Host,
nurLoopback8443, abgewiesene80/443 und fehlende Anmeldedomain.
Eine bereits laufende öffentliche TLS-Terminierung ist hier nicht nachgewiesen.

Separates opt-in Overlay verwendet den gepinnten Caddy mit einzigem
Let’s-Encrypt-Issuer, zentralen expliziten80/443, getrenntem ACME-/Sessionzustand
und passenden Origin-/Issuer-/Cookie-/RP-Werten. Standardprofil bleibt lokal.
Geschützter Renderer übernimmt nur unveränderte synthetische Quellkonfiguration,
kein automatischer DNS-/Dienst-/Identitäts-/DB-Eingriff.

Sechs Tests, Compose-Grenzprüfung und gepinnte Caddy-/Autheliavalidatoren grün;
unabhängiger Review nach PEM-Grammatikkorrektur ohne Restblocker.
Neue Issueridentität und RP benötigen bewusste Provisionierung/Registrierung;
alte Bindungen bleiben erhalten. Keine Zertifikatsanfrage oder Aktivierung.
[Befund und Freigabegates](../https-entry.md).

## 2026-11-07 — D-040: Öffentliche Entwicklungsvorschau freigegeben und aktiviert

**Status: ausdrücklich bestätigt und umgesetzt.** Nach Einrichtung der
Anmeldedomain bittet der Nutzer um Freischaltung zum Betrachten des Fortschritts.
Die Freigabe umfasst die synthetische Entwicklungsvorschau über den zentralen
Edge; vollständiger Privatpilot, Produktion und Echtgeld bleiben separate Gates.

Beide Domains lösen auf5.45.96.83 auf. Caddy liefert gültige Let’s-Encrypt-
Zertifikate bis2027-02-05; nur80/443 sind veröffentlicht. Separate ACME- und
Cockpitsitzungsordner, interne TLS-Prüfung und eingeschränkte Dienstrechte bleiben.
Neustart erhält Zertifikate; automatische Erneuerung/Ablaufalarm/externes Restore
bleiben BL-026.

Der öffentliche Issuer erzeugt bewusst einen weiteren synthetischen Nutzer,
gebunden an genau den bereits vorhandenen Entwicklungstenant. Alter Nutzer,
Faktoren, Workerbindung und Datasets bleiben erhalten; keine Übertragung von
Credential-/Passkey-Eigentum. Passwort und TOTP bleiben erforderlich.
Zwölf Helpertests und48 öffentliche HTTPS-Prüfpunkte einschließlich tatsächlicher
Backtestausführung/SVG/Logout bestanden; unabhängiger Review ohne Blocker.
IP-035 erledigt. [Zugang und Betrieb](../https-entry.md).

## 2026-11-07 — D-041: Dauerhafter interner Passkey-Aktionsnachweis

**Status: Umsetzung der bereits bestätigten zusätzlichen Passkeyprüfung.**
Der Nutzer bestätigt den öffentlichen Browserlogin mit Google Authenticator,
meldet den HTTPS-Branch als gemerged und beauftragt Fortsetzung.
Merge `35960f3` in Main `e741c6b` verifiziert; neuer Checkpoint IP-036.

Additive007 speichert zielgebundene Einmalnachweise mit eingefrorenen
Kontometadaten/CAS, Faktorversion und Sitzung/CSRF/Origin. RP-weite
Challenge-Eindeutigkeit schützt auch Counter0; höchstens acht gültige Nachweise
je Actor/Tenant/RP. Claim committed vor Kryptoprüfung, Counter und Grant
atomar, Bestätigung nur mit der eigenen Vorschaukennung. Ablauf und Bindungen
werden nach Sperrwartezeiten erneut geprüft; Registrierungsinsert wird über
die bestehende Kontozeile serialisiert. Unbekannte Commits öffnen keinen Replay.

Originale OIDC-Claims und Loginzeit bleiben unverändert; `checked_at` beschreibt
separat die tatsächliche Passkeyprüfung. API/SQL vertrauen dem signierten BFF
und dessen Kryptoverdict. Der interne Nachweis meldet `execution_enabled:false`.
Browserintegration und003/004-Credentialfreigabe bleiben separate geprüfte
Schritte; dieser Checkpoint öffnet keine Keyannahme oder Brokeraktion.

724 Prüfungen grün:461 API/Worker (70 neue tatsächliche PG),143 Cockpit
(28 neue synthetische P256-Abläufe),120 Credentialregressionen. Typecheck,
gepinntes Imagebauen und unabhängige Reviews ohne Restblocker.
Beide DBs001–007 immutable; Vorschaucontainer nicht neu erstellt.
Vollständiges BFF-Enrollment und reale Geräteabnahme bleiben IP-033,
Retention/Ratenbetrieb BL-017 und Recovery BL-025.
[Vertrag und Prüfbelege](../passkey-action-proofs.md).

## 2026-11-08 — D-042: Passkey-Prüfseite und synthetischer vollständiger BFF-Ablauf

**Status: Umsetzung der bestätigten Passkeyprüfung; keine neue Konto-/Betriebsfreigabe.**
Der Nutzer bestätigt den Merge und beauftragt Fortsetzung. `9b47ae1` und
`4c9f63f` in Main `2c996d5` verifiziert; IP-037 auf eigenem Featurebranch.

Die separate Seite zeigt Konto/Aktion, fordert eine frische Assertion und
bestätigt genau die eigene Vorschau einmalig. Vier POST-Routen und Oberfläche
verlangen `COCKPIT_PASSKEY_PROOF_PREVIEW=1`; Default und öffentliche Vorschau
lassen das Flag aus. `execution_enabled:false`, Credentialrouten503 und
keine003/004-Verbindung. Die Sitzung, deren Origin/CSRF den HTTP-Aufruf
autorisierten, wird unveränderlich an den Adapter übergeben und nach allen
asynchronen Grenzen erneut geprüft. Originale OIDC-Claims bleiben erhalten.
Browser erhält nur sichere Projektionen; Vorschaukennung bleibt im Seitenzustand.

Vollständiges Enrollment ist als injizierbare Orchestrierung getrennt,
behält ursprüngliche Sitzungsfrist und atomaren verschlüsselten Versuchsspeicher.
Nach Speicherung verlangt es eine aktuelle autoritative Faktorlesebestätigung.
90 reale isolierte HTTPS/BFF/API/PG-Prüfpunkte mit synthetischen P256-Schlüsseln
und ausdrücklich synthetischer administrativer Freigabe schließen den bisher
offenen positiven BFF-Durchlauf.9 deaktivierte Prüfpunkte ohne Mutation,
265 Cockpittests, Typecheck/Build und8 Vorbereitungstests bestanden.
Unabhängiger Review nach Sitzungs-/Dateivorbereitungskorrekturen ohne Restblocker.

Prüfdienste verwendeten eigene Testkeys und feste geschützte Fixtureablage,
keine Hostports; nach Prüfung angehalten. Öffentliche Dienste unverändert,
gesund und TLS200.001–007 bleiben immutable, keine neuen Abhängigkeiten.
Physischer `navigator.credentials`-Aufruf, echte E-Mail-Attestierung, öffentliche
Aktivierung, Credentialintegration, Recovery und Betrieb sind nicht abgenommen.
[Ablauf/Gates](../passkey-browser-proof.md),
[SimpleWebAuthn14.1.x](https://simplewebauthn.dev/docs/packages/server),
[W3C Assertionprüfung](https://www.w3.org/TR/webauthn-3/#sctn-verifying-assertion).

## 2026-11-08 — D-043: Separater Passkey-Credential-Vertrag vor dauerhafter Integration

Nutzer bestätigt Merge und beauftragt Fortsetzung. Checkpoint84f7633 in
Main512c096 verifiziert; IP-038 auf eigenem Featurebranch. Der bisherige
Credentialvertrag/004 setzt eine frische IdP-Zeit voraus, während007 die
ursprüngliche Loginzeit bewahrt. `checked_at` ersetzt diese Zeit nicht.
Ein neuer isolierter Vertrag erhält deshalb getrennte Audience und Zweckkind,
eigene Authorization-ID und unveränderliche Actor-/Sitzungs-/Ziel-/CAS-/
Metadaten-/Bodybindung. Keine erfundenen AMR-Claims, keine Änderung alter
Prüfregeln und keine neue Strategy-/Betriebsfreigabe.

Signer/Verifier sind wiederholbare vertrauenswürdige Primitive. Ein strukturell
gültiger Zweckreceipt beweist hier keine DB-Ausgabe oder aktuelle Autorität.
Die007-Funktionsbestätigung ist keine Schreibzustimmung. Eine künftige008 muss
ausdrückliche Credentialautorisierung global einmalig vor Probe konsumieren,
aktuellen Actor/Epoch/Reauth/Faktor/Metadaten bei Annahme und Write prüfen
und Mutation/CAS/Audit atomar abschließen. Unbekannte Commits abgleichen.
001–007 bleiben immutable; keine neue HTTProute oder Credentialausführung.

Reale TS/Jose-/Python-Interop mit synthetischen Keys/Receipts ist offline geprüft.
Ein optionales gehärtetes Offlineprofil nutzt das bestehende gepinnte
Prüfimage ohne Netzwerk/Secrets/Mounts/DB; bestehende Dienste bleiben unverändert.
[Vertrag/Gates](../passkey-credential-assertions.md),
[RFC8725 §3.12](https://www.rfc-editor.org/rfc/rfc8725.html#section-3.12),
[OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html).

## 2026-11-08 — D-044: Dauerhafte Zweckfreigabe vor separater Credentialausführung

Nutzer bestätigt Merge8bb64db/Main13ba2e2 und erneut autonome lokale Befehle.
IP-039 ergänzt008 auf eigenem Featurebranch. Zweck, Origin und Bodydigest werden
bereits bei Vorbereitung atomar mit007 eingefroren. Eine ausdrückliche
Credentialzustimmung bestätigt den noch lebenden Grant und stellt einen
eigenen Receipt aus; eine007-Funktionsbestätigung wird nicht nachgerüstet.

Der private Pythonclient prüft den30-Claim-Vertrag vor DB-Zugriff.008 konsumiert
die eigene Freigabe global einmalig, bevor ein späterer Probeexecutor starten
darf. Erst ein bestätigter Commit erzeugt den privaten Handle. Eine andere
Transaktion prüft dieselben Claims sowie aktuellen Actor/SESSION_USER/Epoch/
Reauth, Faktor, Metadaten/CAS und Fristen unter geordneten Sperren erneut.
Ihr erfolgreicher Lockcommit ist terminal. SQL vertraut der Python-/BFF-
Signaturprüfung; keine universelle MFA-Garantie für direkte003-Primitive.
Unbekannte Commits werden nicht automatisch wiederholt.

008 zunächst nur Fixture-DB; investalo001–007 und öffentliche Dienste bleiben
unverändert. Keine HTTProute, Brokerprobe, echte Keyeingabe oder003/004-Ausführung.
Vorprüfung mit vollständigem Rollback prüft DDL und echte Runtimevorbereitung,
bevor der neue Checksum in der Fixture-DB festgeschrieben wird. Frühere
Migrationen bleiben immutable. [Zweckgrenze/Prüfbelege](../passkey-credential-authorizations.md),
[PG18-Sperren](https://www.postgresql.org/docs/18/explicit-locking.html),
[PG18-Definerfunktionen](https://www.postgresql.org/docs/18/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).

## 2026-11-08 — D-045: Private Passkeyausführung mit atomarem Abschluss

Nutzer bestätigt Merge `389082a` und beauftragt Fortsetzung. Main `be13145`
verifiziert; IP-040 auf `feat/m1-passkey-credential-execution`.
Der neue private Executor verbindet008-Verbrauch vor Credentialread/Probe
mit einer separaten finalen Transaktion aus008-Lock,003-AEAD-Mutation und
009-Abschlussaudit. Ursprüngliche OIDC-Zeit und alle neuen Zweckbindungen
bleiben erhalten. Der alte004-Vertrag wird nicht als Brücke verwendet.

009 ergänzt eine immutable FORCE-RLS-Terminaltabelle. Abschluss verlangt
identische authentifizierte Claims, SESSION_USER und aktuellen Lock-XID
sowie den exakt erlaubten neuen Connectionzustand. Die bisherige Prüfung
alter Metadaten kann nach der gewollten Mutation nicht erneut verwendet werden;
Account/Actor/Faktor bleiben aktuell gebunden. Frist nach Auditwartezeiten
prüfen, dann an den Commit übergeben. Widerruf benötigt weder Broker noch
Entschlüsselung und bleibt für pausierte Konten verfügbar.

Fehler rollen Lock, Write und Abschluss zurück; der vorherige Verbrauch bleibt.
Fehleraudit ist best effort und verleiht keine neue Autorität.
Verlorene Commitantworten erlauben keine automatischen Wiederholungen und
überschreiben keinen bereits bestätigten Erfolg. SQL vertraut weiterhin dem
privaten Verifier/BFF/Probe; direkte003-Primitive bleiben vertrauenswürdig.
009 nach vollständig zurückgerollter DDL-/echter Failure-Abschlussvorprüfung
nur Fixture-DB,001–008 unverändert. Keine HTTP-/öffentliche/echte Brokeraktivierung.
[Ablauf/Grenzen](../passkey-credential-execution.md),
[PG18-Sperren](https://www.postgresql.org/docs/18/explicit-locking.html),
[OWASP Transaktionsfreigabe](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html).

## 2026-11-08 — D-046: Privater Cockpitablauf mit ausdrücklichem Credentialzweck

Nutzer bestätigt Merge `3476f74`; Main `0fd25b6` verifiziert.
IP-041 verbindet die vorhandenen007/008/009-Grenzen über einen injizierten
Cockpitkern und zwei standardmäßig deaktivierte interne API-Routen.
Die vollständige ursprüngliche `ProofSession` wird vom bereits autorisierten
Aufrufer übergeben und nach Await-Schritten erneut verglichen.

Ziel aus eigener aktueller Metadata ableiten; private Bodybytes genau einmal
erzeugen und hashen.008 friert Zweck, Origin und Digest vor WebAuthn ein.
Fortsetzungen enthalten nur Korrelation/Digests und sichere Snapshots.
Eine separate Credentialzustimmung führt über008 zum23-Feld-Receipt;
007-Funktionsbestätigung bleibt unverändert. Nach008 keine erneute007-
Grantabfrage, sondern gespeicherter Grant plus aktuelle Bindungen prüfen.
Der separate Signer stellt den exakten Token für den privaten Executor aus.

Die integrierte Prüfung benutzt echtes SimpleWebAuthn/Jose, HTTPS/API/PG und
den Python-/AEAD-/009-Executor mit synthetischen Schlüsseln und Brokerantworten.
Ein gehärtetes Opt-in-Profil mit interner Testnetwork, ohne Hostports und
ohne Logs, reicht bounded Daten ausschließlich durch Prozesspipes weiter.
Nur der administrative Pythonchecker besitzt Fixture-DB-Credentials.
Dieser Prüfaufbau ist kein Runtime-Credentialdienst.

Keine neue Migration oder Änderung angewendeter001–009. `investalo` bleibt
001–007. Browser-Keyeingabe, provisionierte Signatur-/Betriebsidentität,
realer Credentialdienst/Transport/Egress und physische Geräteabnahme bleiben
gesondert; öffentliche Dienste/Flags werden nicht aktiviert.
[Vertrag und Prüfbelege](../passkey-credential-cockpit.md),
[OWASP Transaktionsfreigabe](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html),
[OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## 2026-11-08 — D-047: Getrennte lokale Credential-Transportidentität

**Status: umgesetzt innerhalb der bestätigten lokalen Anbindung.** Nutzer
bestätigt Merge `cd66c3a`; Main `c573ab3` verifiziert und Fortsetzung beauftragt.
IP-042 verwendet gegenseitiges TLS mit einer eigenen CA und festem
BFF-Clientzertifikatsfingerprint unabhängig vom vorhandenen Passkey-JWT.
Der erwartete ursprüngliche Sitzungskontext kommt separat vom
vertrauenswürdigen BFF; Claims dürfen diesen Kontext nicht selbst begründen.
Tenant/User und Credential-LOGIN bleiben feste Serverkonfiguration.
Keine Änderung der bestehenden AEAD-/Signatur-/SQL-Strukturen.

Nur injizierte Entwicklungsadapter ohne neue Abhängigkeiten, Provider oder
Produktionslauncher. Python warnt vor `http.server` in Produktion; der
zusätzlich begrenzte Adapter bleibt daher ein lokaler Prüfstand. Die
synthetische administrative Fixture beweist kein Least-Privilege-Runtime-
Deployment oder physischen Besitznachweis. Tatsächliche Keyannahme,
Betriebsprovider, geeigneter Produktionsserver und Browserabnahme bleiben offen.
Keine öffentlichen Flags, laufenden Dienste oder Migrationen aktiviert.

Der Nutzer weist erneut auf den kurzen Bitcoin-Zeitraum hin. Dies bestätigt
D-020/D-030:90 Tage prüfen den Ablauf; mindestens drei Jahre BTC/ETH-Historie,
chronologische Fenster und unabhängiger Holdout bleiben IP-011/IP-013/BL-018.
[HTTP-/TLS-Grenze](../passkey-credential-https.md),
[Python Servergrenzen](https://docs.python.org/3.14/library/http.server.html),
[Node HTTPS](https://nodejs.org/api/https.html).

## 2026-11-08 — D-048: Synthetischer Credentialdienst mit eigener Runtimeidentität

**Status: lokal implementiert und geprüft.** Nutzer bestätigt Merge `94fb73b`;
Main `6300971` verifiziert und Fortsetzung beauftragt. IP-043 konkretisiert
die bestehende Entwicklungsgrenze durch einen getrennten Container.
Der administrative Checker provisioniert und prüft Testdaten; ausschließlich
der Dienst konsumiert008 und führt003/009 aus. Runtime erhält weder
Migrations-/API-Credentials noch den privaten BFF-Clientschlüssel.

Feste Fixture-DB und LOGIN, tatsächliche Rollen-/Actor-/Funktionsprüfung
vor dem Listener, explizites `--development`, owned0400-Dateien und
separate32-Byte-Identitäten mit festen Pins. Umgebungsdaten und Requests
wählen keine Rolle oder Schlüssel; `PG*`-Umgebung wird abgewiesen.
Nur exakte synthetische Credentials werden vor Verifier/Consume akzeptiert.
Keine Änderung an AEAD-, Signatur-, SQL- oder Strategieverträgen.

Jeder Lauf erstellt neue UUID-Ablagen einmalig und prüft die tatsächlichen
Container-Mounts/Härtung mit begrenzten Metadaten. Kein neuer externer
Schlüsseldienst, keine Abhängigkeiten oder Migrationsaktivierung.
Der stdlib-HTTP-Server bleibt Entwicklungsprüfstand. Produktionsserver,
Betriebsidentitäten/-provider, reale Broker-/Egressprüfung und Browserabnahme
bleiben eigene Arbeit; öffentliche Dienste und Flags werden nicht aktiviert.
[Dienstgrenze](../credential-development-service.md),
[Docker Compose Services](https://docs.docker.com/reference/compose-file/services/),
[PostgreSQL Verbindungsparameter](https://www.postgresql.org/docs/18/libpq-connect.html#LIBPQ-PARAMKEYWORDS).

## 2026-11-08 — D-049: Kontrollierte Socketübergabe an den gepinnten ASGI-Stack

**Status: lokal implementiert und geprüft.** Nutzer bestätigt Merge `998bb90`;
Main `9f2a9a5` verifiziert und Fortsetzung beauftragt. IP-044 übernimmt
Uvicorn 0.54.0/h11 0.16.0 aus den vorhandenen API-Pins für den isolierten
synthetischen Credentialdienst. Keine neue Version oder CI-Werkzeuge.

Ein kontrollierter Listener begrenzt Verbindungen einschließlich Handshakes
und übergibt Sockets über dokumentiertes asyncio an das gepinnte Protokoll.
Peerfingerprint vor Parser, absolute Frist seit Accept und Rawheader-Guard
vor h11-Normalisierung. Kein kopierter Uvicorn-Serverlebenszyklus.
Die Protokoll-/ServerState-Anbindung bleibt versionsspezifisch und benötigt
bei Upgrades echte TLS-/Framing-/Kapazitätsprüfungen.

Verbindungen und laufende Credentialarbeit getrennt begrenzen. Timeout oder
Disconnect können einen Socket schließen, während ein Commit weiterläuft;
Arbeitsslots erst nach tatsächlichem Worker-Future-Ende freigeben. Ein begrenzter
Threadpool allein verhindert keine unbegrenzte Queue. Keine Wiederholung
oder nachträgliches Failureaudit über unbekanntem Commit.

Launcher, synthetische Guard, Dateiprovider, feste DB-Rolle und unveränderte
Freigabe-/AEAD-Verträge bleiben erhalten. Keine Migration, echte Schlüssel,
Broker-/öffentliche Aktivierung oder Produktionsabnahme.
419 gepinnte Credentialtests/52 Subtests und451 tatsächliche Dienstprüfpunkte
bestanden; beide Pythonbuilds und unabhängiger Review grün. Alle aktuellen
Migrationsprüfsummen normal007/Fixture009 unverändert; Testcontainer beendet,
öffentliche Dienste gesund und reguläres TLS HTTP200.
[ASGI-Vertrag](../credential-asgi-transport.md),
[Python Socketübergabe](https://docs.python.org/3.14/library/asyncio-eventloop.html#asyncio.loop.connect_accepted_socket),
[ASGI TLS-Erweiterung](https://asgi.readthedocs.io/en/latest/specs/tls.html).

## 2026-11-08 — D-050: Browserfortsetzungen ohne gespeicherte Credentialbytes

**Status: lokal implementiert und geprüft.** Nutzer bestätigt Merge `9555624`;
Main `dcb9feb` verifiziert und Fortsetzung beauftragt. IP-045 verbindet
Schlüsseleingabe, zweckgebundene Vorschau, Passkey und ausdrücklichen
Credentialconsent im isolierten synthetischen Prüfstand.
Register erzeugt die neue Connection-ID serverseitig. Gemeinsamer Serializer
erzeugt beim Start im BFF und danach auf der Seite identische private Bytes;
die Antwort enthält nur das sichere Ziel, keine zurückgespiegelten Keys.

Eigener begrenzter Prozessspeicher hält die originalen Core-/Portsbezüge,
weil WeakMap-Fortsetzungen nicht serialisiert werden können. Keine Triples,
Rohbodys, Schlüssel oder JWTs in Session-/Fortsetzungsstorage. Admission vor
Await, Ownerprüfung vor Take, frischer Token nach Finish und ursprüngliche
Frist. Laufende Arbeit bleibt bis Promise-Ende belegt; Unknowncommit nie retry.
Lokale32/2-Limits sind Prüfvorgaben, keine produktiven Quotenentscheidung.

HTTP prüft ursprüngliche Sitzung nach langsamem Body/Origin und nach Execute,
liest UTF8 fatal und projiziert geschlossene sichere Antwortschemas.
Die Seite hat keinen nativen GET-Submit, behält nur private Seitenreferenzen
und verwirft verspätete Antworten nach Abort/Ablauf/Identitätswechsel.
Öffentliche Routes bleiben wegen fehlender BFF-Betriebsprovider gesperrt;
kein Flag erschafft eine Schlüsselidentität. Physische Geräte/Next-Sitzungen,
Keybetrieb, Recovery und echte Brokerabnahme bleiben separate Gates.
540 Cockpittests, Typecheck, gepinnte Cockpit-/Nodebuilds,481 synthetische
Controller-/HTTPS-/Dienstprüfpunkte und sechs tatsächliche gesperrte Next-
Routenchecks bestanden. Unabhängiger Review ohne verbleibenden Blocker;
keine Abhängigkeiten/SQL-Migrationen geändert.
[Browservertrag](../credential-browser-flow.md),
[OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html).

## 2026-11-08 — D-051: Tradingpriorität und mehrjährige Forschung

**Status: lokal implementiert und geprüft.** Nutzer bestätigt IP-045-Merge;
0a0751b ist Vorfahr von Main073c474 (verifiziert). Er fragt ausdrücklich nach
dem eigentlichen Trading-/Backtestsystem. Schwerpunkt jetzt IP-011/012/013
und Paper; weitere Credentialbetriebsaktivierung zurückgestellt. Öffentliche
historische Daten und Simulation brauchen keine privaten Kontoschlüssel.

IP-046 übernimmt die vorhandene öffentliche Bitgetpagination:90 Tage gelten
pro Anfrage, keine Gesamtgrenze. BTC/ETH jeweils vier Jahre2022-08-01 bis
2026-08-01 lückenlos,8766 H4-Kerzen. Vor Leistungsberechnung gefrorenes
technisches Protokoll: erste drei Jahre6576 Kerzen Forschung; anschließend
2190 Kerzen ausschließlich reservierter Holdout. Das bereits ausgewertete
90-Tage-Demo liegt außerhalb. Kein voller Vierjahresimport als Research,
keine Holdoutjobs/Leistungslektüre. Diese konkreten Fenster sind eine
explizite technische Umsetzung, keine Q26 zugeschriebene Splitentscheidung.

Exakte Fensterbildung erhält Preise/Provenienz; vorhandene API-/SQL-/Worker-
Isolation bleibt unverändert. BTC und ETH tatsächlich über HTTPS/MFA/BFF/
Offlineworker gespeichert, jeweils eigene10.000-USDT-Simulation. Read-only-
Audit und direkter Kernreplay reproduzieren wirtschaftliche Werte exakt.
Positive Forschungszahlen sind kein Netto-Holdoutnachweis; Kostenkalibrierung,
Training-/Validierungsauswahl,30 Holdoutbaskets je Asset und PF>=1,2 bleiben
separate wirtschaftliche Abnahme. Keine automatische manuelle Reservetranche.

66 gepinnte Markt-/Tradingtests mit33 Subtests, fünf neue ETH-Clientmetadaten-
Fixturetests,572 API-/Workerfälle gegen Fixture009 und je48 reale HTTPS-
Prüfpunkte bestanden. Unabhängiger Review ohne Blocker. Keine neue Dependency,
Migration oder öffentliche Containerneuerstellung. DB-Prüfsummen normal007/
Fixture009 unverändert; sechs vorhandene Dienste gesund/TLS200.
Nächster konkreter Schritt IP-047: persistentes Paper mit denselben Handels-/
Risikoregeln, simulierten Orders/Fills und Journal, kein Echtgeld.
[Protokoll und Ergebnisse](../long-history-backtests.md),
[Bitget offizielle Historiengrenze](https://www.bitget.com/docs/catalog/market/market-data#get-klinecandlestick-history).

## 2026-11-09 — D-052: Begrenzter inkrementeller Papercheckpoint

IP-046eb62176 ist in Maindd1903b verifiziert. Nutzer verlangt ausdrücklich
sparsamere LLM/API-Nutzung. Scoped Reads, knappe Ausgaben und passende gezielte
Tests; keine zusätzlichen Agentaufrufe für Routine, keine unbelegten Kostenwerte.
IP-048 erweitert den vorhandenen Kern um schrittweise Quotes/H4-Signale und
gebundene Restorecheckpoints mit Journalreceipt. Käufe erst nach späterem
frischem Quote des Assets; kein automatischer manueller Puffer/Resume.
Historische Simulatordefaults/Strategie/Kosten unverändert.84 gezielte gepinnte
Tests/48 Subtests bestanden; keine Migration/Dependency/Dienstaktivierung.
DB-Persistenz muss Zustand und append-only Journal mit Revision-CAS atomar
schreiben. Writer, Feedworker und Cockpitstatus bleiben IP-047; der isolierte
Runner ist noch kein betriebener Paperdienst. [Vertrag](../paper-runner.md).

## 2026-11-09 — D-053: Atomare Paperpersistenz mit eigener Kontorolle

Nutzer bestätigt IP-048-Merge; fe6309a in Maindc60c19 verifiziert.
IP-049 speichert Checkpoint und append-only Journal mit Revision-/Checksum-CAS
in einer Transaktion. Eigene LOGIN-Gruppe und SESSION_USER-Kontobindung,
keine direkten Tabellen-/Credentialrechte oder neuen Runtime-/Researchrechte.
SQL vertraut Python für Handels-/Wirtschaftssemantik; keine Strategieveränderung.
Client verlangt frische Verbindung ohne Autocommit/laufende Transaktion;
Commitverlust wird durch Readback geklärt, nie automatisch erneut geschrieben.

010 nach vollständig zurückgerolltem DDL-/Worker-/Failurepreflight nur in
Fixture angewendet. SHA256:
`812a0a1f1702f09ef3b9410640eae7b60498320326888a86c494a83f8f3f5797`.
Normal007/Fixture010 und sämtliche angewendeten Prüfsummen verifiziert.
HBA nur Fixture-TLS/SCRAM für Papergruppe; PostgreSQL configreload.
Synthetisches Testpasswort aus anfänglichem Verbindungstrace rotiert,
Trace bereinigt, Factoryfehler sanitisiert; keine echten Credentials betroffen.
78 gepinnte Tests/15 Subtests,29 echte PG-Fälle und unabhängiger Review grün.
Keine Builds/Dependencies/öffentliche Dienstneuerstellung; Cockpit TLS200.
Kostenpräferenz bleibt: gezielte Checks, keine breiten Auth-Regressionsläufe.
IP-047 nächster Schritt Marktfeed/laufender Worker/Cockpitanzeige.
[Speichervertrag](../paper-postgres-store.md).

## 2026-11-09 — D-054: Öffentlicher Feed und begrenzte Paperworkerabnahme

Nutzer bestätigt IP-049-Merge; e0cfb45 in Main1a805e5 verifiziert.
IP-050 bindet echte unsignierte BTC/ETH-Spotquotes und geschlossene H4-Kerzen
an denselben Runner/Store.40 Vorlaufkerzen pro Asset, danach lückenlose
Fortsetzung mit revidiertem Overlapcheck; keine historischen Fills.
Realer aktueller Kerzenendpunkt schließt startTime aus: ein vorheriges Intervall
anfragen und Sollabdeckung weiter streng prüfen, keine Strategieänderung.
Konflikt/Fehler => frisches Readback und neue Daten; Unknowncommit beendet
Prozess sofort. Eingeschränkter synthetischer LOGIN/Fixture010, eigene
Entwicklungs-Egressbridge ohne Hostports, keine Admin-/Brokercredentials.

Drei tatsächliche öffentliche Feedzyklen committed82/84/86, Prozessneustart88;
zero fills, kein Profitabilitätsbeleg.151 gepinnte Tests/48 Subtests mit30 echten
PG-Fällen; integrierter synthetischer Signal-/Fill-/Restartfall genau einmal.
Review ohne Blocker für begrenzte Abnahme. Exakte Mitternachtsbaseline aus
bestehendem Runner wird durch REST-Polling nicht zuverlässig erreicht.
Neue Käufe bleiben folglich gesperrt; Dauerbetrieb im CLI ausdrücklich
abgewiesen, nur --once/--cycles1..100. BL-028 verfolgt sichere Tageswechsel-
und Betriebsabnahme. Keine nachträglich erfundene Equity oder Risikowechsel.
Keine Migration/Build/Dependency, normal007/Fixture010-Prüfsummen unverändert.
Einmalcontainer beendet, sechs öffentliche Dienste unverändert/TLS200.
Nächstes IP-047: sichere Tagesbaseline, dauerhafte Entwicklungsidentität und
Paperstatus-/Journalanzeige. [Vertrag](../paper-market-worker.md).

## 2026-11-09 — D-055: Lesender Paperstatus vor Betriebsaktivierung

Nutzer bestätigt Merge; af65c51 in Mainb9d4b41 verifiziert. IP-051 ergänzt
eigene Paperkonten/Status/Journal über restricted Runtimefunktion011,
authentifizierte API und standardmäßig ausgeschaltetes Cockpitpanel.
SQL vertraut der API und transaktionslokalen Identität, recheckt aktiven
Actor/Mitgliedschaft/Epoch/originale OIDC-Zeit. Keine Tabellen-/Writerrechte.
API/TS projizieren erlaubte Felder; Journal enthält nur feste Meldungen.
Gespeicherter Input ist kein Worker-Lebenszeichen. Historische/fehlende
Bewertung, ungestarteter Zustand und Tagesbaseline-Kaufsperre ausdrücklich.

011 nach vollständig zurückgerolltem Preflight und gezieltem unabhängigem
Review nur Fixture-DB angewendet; normal007/Fixture011 und alle Ledger
geprüft.170 gepinnte Tests/48 Subtests (37 tatsächliche PG/API),
16 Cockpit-Vertrags-/SSR-Paneltests, Typecheck/gepinnter Build grün.
Keine neuen Dependencies/breiten Wiederholungen; öffentliche Container
unverändert/gesund, Cockpit TLS200, beide Anzeigeflags aus.

Q32 fragt ausdrücklich nach gekennzeichneter H4-Modellbewertung ausschließlich
für die00:00UTC-Tagesbasis, unverändertem6%-Limit und tatsächlichen Bid/Ask-Fills.
Antwort ausstehend; keine Risk-/Strategieänderung implementiert. Nächstes
IP-047/BL-028: Entscheidung, Tageswechsel, permanente Entwicklungsidentität
und gesonderte Betriebs-/Anzeigeabnahme. [Vertrag](../paper-status-readmodel.md).

## 2026-11-09 — D-056: Q32-Mitternachtsbewertung freigegeben und umgesetzt

Nutzer bestätigt Merge05ea009; Main5d5c61e verifiziert. Er folgt ausdrücklich
der Q32-Empfehlung und erinnert an RSI als Einstiegskriterium.
IP-052 friert die Paper-Tagesbasis um00UTC aus vorherigem Cash/Beständen und
beiden exakt abgeschlossenen H4-Closes ein. Eigener Input/Policy
paper-h4-close/1, atomarer Commit vor neuen Quotes/Fills; kein nachträglicher
Ersatz durch veränderte Tages-Equity. Fehlende/unbelegte Basis sperrt Käufe.
RSI14/Wilder/geschlossene-H4-Einstiege, spätere echte Quotes/Fills,6%/8%,
manuelle Ausnahme Q29 und latched Halts unverändert. Bewertungsinput erzeugt
keine Indikatorfortschreibung. Historische Researchresultate unverändert.

012 erhält Tagesbeleg/Fingerprints über Quotecommits/Neustart und verhindert
geänderte Mitternachtskerzen bei späterer RSI-Verarbeitung. SQL vertraut dem
gebundenen Pythonwriter, keine zweite Berechnungs-/Riskimplementation.
Getrennter Modellhinweis in weiterhin ausgeschaltetem Statuspanel.
Vollständig zurückgerollter tatsächlicher Writer-/Replaypreflight,
unabhängiger Review grün;012 ausschließlich Fixture angewendet.
190 unterschiedliche Fälle/48 Subtests (43PG/API) und17 Cockpitfälle/
Typecheck/gepinnter Build grün; ein ungültiger Test-OHLC korrigiert,
gezielte Wiederholung3. Normal007/Fixture012 und alle Ledger bestätigt,
öffentliche Dienste unverändert/gesund, Cockpit TLS200.
Keine neuen Dependencies/normalen Migrationen/öffentlichen Flagänderungen.
Permanenter Entwicklungsdienst und Betriebs-/Anzeigeabnahme bleiben
IP-047/BL-028. [Vertrag](../paper-midnight-basis.md).

## 2026-11-09 — D-057: Stabile lokale Paperbeobachtung

Mergec1703c1 in Maina996bf2 verifiziert. IP-053: separater fixer Fixture-LOGIN,
synthetisches Konto und geschütztes prepared/bound Manifest; prüfen oder ablehnen,
keine Wiederbindung/Rotation/Unpause. Autocommit-Session-Advisory-Lock vermeidet
Doppelstart, Write-/Healthguards; CAS bleibt atomarer Schutz. Strict feste PG-
Konfiguration, sechs Fehler terminal,24h für neue Zyklusstarts, restart:no.
Keine Änderung RSI/Q32/Risk, keine Dependency/Migration/öffentliche Aktivierung.

44 gepinnte Workerfälle/3 Dateischutzunits und tatsächliche Provisionierungs-
Idempotenz, vier zurückgerollte Driftprobes, TLS/Singleton/Sessionverlust/normale
DB-Verweigerung bestanden. Feed82/84/86, Prozess88 ohne Fills. Lokaler Dienst
healthy, Doppelprozess abgewiesen, kontrollierter Neustart100→102+.
Normal007/Fixture012/hash und öffentliche sechs Dienste/TLS200 unverändert.
Scoped Review ohne Blocker; keine breite Wiederholung oder neuer Build.
Nächste IP-047: Nutzer-/Cockpitanbindung. BL-028 echte Mitternachtsbeobachtung,
Retentions-/Quota-/Egress-/Recoverybetrieb vor längerem Pilotlauf.
[Vertrag](../paper-development-runtime.md).

## 2026-11-09 — D-058: Eigene lesende Paper-Entwicklungsvorschau

03fee1e in Mainb0827ba verifiziert. IP-054: eigenes normales simuliertes Konto
unter bestehendem geschütztem öffentlichen Owner-Tenant, fester LOGIN und
Prepared/Bound-Manifest, keine Fixturekopie oder bestehende Bindungsänderung.
Bewusst begrenzter Einmal-Kurslauf und lesende Anzeige; weiter kein dauerhaft
bestätigter Previewworker. RSI/Q32/Risk/Kosten unverändert,82/zero fills.

008–012 im vollständigen normalen Runtime-/Kontextpreflight zurückgerollt,
danach atomar normal angewendet; beide012-Ledger unverändert. Private008/009-
Capabilities jetzt vorhanden, tatsächliche Flags/Routen bleiben gesperrt.
Exact TLS/SCRAM-HBA nur neue Rolle; Fixture/directtables/otherdefiners denied.
Prepared-Recovery prüft bestehende Rolle vollständig vor Grants; kein Repair.
34 pinned Python/5 stdlib/17 Cockpit und29 tatsächliche HTTPS/MFA/BFF-Prüfpunkte,
pinned builds/scoped Review grün. Eigener Stand auf drei Seiten/no-store,
sensitive Routen503, Prüfsitzung sauber abgemeldet, kein Researchjob.
Nur API/Cockpit der ausdrücklich freigegebenen Entwicklungsvorschau aktualisiert.
Weiter beide Public/Paperoverlays verwenden; nacktes Publicoverlay schaltet
Anzeige aus. Übrige Dienste und ursprüngliche Faktoren/Identitäten unverändert.
Nächste IP-047: eigener begrenzter Preview-Beobachtungsworker; Betrieb BL-028.
[Vertrag](../paper-preview-integration.md).

## 2026-11-09 — D-059: Gemeinsames Basketportfolio und spätere KI-Prüfung

**Status: Planungsziel und Kontolimits bestätigt, Q33.** Nutzer plant3–5
gleichzeitig gehandelte Coins, volle Kontokapitalzuordnung und später eine
Marktanalyse nach RSI-Signalen: Marktphase/Wall Street Cheat Sheet,
Fear & Greed, News und Crypto-Vierjahreszyklus. Hebel und weniger Einstiegs-
stufen im Aufwärtstrend sind mögliche spätere Varianten.

Nach ausdrücklicher Rückfrage bleiben6% Tages-/8% Startkapitalverlust bindend.
Volle Zuordnung ist keine Vollinvestitionsfreigabe. Baskets teilen Equity,
Liquidität, Reservierungen und Risikogates. Bei korreliertem −50%-Stress
verlöre die bisherige beispielhafte5%-Staffel nach fünf regulären Stufen
31,49% eines vollständig als Principal zugeordneten Kontos vor Kosten;
drei statt fünf Coins ändern diese Quote nicht. Risk Gates können daher
Stufen verhindern oder Baskets vorzeitig schließen; Gaps bleiben ein Risiko.

IP-055 bereitet eine gemeinsame versionierte Portfoliosimulation vor.
Zusätzliche Coins, genaue Budgets/Reservierungen und Signalpriorität werden
vor Leistungsläufen festgelegt; vorhandene Einzelassetjobs bleiben immutable.
KI zunächst Shadow Mode, kein Override harter Limits, keine verspäteten
Schutzaktionen und keine heutige News/Modellkenntnis als historischen Beweis.
Varianten/Derivate, Provider und tatsächliche Aktivierung bleiben eigene
konkrete Freigaben. Kein Code-, Schema-, Profil- oder Deploywechsel.
[Plan und Quellen](../multi-basket-ai-plan.md).

## 2026-11-09 — D-060: Gemeinsame Baseline vor erweitertem Basketprofil

**Status: IP-056 umgesetzt, Q33 fortgeführt.**9455bfe in Mainef18d74
verifiziert. Neuer Offline-Portfolio-Simulator mit unveränderten BTC-/ETH-
500+5-Budgets auf gemeinsamem10k-Konto. Atomare Quote-Batches verhindern
Zwischenbewertungen vor Riskprüfung; historische Mitternachtscloses prüfen
alten Tagesverlust vor neuer Basis. Einzelquote-/Paperpfade unverändert.

Eigene eingefrorene Policy, identische H4-Fenster und passive kostenvergleichbare
Referenz. Reale Forschung: net228,72 USDT, zeitgewichteter gehaltener
Einstand72,56 USDT. Benchmark2577,90 netto/12,1145% Peakdrawdown; Verluste
zum Start/Tagesbasis3,4806%/3,1921%, keine beobachtete8%/6%-Verletzung.
Peak-/Start-/Tagesbezug getrennt prüfen; keine Strategie-/Holdoutabnahme
aus dem passiven Vergleich. Erweiterte Coins erfragt, Budget-/Reservierungs-/
Stressablehnungs-/Prioritätsregeln bleiben IP-055. Kein DB-/Holdout-/Broker-
zugriff, keine öffentliche Aktivierung. [Vertrag](../portfolio-reference.md).

## 2026-11-10 — D-061: Allokation als prüfbarer Offlinevorschlag

**Status: IP-057 umgesetzt; größeres Forschungsprofil zur Entscheidung gestellt.**
698146f in Main3bb0d0c verifiziert. Separater stdlib-Kern plant gleiche3–5
Slots mit expliziter Kostenquote; bestehendes Strategieprofil bleibt unverändert.
Käufe teilen Cash, verbrauchte Slotbudgets, Kostenreserven und min6%/8%-
Verlustspielraum. Vorgeschlagener korrelierter50%-Stress zählt positive
Holdingverluste, halbes offenes/neues Principal und ungenutzte Kosten einmal.
Weitere Käufe benötigen Maximalpreis ≤ erster Fill. Keine Gewinnkompensation,
stilles Orderresizing oder Budgetfreigabe durch Exit.

Immutable Reservierung bindet Identität/Plan/Revision; unklare/Storno-
angeforderte Orders bleiben reserviert und sperren neue Käufe. Kein dauerhafter
CAS-/Ausführungs-/Release-/Retry-/Zyklusresetvertrag. Vollständige authentifizierte
Kontoevidenz ist Aufgabe der späteren Anwendung. Bei10k/1% Reserve anfangs
rund1002 USDT Kaufprincipal; fünf erste Stufen passen. Die zusätzliche
Stressregel kann Kapitalnutzung begrenzen; Vergleich erst nach Profilentscheidung.

85 gepinnte Fälle/65 Subtests,81 Hostfälle und gezielter Abschlussreview grün.
Coins/Profil erfragt; Wiederbelegung, Priorität und Researchadapter offen.
Kein DB-/Holdout-/Brokerzugriff oder Deploy. [Vorschlag](../portfolio-allocation.md).

## 2026-11-10 — D-062: Forschungsprofil bestätigt, Nachkäufe integriert

**Status: Q34 bestätigt, IP-058 umgesetzt.** Nutzer akzeptiert das konkrete
Forschungsprofil und erinnert ausdrücklich an Nachkäufe zur Senkung des
Durchschnittspreises. d31dcf3 in Main1f44b7f verifiziert. Gleiche3–5 Slots,
1% Principal-Kostenreserve und zusätzliche gemeinsame50%-Stressablehnung
sind für Offlineforschung freigegeben;6%/8% bleiben bindend.

Eigene `allocated-rsi-research/1` verbindet den Allokator mit unveränderter
CryptoEngine-/PaperSimulator-/PortfolioSimulator-Logik. Alle fünf regulären
RSI-Stufen und manuelle sechste Stufe; keine Verkleinerung einer abgelehnten
Stufe. Prüfung vor Intentaufnahme und unmittelbar beim simulierten Dispatch;
eigene Reservierung dort nicht doppelt rechnen. Immutable Lifetime-Ausgaben
enthalten tatsächliche Buyprincipal-/Buy-/Sellfees auch nach vollständigem
Abschluss. Keine automatische Wiederbelegung/Resetfreigabe. Baseline v1 und
deren Runtime-Snapshotloader/Whitelist bleiben unverändert.

97 gezielte gepinnte Fälle/65 Subtests,93 Hostfälle und Abschlussreview grün;
zwölf Adapterfälle nach Reviewergänzung nochmals gepinnt/Host bestanden.
Test mit vorhandenem synthetischem Gewinn führt fünf Stufen und ausdrücklich
bestätigte sechste samt Fill aus; Durchschnitt sinkt. Keine Leistungs-/MFA-
Hardwareabnahme daraus. Coins und feste Slotwiederbelegung nach normalen
abgeglichenen Exits konkret erfragt, vor erweitertem Mehrjahreslauf offen.
Keine neuen Abhängigkeiten/DB-/Broker-/Holdout-/Runtimeaktivierung.
[Vertrag und Zyklusvorschlag](../staged-portfolio-research.md).

## 2026-11-10 — D-063: Verfügbarkeitsprüfung vor Assetentscheidung

4f56024 in Main7ec9b41 verifiziert. Nutzer bittet erneut um Erklärung der
offenen Coins-/Wiederbelegungsfragen; beide konkret erläutert und erfragt.
Keine Freigabe aus Mergemeldung abgeleitet. Unabhängiger öffentlicher Vorcheck
bestätigt BTC/ETH/SOL/BNB/XRP online, heutige Spotregeln und je zwei H4-Kerzen
am Forschungsbeginn. Responsehashes/Providerzeiten im eigenen Record.
Kein vollständiger Historien-, Leistungs- oder Holdoutnachweis.

ETH-Mindestmenge0,0005 ist im bisherigen v1-InstrumentRules nicht repräsentiert.
Neuen Researchvertrag vorbereiten; kein Defaultfeld in alte Digestrecords
einfügen oder heutige Metadaten als historische Regeln ausgeben. Fünf
Antworten/zehn OHLC-Kerzen und JSON-Roundtrip geprüft; keine Runtime-, DB-,
Privatadapter- oder Strategieänderung. [Vorcheck](../portfolio-history-preflight.md).

## 2026-11-10 — D-064: Bestätigter Kandidatenpool und fixe Slotzyklen

Q35: Nutzer ergänzt BTC/ETH/SOL/BNB/XRP um neun Kandidaten und bestätigt
feste Wiederbelegung.14 Kandidaten, unabhängig3–5 Slots; frische RSI-Signale,
vollständiger normaler abgeglichener Exit, unveränderte nominale Budgets,
kein automatischer Riskneustart. Main bleibt7ec9b41; neuer Branch enthält
noch ungemergten IP-059b944be1.

Separate Researchversion projiziert dynamisch belegte Slots auf den bestehenden
Allokator. Aktuelle Zyklusausgaben begrenzen Käufe, Lifetime-/Abschlussbelege
erhalten bezahlte Kosten. Ungeklärte Orders halten Slots, Risiko-/unklassifizierte
Exits quarantänisieren. Technisch kanonische Signalpriorität eingefroren.
Mindestmenge separat, gerundete Mindestquote/Slippage am Dispatch geprüft.
Reportkapital nach Kapazität; Benchmark vorerst explizit nicht berechnet, weil
die alte passive Vollbudgetreferenz14 Slots finanzieren würde.

Öffentlich13 Spotmetadaten online, XMR40034; ZEC/HYPE/XLM ohne2022-08-01-Sample.
Keine Historien auffüllen oder aktuelle launchTime als damaligen Beleg ausgeben.
Vor Leistungsauswertung vollständige Daten und berechtigte Kohorten einfrieren.
114 gepinnte Fälle/65 Subtests,17 neue Poolfälle/Review grün. Synthetisch drei
natürliche RSI-Zyklen/15 Käufe/10 Exits mit Wiederbelegung; finale Sellfee am
Kontolimit separat getestet. Kein Profitabilitäts-/Holdoutnachweis oder
Runtime-/Broker-/DB-/Dependencywechsel. [Vertrag](../candidate-pool-research.md).

## 2026-11-10 — D-065: Gewinnetappen statt unbegrenztem Sofortwachstum

22534b7 in Mainab928ee verifiziert. Nutzer erweitert die fixe Budgetpräferenz:
Gewinne geschlossener Baskets sammeln und ab einer vollständigen Basketstaffel
für weitere Slots oder höhere künftige Budgets nutzen. Drei profitable
Abschlüsse sind ausdrücklich ein Beispiel. Konkreter Modus/Schwelle/Rhythmus
erfragt; noch keine stille Strategie-/Budget-/Risikobasisänderung.

Reviewbarer Vorschlag: Nettogewinne inklusive geschlossener Verluste/Kosten,
bereits zugeordnetes Gewinnkapital nicht doppelt verwenden; Schwelle ein
ursprüngliches Vollbudget inkl. manueller und Kostenreserve. Nach drei
abgeglichenen Abschlüssen prüfen, zunächst bis fünf Slots, danach neue Budgets
erhöhen; alternativ feste Kapazität. Offene Baskets ihre eingefrorene Staffel
behalten lassen. Planungskapital und ursprüngliche8%-Risikobasis trennen.
Keine sechste Position, Holdout-/Runtime-/Livefreigabe. Rechenbeispiele mit
bestehendem PoolPlan geprüft; reine Dokumentationsänderung, keine neuen Tests.
[Vorschlag](../profit-etapes.md).

## 2026-11-10 — D-066: Bestätigte Gewinnetappen bis sieben Slots

Q36-Antwort bestätigt Option1 und erweitert die Kapazität auf maximal sieben:
zuerst weitere Slots, danach größere neue Baskets. Mindestens drei neue
abgeglichene Abschlüsse und ein ursprüngliches Slotvollbudget je Freigabe,
Nettoverluste/Kosten und vorherige Zuordnung mitzählen. D-065-Vorschlag
damit entschieden; offene Baskets und ursprüngliche6%/8%-Basen erhalten.

IP-061 ergänzt separate `seven-slot-profit-rsi-research/1`, immutable
Budgetepochen und `variable-slot-stress-research/1`. Epochen halten
Abschlusspräfixhash, Netto-/zugeordneten Gewinn und damalige Cash-/Equitydeckung.
Belegte ältere Slots behalten eigene Budgets; noch nicht nutzbare Erhöhungen
bleiben reserviert. Keine Cashgutschrift, automatische Quarantänefreigabe,
ungeklärte Orderwiederholung oder künstliche manuelle Historienfills.
Defaultneutrale Budgethooks erhalten alte Strategiekonfigurationen/Digests.

143 Hostfälle/147 gepinnte Fälle mit87 Subtests bestanden;33 neue Fälle
einschließlich sieben simultaner Baskets, blockiertem achten Kandidaten,
alter/neuer gemischter Staffel, expliziter Reserve, fehlender Cash-/Equity-/
Stressdeckung und einmaliger kausaler H4-Freigabe. Unabhängiger Review ohne
Blocker, ergänzte Deckungsfälle grün. Gemeinsame echte Dreijahresbaseline
BTC/ETH vollständig exakt gegen eingefrorenen Report reproduziert.
Keine Aussage zur Marktleistung des Gewinnprofils; Vollhistorien/Kohorten/
Benchmark und echter Vergleich bleiben IP-055. Kein Holdout-, Dependency-,
DB-, Runtime-, Broker- oder öffentlicher Dienstwechsel.
[Vertrag](../profit-etapes.md).

## 2026-11-10 — D-067: Futuresziel mit isoliertem Budget und erhaltenem Stress

Q37: Nutzer nennt AVAX/HBAR/TRX/BGB/BAT/RENDER als Alternativen und plant
später Futures mit marktphasenabhängigem2×–10× statt Spot. Auf konkrete
Fragen bestätigt er isolierte USDT-M-Long-Baskets, echtes Budget inklusive
Kosten/Marginpuffer, keine automatischen Nachschüsse anderer Baskets und
weiter−50%-Stress/6%/8%. Hebel reduzieren oder Einstieg sperren statt
Rückgangstoleranz still zu verkleinern. Exakte Regime-/Hebel-/Budgetaufteilung
noch nicht definiert; keine Live-/Kontoänderung.

IP-062 misst öffentliche Classic-V2-Daten:20 normal Perpetuals,40 kleine
Trade-/Markproben,52 validierte frühe OHLC-Kerzen für13 Kontrakte. Alle sechs
Alternativen aktuell verfügbar; nur AVAX/TRX mit2022-Proben. XLM hat
Futuresproben trotz Spotlücke, XMR hat heutigen Kontrakt; heutiges Listing
beweist keine Vollhistorie. RENDER aktuelles Fundingintervall4h, andere
Alternativen8h. URLs/Responsehashes/Providerzeiten/Metadaten/OHLC gespeichert,
JSON-/Identitäts-/Decimal-/UTC-Abnahme und fachlicher Review.

Neue Entscheidung überschreibt späteres Spotziel, nicht alte frozen
Strategie-/Daten-/Ergebnisrecords. Wirtschaftlich getrennte Futuresökonomie
mit Nominal, Margin, Reserven, Markpreis, Funding und Maintenance/
Liquidation in IP-063; keine Spot-PnL-Multiplikation. Früher−55%-Stop
kann sonst hinter der Liquidation liegen. Keine Holdoutauswertung, neue
Abhängigkeiten, DB-/Runtime-/Broker-/Publicaktivierung. Branch enthält
noch ungemergten IP-06154d2a7d, Mainab928ee erneut verifiziert.
[Vertrag und Daten](../futures-research.md).

## 2026-11-10 — D-068: Getrennte Futuresrechnung ohne fiktiven Hebelgewinn

Nutzer bestätigt alle Merges;54d2a7d/f6617b6 in Main168219f verifiziert.
IP-063 ergänzt zwei pure Offlineversionen für lineare USDT-Longökonomie
und gemeinsame Kaufstressprüfung. Nominal, tatsächliche Nettomargin,
unposted Cash und übrige Slot-/Costreserven getrennt; Margintransfer kein
Equitygewinn, Funding signed, Fees nicht doppelt abbuchen.

Maintenance bewusst als konservative Whole-tier-Annahme, keine exakte
historische Bitgetliquidation. Vollständige begrenzte monotone Stufen, Source-
Assumptionsdigest und Kosten/Precision gebunden; fehlende Deckung blockiert.
First-fill−50% auch nach Durchschnittssenkung, reale gestellte Margin und
gesamte3–7-Basketverluste gegen original6%/8%; kein ungeposteter Gapschutz.
Aktuelle Halts/Liquidationsgefährdung vorher prüfen. Alle ungeklärten Orders
und Fillbound unter Mark im ersten Rechner blockieren.

Erster Fill ohne Buchgewinn benötigt >50% Nominal als Margin; effektiver
Entryhebel<2, auch wenn Broker10× eingestellt ist. Diese Konsequenz der
bestätigten Q37-Regeln erklärt, warum bloßes Einstellen10× keinen zehnfachen
PnL ergibt. Noch keine Uptrend-/Marginaufteilung oder Strategiepromotion.

44 neue Fälle,187 Host-/191 gepinnte Fälle mit135 Subtests grün.
Unabhängiger Review ohne verbleibenden wirtschaftlichen/Accountingblocker.
Reviewfix verhindert Sofortgewinn aus theoretischem Kaufpreis unter Mark.
Nur neue Module, keine Spotexports/-Schemas/-Digests verändert; alte
Trading-/Workerfälle bestanden, echter alter Dreijahresreplay diesmal nicht
wiederholt. IP-063 bleibt bis Ereignisledger/Teilfills/Funding-/Gapabnahme offen,
IP-064 eigene Futures-/Preisartdaten vor langem Nettovergleich.
Kein Holdout-, Dependency-, DB-, Runtime-, Broker- oder Publicwechsel.
[Rechenvertrag](../futures-economics.md).

## 2026-11-10 — D-069: Futureshistorien mit gebundener Preisart

IP-063`0cf8a2b` in Main`6d06ec5` verifiziert; Nutzer erlaubt Fortsetzung.
Frage nach2×-Start und höheren Nachkaufhebeln beantwortet: kein fester
effektiver2×-Start unter bestehendem−50%-Stress, keine automatische Leiter
oder geänderte Risikofreigabe. Jeder Fill braucht gesamte Basket-/Kontoprüfung.

IP-064 ergänzt eigene H4-/Fundingversionen, explicit Classic-V2 USDT-M
perpetual und trade/mark/index in Quelle/Digest/Candleidentität gebunden.
Spotkern kann markierte Candles nicht ausführen; alte Contracts unverändert.
Funding signed und tatsächliche UTC-Zeitpunkte, ohne angenommene Kadenz,
Nullergänzung oder Vollständigkeitsbehauptung. Öffentlicher OHLCimport bounded,
ohne Redirect/Retry; Fundingtransport wegen fehlendem Datumsfilter offen.

Vorab eingefrorenes reines Datenprotokoll BTC/ETH2022-08-01–2025-08-01,
keine PnL-/Kosten-/Regimeauswahl.198 öffentliche Pages, alle sechs Streams
je6576 lückenlose H4-Kerzen,39.456 insgesamt. Identische UTC-Achsen,
strict Roundtrips, Datei-/Datendigest und Protokollhash geprüft.
Messrecord bindet perpage kanonische dekodierte Responsehashes.
Originale ignoriert lokal, Protokoll/Quittung im Git. Kein Holdout angefragt.

23 neue Hostfälle,81 gepinnte Daten-/Workerfälle mit147 Subtests bestanden.
Testhelper nur um zwei readonly Script-/Protokollmounts ergänzt; keine
Dependencies, Migrationen, Runtime-/Privatebroker-/Publicänderungen.
IP-064 abgeschlossen; Fundingarchive/andere Kandidaten/historische Kontrakt-
annahmen BL-030/IP-055, Ereignisledger/Teilfills/Gaps IP-063 weiter offen.
[Datenvertrag](../futures-marketdata.md).

## 2026-11-10 — D-070: Abgeglichene Futuresbuchungen ohne Kaufautorität

IP-0647007e90 in Mainab2b6bb verifiziert. Nutzer erläutert2× als Minimum;
Brokerprofil2–10 bleibt, effektiver Hebel mit bereits gestelltem Puffer
separat. Keine Hebelleiter oder schwächere−50%/6%/8%-Regel daraus ableiten.
Broker muss Puffer vor unmittelbarem First-fill-Gap wirksam nachweisen;
zwei sequenzielle API-Aufrufe sind keine atomare Marginbereitstellung.

IP-065 ergänzt pure Ereignisbuchungen mit3–7 Budgets, Tenant/Plan/Revision/
Hashkette. Tatsächliche Teilkäufe, Teil-/Vollschließungen, signed Funding,
eigene Marginpostings, komplette Marks und explizite Vormutations-Tagesbasis.
Gross Marginzuordnung von Fundingnettostand getrennt; Kostenbudget je Epoche
nicht beim Abschluss erneuern. Signed Defizite korrekt buchen, keine
fiktiven Stop-/Liquidationsfills oder automatischen Nachschüsse anderer Baskets.
Halts bleiben nach Kurs-/Margin-/Tageserholung; normale Verlustabschlüsse
erzeugen gegebenenfalls Reserveshortfall, nicht allein einen permanenten Halt.

Versionierte konservative Gleichzeitigkeit Mark/Tag/Funding/Margin/Entry/Exit.
Fundingzeitpunkt je Symbol einmal verbrauchen; genaue Revision verhindert
identischen Commandreplay. Globale Broker-Fill-Dedupe/Journal-CAS/Orderabgleich
fehlen; keine Kaufgenehmigung. Proportionale Teilclose-Marginfreigabe bewusst
Forschungsannahme, keine historische Brokerformel oder Strategiepromotion.

31 neue Fälle,218 Host-/222 gepinnte Trading-/Workerfälle mit157 Subtests grün.
Eigenprüfung korrigiert Reserveshortfall-vs-Halt und doppelte Fundingtimestamps;
vollständiger deklarierter Fill entspricht bisheriger Kaufprojektion3/5/7 Slots.
Keine neue Agentdelegation nach ersetzten Nutzer-AGENT-Anweisungen; obsolete
automatische Delegations-/CLI-Modelldirektiven im Repository entfernt.

Offizielle V3-Fundingquelle90 Tage/cursor statt Zeitraum; öffentlicher
Downloadcenter nennt keine vollständige Fundinghistorie. Keine Marktarchive/
Holdoutabfragen oder Ersatzraten verwendet. Fundingarchive/historische Regeln
BL-030/IP-055, Intent-/Pending-/Riskadapter IP-066, IP-063 weiterhin offen.
Keine bestehenden Kernänderungen, Dependencies, Migrationen, DB-/Runtime-/
Broker-/Publicaktivierung. [Ledgervertrag](../futures-event-ledger.md).

## 2026-11-11 — D-071: Ledgerbasierte Kaufprüfung mit begrenztem Orderabgleich

Nutzer bestätigt IP-065;12c2b6c in Mainffd4211 verifiziert. IP-066 ergänzt
einen reinen versionierten Researchwrapper über unveränderte Futureskerne.
Bruttomarginkapital, signed Fundingnettostand, verbrauchte Kosten und
unwiederhergestellte Fundingprincipaldebits separat prüfen.
Originale6%/8%/First-fill−50%, eigene Budgetgrenzen und3–7 Slots unverändert.

Ein ausstehender Kaufintent sperrt neue Käufe. Reservierung bewegt kein Cash,
Teilfills vermindern nur tatsächlich verbrauchte Restreserven. Attempt
zeichnet Unsicherheit auf, erteilt keine Ordergenehmigung; keine Timeout-
Freigabe/automatische Wiederholung. Exakte abgeglichene Terminalsummen
erforderlich; bekannte ungeplante/überreservierte Fills dennoch buchen und
dauerhaft im Wrapper sperren, ursprüngliche Ledgerhashkette erhalten.

Fill-/Order-/Eventidentitäten im bewahrten State dedupliziert, nicht dauerhaft
im Brokerbetrieb.1024 Einträge je Liste; nie automatisch leeren/evicten.
Neuer Wrapper ist kein Restore-/Herkunftsbeweis. Chronologische Evidence und
Terminaldigest bleiben vertrauenswürdige Callerannahmen; keine DB-CAS.

Eigenprüfung hält zusätzlich unterschiedliche First-fragment-Preispfade fest:
Maximalpreis-Vollfill ist kein Beweis sicherer restlicher Fills. Nach
tatsächlichem günstigerem First Fill wird der nächste Kauf am echten
Stressanker gesperrt. IP-067 muss Restfillhülle/Gaps vor kausalem
Signal-/Replayadapter prüfen; keine ursprüngliche Freigabe wiederverwenden.

28 neue Fälle;246 unterschiedliche Host-/250 gepinnte Trading-/Workerfälle
mit167 Subtests grün: Vollsuite245/249, neuer Grenzfall anschließend gezielt.
Keine neue Delegation oder Broadcredential-/DB-/Publicchecks, keine
Dependencies/Migrationen/alten Kerne/Daten-/Holdout-/Runtimeänderungen.
Funding-/historische Regeln und Brokerpuffertiming BL-030 weiterhin offen.
[Vertrag](../futures-pending-research.md).

## 2026-11-11 — D-072: Kausale Restfill-/Gapstresshülle ohne Dispatch

IP-06640d8ba6 in Main1d06dd3 verifiziert. IP-067 ergänzt continuation/1
als separaten reinen Rechner über unverändertem Ledger-/Pendingstand.
Echter First Fill und bereits gestellter signed Nettostand decken aktuelle
Position sowie volle Restmenge am eingefrorenen Preis-/Fee-/Hebelmodell.
Alle Plansymbole, strikte volle Maintenance,6%/8%/−50%, Bruttobudgets,
gebuchte Kosten/Funding und ausstehende Principalrestoration bleiben geprüft.
Keine ungepostete Reserve, zukünftige Wiederauffüllung oder andere Baskets
als Gaprettung vorwegnehmen.

Endpunktprüfung deckt lineare Zwischenmengen bei festem tatsächlichem
First Fill und innerhalb der deklarierten abwärts gerichteten Markhülle.
Volle restliche Entryfee schon am Nullmengenendpunkt vorsichtig abziehen.
Eigenprüfung ergänzt Kostendeckung an beiden Endpunkten: ein im Stress
günstiger hypothetischer Restfill darf fehlende freie Kostenreserven vor
weiteren Fills nicht heilen. Echte Tageswechsel-/Markfolge bildet den
Gegenbeispieltest; ursprünglicher günstiger First Fill sperrt schon seine
restlichen teureren Fragmente.

Keine Ordergenehmigung: risk_covered bezeichnet nur ökonomische Research-
deckung; requires_reconciliation=true/execution_enabled=false unveränderlich.
Mindestmargin/Fehlbetrag nur Anzeige, kein Posting oder Haltreset.
Keine First-fill-Puffertiming-, Zukunftskosten-/Markupper- oder dauerhafte
Broker-/Restore-/Strategiezyklusautorität. Chronologische Callerannahmen
und begrenzte Pending-IDs bleiben; IP-068 muss ursprünglichen Zyklus binden.

31 neue Fälle;277 unterschiedliche Host-/281 gepinnte Trading-/Workerfälle
mit219 Subtests grün (Vollsuite276/280, danach alle31 aktualisierten
Modulfälle gezielt).45 Zwischenmengen-/Preis-/Feekombinationen,3/5/7 Slots.
Keine Delegation/Broadregressionen/alten Versionen/Daten-/Holdout-/DB-/
Dependency-/Runtime-/Broker-/Publicänderungen. IP-068 RSI-/Staffel-/Zyklus-
Replay unter expliziten Forschungsannahmen folgt; Fundingarchive/historische
Kontrakt-/Regime-/Budgetregeln IP-055/063/BL-030 offen.
[Vertrag](../futures-continuation-stress.md).

## 2026-11-11 — D-073: Kausaler Futures-RSI-/Staffelreplay ohne Performancebehauptung

Nutzer bestätigt IP-067;f18188d in Mainf844b66 verifiziert. IP-068 verbindet
bestehende Wilderindikatoren mit nativen vollständigen H4-Trade-/Markframes,
fünf regulären Stufen, tatsächlichem abgeglichenem Teilfill-VWAP und bindet
jede Order an Profil/Signal/Intent/Basketzyklus. Manuelle sechste Stufe und
eigener Marginpuffer bleiben getrennt.2× konstant als begrenzte Forschungsbasis;
keine neue bestätigte Regime-/Budgetaufteilung oder automatische Hebeltreppe.

Explizit eingefrorene Forschungsannahme: volle eigene Intentmargin mit erstem
Fragment, ohne Broker-Timing-/Atomizitätsbeweis. Bekannte abweichende/alte oder
nach Gewinnschutz eintreffende Fills korrekt buchen und global quarantänisieren.
Unbekannte Orders behalten Reserven, terminaler Abgleich erhält seit letztem
Fill beobachteten RSI-Rearm. Vollständiger normaler Close startet neuen Zyklus
mit alter Indikatorhistorie; Risiko-/Quarantänesperren bleiben.

+5%-Close aktiviert Schutz mit fee-/funding-/Teilexitbereinigtem Nettofloor;
kein vorheriger Close als erfundener Nachfillgewinn oder garantierter Stopfill.
Negative Gap-Equity bleibt gebucht, keine positive Mitternachtsbasis erfinden.
36 neue Fälle/313 unterschiedliche Host-/317 gepinnte Fälle mit228 Subtests
grün; Eigenprüfung ohne Delegation. Keine alten Module/Exports, Daten/Holdouts,
Dependencies, Migrationen oder öffentlichen Dienste verändert.
IP-069: historische Fundingquelle und langes eingefrorenes Replayprotokoll;
noch keine neue wirtschaftliche Futuresperformance. IP-055/063/BL-030 offen.
Vertrag: `docs/futures-signal-replay.md`.

## 2026-11-11 — D-074: Fundinglücken belegen statt kostenlose Finanzierung erfinden

Nutzer bestätigt IP-068;91a1547 in Main56877b0 verifiziert. IP-069 erster
Quellencheckpoint ergänzt reinen öffentlichen Classic-V2-Fundingimport,
expliziten erwarteten Settlementkalender und create-only gepinntes CLI.
Bestehende Funding-/Futures-/Spotformate und Tradingkerne bleiben unverändert.

Offizielle aktuelle V3-Dokumentation nennt90 Tage, ältere Legacyseite nicht.
Native V2-Abnahme: BTC/ETH je270 Ereignisse2026-08-13T16Z..2026-11-11T08Z,
je vier Pages einschließlich leerem Abschluss, insgesamt8 protokollierte
GETs/540 Beobachtungen. Angefragtes2022–2025-Fenster hat jeweils0 Ereignisse;
gegen deklarierte8h-Annahme je3288 Missing, keine Nullsubstitution. Jüngste
Raten bleiben im eigenen Snapshot. Historischer Kalender bleibt unbelegt.

25 neue Hostfälle/102 unterschiedliche gepinnte Marktdatafälle/187 Subtests
grün (101 Regression, finale25 Modulchecks). Vier echte Datei-/Datendigests
und acht Pagehashes geprüft, Receipt mit Protokollchecksum committed; rohe
Snapshots ignored. Keine Delegation/Trading-/Credential-/DB-Wiederholung,
Dependencies, Migrationen, Holdoutjobs oder öffentliche Aktivierung. Nur
zwei Fixturemounts readonly ergänzt. Eigenprüfung.

IP-069 bleibt offen für vollständige historische native Quellen, konkrete
wirtschaftliche Forschungsannahmen und Langlaufjournal ohne ID-Verwerfen.
Optional Nutzerpräferenz zu getrenntem kostenlosem Binance-Futuresvergleich
erfragt, noch unbeantwortet; keine Venue-/Fundingumwidmung oder Handelsänderung.
Bitget bleibt Tradingziel. `docs/futures-funding-availability.md`.

## 2026-11-11 — D-075: Zusätzliche Binanceforschung ausdrücklich bestätigt

Nutzer beantwortet die konkret erläuterte Binancefrage mit „Ja können wir
gern machen“. Q38: eigene Binance-Kurs-/Fundingdaten für separaten kostenlosen
Dreijahresvergleich; Bitget bleibt Handelsziel, keine Konto-/Livefreigabe.
IP-06957b2858 in Mainf37be4b verifiziert.

IP-070 eigene immutable Venue/Preisart/Fensteridentität und bounded unsigned
Transport/Importer. BTC/ETH je6576 H4-Trade/Mark/Index und3288 signed Fundingraten
2022-08-01..2025-08-01 exklusiv,52 GETs. Acht Snapshots erneut geladen/Datei/
Datasetdigests/Achsen geprüft, H4 vollständig, null fehlende/doppelte/fremde
deklarierte8h-Buckets. Originaloffsets bis29ms, je1369 fehlende native
Settlement-Markpreise None. Keine Rundung/Null-/Venueersatzdaten.

25 neue Hostfälle,127 gepinnte Marktdatafälle/229 Subtests zunächst grün;
final28 Binancefälle/44 Subtests nach Grenzprüfungen grün.130 unterschiedliche
gepinnt insgesamt, keine Addition überlappender Läufe. Eigenreview, kein Agent,
nur zwei readonly Testmounts, keine Dependencies/DB/Migration/Paper/Publicänderung.
Initialer Sandbox-DNS-Lauf ohne Receipt erhalten, neuer autorisierter
Netzwerklauf im ignorierten20261111-native-network. Checksumprotokoll vor
Import/create-only. Receipt behauptet weder Nettoergebnis noch Holdout/
Gebühren/Maintenance/Settlementpreisvalidierung.

Nächstes IP-069: wirtschaftliches Profil mit ausdrücklich benanntem Fundingpreis
und Langlaufjournal jenseits1024 IDs ohne Eviction, dann Nettovergleich.
`docs/binance-futures-research-data.md`.

## 2026-11-11 — D-076: Langes Journal hält alle IDs und offene Orderzustände

Nutzer bestätigt IP-070-Merge;0ebb98b in Main629901b verifiziert.
IP-071 eigener Long-Pending/2-Modus mit immutable vollständigen vier ID-
Historien, default50000/max100000. Vorheriger Pending/1-Standard1024 und
bestehende Wirtschaftlichkeits-/RSI-/Risikoprüfungen bleiben identisch.
Logarithmischer Insert/Lookup, Root/Count/Namespace/Kapazität im expliziten
Snapshotprimitive; allein kein Restore. Kein Convert/Reset eines bereits
fortgeschrittenen Ledgers als angebliche Historienübernahme.

Eigenes create-only lokales JSONL-Journal; genesis/Profil/Plan/Actor/Kosten/
Protokoll/Datasets gebunden, Inputs typisiert, Sequence/Head/States geprüft.
Write+fsync vor Ack; Unknown sperrt Reads/weitere Writes bis Close/Fullreadback,
kein Retry/automatische Tailreparatur. Separat behaltene `minimum_receipt`
erkennt auch ganze verlorene letzte Records; ohne extern behaltenen Anker
keine Erkennung gültiger früherer Präfixe/keine Broker-/Manipulationsautorität.
Restore faltet vollständige Inputs inklusive Unknownorder/Teilfill/Terminal/
Wilder/Quarantäne, kein Snapshotshortcut. Linux-Owner0600/Regular/no leaf
symlink/hardlink/Writerlock und256KiB/128MiB/100000Commands explizit begrenzt.

25 neue Fälle,337 ursprüngliche gepinnte Trading-/Workerfälle/253 Subtests,
25 Journalfälle/26 Subtests, finale53 Pending-/Journalfälle/37 Subtests nach
Halt-Typprüfung grün;342 unterschiedliche Fälle insgesamt.
Voller synthetischer6576-H4-/1096-Mitternachtslauf,7672 IDs/9.544.108 Bytes,
exakter vollständiger Restore und zusätzliche vollständige Ankerprüfung.
59,228s Schreiben/62,707s ursprünglicher Restore auf diesem Host.
Keine Marktperformance, reale Orders, Holdout-/Fundingkosten-/Profitvalidierung.
Eigenreview/keine Agents/Dependencies/PostgreSQL/Migrations-/Publicänderung.

Nächstes IP-069: wirtschaftliches Forschungsprotokoll mit Fundingpreisbezug
und echter passender Kohorte, dann Nettovergleich. Native Binanceartefakte
bislang BTC/ETH,3–7-Symbol-Profil braucht echte weitere Daten; keine synthetische
dritte Coinperformance. `docs/futures-long-replay-journal.md`.

## 2026-11-11 — D-077: H1/H4 mit größeren festen Basketbudgets vergleichen

Nutzer beauftragt ausdrücklich H1-Test und H4 mit korrekter größerer
Basket-Kapitalplanung. Q39/IP-072 verwendet zunächst den vorhandenen Spotkern,
ein10.000-USDT-Konto und dieselben fünf bestätigten BNB/BTC/ETH/SOL/XRP-
Kandidaten in drei/fünf Slots; kein synthetischer Coin und keine Futuresrendite.
RSI/Rearm/5%-Abstand/25%-Staffel/manuelle Reserve und6%/8%/−50% unverändert.
Native Binance-H1 bildet auch H4; vier Grundfälle plus zwei vorab bestimmte
doppelte Kostenfälle, kein Holdout/Parametersuchen/Runtimewechsel.

Native Unterbrechung2023-03-24:13h fehlt,12h verkürzt. Gemeinsamer12–16h-Block
vor erster Marktperformance ausdrücklich ausgeschlossen, Indikatoren danach
neu starten, Kaufpending stornieren; echte Holdings/Stopps/Halts/Belege erhalten.
Erste streng lückenfreie Quelle wurde vor Leistung verworfen/archiviert,
kein Forwardfill/Lookahead. Quelle/Dateien im create-only Manifest versiegelt.
Vertrag und vollständige Ergebnisse: `docs/h1-h4-basket-comparison.md`.

Sechs echte Marktläufe beendet. H1/H4 drei Slots+725,04/+1251,79 USDT;
fünf Slots+985,30/+1064,30; DD H1 höher. Nachkäufe fünf Slots66/47,
zusätzliche Stressprüfung sperrt1740/186 Versuche, Stufe5 nie ausgeführt.
Doppelte Kosten fünf Slots+1015,72/+1554,99: tatsächliche höhere Gebühren
geprüft, Handelspfad ändert sich durch Fill-/Stoppschwellen; kein Beweis
Kostenrobustheit/höhere Gebühren vorteilhaft. H4 als Referenz behalten,
keine automatische Promotion; Ausführungs-/Stoppsensitivität vor Holdout.
135GETs, je26303 native H1/26300 evaluierte H1/6575 H4, sechs volle Kurven
geprüft.18 neue/356 unterschiedliche gepinnte Fälle, alte228,7169/56-
Baseline exakt reproduziert. Keine DB/Dependencies/Public-/Runtimeänderung.

## 2026-11-11 — D-078: Futuresvergleich und H1-Supertrend priorisieren

Q40: Nutzer ordnet Basketstrategie ausdrücklich Futures zu; separate spätere
Spot-Investingstrategie, alte Spotreferenzen unverändert. Vorschlag als
Forschungsvariante aufnehmen: geschlossene H4-RSI-Einstiege/Nachkäufe,
geschlossener H1-Supertrend für Schutz. +5%-Aktivierung, Nettofloor,
aufwärts ratcheted Stop/Kaufstopp, manuelle Reserve und−55%/−50%/6%/8%
erhalten; Nachfrage zu Kontolimits ist keine Lockerungsfreigabe.
Auf identischer feinerer Futurespreisachse H4- und H1-Supertrend vergleichen,
Indikatoränderung nicht mit veränderter Stopausführung vermischen.
IP-069 priorisiert; native H1-Kohorte und eingefrorene Funding-/Kosten-/
Marginannahmen fehlen noch, keine Runtime-/Livefreigabe.

Zusätzlicher lesender Replay des veröffentlichten H4-Fünf-Slot-Spotfalls
reproduziert+1064,3000798076551643529605 USDT exakt:
49 positive Abschlüsse zusammen+1360,2861442755689801642355,
38 negative zusammen−295,986064467913815811275.
37 negative Trailing-Stop-Abschlüsse und ein SOL−55%-Notausstieg
mit−160,5093522835841240205 USDT. Coarse OHLC-Stopausführung kann Verluste
überschätzen; keine reale Stopfillqualität aus diesen Abschlüssen ableiten.
Maximaler Equitydrawdown3,813586%:10542,6314058 am2024-07-22 02:00Z
zu10140,5790659 am2024-08-05 13:00Z, weiterhin über10000 Initialkapital.

## 2026-11-12 — D-079: Kontogates dürfen volle geplante Staffel nicht sperren

Q41: Nutzer bestätigt vollständige Tabelle und verlangt, dass Schutzgrenzen
ihre Ausführung nicht verhindern. Für nächste getrennte Futuresvariante
frühere6%/8%-Hardgates durch Warnschwellen und gemeinsamen−50%-Kontostress
durch Diagnose ersetzen; keine Behauptung schon aktivierter Codeänderung.
Die Erklärung nahezu unmöglicher sofortiger−50%/immer nutzbarer Erholung
ist keine gemessene Marktgarantie. Auch langsamer Rückgang kann ohne erneutes
RSI-Rearm/unterschrittenem Netto-Breakeven zum Notausstieg/Liquidation führen;
späterer AI-Filter hebt Budget/Margin/Orderwahrheit nicht auf.
−55% und übrige Signal-/manuelle Reserve-/Liquidationsbedingungen erhalten.
Offen per Nutzerfrage: Tabellenbeträge eigenes Einstiegskapital oder Nominal.
Keine konkrete Futures-Marginaufteilung vor Antwort; alte Rechenkerne und
gefrorene Marktresultate bleiben unverändert, keine Live/Publicaktivierung.

## 2026-11-12 — D-080: Eigenkapitalstaffel mit akzeptierter Liquidation

Q42:293,13 erste Stufe ist eigenes Kapital; Kaufnominal=Kapital×Hebel.
Späterer AI-Agent soll2×–10× marktphasenabhängig wählen. Nutzer akzeptiert
bei höherem Hebel Liquidation vor allen fünf Käufen, damit frühere
−50%-Überlebensgarantie je Fillstand für neue Variante aufgehoben.
Keine tatsächlichen marginlosen Käufe/Weiterkäufe nach Liquidation;
ungenutzte Stufen bleiben getrennt, manuelle Stufe6 und keine Fremdbasket-
Nachschüsse erhalten. Hypothetische spätere Liquidation diagnostisch.
Fixierung je Basket oder Neubewertung je Nachkauf ist noch gefragt;
keine rückblickende perfekte AI/garantierte profitable Erholung.

Lesende Modellrechnung vorhandener Kern,10000/drei Slots, feste2/5/10×,
Kaufpreise100/95/90,25/85,7375/81,450625, angenommene RSI-Signale,
Maintenance0,5%/Closefeeschutz0,1%, keine Puffer/Funding:
2×/5× erreichen fünf Käufe, letzte Modellgrenzen44,282902/70,852643.
10× nach vier Käufen Grenze82,534159 vor fünftem Preis81,450625;
gestellte Stufenmargin1690,09875224, ungestellte Reststaffel1610,23128073.
Keine historische Liquidationshäufigkeit/Nettoleistung/Brokerpreis.
Kapitalprofil und Grenzen `docs/futures-capital-ladder.md`.
Keine Rechenmodule/Dependencies/DB/Public geändert; Entscheidung und
arithmetisches Beispiel, Marktleistung weiterhin eigenes eingefrorenes Profil.

## 2026-11-12 — D-081: AI-Hebel für gesamten Basket beim Start festlegen

Q43 bestätigt explizit: AI-Profil bewertet Marktphase/Risiko vor dem ersten
Kauf und friert den Hebel für den kompletten Basket ein. Alle regulären
Nachkäufe und bestätigte manuelle Stufe6 verwenden denselben Hebel.
Keine stufenweise Erhöhung oder Regimeanpassung offener Baskethebel.
Neue Baskets erhalten neue Bewertungen.2×–10×-Rahmen und Q41/Q42 erhalten.
Exakte Kriterien/kausale Regimevalidierung noch offen, keine aktive AI,
Renditebehauptung oder Runtimeänderung. Die bisher offene Hebelfixierungsfrage
ist damit beantwortet; Kapital-/Hebelprofil und Navigation aktualisiert.

## 2026-11-12 — D-082: Separater Futures-Kapitalkern setzt Q41–Q43 um

Nutzer beauftragt weitere Implementierung. Main bleibtd749081;49c93b6
noch nicht gemerged, daher bestehender Branch fortgesetzt.
IP-073 CapitalPlan/State/Assessment im eigenen Modul, bestätigte sechs
Eigenkapitalgewichte, feste2×–10×-Zyklusentscheidung, nur fünf automatische
Kapitaladmissions. Keine AI-/RSI-/Brokerautorität aus diesen Methoden.
6%/8% Warnungen und−50%/hypothetische Liquidation Diagnosen, tatsächliche
Deckung/Fees/Raster/Tag/Revision weiter verbindlich.
Initialmarginbasis im neuen Modell aus tatsächlichem Einstand/Mark,
First-fill-Anker ausschließlich Stress; deklarierte Modellannahme.

Neue explizite volle Liquidation mit Restmargin/Fees/Versicherungsbeleg,
Abgleich in einem reinen Ledgerübergang; kein angenommener Nullreststand.
Liquidierter Zyklus gesperrt, ungestellte Reserven getrennt; verlorene Margin
nicht erneut finanzieren und andere korrekt gedeckte Baskets nicht deswegen
sperren. Altplan-Hooks defaultidentisch, neue Pläne explizit aus Legacy-
Pending/RSI-Adaptern ausgeschlossen. Sieben akzeptierte Legacyzustände
gegen HEAD exakt gleiche Digests. Normale Abschlüsse erneuern das
Kostenbudget pro Zyklus, ohne bezahlte Gebühren zu erstatten; tatsächliche
Überschreitungen bleiben Budgetfehler.35 abgeschlossene Zyklen belegt.
Neue24 synthetische Fälle grün;
293 gepinnte Futuresfälle/379 Subtests im ersten Lauf inkl22 neuer,
danach87 Kapital/Pending/Signal mit34 und21 Langpending/Journal mit17
Subtests grün. Abschließend55 Kapital/Ledger mit37 Subtests und erneut
identischen sieben Legacydigests:295 unterschiedliche Fälle insgesamt,
24 neue, keine Summenaddition.
Keine Dependencies/DB/Migrationen/Credential-/Runtime-/Publicänderungen.
Nächstes IP-074: RSI/H1-Schutz/nativer Marktvergleich inklFunding und
vollständigem Langrestore; heutige Hashwurzel allein kein Restore.

## 2026-11-12 — D-083: H4-RSI und kausaler H1-Schutz am neuen Kapitalkern

Nutzer bestätigt Merge und erlaubt eigene Pull Requests zur Nutzerfreigabe.
`b9a9c0e` als Ancestor von Main`452c9d8` verifiziert; neuer Featurebranch
`feat/m1-futures-rsi-h1-protection`. Keine eigenständige Mergefreigabe.
GitHub-PR-Integration gesucht/vorgeschlagen; Deploy-SSH kann pushen, besitzt
keine automatisch abgeleitete API-/PR-Authentifizierung.

IP-074 eigener `futures_capital_signals.py`: vollständige geschlossene H1-
Trade-/Markachsen, vier Stunden exakt zu H4-RSI14/Wilder aggregiert; strikt
zwei Unter30-Erstwerte, tatsächlicher Rearm und5%-Abstand für fünf Stufen.
Die sechste bleibt manuell. Feste Basketentscheidung vor Erstkauf; keine AI.
Getrennte H1/H4-Supertrendindikatoren auf derselben Preisachse, alte Stopprüfung
vor neuer geschlossener Linie; explizite Intrabarbeobachtungen statt OHLC-Pfadfantasie.
6%/8% nur Warnungen, echte Deckung/Integritätsconstraints bleiben.

Liquidation ist vor neuen Einstiegen terminal abzugleichen; eine Erholung
löscht die bereits beobachtete Pflicht nicht. Mark-only-Evidence vor Funding
erfindet keine Tradebeobachtung. Netfloor berücksichtigt signed Funding und
Teilverkaufs-PnL; normale Zykluswechsel erhalten Indikator-/Gebührenhistorie.
Genesis-only-Start, kein frischer Wrapperrestore über fortgeschrittener Ökonomie.

27 neue Host-/gepinnt synthetische Fälle,105 gezielte Kapital/Legacy-Signal/
Timeframefälle mit46 Subtests grün. Eigenreview, keine Agentdelegation.
Keine bestehende Modulmutation, Dependencies, Migrationen oder Publicänderungen.
Native H1-Kohorte mit mindestens drei echten Coins, Fundingnominal-/Kosten-/
Margin-/Liquidationsannahmen und neuer vollständiger Journalrestore bleiben
IP-074/IP-069. Keine neue native Futuresrendite oder Holdoutauswertung.

## 2026-11-12 — D-084: Native H1-Kohorte und bestätigte GH-CLI

Nutzer bestätigt Merge;2d7878f als Ancestor von Main507cb87 verifiziert.
GitHubplugin meldet installiert, Werkzeuge noch nicht in Sitzung verfügbar.
Nutzer richtet Konto ein und provisioniert anschließend GH CLI auf dem Host.
GH2.46.0 ist als cadm-balzer mit repo/read:org angemeldet. Ein sandboxbedingtes
„invalid token“ wurde durch erlaubte externe Statusprüfung widerlegt; keine
Authänderung, kein Tokenoutput. Nutzer erlaubt eigene PRs und genehmigt sie
selbst; keine eigenständige Merge-/Deployfreigabe.

IP-075 eigener H1-/Fundingvertrag für die bereits erklärte Fünf-Coin-Kohorte:
BNB/BTC/ETH/SOL/XRP,2022-08-01..2025-08-01. Protokoll vor Netzwerk eingefroren,
sha3b3ecdd1b9c630a59e0b5f33f1255b0012c73dce7274bba81ee3435224336c57.
Create-only Import mit gleicher nativer Trade-/Markachse; alle15 tatsächlichen
Dateien unabhängig zurückgelesen und Hash-/Datasetdigest-/Fensterabgleich.
263040 native Kerzen,16515 Fundingevents,295 öffentliche GETs. Erster
sandboxgesperrter DNS-Lauf ohne Receipt, ausdrücklich autorisierter neuer
Netzwerklauf in eigenem Ziel erfolgreich. Kein Holdout oder anderer Markt.

SOL:75 zusätzliche einzigartige native Abrechnungen in den erklärten8h-
Buckets2022-11-09..18; behalten, keine Dedupe/Zeitrundung/Nullersetzung.
Alle8h-Buckets sind belegt, aber Kalenderdiagnose „alle gleich“ korrekt false.
6920 ältere native Settlement-Markpreise fehlen weiterhin; Raten vorhanden.
BTC/ETH-Funding identisch zur alten Quelle. Je Coin zwei H4-Trade- und eine
H4-Markabweichung zwischen H1-Aggregation und alter nativer H4-Quelle, vollständige
Preise/Hashes dokumentiert. Ursache offen, keine stillen Quellkorrekturen.
Beide neuen Schutzvarianten verwenden dieselbe H1-Achse.

22 neue Hostfälle; zunächst49 gepinnte Quellenfälle/78 Subtests, abschließend
17 H1-Fälle/34 Subtests inkl zusätzlichem SOL-Kalenderfall.50 unterschiedliche
geprüfte Fälle, Überschneidungen nicht addiert. Eigenreview, keine Delegation.
Keine neuen Dependencies, Migrationen, privaten Calls oder Runtimeaktivierung.
Nächster Nettojob benötigt erklärte Kosten/Fundingnominal-/Margin-/Liquidations-
annahmen sowie vollständigen Restore/Kapazität des neuen Kapital-/Signalprofils.

## 2026-11-12 — D-085: Vollständiger Kapital-/Signalrestore mit größeren ID-Historien

Nutzer bestätigt erfolgreichen GH-CLI-PR und Merge; Weiterarbeit autorisiert.
IP-075`fd99018` als Ancestor von Main`d0fa375` verifiziert; Featurebranch
`feat/m1-futures-capital-journal`. Eigene PRs zur Nutzerfreigabe, kein Selfmerge.

IP-076 ergänzt eigenes `futures_capital_journal.py`, ausdrücklich neue
Genesis mit vollständigem Kapital-/Kostenplan, H1/H4-Schutz, ursprünglichen
Trade-/Markpreisen, UTC-Mitternacht, Protokoll-/Datasetdigests und Grenzen.
Alle typisierten Stunden/feineren Beobachtungen/Leverageentscheidungen/
Assessment-Vollkäufe/Funding/Mark-only/Marginrestoration/Teil-/Vollexits/
Liquidationsbelege werden durch den vorhandenen Kern gefaltet.
H4-Puffer, RSI-Rearm, fünf Stufen, feste Hebelzyklen, Tagesbasen, alle Kosten,
Trailings und terminale Verluste bleiben erhalten. Kein automatischer Stufe6-
Input oder Neustart über fortgeschrittener Ökonomie.

Eigene `CapitalIdentityHistory` mit separater Hashdomäne/balancierten immutable
Knoten; Default250000, explizit1..1000000 IDs. Alter100000-Maximalvertrag und
alle bestehenden Module/Exporte/Codec unverändert. Largerpolicy nur in neuer
flat Journalgenesis, niemals ID-Verwerfen oder Bestandskonvertierung.
Record256KiB/Datei512MiB/Commands250000; Ressourcenerschöpfung ohne Erfolg.
0600/Owner/Regular/Leaf-Symlink-/Hardlinkschutz/exklusiver Writerlock,
vollständiger Write/fsync und Parentfsync. Unknownwrite sperrt Reads/Appends;
vollständiger Readback mit bestätigtem Mindestanker statt Retry/Tailreparatur.

22 erste gepinnte neue Fälle/28 Subtests,77 direkt angrenzende Fälle/
45 Subtests einschließlich ergänztem Funding-/Marginfall. Abschließend
Mark-only-Variante dieses Falls einzeln Host/gepinnt grün:23 neue/
99 unterschiedliche gepinnte Fälle, überlappende Läufe nicht addiert.
Synthetischer Fünf-Coin-Lauf1200 Stunden/vier feinere Quotes je Stunde:
6000 Commands,6050 retained IDs; vollständiger Restore mit gleichem State,
Receipt und ursprünglicher ID. Baumtest prüft alle100005 IDs jenseits
Legacymaximum und alte immutable Präfixe. Kein nativer Renditebefund.
Eigenreview, keine Delegation/breiten Wiederholungen/Dependencies/Migrationen/
DB-/Runtime-/Publicänderungen oder weiteren Markt-/Broker-/Holdoutzugriffe.
Nächster Nettojob: wirtschaftliches Profil vor Auswertung einfrieren,
Fundingnominalreferenz/Fees/Slippage/Intrabarweg/Maintenance/Liquidations-
abrechnung samt Kostenstress; gemeinsamer nativer H1-/H4-Schutzvergleich.

## 2026-11-12 — D-086: Eingefrorene Wirtschaftsannahmen und native Fundinggrenzen

Nutzer bestätigt IP-076-Merge;29d76d9 als Ancestor von Mainef2aa9b verifiziert.
Featurebranch `feat/m1-futures-economic-profile`. GH-CLI-PR zur Nutzerfreigabe;
keine eigene Merge-/Deploy-/Livefreigabe.

IP-077 vor erster Marktleistung eingefroren:
futures-capital-economics-20261112.json,
shaeb9a278513facb4f7560413c6ae269dc2fd44adf917eec00ebec9925ddcc8c06.
Fünf feste native Slots BNB/BTC/ETH/SOL/XRP,10000 USDT, bestätigte Staffel
mit1%-Costreserve. Sechs Basisfälle2×/5×/10× und H1/H4-Schutz; zwei2×-
Kostenstress- und zwei2×-Reihenfolgefälle. Feste deklarierte Baskethebel,
keine AI-/Gewinnetappenwahl. Normale Slotreuse, liquidierte Slots terminal.
Gebühren/Slippage/Maintenance/Lot/Insurance sind deklarierte Modelle,
keine historischen Binance-/Bitgettarife oder Brokeracceptance.

NativeFundings unverändert, vorhandene Marks oder explizite H1-open-Näherung;
Kostenstress verdoppelt nur positive Raten. Quellheader bleibt nativer Ticker,
Kerzen BINANCE:<ticker>:USDT-M:<kind>, neue Ledgeridentitäten BINANCE:<ticker>.
10937 native Ereignisse exakt auf voller Stunde brauchen valued_hour-
Markbewertung vor Tagesbasis, keine Markphase0 nach Tagesphase1/Zeitenverschiebung.
Gleichzeitige Settlements als kanonischer atomarer Fundingbatch, einzeln
behaltene IDs und vollständiger Journalrestore; spätes Scheitern ohne halben
Append. Unveränderte normale Hour-Replays bleiben geprüft.
Gapexits können unter Nettofloor verlieren; Liquidation inklusive ausdrücklich
angenommener isolierter Versicherung separat abgeglichen. Erholung ersetzt
ursprüngliches unsicheres Preisbild nicht; unveränderter Preis plus fälliger
Fundingcredit benötigt ursprünglichen unsicheren Zustand als trusted Input.

Create-only nativer Quellenpreflight: alle15 Hash-/Datasetbindungen/
Fenster/Achsen und sämtliche Fundingreferenzen für zehn Profile geprüft.
263040 Preise,16515 Settlements,3363 Zeitgruppen/max5, je Profil9595 native
Marks/6920 Open-Näherungen. Kostenstress verändert11335 positive Raten.
Receiptsha2252c6f78054a482a2eb67ecdc344d517aeb46083ce518141ccf0c00b549064c.
Erster Lauf ohne Receipt am fehlenden Venuepräfix abgewiesen; nächster eigener
Lauf wegen unnötiger vollständiger Datasetdigest-Neuberechnung pro Referenz
gezielt beendet. Nach Cache pro Stream neuer eigener Output erfolgreich;
keine Rohdaten-/Receiptüberschreibung oder performancebasierte Protokollwahl.

53 erste gepinnte Fälle/26 Subtests,16 korrigierte Profilfälle, drei neue
Preflightfälle/finale Identität sowie drei verschärfte Liquidationsevidenzfälle:
27 neue/56 unterschiedliche gezielte gepinnte Fälle bestanden, keine Addition
überlappender Läufe. Native readback/Hashes zusätzlich erfolgreich.
Eigenreview, keine Agentdelegation/breiten Wiederholungen/Dependencies/
Migrationen/DB-/Runtime-/Publicänderungen oder zusätzlichen Netzwerkimporte.
Noch kein Nettoleistungslauf; nächstes IP-074/IP-069 ist vollständiger nativer
Marktjob mit allen eingefrorenen Fällen, Funding/Costs/Exits/Liquidation/
Endbewertung und Journal. Holdout und tatsächliche Broker/AI bleiben aus.

## 2026-11-12 — D-087: Vollständiger nativer Marktjob und Modellbremsen

Nutzer bestätigt PR48-Merge und erwartet den Backtest. `ca98561` ist Ancestor
von Main`ab3b4ab`; neuer Branch`feat/m1-futures-market-backtest`. Umsetzung
und GH-PR bleiben autorisiert, ohne eigene Merge-/Deploy-/Livefreigabe.

IP-078 verwendet die unveränderten zehn eingefrorenen IP-077-Varianten und
dieselbe native Fünf-Coin-Kohorte2022-08-01..2025-08-01. Create-only Ausgaben:
vollständiges Journal, stündliche Equity samt Ereignis-Min/Max, geschlossene
Basketbelege, realisiertes/offenes Netto, Gebühren/Funding/Insurance, Kaufstufen,
Kapitalablehnungen und Marginbindung. Erfolg erst nach vollständigem Fold ab
Genesis gegen bestätigten Mindestanker. Alle zehn Fälle vor Gesamtreceipt.

Offener Modellpreis bei+1s, bestehende Exitpflichten zuerst; bei+2s vollständige
Bewertung desselben frischen Open, eigene Costrestoration und mögliche Käufe.
Erster synthetischer Job hatte wegen unvollständiger same-time Markevidenz
nur den ersten Slot zugelassen; Ursache korrigiert, fünf gleichzeitige Baskets
geprüft. Native Fundings inklusive0/18ms unverändert, keine zwischenzeitlichen
Käufe im Batch. Keine Auto-Stufe6, Liquidation vor Erholung/Nachschuss,
Endbestände ausschließlich MTM. Wirtschaftlich leere Intrabarquotes entfallen;
Vergleich mit vollständigen Quotes erhält alle wirtschaftlichen Kennzahlen.

Eigene gecachte kanonische Kapital-JSON-Fragmente sind byteidentisch zum alten
Snapshotdigest, einschließlich aller Ereignisse/Staffelbelege. Begrenzte
Dataclass-Schemata und unveränderliche Digestproperties gecacht. Keine neuen
Hashfelder/Versionen oder Historyverkürzung. Original335-Command-Journal mit
gleichem Receipt restauriert; zusätzlich alle57044 native Commands plus
Genesis und26305 Equitypunkte vor/nach Optimierung bytegleich.
115 unterschiedliche gezielte gepinnte Tests/166 Subtests bestanden, sieben
neue Marktjobfälle; überlappende Läufe nicht addieren.

Paralleler Prozesskanal zuerst von Sandbox verweigert; freigegebener Hostpool
verlor anschließend einen Prozess. Ursache nicht endgültig bewiesen. Auf dem
2-GB-Host nur eine geladene Kohorte/Variante gleichzeitig. Erster sequenzieller
Lauf nach Hashnachweis während Restore gezielt beendet; sämtliche gescheiterten/
unterbrochenen Outputs ohne Erfolgsreceipt erhalten. Aktueller tatsächlicher
Lauf: `infra/local/futures-capital-research/20261112-market-canonical`.

Erste vollständig restaurierte Basisbefunde:2× H1+687,70 USDT,
Drawdown6,83%,51 geschlossene Baskets/eine Liquidation; Käufe51/18/7/1/1.
2× H4−7,28 USDT/fünf geschlossene Baskets;5× H1+1670,50 USDT/
Drawdown9,53%/zwei Liquidationen. Alle zehn Varianten inzwischen abgeschlossen:
451193 vollständig restaurierte Commands,40 Artefakthashes/907593935 Bytes.
Basis-H4 netto−7,28/−213,35/−725,44 USDT bei2×/5×/10×; H1−625,65 bei10×.
Kostenstress H1/H4+406,00/−11,88; alternative Reihenfolge+659,81/−7,28.
Erfolgsreceiptsha9e7802ecbc7d99bb44d8430ae4b9200c37633cfab5d276c0f8ec5c3e31bc5897.
Host-Python3.14.4; Checks gepinnt3.14.10. Kopierte Einzelreports stimmen mit
Gesamtreceipt überein, Marktjob-Implementationshash geprüft. Keine offenen
Endbaskets im realen Kohortenlauf; offene End-MTM synthetisch belegt.

Wichtige Modellbremsen statt Leistungsfreigabe: BNB2× H1 stoppt am2023-10-27
wegen19,94285425 kumulierter Brutto-Kosten gegen19,80198020 Reserve trotz
+38,63514762 Fundingnetto und nur0,27569574 Costrestoration. Gutschriften
vermindern den historischen Brutto-Kostenzähler nicht. H4 reserviert alle
ursprünglichen Ranges auch für leere Slots; kleiner realisierter Verlust
blockiert deshalb weitere Einstiege (887 Cashablehnungen). Keine6%/8%-Gates.
Vor Rendite-Feintuning separates neues Forschungsprofil mit echten eigenen
Cash-/Fundingkosten und vollständiger Rangebindung für aktive/neu aufzunehmende
Baskets prüfen. Keine rückwirkende Änderung der eingefrorenen Varianten oder
Zusage verbesserter Rendite; bisherige Stufen/Manualreserve/Finanzierungs-/
Margin-/Liquidationsconstraints bleiben zu sichern.

Eigenreview, keine Agentdelegation, Dependencies, Migrationen, DB-/Public-
Änderungen, neuen Marktimporte, Holdout, private Broker oder aktive AI.
Cockpit/auth reguläres TLS/HTTPS200 nach vollständigem Lauf. IP-074/IP-078
technisch abgeschlossen; IP-069 wirtschaftliche Broker-/Kalibrierungsprüfung
offen, nächste Modellkorrektur IP-079 separat. Results:
`docs/futures-market-results-20261112.md`.

## 2026-11-12 — D-088: Nachgewiesene Basket-Budgetbremsen korrigieren

**Status: beauftragt; Implementierung geprüft, Marktvergleich läuft.** Nutzer
beanstandet die geringe Dreijahresperformance und vermutet blockierte Baskets.
IP-079 korrigiert die zwei IP-078-Nachweise in separatem
`isolated-usdt-capital-cash/2`, statt die alten Ergebnisse umzudeuten:
alle Gebühren plus max(Restoration, negatives Nettofunding,0) als eigene
Kosten; Fundingcredits bleiben isoliert und decken spätere Belastungen.
Cash muss nur aktive/beantragte vollständige Ranges sowie gestoppte Reserven
decken, keine hypothetischen unbeanspruchten Leerslots.

Eigenkapitalstaffel/Manualreserve/fester Zyklushebel und reale Margin-/
Liquidations-/Kosten-/Orderregeln bleiben verbindlich; 6%/8% Warnungen.
Originalauftrag ausdrücklich erneut abgeglichen: RSI-Rearm und 5%-Abstand
bleiben auch für reguläre Nachkäufe erhalten. Kein automatischer Kauf nur
wegen Kursrückgang; keine KI-/Live-/Holdoutaktivierung oder Kostenkalibrierung.

Vor erneutem Lauf bytegebundenes Protokollsha
1dfc67d29dcc5f89e72a610d43823b7041470810f10e3757d7fd2d135effb4fa,
identische zehn Wirtschaftsfälle/nativer Quellenbestand. 160 unterschiedliche
gezielte gepinnte Tests/101 Subtests grün, einschließlich vollständigem
neuem Marktjournalrestore. Finanzielle Ablehnungen und frische H4-Signalfilter
getrennt gezählt. Eigenreview ohne Agentdelegation; kein breiter DB-/UI-Testlauf.
Codecheckpoint4146877; PR49 noch OPEN, Korrektur wird dort ergänzt.
`docs/futures-cash-budgets.md`.

IP-079 Abschlussbeleg der technischen Korrektur: beide vollständigen nativen
2×-Jobs/Restores bestanden, H1/H4 netto+2507,71/+2410,79USDT statt
+687,70/−7,28;107/106 geschlossene Baskets, je eine Liquidation, keine
Budgethaltes/offenen Endbaskets. Reguläre Stufen107/38/16/6/2 und106/38/16/6/2;
mittlere Eigenmargin605,87/701,74USDT. Acht geprüfte Artefakthashes;
Zwischenreceiptsha9ee1731f5859ead3edbd577e6d0f519b71df002c1a3c5f468a2c8b2b93dd33a9.
All-ten-Gesamtauswertung läuft lokal unter IP-069 weiter, nicht abgeschlossen.
Kein weiterer LLM-/Agentaufruf innerhalb des Python-Datenjobs.
Nächster bereits autorisierter H1-RSI-Einstiegsvergleich IP-080; keine
Änderung der laufenden acht gebundenen Implementationsdateien bis Jobende.
`docs/futures-cash-interim-20261112.md`.

## 2026-11-12 — D-089: H1-Futuresvergleich und bestätigte eigene Abschlusskostendeckung

**Status: beauftragt, Q44 bestätigt.** PR49-Merge verifiziert:
head0cd45d5 in main0c0c7ce. Alle zehn IP-079-Jobs/Restores fertig;
666180 Commands/40 erneut geprüfte Artefakthashes, Receiptsha
979880a5b9fdcadc1a8aa8f11f23e7e1af158c86b68d4ea3d27c2b282470476e.
Neue Arbeit auf feat/m1-futures-h1-entries.

IP-080 vor Leistung eingefroren, neue H1-Signal-/Journalidentität,
gleiche Cashstaffel/H1-Schutz/2×. Native Auswertung vollständig restauriert:
+2643,89 USDT, DD17,62%,43 Abschlüsse, keine Liquidationen, Stufen43/23/15/9/7.
Receiptsha3c6fdfb5b1c5ec6129f9bc7e4c4f1368ec19761f06e0d628707f8b72f12ed130.
Handel endet bereits2023-01-16: profitabler BTC-Zyklus4 (+446,84 netto)
überschreitet Kostenreserve um2,29516530 beim vollständigen Exit und löst
globalen Halt aus. Inputkostenfold/Command17473 deckt sich mit Abschluss.

Nutzer bestätigt Q44 ausdrücklich: „Ja, nur aus dem eigenen abgeschlossenen
Basketgewinn (empfohlen)“. IP-081 separate realized-cash/3-Policy erlaubt
nur vollständigen normalen eigenen Abschlussnettogewinn≥gesamten Überhang.
Alle Gebühren/Funding weiter einmal vollständig netto; keine Zusatzgutschrift,
fremde/unrealisierte Gewinne, Teilverkäufe, Liquidationsexzeption oder
Haltlöschung. Offene Budgets, volle Kaufstaffel und manuelle Reserve bleiben.
174 unterschiedliche gezielte gepinnte Tests/103 Subtests grün,
14 neue Fälle in080/081. Neue Protocolsha
719716bcc813c1fa22de769c2b86ed43d72b4e0d29a9d133065c06cf0cbf339a
vor separatem nativen H1-/2×-Lauf eingefroren.
Nach Daemonrestart2026-11-13 tatsächliche vollständige Receipt geprüft:
64277 Commands, vier Artefakt- und acht Implementationshashes erneut geprüft.
Receiptsha893bfedeb260b9f4b44589c2719a9135e4876ceda72c87f6285a5294b0c952db.
Netto+3928,28 USDT/DD17,62%,98 Abschlüsse/keine Liquidationen,
Stufen98/48/30/16/13. Der vorherige profitable BTC-Abschluss löst keinen
Halt mehr aus. Nächster Halt2023-10-02, XRP-Zyklus21, Fundingbatch43858:
eigene offene Kosten19,94101471 überschreiten19,80198020 um0,13903451.
Dieser offene Fall ist ausdrücklich nicht in Q44 enthalten. Kein
durchgehender Dreijahreshandel. IP-082 bereitet einen separaten konkreten
Funding-/Haltedauerbudgetvorschlag vor; neue offene Limits nicht unterstellen.
Keine Agentdelegation, DB-/Credential-/Frontendwiederholungen oder
AI-/Holdout-/Live-/öffentliche Aktivierung.

IP-080/081-Checkpoint65a5513 gepusht; PR50
https://github.com/cadm-balzer/Investalo_Trading-Platform/pull/50 offen,
kein Draft, mergebar. Nutzer übernimmt Review/Merge. Öffentliche
Cockpit-/Auth-HTTPS-Abfragen beide200, laufende Container unverändert.
Zusätzliche reine read-only Protokollmounts im Prüfscript mit `bash -n`
geprüft; keine weitere wirtschaftliche Codeänderung oder breite Wiederholung.

## 2026-11-13 — D-090: Reserviertes Budget ohne zusätzlichen Fundingquotenhalt

**Status: beauftragt, Q45; Umsetzung separat vor Auswertung eingefroren.**
PR50 gemerged, head6dfde31 Vorfahr von mainbde1cee über GH/Fetch geprüft.
Nutzer verlangt, dass das fest reservierte Basketbudget keine zusätzliche
Handelsbremse erhält. Interpretation: Funding ist bereits aus eigener
isolierter Margin bezahlt; nur tatsächliche Walletgebühren/Restoration
verbrauchen die Kostenbarreserve. Neues reserved-cash/4-Profil,
keine Änderung historischer Policys1–3. Restoration hält Gebühren für
restliche reguläre Käufe/deklarierten vollständigen Ausstieg zurück.
Alle sechs Eigenkapitalbeträge bleiben identisch, keine manuelle/fremde
Reserve oder unrealisierten Gewinne als erfundene zusätzliche Cashquelle.
Echte Initialmargin, Liquidation und Gelddeckung bleiben verbindlich.
Q44 gilt weiterhin für eigenen vollständigen profitablen Normalabschluss.

183 unterschiedliche gezielte gepinnte Prüfungen/108 Subtests bestehen,
neun neue. Ein Test-Fixture erhielt höhere Fundingbelastung, um den alten
Halt tatsächlich auszulösen; nur die betroffenen zwei Markttests wiederholt.
Full-Genesis-Restore des neuen Profils synthetisch geprüft. Rootreview,
keine Delegation, breiten DB/Credential/UI-Suites oder neue Abhängigkeiten.
Protokollsha b1892df1eac4a66f157b0576b1efef7017f0e62bccc10c2bedb110441316be21
vor nativer Leistung eingefroren. Eigene acht Startimplementationshashes
in /tmp/investalo-reserved-implementation-start.json;
Job20261113-h1-reserved-cash läuft, unveränderte fünf native Coins/
Dreijahresquelle/2×/H1-Signal und Schutz. Keine aktive AI, Live, Holdout,
Reinvestition, öffentliche Profiländerung oder Migration.

Nativer Job/Vollrestore abgeschlossen und vor weiteren Implementationsänderungen
exportiert:109440 Commands, vier rehashte Artefakte und acht Start-/End-
Implementationshashes stimmen. Receiptsha
4e7d902c7127b317932c75e3b3878ffcaa3971c7863f077f477d2ca490713cec.
Netto+9579,93 USDT/DD17,62%,269 Abschlüsse/keine Liquidationen/Kontohaltes,
Stufen271/126/72/37/24. Letzter tatsächlicher Einstieg2025-07-29,
letzter Abschluss2025-07-28; zwei Endpositionen zum Markkurs, keine erzwungenen
Profitabschlüsse. Keine Budget-/Cashablehnung;29 deklarierte Initialmargin-
und32 Fillbound-Ablehnungen bleiben für separate IP-083-Diagnose.
Keine stillen Änderungen der Margin-/Preisgrenzen oder neuen Geldquellen.

## 2026-11-13 — D-092: Aktuelle Classic-Raster getrennt von Geldrundung sichern

**Status: IP-084 abgeschlossen, keine wirtschaftliche Policyänderung.**
Nutzer bestätigt PR52 gemerged; head8d71aeb ist Vorfahr von main5a89712.
Eigener Featurebranch feat/m1-futures-broker-calibration.
Ein fixer unsigned Bitget-Classic-USDT-Contract-GET;685029 Antwortbytes
lokal hashgebunden, fünf originale Objekte im Repository gesichert.
Aktuelle Mengenraster BNB.01/BTC.0001/ETH.01/SOL.1/XRP1,
öffentlicher Takertarif.0006, nicht individuelles Konto oder historische Regel.
Diese2026-Bitget-Quelle wird nicht als2022–2025-Binance-Brokerregel ausgegeben.
Receiptsha61c50ac6bc85b86ee176f1c7d926153d899f16c4b4cbeec35437a1a1a37d6e5c.

Alle51 hashgebundenen IP-083-Ablehnungszeilen statisch geprüft, keine Menge
bereits auf aktuellem Raster. Nur vorgeschlagene Menge heruntergerundet,
altes Basis-/Mark-/Preis-/Kapitalmodell unverändert. Alle19 reinen XRP-
Marginreste dadurch unter alter Formel gedeckt; Headroom.0037758872 bis
1.1089281855 USDT. Kein neuer Fill/Journalfold/PNL-Nachweis; Preisraster,
Gebührenfreeze und weitere Brokerzulassung werden nicht behauptet.
Probereceiptshad95eb94d18a46e67f67fd6e0f31de59cfd6186905715028de4be5cba64a22ab1.
Zehn Referenzmodule unverändert, neue drei Implementationshashes gebunden.

Classic-Marginguide beschreibt Long-Eröffnungsverlust bei Order>Mark.
Das bestätigt nicht den bisherigen pauschalen Mark>Maxfill-Guard.
Keine UTA-Formelübertragung, keine Ableitung von USDT-Buchungspräzision
aus Preis-/Mengenstellen und kein ungeprüftes Money-Epsilon.
Geldquantum/Rundungsrichtung, historische Tiers und Kontotarife bleiben offen.
IP-085 plant eine eigene vorab eingefrorene rastergerechte Forschungsvariante.

16 unterschiedliche fokussierte gepinnte Fälle/20 Subtests bestehen.
Der erste Netzwerksandboxversuch scheiterte ohne Receipt; ein bewusster
neuer Capture außerhalb der Sandbox erfolgreich. Erste lokale Proben
stoppten an der größeren audit-internen Dezimalpräzision. Begrenzter eigener
Auditcodec plus reale XRP-Referenz beheben dies ohne bestehenden Codec zu
ändern. Fehlordner erhalten. Eigenreview, kein Subagent/breiter unveränderter
Regressionstest/neuer Marktjob/AI-/Live-/Holdout-/Public-/DB-/Dependencywechsel.
Siehe docs/futures-broker-calibration.md.

## 2026-11-13 — D-091: Verbleibende Ablehnungen vollständig erklärt

**Status: IP-083 abgeschlossen, wirtschaftliche Regeln unverändert.**
PR51 head7c239a2 ist Vorfahr von main165c5f4; GH/Fetch verifiziert.
Eigener nur lesender Journalabgleich auf feat/m1-futures-admission-audit.
Alle109440 Commands, exakter Endreceipt,530 echte Käufe/581 Kandidaten,
vier ursprüngliche Artefakte und zehn Start-/Endimplementationshashes
bestätigt. Erfolgsreceiptsha
4e4b5bf91f13cd8771c0f18b051d28b79305a34e4e8695ea90f3d0faa8d5c86b;
Evidence198c9a3ac87b92f141b6583113731842980ade9f989a62601c86940ebb9ee305.

51 abgelehnte Versuche:22 nur Preis,19 nur Margin,zehn beide.
34 Coin-/Zyklus-/Stufenkombinationen;33 wurden später tatsächlich ausgeführt,
entsprechend50 Versuchen.530 Entrycommands gelesen,271 tatsächliche
Zyklusidentitäten gegen269 Abschlüsse/zwei Endbaskets bestätigt.
Einzige nicht später ausgeführte Stufe: XRP49/Stufe5 am2025-04-09,
nur Preisbound. Keine hypothetische Mehrgewinnrechnung.

Alle19 reinen Marginablehnungen sind XRP-Rundungsreste:
3,76911191307543E−10 bis7,376838495785480E−9 USDT, unter Quantum1E−8;
eigene Restorationkapazität7,7667–14,0104 USDT, also nicht erschöpft.
Abgerundete Restoration plus Mengenraster und exakt-dezimale Marginregel
verursachen die kleine Modellbremse. Ein weiterer XRP-Fall kombiniert
Rundungsrest und Preisbound. Die übrigen neun Marginablehnungen sind
erste Käufe mit Markpremium, höchstens0,89987382 USDT. Alle später gefüllt.
32 Preisbounds: Mark liegt0,04394–51,16403bp über Trade×1,0005.
Diese Regel ist nicht als historische Brokerablehnung belegt.
Nächster Schritt: Geldquantisierung/Broker-/Kosten-/Mengenregelkalibrierung
mit eingefrorenem Referenzanker; keine neue Kapitalquelle/Grenzaufhebung.

Neun unterschiedliche gepinnte Tests/zehn Subtests bestehen. Der erste
Abgleich wurde durch Daemonneustart unterbrochen. Der nächste bestätigte
Kette/Zähler, aber der neue Export scheiterte an flachem dict-primitive und
Text-/Bytegrenze. Explizite Dezimalstrings/UTF8-Bytes, zusätzlicher vollständiger
Exporttest und drei gezielt nachgeprüfte Fälle beheben dies. Erfolgreicher
finaler Lauf20261113-native-export-corrected; fehlgeschlagene Ordner ohne
Erfolgsreceipt erhalten. Keine breite Regression oder Marktperformance
wiederholt, kein Agent, neue Abhängigkeit/DB/Public-/AI-/Live-/Holdoutänderung.
IP-082 bleibt netto+9579,93/DD17,62% ohne Kontohalt/Liquidation.
