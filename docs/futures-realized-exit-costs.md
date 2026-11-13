# Eigener realisierter Gewinn deckt Kosten am vollständigen Abschluss

Q44 ist ausdrücklich bestätigt: „Ja, nur aus dem eigenen abgeschlossenen
Basketgewinn (empfohlen)“. IP-081 führt dafür eine eigene Forschungspolicy
`isolated-usdt-capital-realized-cash/3` ein. Die früheren Kostenbudgets/2
und Kapitalprofile/1 bleiben unverändert.

Eine Ausnahme gilt ausschließlich beim vollständig gebuchten normalen Exit
des gleichen Symbols/Zyklus. Sein Nettogewinn nach sämtlichen Gebühren und
Funding muss positiv sein und mindestens den gesamten Kostenüberhang über
die zugeteilte Reserve decken. Die Buchung enthält weiterhin sämtliche
Kosten. Es gibt keine zusätzliche Profit-/Cashgutschrift, Reservenumbuchung
oder Änderung des beobachteten Fillpreises.

Offene Baskets, Teilverkäufe und Liquidationen erhalten keine Ausnahme.
Ein vorher bereits ausgelöster Halt bleibt terminal. Die Ausnahme kann weder
unrealisierten Gewinn noch Gewinn anderer Baskets verwenden. Initialmargin,
Liquidationsvorrang, aktuelle Cashdeckung, fünf eigene Kaufstufen,
manuelle sechste Reserve und feste Hebel bleiben unverändert.

Vor Auswertung eingefroren:
`research-protocols/futures-capital-h1-realized-cost-20261112.json`,
SHA256 `719716bcc813c1fa22de769c2b86ed43d72b4e0d29a9d133065c06cf0cbf339a`.
Der gleiche H1-RSI/H1-Schutz/2×-Fall verwendet unveränderte native Quellen
und wirtschaftliche Annahmen. Referenz ist IP-080 inklusive vollständig
restauriertem Journal, Receiptsha
`3c6fdfb5b1c5ec6129f9bc7e4c4f1368ec19761f06e0d628707f8b72f12ed130`.

Expliziter create-only Offlinejob:

```sh
python3 infra/scripts/backtest-futures-capital.py --h1-realized-costs NEW_OUTPUT_DIRECTORY
```

Technische Prüfungen umfassen unveränderten strikten Legacyexit,
profitablen vollständigen Abschluss/Slotwiederbelegung, unzureichenden eigenen
Nettogewinn, anderen Basketgewinn, Teilverkauf und offenen Kostenhalt trotz
unrealisiertem Gewinn. Die volle Sechsstufenstaffel und vollständiger
H1-Journalrestore werden mit der neuen Planidentität geprüft.

Die bestätigte Ausnahme ist keine allgemeine Kostenbudgetlockerung:
ein offener Kostenüberlauf kann weiterhin den Forschungslauf stoppen.
AI, Holdout, Paper-/Cockpitprofilwechsel und echte Orders bleiben aus.
