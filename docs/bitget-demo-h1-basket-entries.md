# H1-Baskets: Kaufplanung und bestätigte Ausführungen

Stand 2026-11-24. PR117 ist als `89a511c` auf Main verifiziert.
Der technische BTC-Eröffnungs-/Abschlusstest ist abgeschlossen.
Dieser Schritt verbindet den gemeinsamen H1-Strategiekern mit einem eigenen
Reducer für tatsächliche Kaufbelege. Der operative Worker, seine dauerhafte
Orderfreigabe und die Brokerübertragung folgen separat.

## Kaufplanung

`futures_broker_entries.py` verwendet die vorhandene H1-RSI-/Kapitalprüfung:
zwei geschlossene RSI-Werte unter30 für den ersten Kauf, Wiederanstieg über30
und erneuter Rückgang unter30 für den Nachkauf, mindestens5% unter dem letzten
tatsächlich ausgeführten Kaufkurs. Der Hebel bleibt pro Basket2×.

Jeder Stufenbetrag ist Eigenkapital-Margin. Die Menge lautet
`floor_to_native_step(Stufenmargin × 2 / Planungspreis)`.
Der Planungspreis ist bei Marketorders keine garantierte Preisgrenze.
Ein bekanntes natives Mengenmaximum darf die Kaufstaffel nicht unbemerkt
verkleinern: eine erforderliche Aufteilung wird explizit zurückgemeldet.
Der separate technische20USDT-Notionaltest wird nicht zur Basketdimensionierung
verwendet.

Bei10.000USDT und drei finanzierten Ranges gelten weiterhin:

| Stufe | Reservierte Kaufmargin in USDT |
| --- | ---: |
| 1 | 293,13365892 |
| 2 | 366,41707366 |
| 3 | 458,02134207 |
| 4 | 572,52667759 |
| 5 | 715,65834699 |
| 6, ausschließlich manuell | 894,57293374 |

Gebühren/Funding liegen in der eigenen Kostenreserve. Kandidatenzahl und
finanzierte Plätze bleiben getrennt; drei finanzierte Ranges werden auch bei
fünf Kandidaten und Obergrenze7 nicht zu sieben finanzierten Ranges.
Die6-/8-%-Kontogrenzen bleiben Warnungen und verhindern keinen sonst regulären
Nachkauf innerhalb der reservierten Staffel.

## Abgleich

Die vorbereitete Order bindet Profil, Basketzyklus, Stufe, vorherige Position,
feste Menge, Hebel und einmalige Command-ID. Solange ihre Ausführung ungeklärt
ist, wird keine weitere Kauforder geplant. Das ist eine Ausführungsbarriere,
keine zusätzliche Kapital- oder Verlustgrenze.

Native kumulative Teilausführungen bleiben im eigenen Zustand als ausstehende
Beobachtung erhalten.
Sie werden weder mehrfach gebucht noch zu mehreren Kaufstufen. Erst ein
terminaler, abgeglichener Beleg wird in den Wirtschaftskern übernommen.
Ein teilweise ausgeführter und anschließend abgebrochener Kauf verbraucht
eine Stufe mit der tatsächlichen Menge; es gibt keinen automatischen Restkauf.
Ein bestätigter Abbruch ohne Ausführung verbraucht die Command-ID, aber keine
Kaufstufe.

Gebucht werden tatsächliche Menge, gewichteter Ausführungskurs, bestätigter
stufenspezifischer Margindebit und gemeldete Gebühr. Der Gesamtmarginbetrag
einer bestehenden Position ist kein Nachweis des neuen Stufendebits.
Der Produktionsadapter muss diesen Debit noch aus nativen Konto-/Positions-
und Transaktionsbelegen abgleichen; dieses Modul berechnet keinen angeblich
bestätigten Kontostand. Eine fehlende Gebühr/Margin oder ein fehlender
Positionsabgleich bleibt ausstehend. Positive Gebührenrückvergütungen benötigen
eine eigene Buchungspolitik und bleiben hier ebenfalls ungeklärt.

Ein gewichteter Fillkurs kann zwischen Preisticks liegen. Ein schlechterer
Marketfill als geplant oder eine tatsächliche Marginüberschreitung wird als
realer Ausgang gebucht und kenntlich gemacht. Eine zu geringe tatsächlich
gemeldete Margin bleibt mit dem bestehenden Integritätsfehler erhalten.
Die Rechnung verwendet keine Modellgebühr. Ein nach dem30s-Signalfenster
eintreffender Beleg wird nicht nachträglich als verbotener Kauf verworfen:
die Zulassung lag vor dem Versand; aktuelle vollständige Marken können vor dem
Abgleich eingespielt werden.

Bitget dokumentiert kumulative Ordermenge, Durchschnittskurs, Gebühr und Status
im [Classic-Orderabruf](https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade).
Der neue Reducer nimmt bereits validierte Belege entgegen; er parselt keine
ungeprüfte native Antwort und erhält keine Broker-Zugriffsdaten.

## Prüfstand und verbleibende Anbindung

21 neue gepinnte Python-Prüffälle decken fünf vollständige H1-Kaufstufen mit
echtem RSI-Verlauf, Nachkaufgrenze am tatsächlichen Fill, gebuchte Gebühren/
Margin, terminalen Teilfill, Unknowns, Doppelbelege, native Raster/Maxima,
verzögerte Beobachtung, Kapazität und die6-/8-%-Warnungen ab.
Brokerbelege sind synthetisch; es wurden keine neuen Bitgetorders gesendet.
Der gemeinsame Lauf mit Kapital-/H1-/Journal-/Paper-/Recoveryregression ist
grün:155 verschiedene gepinnte Pythonfälle und69 Subtests in104,71s.
Bestehende Paperfills oder Papergewinne können nicht als tatsächliche Positionen
übernommen werden. Die bestehende technische Orderjournalidentität bleibt separat.

Der neue Zustand ist derzeit ein reiner, unveränderlicher In-Memory-Reducer:
`execution_enabled=False`. Nächster Schritt sind eigenes persistentes
Basketjournal/Restore, native H1-Quellen-/Kontoanbindung und die Strategie-
Startfreigabe aus der originalen Dashboard-Sitzung. Der vorhandene kleine
BTC-Testconsent darf hierfür nicht verwendet werden. Die ungeklärten nativen
Maxima/Kosten/Kontofelder erhalten keine erfundenen Standardwerte.
Ein Deployment allein würde diesen neuen Worker noch nicht aktivieren.
