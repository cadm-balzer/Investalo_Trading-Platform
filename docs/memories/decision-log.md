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
