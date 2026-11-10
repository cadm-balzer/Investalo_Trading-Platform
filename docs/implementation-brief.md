# Bestätigter M1-Umfang und Umsetzungsstand

Q37 ergänzt das spätere Ziel isolierter USDT-M-Long-Futures, marktphasenabhängig
2×–10× nach unabhängiger Risiko-/Liquidationsprüfung. Eigene Marginpuffer,
−50%-Stress vom ersten Fill und6%/8% bleiben; separate Futuresökonomie in IP-063.
Entwicklungspaper/Spotreferenzen unverändert. [Vertrag](futures-research.md).

Stand 2026-11-10. Sachentscheidungen Q1–Q30 und Abschlussbestätigung Q31
sind bestätigt. Der Nutzer beauftragt ausdrücklich den Umsetzungsstart.
Dieser Stand bündelt die bestätigte Planung; lokale M1-Implementierung begonnen.
Entscheidungsverlauf: [interview.md](interview.md).

Q33 ergänzt die Planung für3–5 gleichzeitige Coinbaskets und spätere
KI-Prüfung von RSI-Signalen. Volle Kontokapitalzuordnung wird von tatsächlicher
Investition getrennt;6%/8%-Kontolimits bleiben ausdrücklich bindend.
Gemeinsamer Portfolio-Research folgt IP-055. Die größere Budget-/Stressverteilung
ist mit Q34 für Forschung bestätigt; zusätzliche Coins und Hebel/variable
Stufen sind noch festzulegen/validieren;
das bisherige Entwicklungsprofil bleibt unverändert.
[Portfolio- und KI-Plan](multi-basket-ai-plan.md).

IP-056 stellt die gemeinsame BTC-/ETH-Baseline für diese Erweiterung bereit:
ein Konto, atomare H4-Batches, Kapitalbindung und passive Referenz.
Die bestehenden500+5-Budgets bleiben dabei erhalten; erweiterte Allokation
und Coinauswahl folgen IP-055. [Befund](portfolio-reference.md).

IP-057 stellt gleiche Slots und gemeinsame Kauf-/Stressprüfung bereit.
Q34 bestätigt das Forschungsprofil; IP-058 verbindet die vollständige
RSI-Nachkaufstaffel damit. Coins, Wiederbelegung/Signalpriorität und
eingefrorene Leistungsläufe bleiben vor Aktivierung festzulegen.
[Konkretes vorgeschlagenes Profil](portfolio-allocation.md).
[Nachkaufadapter](staged-portfolio-research.md).

Das erste lokale Fundament umfasst gepinnte Compose-Dienste, HTTPS,
MFA/OIDC-BFF, DB-Mandantenisolation, ein Cockpit mit ehrlichen Leerzuständen
und den deterministischen Crypto-/Paperkern. Validierte H4-Snapshots werden
importiert; tenantgebundene Offlineworker berechnen eingefrorene Backtestjobs.
Das Cockpit zeigt tatsächliche Nettoergebnisse und Equitykurven mit Provenienz.
Brokerpfade, manueller UI-Einstieg, Recovery und Backupabnahme folgen.
Der lokale 90-Tage-BTC-Lauf erfüllt keine wirtschaftliche Holdoutabnahme.
Dies ist eine Zwischenabnahme, kein fertiger
M1-Pilot. Start/Prüfung: [infra/README.md](../infra/README.md).

## Erster Release

Privater Nutzerkreis per Einladung, Mandantentrennung von Beginn an,
öffentlicher zentraler HTTPS-Einstieg unter `cockpit.investalo.de`.
MFA-Anmeldung, Konten/Portfolio/offene Positionen mit Datenalter, Journal,
reproduzierbare Backtests mit grafischen Ergebnissen sowie **beide**
Paper-/Demopfade: Bitget und MT5.

BTC/USDT und ETH/USDT Spot ohne Hebel auf H4; XAUUSD Trend/Pullback mit
H1-Regime und M15-Einstiegen nach unabhängiger Kosten-/Risiko-/Kausalitätsprüfung.
Echte KI-Bewertung, vollständige News-/Kalenderfeeds und weitere Märkte folgen
als Ausbau. Schnittstellen dafür vorsehen.

## Strategie und Kapitalgrenzen

Crypto: RSI14/Wilder auf geschlossenen H4-Kerzen. Erster Kauf nach zwei
aufeinanderfolgenden `<30`-Kerzen; reguläre Nachkäufe nach Rearm `>30`,
einer `<30`-Kerze und mindestens 5 % Rückgang zum letzten tatsächlichen Fill.
Genau 30 kein Trigger, höchstens eine neue Stufe je Kerzenereignis.
Quote-Beträge wachsen 25 %, insgesamt fünf reguläre Stufen plus Reserve.

Die sechste Tranche bleibt **manuell**: nach fünf regulären Stufen höchstens
ein bewusst bestätigter Kauf, ohne RSI-Signal, aber mit mindestens 5 %
Preisabstand zum letzten regulären Fill. Vorschau, frische MFA und erneute
unabhängige Risikoprüfung. Einmalige Cockpitmeldung plus einschaltbare E-Mail.

Ab +5 % verkaufbarem Kurs zum tatsächlichen Durchschnitt: Supertrend
ATR10/Wilder ×3 aus geschlossenen H4-Kerzen, Stop mindestens Nettobreakeven,
nur monotones Long-Trailing, keine Nachkäufe nach Schutz und kein zusätzlicher
Flipexit. Kontolimits und −55%-Ausstieg gehen auch vor einem manuellen Kauf.

| Profil | Bestätigte Limits |
|---|---|
| Crypto Paper | 10.000 virtuelle USDT; BTC/ETH je 500 Kaufprincipal +5 Kostenreserve; 6 % täglich gegen Equity 00:00 UTC, 8 % gegen Startkapital, −55 % Preisexit zum ersten Fill |
| MT5 Brokerdemo | Getrenntes Demo; 0,25 % modelliertes Risiko je Idee inklusive Kosten, maximal eine offene Idee, 1 % täglich gegen Equity 00:00 Europe/Prague, 5 % gegen Startdemoequity |

Manuelle Reserve rund 135,53 USDT je 500-USDT-Basket; die 5-USDT-Kostenreserve
gilt für den ganzen Basket. Keine automatische Budgeterhöhung; Lots abrunden,
unter Mindestlot auslassen. Schutz-/Limittrigger sperren neue Exposition.
Modellierte Risiken und Stoppreise garantieren bei Gaps keinen Ausführungspreis.
Vollständige Regeln: [trading.md](trading.md).

## Architektur und Betrieb

Modularer Monolith mit getrennten Workern: Python/FastAPI,
Next.js/TypeScript, PostgreSQL mit persistenten Jobs/Outbox.
Docker Compose von Beginn an, lokales Authelia OIDC mit Passwort plus
TOTP/WebAuthn. Keine öffentliche Selbstregistrierung, DB/Worker intern.
Exakte unterstützte Releases, Lockdateien/Hashes und Imagedigests vor Bootstrap
prüfen. Hostkapazität messen; Builds/Research auf dem kleinen Host begrenzen.

MT5 läuft laut Nutzer auf einem separaten Heimnetzserver. Ausgehende
authentifizierte HTTPS-Bridge, keine Routerportweiterleitung. Separate
Demo-/Geräte-/Kontobindung, ein Writer je Brokerkonto, lokale Journale und
Abgleich bei Timeout/Neustart. Konkretes OS/Terminalbuild noch ungeprüft.
Plan: [mt5-bridge.md](mt5-bridge.md).

Bitget ist als Classic-Konto mit getrennten Spot-/Futures-Wallets bestätigt.
Jeder Nutzer erstellt einen eigenen dedizierten API-Key im eigenen Konto.
Geschützte API-Key-/Secret-/Passphrase-Eingabe, tatsächliche UID-/Rechteprüfung
und feste Kontobindung sind Teil der Integration. Realkonto zunächst lesend;
Futureskapital erhöht kein Spotbudget und aktiviert keinen Handel.
Plan: [bitget-connection.md](bitget-connection.md).

Vorhandenen kostenlosen SMTP mit TLS nutzen. Administratives MFA-Recovery
nach Einmalbestätigung an bestehende E-Mail-Adresse; keine gleichzeitige
Adressänderung. Alte Sitzungen/Token behandeln, neuen MFA-Faktor einrichten.
Normale Faktoränderungen weiterhin MFA-geschützt. Diese Recovery hängt am
Postfachschutz. Details: [deployment-plan.md](deployment-plan.md).

Pilotziele: RPO 24 Stunden/RTO vier Stunden, tägliche verschlüsselte externe
Sicherung, zusätzliche geschützte Offlinekopie und getrennte Schlüssel.
Konkretes kostenloses Ziel und Restoretest vor Pilotfreigabe.
Free-Tools/-Accounts zuerst; vorhandenes TradingView Essentials bleibt das
bisherige bezahlte Werkzeug. Keine zusätzlichen kostenpflichtigen Dienste.

## Nachweise und nächste Umsetzungsschritte

Datenziel: mindestens drei Jahre Crypto und zwei Jahre brokerpassendes Gold.
Getrennte chronologische Fenster, ungeöffneter unabhängiger Holdout.
Wirtschaftlicher Filter dort: positiver Nettoertrag, PF ≥1,2 und mindestens
30 geschlossene Baskets je Crypto-Asset beziehungsweise 100 Goldtrades.
Unzureichende Daten/Stichprobe als fehlenden Nachweis ausweisen.
Referenzbacktest: fünf reguläre Stufen und Reserve als Cash; tatsächliche
manuelle Paperaktionen separat journalisieren und auswerten.

Wir arbeiten die [Roadmap](roadmap.md) ab:

1. Unterstützte Versionen verifizieren/pinnen, reproduzierbaren lokalen
   Compose-Start und Projektbootstrap erstellen.
2. MFA/Tenants/DB-Isolation und geschützte Credentials implementieren.
3. Datenimport, gemeinsame Strategie-/Riskkerne und konservative Backtests.
4. Cockpit/Journal/Portfolio, manueller Paperpuffer und beide Adapterpfade.
5. Fehlerszenarien, Isolation, Bridgebindung, SMTP/Recovery und Restore prüfen;
   konkreten Pilotrollout zur Freigabe vorlegen.

Publikumszugang/Produktionsrollout, Echtgeldkonto/-budget/-ausführung,
FTMO-Verträge, externe AI-Provider und Kundenbetrieb haben eigene spätere Gates.
Q31 bestätigt das gemeinsame Verständnis und den Start der **lokalen
M1-Implementierung**. Tasks: [Ticketboard](tasks/board.md).
