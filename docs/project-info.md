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

2026-11-19: [Handelskey-API](bitget-demo-trading-api.md) ergänzt eigene
Passkey-Endpunkte und sichere Rechte-/Metadatenanzeige.427 Prüfungen grün.
Eigene BFF-/Browser-/private HTTP-Anbindung und operative Abnahme folgen.

2026-11-19: [Handels-Passkey und privater Executor](bitget-demo-trading-passkey.md)
verbinden dauerhafte einmalige Freigabe und atomare Speicherung in Fixture019.
Eigene API-/BFF-/Dashboardanbindung und operative Abnahme folgen.

2026-11-18: [Demo-Handelsstore](bitget-demo-trading-store.md) und aktuelle
Provider-/Metadatengrundlage in isolierter Fixture018 geprüft.
Eigene Trading-Passkey-/Dashboardanbindung bleibt der nächste Schritt.

2026-11-17: Nutzer bestätigt Demo-Read-Write für Futures und Spot.
[Eigenes Handelskeyprofil](bitget-demo-trading-profile.md) prüft und
verschlüsselt diesen Umfang separat; dauerhafte Dashboardanbindung folgt.

2026-11-17: Der [Demo-Einrichtungsbereich](bitget-demo-dashboard-setup.md)
erhält einen sichtbaren Einstieg auf der Sicherheitsseite und erklärt die
offene Freischaltung. Echte Keyeingabe und öffentlicher Rollout bleiben offen.

Stand 2026-11-07: Der Auftrag oben bleibt als ursprünglicher Projektprompt erhalten.
Planung und Interview nach `SKILLS/grill-me/SKILL.md` sind durch Q31 bestätigt.
Die lokale M1-Umsetzung läuft: Compose, MFA-/API-/Cockpitfundament und
Crypto-Kern sowie immutable Marktdaten und tenantgebundene Offlinebacktests
mit grafischen Ergebnissen. Aktueller Start: [infra/README.md](../infra/README.md).
Der eigene Futures-Paperpfad samt lokaler Cockpit-Recovery ist umgesetzt.
Der separate [Classic-Demo-Auftragsvertrag](bitget-futures-demo.md) startet
mit unsignierten Plänen und Teilfill-/Positionsmengenabgleich.
Die [private Demo-Outbox](bitget-demo-outbox.md) erhält Aufträge dauerhaft
über Prozessabbrüche. Native Ausführung, Kontobindung und Kostenabnahme
folgen ohne Liveaktivierung.
Der [Demo-Accountcheck](bitget-demo-account-check.md) erkennt Abweichungen
zwischen eigenem Outboxstand und Wallet-/Positions-/Order-/Trigger-Snapshots;
der Reader erteilt noch keine Brokerfreigabe.
Die [Demo-Kontopfadregistry](bitget-demo-account-registry.md) bindet
kooperierende Writer unter einem gemeinsamen privaten Root dauerhaft
an das Originaljournal. Native Demo-Key-/UID-Provenienz bleibt offen.
Der [getrennte Demo-Lesezugang](bitget-demo-read-transport.md) bindet
signierte feste Requests an diese Registry und eine aktuelle geschützte
Providerdeklaration. Tatsächlicher Provider/Keyeinrichtung und native
Endpointabnahme fehlen; keine automatische Brokeraktivierung.
Der [eigene verschlüsselte Demo-Providerkern](bitget-demo-secret-provider.md)
trennt Demo-/Normal-Purpose kryptografisch. Dauerhafte Demo-Purpose-/Passkey-
Einrichtung und geschützte Dashboard-Eingabe werden als Nächstes angebunden.
Demo-Key wird ausdrücklich im Bitget-Demo-Modus erstellt, Live später separat.
Der [dauerhafte Demo-Store](bitget-demo-credential-store.md) ergänzt inzwischen
einen eigenen Kontomodus/Ciphertextdatensatz und aktuellen tatsächlichen
DB-Actor-/Epoch-/Reauth-/Readyreader mit CAS und atomarem Audit.
Additive014 ist nur in der isolierten Fixture angewendet.
Die [eigene Demo-Passkey-Zweckfreigabe](bitget-demo-passkey-purpose.md) ergänzt
inzwischen Fixture015, getrennte signierte Assertionprüfung und einmaligen
Consume-/Lockclient. Der [eigene private Demo-Executor](bitget-demo-passkey-executor.md)
verbindet dies mit014-Storewrite und eigenem atomarem016-Abschluss.
Die [eigene interne Demo-API](bitget-demo-passkey-api.md) ergänzt fünf
standardmäßig gesperrte Proof-/Consent-Routen über015 mit getrennten Domains.
Der [eigene private Demo-BFF](bitget-demo-bff-flow.md) ergänzt tatsächliche
WebAuthnprüfung, Demo-Consent/Signing und getrennten mTLS-Executortransport
mit injizierten vertrauenswürdigen Adaptern.
Der [eigene Metadatenzugriff und Cockpit-Serveradapter](bitget-demo-metadata-provider.md)
verbinden aktuelle Serversitzung/APIassertions mit dem getrennten Demo-Kontostand.
Der [eigene geschützte Demo-Browserablauf](bitget-demo-browser-flow.md) ergänzt
Formular, Passkey/Consent und getrennte Next-Routen mit fest gesperrtem Provider.
101 neue/881 gepinnte Cockpitfälle, Typecheck/Build grün. Private
Identitätsverdrahtung, kombinierte laufende und native Abnahme folgen.
Der [eigene private Demo-Dateiprovider](bitget-demo-private-identity.md) ergänzt
nun Originaldatei-/Fingerprint-/TLSprüfung und explizite Serverfactory mit
unabhängig gelesenem API-Benutzer.33 neue/914 gepinnte Cockpitfälle grün.
Die operative Installation und native Demo-Key-/Readabnahme folgen;
echte Demo-Keys werden weiterhin nicht angenommen.
Die [gemeinsame isolierte Demo-Abnahme](bitget-demo-local-acceptance.md) verbindet
inzwischen den HTTPS-BFF mit echter API, PostgreSQL und getrenntem privaten
Python-Executor. Registrierung, Neustart, Widerruf und unbestätigte Antwort
nach erfolgreichem Commit werden zusammen geprüft. Sitzung und
Brokerprovenienz bleiben synthetisch; native Demo-Key-/Readabnahme folgt.
438 tatsächliche gemeinsame Prüfungen und54 gepinnte Python-Fälle/35
Unterfälle bestanden; normaler Browserprovider weiterhin gesperrt.
Der [eigene native Registrierungsprüfer](bitget-demo-native-provisioning.md)
ergänzt inzwischen private MAC-gebundene Herkunftsfreigabe, ursprüngliche
Dateibindung und einen festen signierten Demo-Identitäts-GET mit exakter
Konto/IP/Rechteprüfung.115 gepinnte Fälle/84 Unterfälle grün; Schlüssel und
Brokerantworten synthetisch. Herkunft ist eine Betreiberattestation,
operative Einrichtung und echte Brokerabnahme bleiben erforderlich.
Der [private Demo-Key-Prüfaufruf](bitget-demo-private-probe.md) ermöglicht
nun eine explizite einmalige Operatorprüfung am Terminal mit verdeckter
Schlüsseleingabe und privatem Ergebnisbeleg.135 gepinnte Fälle/84 Unterfälle,
einschließlich echtem Linux-PTY, grün; Brokerantworten synthetisch.
Private reale Metadaten-/Keyvorbereitung und native Abnahme folgen.
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
