# Gemeinsamer Order-/Fundingabschluss

Stand2026-11-24, PR124/main`c25c767` verifiziert.

Der aktuelle [native Workerstart](bitget-demo-worker-bootstrap.md) ergänzt
Journal`/7` mit heutiger Finanzbasis und separatem Indikatorwarmup.
Die hier beschriebenen gemeinsamen Order-/Fundingabschlüsse bleiben erhalten.

Die native Basketquelle kann eine terminale Order und zeitgleich gebuchte
Fundingbeträge in einem einzigen bestätigten Journalabschluss verarbeiten.
Dies ergänzt die einzelnen Kauf-, Verkaufs- und Fundingquellen.
Dispatcher standardmäßig aus; keine operative Worker-/Startfreigabe installiert.

## Belegte Fälle

- Kauf oder Verkauf mit Funding eines anderen bereits eigenen Baskets:
  Dessen native Menge, Durchschnitt, Preis-PnL und Transaktionsgebühren bleiben
  unverändert. Seine Wallet-/Marginänderung wird aus den nativen Quellen
  übernommen, anschließend die tatsächliche Order verbucht. Auch terminale
  Teilkäufe können so ihre tatsächliche Menge als eine Stufe übernehmen.
- Vollständiger eigener Verkauf mit Funding des schließenden Baskets:
  Originale Margin, vollständige Sell-/Funding-Bills, Orderfee, Preis-PnL,
  Nullposition und gesamtes Kontokapital ohne UPL belegen den terminalen
  Cashsaldo. Zahlung aus Wallet, isolierter Margin oder deren Mischung muss
  für diesen abgeschlossenen Gesamtsaldo nicht erfunden werden.

Der vollständige Abschluss verwendet `BrokerFundingCloseFill`, nimmt
Nettofunding und Bruttozahlungen ins geschlossene Ergebnis auf und setzt
den nächsten RSI-Zyklus erst danach zurück. Der konkret nicht belegte
ursprüngliche Funding-Abbuchungspool bleibt ausdrücklich unzugeordnet.
Für die Reserveprüfung bilden die Bruttozahlungen eine obere Grenze der
hier möglicherweise aus Wallet bezahlten Kosten, keine behauptete Ausgabe.
Der Abschluss muss die Reserve für jede mögliche Kapitalzuordnung einhalten
oder gemäß Q44 die Überschreitung durch eigenen bestätigten Nettogewinn decken.
Andernfalls bleibt die Kostenentscheidung ausstehend, statt eine vermutete
Reserveverletzung als Tatsache zu buchen. Q45 bleibt erhalten: nur tatsächliche
Walletausgaben verbrauchen die Reserve. Andere Baskets stellen kein Kapital bereit.

## Originale Quellen und Atomizität

Eigener Versuch, genaue Orderidentität, persistierter ursprünglicher
Wallet-/Positionsvorzustand und native kumulative Orderclock bleiben gebunden.
Vorherige native Kontobeträge und Positionszähler müssen zum eigenen Ledger
passen. Der vollständige ursprüngliche Billzeitraum erlaubt ausschließlich
die eigene Buy-/Sell-Order und bekannte Funding-Bills eigener Zyklen.
Transfers, Marginänderungen, Bonus, fremde Order/Position und unbekannte Beträge
bestätigen keinen Abschluss. Funding nach der terminalen vollständigen
Schließung darf nicht dem geschlossenen Zyklus zugerechnet werden.

`settle_order_funding` im neuen Journalformat `/6` speichert den
Order-/Fundingbeleg, alle gehashten Bill-IDs und den originalen finanziellen
Prüfzeitpunkt mit nur einem fsync-bestätigten Zustandswechsel.
Ein späterer Fehler veröffentlicht keine vorherige Funding-Teilbuchung.
Restore spielt denselben Gesamtabschluss erneut ab. Bei verlorenem ACK
bleibt Recovery GET-only zum ursprünglichen Client-Identifier; kein Resend.
Frühere `/2`–`/5`-Journale werden nicht automatisch übernommen.
Das ursprüngliche technische BTC-Testjournal bleibt getrennt.

## Grenzen und nächste Integration

Funding des gerade gekauften Baskets oder des teilweise verkauften Baskets
benötigt einen separaten eindeutigen Nachweis der Kaufmargin beziehungsweise
Funding-/Restmarginzuordnung. Ein berechnetes `Menge×VWAP/2` darf den fehlenden
nativen Marginnachweis nicht ersetzen. Solche Fälle bleiben sichtbar ausstehend;
der gemeinsame Abgleich behauptet hierfür keinen Abschluss.

Nächste operative Schritte sind H1-Worker, ursprünglicher dauerhafter
Start-/Pause-Consumer, native Zulassung sowie Behandlung dieser ungeklärten
Kapitalzuordnung. Echtgeld und automatische Demo-Aktivierung bleiben aus.

API-Grundlage: [Bitget-Ordervertrag](https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade)
und [native Account-Bills](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account).
Verifikation erfolgt mit tatsächlichen Dateien/Restore/Trading-AEAD/HMAC und
finanziellen Reducern; Actor-/Brokerantworten sind synthetisch.
20 neue/454 verschiedene betroffene gepinnte Pythonfälle in Gesamtabdeckung
grün: breite453-Fall-Regression, finale88-Fall-Gruppe inklusive der
Kostenentscheidung bei unbekanntem Fundingpool.
Lesender Audit bestätigt Originalhashes und alle sieben laufenden Dienste/
Image-IDs unverändert; technisches Journal8.
Finaler Executorbuild/Paketimport/zehn Quellhashes ohne Netzwerk,
Quellmounts oder Zugangsdaten bestätigt; Versand standardmäßig aus.
