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
