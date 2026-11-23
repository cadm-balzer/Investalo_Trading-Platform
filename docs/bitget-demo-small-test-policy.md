# Freigegebener einzelner technischer BTC-Market-Demotest

Status2026-11-24: **Vom Nutzer ausdrücklich freigegeben, operativ installiert
und erste Eröffnung vollständig ausgeführt und abgeglichen.**
Die Freigabe gilt für den kleinen technischen Demotest. Der Nutzer hat
Market statt Limit-IOC gewählt; auch die spätere Basketstrategie soll
Market verwenden. Dies aktiviert noch keine automatische Strategie.

Der bisherige [Auftragsvertrag](bitget-demo-order-dispatch.md) verlangt
native Konto-/Mengenklärung vor dem ersten Versand. Bitget liefert im
tatsächlich geprüften Demokonto weder Grantbetrag noch maximale
Ordermenge; Kosten und ältere Auftragsabdeckung sind weiterhin nicht
bestätigt. Für normale Aufträge bleibt diese bisherige Regel bestehen.
Bitget beschreibt Demo ausdrücklich als Handel mit virtuellen Mitteln:
[offizielle Demo-Dokumentation](https://www.bitget.com/docs/classic/demo-trading/rest-api),
geprüft2026-11-23.

Für den vom Nutzer genehmigten technischen Test gilt ein eigener enger
Testmodus. Dieser Modus lässt genau diese unbestätigten
Angaben sichtbar und akzeptiert, dass Bitget den kleinen Auftrag wegen
eigener Limits ablehnen kann. Er behauptet keine Nullbeträge, bestätigte
native Mengenhöchstgrenze, Gebühren oder vollständige ältere Auftragshistorie.

Der konkrete Umfang:

- Ausschließlich das bestehende, nativ identifizierte Bitget-Demokonto
  mit bestätigten10.000 virtuellen USDT und aktivem Trading-Key.
- Ein neuer BTCUSDT-Long mit isolierter Margin, One-way und2×.
  Zielgröße etwa20 USDT Positionswert und10 USDT Initialmargin vor
  den weiterhin unbestätigten tatsächlichen Gebühren. Die feste BTC-Menge
  wird anhand des aktuellen Ask mit1% Planungspuffer nach unten gerundet.
  Der tatsächliche Marketkurs und damit der ausgeführte Positionswert
  sind nicht garantiert auf20 USDT begrenzt.
- Native Mindestmenge, Mengenraster und Mindestnotional müssen
  bestätigt sein. Keine Vergrößerung bei nicht passender Mindestmenge.
- Frische freie Margin, keine aktuellen Positionen, keine bekannten
  Aufträge in allen fünf Pendingfamilien. UID/Parent/Rechte, aktueller
  Actor/Key und ursprüngliche Zeit-/Quota-/Installationsguards bleiben Pflicht.
- Market ohne `price` und `force`; explizite
  aktuelle Zustimmung, dauerhafte einmalige Freigabe und Orderjournal.
  Kein wiederholter POST bei unbestätigtem Ausgang; nur Statusabfrage.
- Ergebnis als technischer Test protokollieren: ACK, tatsächliche
  Ausführung und Position getrennt. Unbekannte Gebühren bleiben unbekannt,
  kein Nettoertrags- oder Strategievalidierungsnachweis.

Der Vorschlag umfasst keine automatische Basketstrategie, andere Coins,
höheren Hebel oder Echtgeld. Die normalen Handelsprüfungen bleiben streng.
Er verwendet eine eigene geprüfte Implementierung; Klassen/Routes
dürfen dafür keine unbekannte native Höchstmenge durch einen erfundenen
`DemoGrid`-Wert ersetzen. Ein späteres Schließen betrifft ausschließlich
die diesem Test belegbar zugehörige Menge per Reduce-only.

Die eigene Market-Projektion liest `maxMarketOrderQty`; `maxOrderQty` ist
ausschließlich die Limit-Grenze. Fehlende native Market-Höchstmenge bleibt
`None`. Ein eigener Intent-/Consentvertrag trennt beide Orderarten auch bei
gleicher Command-ID. Der native Admissioncheck akzeptiert ausschließlich
fehlendes Grantguthaben, fehlende Market-Maximalmenge, unbekannte tatsächliche
Kosten und ältere Auftragshistorie. Andere unbekannte Kontofelder, bekannte
Sicherheiten, belegte Margin, Positionen, offene oder unvollständig geprüfte
Pendingseiten, falsche BTC-Einstellungen und veraltete Quellen sperren
weiterhin. Die freigegebene Menge wird am frischen Ask erneut geprüft und
nicht nach der Zustimmung vergrößert.

[Umsetzung und Abnahme](bitget-demo-btc-market-test.md).

## Testgröße und Strategie-Kaufkapital

Der Nutzer bestätigt am2026-11-24 nochmals Q42:
Für die Strategie ist jeder geplante Kaufbetrag aus dem Basketbudget
Eigenkapital-Margin. Positionswert = Kaufmargin × fester Baskethebel;
Menge = Positionswert / Kaufpreis, abgerundet auf das Brokerraster.
Die Staffelbeträge werden nicht durch den Hebel geteilt. Das gilt
ebenso für alle gestaffelten Nachkäufe. Kosten bleiben separat eingeplant.
Der bestehende Kapital-/Paperkern berechnet Mengen bereits so.

Der einzelne technische Test verwendet ausdrücklich die oben freigegebene
Positionswertgröße von etwa20USDT. Tatsächlich wurden0,0003BTC zu
61.425,7USDT ausgeführt: Positionswert18,42771USDT und rechnerische
Initialmargin9,213855USDT bei2× vor Kosten. Dies ist kein Basket-Erstkauf
und keine Änderung der [Eigenkapitalstaffel](futures-capital-ladder.md).
Ein Strategie-Kaufbetrag20USDT würde bei2× etwa40USDT Positionswert
ergeben. Die spezielle Testmengenberechnung darf nicht als Positionswert-
Budgetierung in den operativen Basketablauf übernommen werden.

[Tatsächliche Eröffnungsabnahme](bitget-demo-market-runtime.md).
