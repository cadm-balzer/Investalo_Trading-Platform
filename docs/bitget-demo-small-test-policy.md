# Vorschlag: einzelner technischer BTC-Demotest

Status: **Nutzerentscheidung offen, nicht implementiert oder aktiviert**.

Der bisherige [Auftragsvertrag](bitget-demo-order-dispatch.md) verlangt
native Konto-/Mengenklärung vor dem ersten Versand. Bitget liefert im
tatsächlich geprüften Demokonto weder Grantbetrag noch maximale
Ordermenge; Kosten und ältere Auftragsabdeckung sind weiterhin nicht
bestätigt. Unter dieser bisherigen Regel bleibt der Versand gesperrt.
Bitget beschreibt Demo ausdrücklich als Handel mit virtuellen Mitteln:
[offizielle Demo-Dokumentation](https://www.bitget.com/docs/classic/demo-trading/rest-api),
geprüft2026-11-23.

Für den vom Nutzer gewünschten technischen Test wird ein eigener enger
Testmodus vorgeschlagen. Dieser Modus lässt genau diese unbestätigten
Angaben sichtbar und akzeptiert, dass Bitget den kleinen Auftrag wegen
eigener Limits ablehnen kann. Er behauptet keine Nullbeträge, bestätigte
native Mengenhöchstgrenze, Gebühren oder vollständige ältere Auftragshistorie.

Der konkrete Umfang:

- Ausschließlich das bestehende, nativ identifizierte Bitget-Demokonto
  mit bestätigten10.000 virtuellen USDT und aktivem Trading-Key.
- Ein neuer BTCUSDT-Long mit isolierter Margin, One-way und2×.
  Höchstens20 USDT Positionswert, höchstens10 USDT Initialmargin vor
  den weiterhin unbestätigten tatsächlichen Gebühren.
- Native Mindestmenge, Mengen-/Preisraster und Mindestnotional müssen
  bestätigt sein. Keine Vergrößerung bei nicht passender Mindestmenge.
- Frische freie Margin, keine aktuellen Positionen, keine bekannten
  Aufträge in allen fünf Pendingfamilien. UID/Parent/Rechte, aktueller
  Actor/Key und ursprüngliche Zeit-/Quota-/Installationsguards bleiben Pflicht.
- Limit-IOC mit höchstens0,1% Aufschlag zum aktuellen Ask, explizite
  aktuelle Zustimmung, dauerhafte einmalige Freigabe und Orderjournal.
  Kein wiederholter POST bei unbestätigtem Ausgang; nur Statusabfrage.
- Ergebnis als technischer Test protokollieren: ACK, tatsächliche
  Ausführung und Position getrennt. Unbekannte Gebühren bleiben unbekannt,
  kein Nettoertrags- oder Strategievalidierungsnachweis.

Der Vorschlag umfasst keine automatische Basketstrategie, andere Coins,
höheren Hebel oder Echtgeld. Die normalen Handelsprüfungen bleiben streng.
Er erfordert eine eigene geprüfte Implementierung; aktuelle Klassen/Routes
dürfen dafür keine unbekannte native Höchstmenge durch einen erfundenen
`DemoGrid`-Wert ersetzen. Ein späteres Schließen betrifft ausschließlich
die diesem Test belegbar zugehörige Menge per Reduce-only.
