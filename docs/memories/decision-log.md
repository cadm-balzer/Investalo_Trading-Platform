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
Die −40%-Schwelle, Freigabe nach fünf Stufen und RSI-Ausnahme in Q23 sind
**noch nicht bestätigt**. Ohne Auslöseregel bleibt diese Tranche unberührt.

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

**Status: Präferenz bestätigt, Q22; Ablauf in Q24 offen.** Nutzer möchte
E-Mail als ausreichenden Nachweis statt verpflichtendem unabhängigem Ersatzfaktor.
Best-Practice-Abweichung festhalten: Die Postfachübernahme könnte dann den
MFA-Reset ermöglichen. Authelia erlaubt kontobezogene administrative Faktorresets;
bei normaler Pflicht zum vorhandenen Faktor kein fertiger Mail-only-Selbstservice.
Q24 schlägt getrennte administrative Einmalchallenge, Sitzung-/Tokenentzug
und erneute MFA-Registrierung vor. Keine stillschweigende Automatisierung.
