# Roadmap

Stand 2026-11-07. Q1–Q5 bestätigen privaten Pilot, Paper zuerst, feste
Risikolimits, kontrollierte KI und kostenlose externe Dienste.
Q6–Q8 bestätigen beide Handelsintegrationen im MVP, Grundstack und eigene MFA.
Q9–Q14 bestätigen BTC/ETH Spot H4, XAUUSD Trend/Pullback H1/M15,
schriftliche Crypto-Vorlage, Quote-/Preisbezüge, Docker Compose und Authelia.
Q15/Q17–Q19 bestätigen RSI-/Supertrend-Regeln und Paper-/Demolimits.
Q16 reserviert die sechste Tranche ausschließlich für einen Notfall; Auslöser offen.
Q20 plant öffentlichen HTTPS-Einstieg für privaten Nutzerkreis, Q21 vorhandenen
SMTP, Q22 bevorzugt E-Mail-Recovery. Q23–Q28 bleiben offen.
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

## Meilenstein M1: privates Cockpit mit Backtests und Paper

Enthält: MFA-Anmeldung nach ausgewähltem Identitykonzept, Tenant-/Kontobindung,
Portfolio und offene Positionen mit Datenalter, Journal, eine Strategie je Brokerpfad,
Backteststart/-abbruch und grafische Auswertung, Paperstatus und Riskanzeigen.
Bitget und MT5 gehören beide zum MVP: BTC/ETH Spot H4 und XAUUSD Trend/Pullback
H1/M15 sind bestätigt, ebenso reguläre Crypto-Signale, Schutz und Risikoprofile.
Notfallpuffer und E-Mail-Recovery werden in Q23/Q24 konkretisiert.
Q28 stellt die M1-Abgrenzung von vollständigen KI-/News-/Kalenderfeeds ausdrücklich
zur Entscheidung; spätere Phasen sind insoweit noch eine vorgeschlagene Reihenfolge.

Abnahme:

- Ein frischer Checkout kann mit dokumentiertem Lockstand privat gestartet werden.
- Zwei Testmandanten können keine Daten, Jobs, Dateien oder Streams voneinander sehen.
- Ein Backtest wird identisch reproduziert; Kosten-/Fillannahmen sind sichtbar.
- Paper verarbeitet doppelte Zustellung und unklare Ausführung ohne Blind-Resend.
- Budget-, Drawdown- und Datenfrischeverletzungen sperren neue Exposition.
- Kontostände, Cashflows und PnL werden nachvollziehbar getrennt.

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
