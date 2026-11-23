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

Der BTC-Lesepfad gleicht `grant` aus der Kontoliste mit dem bereits
abgefragten BTC-Einzelkonto ab. Beide Endpunkte dokumentieren dieses Feld
als Futures-Airdrop-Voucherbetrag.
[Bitget Classic-Kontofelder](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account),
geprüft am 2026-11-23.
Ein fehlender Listenwert darf durch einen bestätigten BTC-Wert ersetzt werden.
Bekannte widersprüchliche Beträge verwerfen den gesamten Bericht; positive
Beträge bleiben eine Sicherheitenwarnung. Fehlt der Wert in beiden Antworten,
bleibt Bonusguthaben unbekannt. Fremde Coins/Symbole und ungültige Beträge
werden abgelehnt.

Es entstehen keine zusätzlichen GETs. Originale Quellezeit, Fünfsekunden-
Kohorte, Credential-/Actorprüfungen und alle anderen Walletchecks bleiben
erhalten. Der Browservertrag bleibt gleich. Nur die private technische
Diagnose nennt die feste Quellenklasse `wallet`, `btc_account` oder
`unconfirmed`; sie enthält keinen Grantbetrag und keine Rohantwort.
Die allgemeine Sieben-Coin-Startprüfung verwendet weiterhin die Kontoliste.

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

Finale gepinnte Cockpit-/Executorbuilds grün. Zwei tatsächliche öffentliche
Demo-GETs liefern eine gültige Vorschau:0,0003 BTC, Limit61519 USDT,
Positionswert18,4557 USDT, Initialmargin9,22785 USDT; datierter Teststand,
keine Orderfreigabe. Native Maximalmenge bleibt dabei tatsächlich unbekannt.
PR109 ist auf main `6d741a3` gemergt und der angekündigte Rollout nach
Nutzerbestätigung abgeschlossen. Der tatsächliche Abruf aus der
Originalanmeldung ist erfolgreich:elf GETs in4044ms, HTTP200/00000,
private technische Abschlussdiagnose ohne Fehler. Nutzer bestätigt die
Anzeige vom20261123 12:02:20/22:0,0003 BTC, Limit61482,7 USDT,
Positionswert18,44481 USDT, Initialmargin9,222405 USDT vor Gebühren.
Alle fünf abgefragten Pendingfamilien zeigen null Aufträge.

Die erste native BTC-Konfiguration war isoliert/Hedge/2×.
Der Nutzer bestätigt anschließend die Vorschau vom20261123 12:23:39/41:
**isoliert/einseitig/2×**, Profil passt und alle fünf Pendingfamilien weiterhin
null Aufträge. Menge0,0003 BTC, Limit61410,6 USDT, Positionswert18,42318 USDT,
Initialmargin9,21159 USDT vor Gebühren. Das Grant-Feld wird nicht bestätigt und bleibt als
Bonusguthaben unbekannt. Native Maximalmenge ist ebenfalls unbestätigt.
Es wurden keine Nullbeträge oder Orderlimits daraus abgeleitet.
Die noch offene Kosten-/ältere Scopeabnahme und einmalige konkrete
Orderfreigabe bleiben eigenständige nächste Schritte.

PR110 ist auf main `a532e07` verifiziert. Der ergänzte Grant-Quellenabgleich
besteht176 gepinnte Pythonfälle inklusive echtem AEAD mit synthetischen
Brokerantworten: bestätigter Null-/Positivbetrag, unbekannte oder widersprüchliche
Quellen, ungültige Beträge, fremde Kontosicherung, alte Quellezeit sowie
unveränderte andere Walletblocker und Sieben-Coin-Startprüfung.
Executorbuild grün; kein Frontendneubau. Ein bestätigter BTC-Grant als
Ersatzquelle ist nativ noch nicht beobachtet. PR111/main `bf5ddbe`
verifiziert und Grant-Rollout abgeschlossen: ausschließlich Executor erneuert,
sechs andere Dienste unverändert, TLS200/anonyme Reads401/mTLS405/Key1/1.
Privater Rückweg unter `infra/local/demo-btc-grant-source`.
Der anschließende originale Nutzerabruf bestätigtelf GETs/3952ms/native200/
00000 und die private Quellenklasse `unconfirmed`: Grant wird von keiner
der beiden Kontoquellen geliefert. Nutzer bestätigt die verbleibende
Bonus-/Maximalmengenwarnung. Kein nativer Nullbetrag oder Orderlimit bestätigt.

Der Cockpit-Build akzeptiert optional
`COCKPIT_BUILD_HEAP_MB`; Standard768 unverändert, dieser kleine Host baut
mit512. Keine neue Dependency oder Migration, laufende Dienste unverändert.
Nur Cockpit und Demo-Executor wurden mit den verifizierten fertigen Images
erneuert; fünf andere laufende Container-IDs unverändert. Public/Paper/
Demo-Trading/Admin-Mail/Account-Sync-Overlays und ursprüngliche Envdatei
beibehalten. Paketierte Python-Hashes entsprechen main, kompilierte
Frontendmarker sind vorhanden; kein neuer Build für diesen Rollout.

Cockpit gesund und beide Dienste ohne Neustarts, Executor readonly,
ohne Hostports und Logausgabe. Öffentliches TLS200, drei nicht angemeldete
Accountvarianten401 und tatsächliches privates mTLS405 geprüft. Bestehender
Demo-Key bleibt active/revision1/storage1.
Private ursprüngliche Image-Rollbackoverlays sowie Vorher-/Aktivbelege unter
`infra/local/demo-btc-test-preview/rollout-*`. Rückweg: dieselben ursprünglichen
Overlays/Envdatei plus dortiges `rollback-images.yaml`, nur die beiden
Dienste mit `up -d --no-deps --no-build --force-recreate` erneuern.

Der kleine Host meldete für die Frontend-Optimierung432,8min. Vor weiteren
größeren Frontendblöcken Buildauslastung/externen Builder prüfen; der
optionale Heapparameter begrenzt RAM, garantiert aber keine kurze Buildzeit.
