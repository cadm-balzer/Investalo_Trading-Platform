# BTC-Demo-Testvorschau

Der Nutzer bestätigt die manuelle Vorbereitung von BTC auf isolierte Margin,
2× und One-way. PR108 ist als `ad32086` auf main verifiziert. Der nächste
Schritt verbindet eine frische, gezielte BTC-Kontoprüfung mit einer kleinen
Ordervorschau im Dashboard und Portfolio.

Die Schaltfläche „BTC-Testvorschau“ zeigt BTC-Menge, Limitpreis, maximalen
Positionswert und geschätzte Eigenkapital-Margin vor Gebühren. Das feste
technische Testlimit beträgt 20 USDT Positionswert und damit höchstens
10 USDT Initialmargin bei 2×; es verändert keine Basket-Kaufstaffel.
Preis und Menge werden bei jedem manuellen Abruf neu berechnet.

## Kontoprüfung und Marktquelle

`GET /api/bitget-demo/account?inspection=btc-test` nutzt den bestehenden
[Kontolesepfad](bitget-demo-account-sync.md), seine ursprüngliche Sitzung,
aktuellen Mitgliedschaften und aktiven Key-Metadaten vor und nach dem Abruf.
Die exakte zusätzliche Auswahl ist in der eigenen kurzen Leseassertion
signiert. Sie erteilt keine Order- oder Kontoänderungsfreigabe.

Der bestehende private Trading-AEAD-Provider liest zunächst native Identität,
USDT-Wallet und alle Positionen. Danach werden die BTC-Einstellung und alle
fünf produktweiten Pendingfamilien geprüft. Andere Coin-Konfigurationen
blockieren den gezielten BTC-Test nicht; fremde Positionen oder Orders im
gleichen Konto bleiben dagegen sichtbar. Originale 10k-Startbasis,
Cursor-/ID-/Statusprüfungen, null/null-Endseite und alle bisherigen
Kontosicherheiten-Prüfungen bleiben erhalten.

Zwei öffentliche, feste Demo-GETs lesen BTC-Kontrakt und Ticker. Sie erhalten
keinen API-Key und teilen die begrenzte Dreierwarteschlange, den 110ms-
Zulassungsabstand sowie frische Actor-/Storageprüfungen vor und nach der
Anfrage. Ohne Cursorfortsetzung sind es insgesamt elf GETs. Quelle und
gesamte Kohorte bleiben höchstens fünf Sekunden alt; kein Retry.

Die vorhandene [öffentliche Vorschau](bitget-demo-order-dispatch.md) berechnet
die exakte Menge aus nativen Mindestmengen und Rastern, rundet ab und begrenzt
den Limitaufschlag zum Ask auf 0,1%. Die ursprünglichen Quellzeiten bleiben
erhalten. Python und TypeScript prüfen Dezimalprodukte, Margin und Budget
exakt; TypeScript verwendet dafür BigInt statt gerundeter Number-Arithmetik.

Primärquelle:
[Bitget Classic-Kontrakte und Ticker](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market),
geprüft am 2026-11-23. `maxOrderQty` ist die native Limit-Höchstmenge;
eine fehlende Angabe bleibt unbekannt und wird nicht aus Spot/Live abgeleitet.

## Grenzen

Der eigene Bericht `investalo-demo-btc-test/1` enthält BTC-Readiness,
Vorschau und eine feste Liste unbekannter Kontofelder. So wird beispielsweise
ein fehlender Grant-/Couponbetrag konkret benannt, ohne ihn als belegte Margin
oder als Nullbetrag zu erfinden. Broker-UID, API-Daten, Rohantworten und
native Order-IDs gelangen nicht in den Browser.

`execution_enabled`, `submission_enabled`, `account_verified`,
`fees_verified`, `costs_verified` und `pending_scope_verified` bleiben false.
Die Kontoprüfung ist ein datierter Lesestand, keine Versandfreigabe.
Es gibt keinen Sendebutton, kein Konto-POST und keine Outboxanlage.
Native maximale Ordermenge, ältere Pendingabdeckung und tatsächliche
Kostenquelle bleiben vor dem gesonderten ersten Auftrag zu klären.

## Prüfung und Rollout

167 gepinnte Python- und 47 Nodefälle sowie vollständige Cockpit-Typprüfung
grün. Geprüft sind aktuelle echte AEAD mit synthetischen Keys, BTC-only-
Konfiguration mit produktweiter Orderprüfung, fremde Triggerorders,
Widerruf während öffentlicher Marktreads, alte Marktzeit, unsupported
Kontrakte, exakte Finanzprojektion und falsche Autoritätsflags.
Tatsächliche synthetische Node-/ASGI-mTLS-Antworten und originaler
Sitzungswechsel nach dem Abruf sind enthalten. Ein tatsächlicher Python-
Readerbericht wird außerdem unverändert vom TypeScript-Vertrag gelesen
(Host Node26.13.0; übrige Nodefälle gepinnt24.22.2).

Produktionsbuilds noch in Arbeit. Der Cockpit-Build akzeptiert optional
`COCKPIT_BUILD_HEAP_MB`; Standard768 unverändert, dieser kleine Host baut
mit512. Keine neue Dependency oder Migration, laufende Dienste unverändert.
Nach Merge und Rolloutfreigabe nur Cockpit und Demo-Executor neu erstellen;
Public/Paper/Demo-Trading/Admin-Mail/Account-Sync-Overlays beibehalten.
Tatsächliche native BTC-Gesamtabnahme folgt dann unter der Originalanmeldung.
