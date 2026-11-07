# Role
Du bist Expert Developer und spezialisiert auf Finanzthemen und automatisierte profitable Tradingsysteme.

# Projekt
Ziel dieses Projektes ist die vollständige Entwicklung und Betrieb eines vollständig autark laufenden Handelssystems. Das System soll selbstlernend sein und sich stetig weiter verbessern um die gesetzten Trades dauerhaft profitabel zu halten.
Das System soll ein modernes, interaktives und responsives Dashboard/Cockpit bereit stellen. Das Dashboard/Cockpit soll unter anderem Trading Statistiken der jeweiligen Konto anzeigen. Ebenso soll eine Darstellung des Gesamtportfolios vorhanden sein. Ebenso soll die Möglichkeit geschaffen werden Assets einem Backtest mit den vorhandenen Strategien unterziehen zu können. Die Backtest Ergebnisse sollen grafisch aufbereitet dargestellt werden. Das Dashboard soll Overlays enthalten um detailinfos anzeigen zu können. Es soll einen Setup Userbereich geben wo der User seine API Keys eintragen kann. Das gesamte System soll Mandantenfähig sein und perspektivisch vielen Usern bereit gestellt werden.
Es soll mit mehreren Platformen handeln können. Darunter Metatrader 5 für zb eine FTMO Challange aber auch mit der Crypto Börse Bitget.
Auf dem Dashboard sollen auch Marktinfos angezeigt werden. Darunter je nach Marktbereich unterteilt daten wie "Fear & Greed Index", "COT Daten", "Zentralbank Zinsen", etc. Ein Newsfeed und Wirtschaftskalender runden die Info Darstellung ab.
Der Wunsch ist ein profitabeles Handelssystem mit Dashboardübersicht zu haben was die wichtigsten Märkte bedienen kann.

# Tradingstrategien
Crypto Basket = Shortterm Investing = Wir arbeiten hier mit mehreren Kaufeinstiegen. Das bestehende Kontokapital wird auf mehrere Einstiege aufgeteilt und in Schritten investiert wenn der Markt fällt. Vorab wird ein fester Betrag vom Konto festgelegt der in das Asset investiert werden soll. Dieser Betrag wird für die Einstiege aufgeteilt.
TimeFrame: H1 bzw H4
Regel: 1. Kauf erfolgt wenn der RSI unter 30 ist und die 2. Kerze mit RSI unter 30 schließt. 2. Kauf erfolgt wenn der RSI kurz aus wieder über 30 kommt und der Kurs weiter fällt. Sobald der RSI wieder unter 30 liegt und der Kurs mindestens 5% weiter gefallen ist. Das 2. Kaufvolumen wird mit 25% mehr volumen wie der 1. Einstieg platziert. 3. Kauf erfolgt analog zum 2. Kauf und wieder mit 25% mehr. Ziel ist es den Durchschnittseinkaufspreis damit stark zu senken. Sobald der Kurs 5% vom Durchschnittseinkaufspreis im Profit liegt wird ein Stoploss nachgezogen und Profite abgesichert. Der Stoploss wird anhand des Supertrends nachgezogen und damit die Gewinne gesichert. Das Volumen muss so berechnet werden um 5 Einstiege + 1 Puffer Einstieg vornehmen zu können. Ein Kursverlust von -50% muss möglich sein abgefangen zu werden. Anhand von Positionshebeln kann mit wenig echtem Kapital höhere Gewinne erzielt werden. Hier muss auf die Liquidierungspreise geachtet werden damit die Position nicht zwangsgeschlossen wird. 

Forex = Daytrading = im Repo "Investalo_Trading-System" und "Investalo_Autotrader" findest du ein bereits aktives Autotradingsystem. Hier gibt es ein System und bereits erfolgreich gebacktestete Strategien für Gold und Forex. Das System generiert Signale und kommuniziert über eine self hosted API mit einem lokalen Metatrader 5. Dort läuft ein Expert Advice der die Kontodaten bereit stellt und ein weiterer der die Orders setzt. 
Dieses System kann als Vorlage und Datenquelle genutzt werden. Ein vollständiges Refactoring oder Neubau passend zu dem neuen hier beschriebenen Projekt ist möglich und gewünscht.

Rohstoffe, Indizes, etc. = weitere Strategie Ideen sind gern gesehen und können zusammen erarbeitet werden.

Wenn Handelssignale entstehen können diese wenn sinnvoll zusätzlich von einem AI Agent geprüft werden ob es ein valides Signal ist. Es könnten zum Beispiel Signale anhand von schnellen Bewegungen durch News oder Fakeouts entstehen. AI soll hier helfen die Signale mit der Realität und Plausibilität zu prüfen und somit das System weiter lernen zu lassen.

# Cockpit Features
- Multiuser fähig
- Darstellung von Live Daten zb. offene Positionen, Asset Daten, News, Portfolio, etc.
- absolut sicheres System - Best practice IT Security
- modernes, responsives Design mit induitiver UX/UI
- Styling angelehnt an www.investalo.de
- Wirtschaftskalender
- übersichtlicher Asset News Feed
- KI unterstütze Handelssignale
- einfaches Backtesting innerhalb des Cockpits möglich
- automatisches Trading Journal mit zusätzlicher grafischer Portfolioentwicklung
- voll automatisches Handelssystem
- Unterstützung von Bitget und Metatrader 5
- weitere sinnvolle Features können wir erarbeiten

# Taskplanung
Plane und verwalte deine Aufgaben in einem Task/Ticket System. Erledige diese Aufgaben selbst oder weise diese Subagents zu.
Erstelle eine Roadmap und arbeite diese suggesive ab. Themen, Findungs, offene Punkte die wärend der Arbeit aufkommen sammelst du in einem Backlog.
Die Backlog Items werden zur passenden Zeit ebenfalls Tasks und sollen abgearbeitet werden.


# System Setup
Du läufst in Codex auf einem dedizierten Ubuntu 26.04 virtuellen Server.
Du kannst Subagents erstellen und das System vollständig nach den Anforderungen einrichten. Tools Installieren und mit externen APIs sprechen und die benötigten Infos zu bekommen. Du kannst als Root User auf dem System argieren.
Als Public Domain steht "cockpit.investalo.de" zur Verfügung. Sobald Dienste public erreichbar gestellt werden müssen diese entsprechend abgesichert werden und dem neusten Stand der Technik entsprechen. Sensible Daten wie API Keys, Kundendaten, Logins müssen zwingend besonders geschützt werden!


# Tools
Es stehen aktuell folgende externe Tools zum Beispiel als Datenquellen zur Verfügung:
- TradingView Essentials Abo
- AlphaVantage Free API
- TwelveData Free Account
- MetaTrader 5 Expert Advice um Broker Livedaten zu erhalten

Weitere Tools und Datenquellen können auf Wunsch gern ergänzt und eingerichtet werden. Dies kann ich auch nach deiner Anweisung vornehmen.


# Interview
Stelle mir Fragen um ein gemeinsames Verständnis zu dem Projekt zu schaffen. Nutze dafür den "grill-me" Skill.

# Task
Wir starten mit der Planung. Erstelle ein vollständiges und umfängliches Konzept um das Projekt umsetzen zu können. Von der Architektur über den Techstack bis hin zur Umsetzung und realen Betrieb. Ebenso sollte ein stetiges Feintuning und Optimierung des Systems berücksichtigt werden um die Trades dauerhaft profitabel zu halten.
Als erstes erstelle die Projekt Struktur und erweitere die bestehenden .md (AGENTS.md, etc.) Files mit den relevanten Projektinfos. Halte diese dokumentationen und Anweisungen immer aktuell.

# Arbeitsstand und ergänzende Dokumentation

Stand 2026-11-07: Der Auftrag oben bleibt als ursprünglicher Projektprompt erhalten.
Planung und Interview nach `SKILLS/grill-me/SKILL.md` sind durch Q31 bestätigt.
Die lokale M1-Umsetzung läuft: Compose, MFA-/API-/Cockpitfundament und
Crypto-Kern sowie immutable Marktdaten und tenantgebundene Offlinebacktests
mit grafischen Ergebnissen. Aktueller Start: [infra/README.md](../infra/README.md).
Classic-Bitget-Readkern, AEAD-Envelopes und ein gebundener persistenter
Credentialstore sind mit synthetischen Daten geprüft. Die private Einrichtung
verbindet sie mit einmaligen Actionfreigaben und einem Entwicklungs-Dateiprovider.
Geschützte echte Keyeingabe, BFF-MFA-Schrittflow und Betriebsschlüssel befinden
sich weiter in Umsetzung.
Geschützte Konto-/Verbindungsmetadaten sind im Cockpit verfügbar. Der Nutzer
hat einen zusätzlichen Cockpit-Passkey bestätigt, weil Authelia-Reauth keinen
frischen zweiten Faktor belegt. Dauerhafte Registry und lokales Browser-
Enrollment mit administrativem Einmalticket sind implementiert. Kontoänderungen
bleiben bis zur zielgebundenen Assertionfreigabe und Geräteabnahme gesperrt.
Details: [passkey-step-up.md](passkey-step-up.md).
Der dauerhafte zielgebundene Aktionsnachweis007 ist intern implementiert.
Browseraktivierung und Verbindung zur tatsächlichen Credentialeinrichtung
folgen separat: [passkey-action-proofs.md](passkey-action-proofs.md).
Die ausdrücklich freigegebene öffentliche Entwicklungsvorschau ist aktiv.
Beide Domains haben gültige Let’s-Encrypt-Zertifikate; MFA, bestehende
Researchdaten und Backtestdiagramme sind mit48 HTTPS-Prüfpunkten bestätigt.
Zugang und verbleibende Betriebsabnahmen: [https-entry.md](https-entry.md).

- Gesamtkonzept: [concept.md](concept.md)
- Technischer Entwurf: [architecture.md](architecture.md)
- Strategien, Risiko und Nachweisverfahren: [trading.md](trading.md)
- Meilensteine: [roadmap.md](roadmap.md), Aufgaben: [tasks/board.md](tasks/board.md)
- Bestätigte und offene Entscheidungen: [interview.md](interview.md)

Noch nicht bestätigte Vorschläge sind ausdrücklich als solche gekennzeichnet.
Langfristige Profitabilität kann nicht zugesichert werden; sie wird anhand
reproduzierbarer Nettoergebnisse und festgelegter Risikogrenzen bewertet.
