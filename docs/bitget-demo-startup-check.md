# Demo-Startprüfung

Fix auf PR108: tatsächlicher originaler Nutzerabruf vollständig erfolgreich,
15 native GETs in4551ms, HTTP200/00000, private Abschlussdiagnose `completed`
ohne Fehler. Sichtbare Berichtbestätigung folgt; ältere Auftragsabdeckung,
Kostenkalibrierung und Orderfreigabe bleiben eigenständige Folgeblöcke.

PR106/30ccdbe ist gemergt und der ausdrücklich freigegebene Rollout erfolgt:
Cockpit und Executor erneuert, fünf andere Dienste unverändert; TLS200,
anonyme Readvarianten401 und echtes privates mTLS405 geprüft.
Der Nutzerretry liefert den konkreten Fehler: zehn erfolgreiche GETs,
5265ms, `XRPUSDT:after_request:cohort_timeout`, HTTP200/00000. Die serielle
Laufzeit überschreitet die unveränderte5s-Kohorte. Der Fix überlappt die
folgenden unabhängigen Lesegruppen.159 gepinnte Pythonfälle inklusive
realistischem Latenztest und finaler Executorbuild grün; nur Executor
innerhalb der bestehenden Freigabe aktualisiert, privates mTLS405 und
unveränderte andere Dienst-IDs geprüft. Der weitere Nutzerabruf erreicht
13 GETs in4371ms; native200/00000, Parserfehler bei `normal_plan`.
Die private feste Diagnose belegt `entrustedList:null,endId:null`.
Die Startprüfung unterstützt nun ausschließlich diese exakte zweifeldrige
Leerantwort zusätzlich zur leeren Liste. Originaler Antwortzeitstempel
bleibt erhalten; fehlende Felder, unbekannte Zusatzfelder oder null-Liste
mit echtem Cursor werden weiterhin abgelehnt. Der alte `_pages`-/Readvertrag
bleibt unverändert. Weiterer Abruf verarbeitet diese Form, benötigt mit
15 GETs aber5246ms. Eine gemeinsame Workerwarteschlange entfernt deshalb
auch die Barriere zwischen Coin-Konfigurationen und Pendingfamilien.
Ein Ereignistest belegt Pendingabruf während letzter Konfiguration.
Tatsächlicher vollständiger nativer Abruf jetzt erfolgreich, siehe oben.

Der Nutzer bestätigt 10.000 virtuelle USDT auf dem API-Demokonto und die
passende Anzeige im Cockpit. Die neue Schaltfläche „Startprüfung“ auf
Dashboard und Portfolio prüft nun die Einstellungen und offenen Aufträge
für den ersten Demo-Test. Ein Bericht aktiviert keinen Handel.

Der manuelle Abruf `GET /api/bitget-demo/account?inspection=startup`
umgeht den numerischen Konto-Cache. Er nutzt die bestehende ursprüngliche
Sitzung, aktuelle Owner-/Trader-Mitgliedschaft, aktive Key-Metadaten,
15s-Leseassertion, private mTLS-Verbindung und den bestehenden Trading-AEAD-
Provider. Die exakte zusätzliche Bodyauswahl `inspection: startup` ist
signiert; beliebige Symbole, Pfade oder Schreibaktionen sind ausgeschlossen.
Ordentliche Kontoabrufe behalten ihre drei GETs und ihren eigenen Vertrag.

Die Startprüfung liest zuerst native Identität, Wallet und alle Positionen.
Danach folgen Kontokonfigurationen für AVAX, BNB, BTC, ETH, LINK, SOL und
XRP sowie fünf produktweite Auftragslisten: live, teilweise ausgeführt,
normale Trigger, Trailing und Take-Profit/Stop-Loss. Die bestehenden festen
`DemoReadPlan`-Ziele werden wiederverwendet. Einseitiger Positionsmodus,
isolierte USDT-Margin, Single-Asset und 2× Long werden je Coin verglichen;
abweichende oder unbekannte Einstellungen bleiben sichtbar.

Das ursprüngliche Startguthaben von 10.000 USDT kommt aus der
Nutzerbestätigung, nicht aus dem gerade abgefragten Konto. Belegte Margin,
abweichende Sicherheiten, Positionen und gefundene Aufträge werden gemeldet.
Dies ist ausschließlich ein Vergleich vor dem ersten Test; für laufende
Baskets muss anschließend die dauerhafte eigene Cash-/Positions-/Outboxbasis
maßgeblich werden. Keine Umdeutung späterer Gewinne als Guthabendrift.

Jede nichtleere `endId` wird mit dem bestehenden monotonen Cursor-/ID-/
Statusprüfer verfolgt, bis eine leere Abschlussseite erreicht wird.
Der eigene Startupadapter behandelt die belegte exakte native null/null-
Leerantwort als solche Abschlussseite, auch nach nichtleeren Cursorseiten.
Vorher gefundene Aufträge bleiben dabei gezählt und blockieren den Start.
Höchstens zehn Seiten je Kategorie; ein abgeschnittener Bereich bleibt
unvollständig. IDs, Client-IDs, native Rohantworten und Zugangsdaten werden
nicht an den Browser weitergegeben. Der Bericht enthält nur Anzahl, Umfang,
Einstellungen und die älteste Quellezeit. Doppelte/regressive IDs, fehlende
Antworten, Widerruf oder veraltete Quellen verwerfen den gesamten Bericht.

Alle GETs teilen den ursprünglichen Registrierungs-/Lesemutex. Die
Requestzulassung bleibt mit mindestens110ms Abstand gepacet; maximal drei
Worker überlappen die unabhängigen Coin-Konfigurationen und Auftragsfamilien.
Alle zwölf unabhängigen Abfragen nutzen eine gemeinsame Warteschlange;
freie Worker warten nicht auf den Abschluss der gesamten Konfigurationsgruppe.
Native Identitäts-/Wallet-/Positionsprüfung erfolgt zuerst; Cursorseiten
derselben Familie bleiben in Reihenfolge. Ein Fehler stoppt neue Jobs und
wartet ausstehende Worker ab, bevor der UID-Mutex freigegeben wird.
Die bestehende5s-Kohorte und
5s-Quellfrische bleiben verbindlich. Ein langsamer nativer Lauf kann deshalb
unbestätigt bleiben; keine automatischen Wiederholungen und kein Rückfall auf
einen alten erfolgreichen Startbericht. Automatische Kontoabrufe im selben
Panel pausieren während der manuellen Prüfung. Der Bericht ist ein datierter
Prüfstand, kein dauerhaftes Bereitschaftssignal.

## Grenzen und nächster Schritt

Die aktuellen offiziellen Classic-Dokumentationen beschreiben bei
[Standardaufträgen](https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade)
und [Triggeraufträgen](https://www.bitget.com/docs/catalog/classic-contract-plan/classic-contract-plan)
ein maximales Zeitfenster von drei Monaten. Vollständige Cursorabfrage
beweist daher noch keine Abdeckung älterer offener Aufträge. Die
[Kontokonfiguration](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account)
dokumentiert `isolatedLongLever` als String, zeigt im aktuellen Beispiel
aber einen Integer; beide exakten Formen werden geprüft, keine Floats/Bools.
Quellen geprüft am 2026-11-22.

`pending_scope_verified`, `costs_verified` und `execution_enabled` sind
im eigenen Antwortvertrag zwingend **false**. Tatsächliche Fill-/Funding-
Kosten bleiben unbekannt, bis sie separat nativ kalibriert sind. Keine
Gebühren mit Null ersetzen und keine Paperkosten als Brokerkosten buchen.
Auch ein Bericht ohne gefundene Abweichungen erteilt keine Orderfreigabe.

Nächster Block: tatsächliche Startprüfung unter gültiger Dashboard-Anmeldung,
ältere Auftragsabdeckung/Kostenquelle und private ursprüngliche Outboxbasis,
danach Demo-Dispatcher und exakte kleine BTC-Limit-IOC-Vorschau mit 2×.
Der konkrete Auftrag benötigt seine eigene Freigabe vor Versand.
H1-RSI/fünf Käufe/drei Anfangsbaskets folgen danach.

## Prüfung und Rollout

Ursprünglicher PR106:50 gepinnte Node- und53 Pythonfälle grün: Projektion, ursprüngliche Sitzung
vor/nach Await, Cachetrennung, exakte Auswahl, echte synthetische Node-/ASGI-
mTLS-Antworten, reale AEAD-Entschlüsselung synthetischer Keys, Paginierung,
Grenzwerte, Widerruf und alte Runtime-/Identitätsfälle. Quellen und
Brokerantworten synthetisch; keine native Gesamtabnahme behauptet.
Typecheck, vollständige Compose-Konfiguration und finale gepinnte
Cockpit-/Executorbuilds ebenfalls grün. Bestehende laufende Dienste bleiben
unverändert; neue Images allein aktivieren die Funktion nicht.

Keine neue Dependency, Migration, private Konfiguration oder Portfreigabe.
Neue Funktion nutzt die vorhandenen Sync-Schalter. Nach Merge und
gesonderter Rolloutfreigabe nur `cockpit` und `demo-trading-executor`
neu erstellen. Public-, Paper-, Demo-Trading-, Admin-Mail- und Account-Sync-
Overlays samt bestehender Envdatei vollständig beibehalten. Keine
Ordereinstellung oder automatische Änderung des Bitget-Kontos.
