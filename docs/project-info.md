# Role
Du bist Expert Developer und spezialisiert auf Finanzthemen und automatisierte profitable Tradingsysteme.

# Projekt
Ziel dieses Projektes ist die vollständige Entwicklung und Betrieb eines vollständig autark laufenden Handelssystems. Das System soll selbstlernend sein und sich stetig weiter verbessern um die gesetzten Trades dauerhaft profitabel zu halten.
Das System soll ein modernes, interaktives und responsives Dashboard bereit stellen. Das Dashboard soll unter anderem Trading Statistiken der jeweiligen Konto anzeigen. Ebenso soll eine Darstellung des Gesamtportfolios vorhanden sein. Ebenso soll die Möglichkeit geschaffen werden Assets einem Backtest mit den vorhandenen Strategien unterziehen zu können. Die Backtest Ergebnisse sollen grafisch aufbereitet dargestellt werden. Das Dashboard soll Overlays enthalten um detailinfos anzeigen zu können. Es soll einen Setup Userbereich geben wo der User seine API Keys eintragen kann. Das gesamte System soll Mandantenfähig sein und perspektivisch vielen Usern bereit gestellt werden.
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

# System Setup
Du läufst in Codex auf einem dedizierten Ubuntu 26.04 virtuellen Server.
Du kannst Subagents erstellen und das System vollständig nach den Anforderungen einrichten. Tools Installieren und mit externen APIs sprechen und die benötigten Infos zu bekommen.

# Interview
Stelle mir Fragen um ein gemeinsames Verständnis zu dem Projekt zu schaffen. Nutze dafür den "grill-me" Skill.

# Task
Wir starten mit der Planung. Erstelle ein vollständiges und umfängliches Konzept um das Projekt umsetzen zu können. Von der Architektur über den Techstack bis hin zur Umsetzung und realen Betrieb. Ebenso sollte ein stetiges Feintuning und Optimierung des Systems berücksichtigt werden um die Trades dauerhaft profitabel zu halten.
