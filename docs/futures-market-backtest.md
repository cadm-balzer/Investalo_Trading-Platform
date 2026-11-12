# Vollständiger nativer Futures-Marktvergleich

IP-078. IP-077 `ca98561` ist in Main `ab3b4ab` verifiziert.
Der create-only Job `infra/scripts/backtest-futures-capital.py` verarbeitet
alle zehn vorab eingefrorenen Varianten des
[Wirtschaftsprofils](futures-economic-profile.md).
Keine neue Parameterauswahl anhand der Ergebnisse, keine aktiven KI-Entscheidungen.

Fünf feste Slots BNB/BTC/ETH/SOL/XRP, 10000 USDT, sechs Eigenkapitalstufen.
Fünf automatische RSI-Käufe; die sechste Stufe bleibt manuelle Reserve.
H4-RSI-Einstiege und H1/H4-Supertrend-Schutz werden auf derselben vollständigen
nativen H1-Achse verglichen: 2022-08-01 bis 2025-08-01 exklusiv.
Kein Holdoutzugriff, keine privaten Schlüssel, Brokerorders oder Deployment.

## Zeitliche Ausführung

Geschlossene H1-/aggregierte H4-Kerzen verändern Indikatoren erst am nativen
Schlusszeitpunkt. Exaktes Funding wird nach vollständiger Settlement-Bewertung
und gegebenenfalls UTC-Tagesbasis verarbeitet. Weitere native Millisekundengruppen
folgen unverändert; zwischen einzelnen Buchungen einer Gruppe gibt es keinen Kauf.

Der deklarierte Openpreis wird bei +1s beobachtet. Bestehende Exitpflichten
werden zuerst abgerechnet; bei +2s folgt eine vollständige Bewertung derselben
weiterhin frischen Preise, danach eigene Kostenrestoration und mögliche Käufe.
Dadurch erhalten auch der zweite bis fünfte gleichzeitige Einstieg vollständige
Markevidenz. Kein neu beobachteter oder rückdatierter Preis wird erfunden.
Die geschlossene H4-Signalfrische bleibt höchstens 30s.

Low/High bei +20/+40min gemäß eingefrorenem Vergleichspfad, anschließend
nativer Schluss. Preise sind diskrete Modellbeobachtungen, kein Tickverlauf
oder garantierter Stopfill. Gaps können normale Stops mit Verlust schließen.
Bei flachen, nicht einstiegsfähigen Baskets entfallen wirtschaftlich wirkungslose
Intrabarbeobachtungen. Jede geschlossene Stunde und jedes Funding bleiben im
Journal; RSI-Warmup, terminale Liquidationen und Halts werden nicht übersprungen.

Liquidationen werden vor neuen Preisen/Nachschüssen abgeglichen. Ungestellte
Staffelreserve wird separat erhalten; liquidierte Slots bleiben terminal.
Kostenrestoration kommt ausschließlich aus der eigenen verbleibenden
Kostenreserve, niemals aus späteren Kaufstufen oder fremden Baskets.
Tatsächliche Budget-, Kapital-, Margin- und Liquidationsgrenzen bleiben verbindlich;
6%/8% sind Warnungen. Ein Signal ohne finanziell zulässige Ausführung wird
als Kapitalablehnung mit Gründen gezählt.

## Nachweise und Kennzahlen

Je Variante: vollständiges Eingabejournal, stündliche Equitykurve mit zusätzlichen
Minimum-/Maximumwerten aller wirtschaftlichen Ereignisse, abgeschlossene
Basketbelege und Nettoauswertung. Der gesamte Journalrestore von flacher Genesis
wird mit dem zuletzt bestätigten Receipt abgeglichen, bevor ein Erfolgsreport
entsteht. Der Gesamtlauf schreibt erst nach allen zehn erfolgreichen Varianten
ein Receipt mit Artefakthashes. Vorhandene Verzeichnisse werden nicht überschrieben.
Auf dem kleinen Entwicklungsserver läuft jeweils eine Variante, mit einem
gemeinsam geladenen Quellbestand; keine Agent- oder API-Aufrufe.

Netto umfasst Gebühren, adverse Slippage, native Fundingraten und offene
Endbestände zum letzten Markpreis. Offene Baskets erhalten keine erfundenen
Profitabschlüsse. Realisierte Belege, Ledger und End-MTM werden bis zum
expliziten Geldquantum 0,00000001 USDT abgeglichen; ein Rundungsrest wird ausgewiesen.
Der Drawdown umfasst auch Zwischenbewertungen vor einer modellierten
Versicherungsgutschrift. Profitfaktor bezieht sich nur auf geschlossene Baskets;
ohne Verluste wird kein numerischer unendlicher PF ausgegeben.

Nachkäufe je Stufe, aktive Baskets, gebundene Margin, zeitgewichtete
Marginzuordnung, Gebühren/Funding, Liquidationen, ungestellte Liquidationsreserve,
modellierte Versicherung, offene Endbestände und terminale Halts bleiben sichtbar.
Historische Gebühren-, Maintenance-, Lot- und Versicherungsregeln sind weiterhin
unbestätigte Modellannahmen; Ergebnisse wären Forschungsbefunde, keine
wirtschaftliche Freigabe oder erwartete Live-Rendite.

## Prüfung

Gezielte synthetische native Quellen prüfen den vollständigen Job mit fünf
gleichzeitigen Einstiegen, exakten und Millisekunden-Fundings, Gap-Liquidation,
End-MTM ohne Zwangsabschluss, unveränderlicher Ausgabe und vollständigem Restore.
Bereits vorhandene Signal-, Journal- und Snapshotverträge werden geprüft.
Unveränderliche Digestwerte und feste Dataclass-Schemata werden begrenzt gecacht;
JSON-Inhalte, Hashdomänen und Ersatzobjekte bleiben unverändert.
Der eigene `capital_digest.py` serialisiert optierte, tief unveränderliche
Kapitalrecords als gecachte kanonische JSON-Fragmente. Ledger, Indikatoren und
Ereignisgeschichte bleiben vollständig gebunden; keine Verkürzung auf bloße
Teilhashes. Alte Snapshotprimitive bleiben identisch. Ein vor der Optimierung
geschriebenes vollständiges 335-Command-Journal wurde danach mit identischem
Receipt und Endzustand restauriert.
Zusätzlich stimmen beim ersten vollständigen nativen Preisreplay vor/nach
Beschleunigung alle 57044 Commands plus Genesiszeile sowie alle
26305 Equitypunkte bytegenau überein. Der frühere Lauf wurde während des
Restores beendet; dieser Vergleich ersetzt seine fehlende Gesamtabnahme nicht.

115 unterschiedliche gezielte gepinnte Tests und 166 Subtests bestanden,
darunter sieben neue Marktjobfälle. Frühere überlappende Läufe werden nicht
addiert. Kompilierung und Diff-Prüfung grün; Eigenreview, keine Agentdelegation.

Der erste parallele Prozesspool wurde vor einem Marktresultat beendet.
Die Sandbox verweigerte zunächst den lokalen Prozesskanal; der freigegebene
Hostlauf verlor danach einen Prozess auf dem kleinen Host. Keine Behauptung
einer eindeutig bewiesenen Abbruchursache. Anschließend sequenzieller Lauf;
nach erfolgreicher Hashgleichheitsprüfung gezielt eigener Prozess beendet
und neuer create-only Lauf mit der Beschleunigung. Alle alten Verzeichnisse
bleiben ohne Erfolgsreceipt erhalten.

## Bereits bestätigte Modellbremsen

Alle zehn Varianten sind abgeschlossen:451193 vollständig restaurierte
Journalcommands,40 Artefakthashes/907593935 lokale Artefaktbytes.
[Ergebnistabellen](futures-market-results-20261112.md);
Erfolgsreceipt-SHA256`9e7802ecbc7d99bb44d8430ae4b9200c37633cfab5d276c0f8ec5c3e31bc5897`.
Tatsächlicher Lauf auf Host-Python3.14.4, gezielte Checks auf gepinntem3.14.10.
Die kopierten Reports stimmen mit dem Gesamtreceipt überein; Implementationshash
gegen die ausgeführte Marktjobdatei geprüft. Keine offenen Endbaskets in diesem
konkreten Lauf; offene End-MTM ohne Zwangsabschluss separat synthetisch geprüft.
Cockpit/auth nach Abschluss weiterhin reguläres TLS/HTTPS200, keine Recreates.

Die Basisvarianten2× sind vollständig restauriert. H1: netto+687,70 USDT,
51 abgeschlossene Baskets, eine Liquidation; Käufe je Stufe51/18/7/1/1.
Danach terminaler `basket_budget_breach` am2023-10-27. Beim BNB-Zyklus10
werden19,94285425 USDT Brutto-Kosten gegen19,80198020 USDT Reserve gezählt,
obwohl der kumulierte Fundingsaldo+38,63514762 USDT beträgt und tatsächlich
nur0,27569574 USDT eigene Kostenrestoration gebucht wurde. Der alte Kern zählt
positive Fundingabbuchungen kumuliert; Gutschriften vermindern diese Größe
nicht. Das ist keine Behauptung eines tatsächlich ausgeschöpften Kontos.

H4: netto−7,28 USDT, fünf geschlossene Baskets, keine Liquidation oder terminaler
Halt. Letzter Abschluss2023-01-30;887 Ablehnungen `insufficient_unposted_cash`.
Der bisherige Allokator reserviert auch für jeden leeren Slot dessen vollständige
ursprüngliche Range. Ein kleiner realisierter Verlust reicht daher, dass das
Konto die Summe aller fünf hypothetischen vollen Ranges nicht mehr deckt und
selbst der erste neue Basket abgelehnt wird. Das sind keine6%/8%-Kontogates.

Die eingefrorenen Varianten bleiben unverändert. Ihre Renditen beschreiben
das bisherige Modell einschließlich Stillstand, keinen ununterbrochenen
Dreijahreshandel. Vor Leverage-/Signaloptimierung folgt ein **separates neues
Forschungsprofil** mit geprüfter eigener Cash-/Fundingkostenbindung und
Reservierung vollständiger Ranges nur für aktive/neu aufzunehmende Baskets.
Geplante Stufenbeträge, manuelle Reserve, reale Kapital-/Marginconstraints
und terminale Liquidationen bleiben dabei nachzuweisen. Noch keine Aktivierung
oder Zusage einer verbesserten Rendite.
