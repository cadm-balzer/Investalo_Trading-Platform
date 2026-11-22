# Demo-Kontodaten im Cockpit

Der Konto-Sync zeigt das USDT-Futures-Konto im Dashboard und im Portfolio:
Kontowert, freie Margin, unrealisiertes Ergebnis, gesperrter Betrag und offene
Positionen mit Richtung, Menge, Durchschnittseinstieg, Markpreis, Hebel,
Marginmodus und Liquidationspreis. Der Browser aktualisiert beim Öffnen,
alle 30 Sekunden in sichtbaren Tabs und über „Aktualisieren“.

Fehlende Beträge bleiben unbekannt (`—`). Erst ein erfolgreich empfangenes
Positionsverzeichnis darf als leer dargestellt werden. Bei Lesefehlern bleibt
der zuletzt bestätigte Stand mit Zeitstempel und Kennzeichnung sichtbar.
Die Anzeige unterdrückt Daten einer zuvor ausgewählten anderen Mandantschaft.

## Lesepfad

`GET /api/bitget-demo/account` verlangt eine gültige ursprüngliche
Cockpit-Sitzung und eine Anfrage derselben Origin. Der BFF prüft `/v1/me`,
Mitgliedschaft, aktuelle Epoche und die aktiven eigenen Demo-Key-Metadaten
vor und nach dem Abruf. Der kurze Cache enthält ausschließlich die unten
beschriebenen Kontodaten; auch Cachetreffer durchlaufen die aktuellen Prüfungen.
Keine Browserpersistenz, keine öffentliche HTTP-Zwischenspeicherung.

Der vorhandene private mTLS-Executor erhält eine eigene, auf 15 Sekunden
begrenzte Leseassertion mit separatem Kind und Audience. Der siebenfeldrige
ursprüngliche Sitzungskontext wird unabhängig über den mTLS-Header übermittelt.
Assertions binden exakten Body, Konto, Keyrevision, Speicherversion und JTI;
ein verbrauchtes JTI wird nicht erneut akzeptiert. Diese Assertion erteilt
keine Schreib- oder Passkey-Autorisierung.

Die eingeschränkte bestehende SQL-/AEAD-Anbindung liest den verschlüsselten
Demo-Handelskey unter aktueller Rolle, Epoche, Kontostatus und Speicherversion.
Entschlüsselung und Bitget-Signatur bleiben im UID10003-Executor. Der Dienst
führt genau drei signierte GETs mit `paptrading: 1` aus:

1. `/api/v2/spot/account/info`: native UID, Parent, Rechte und IP-Policy.
2. `/api/v2/mix/account/accounts?productType=USDT-FUTURES`: USDT-Konto.
3. `/api/v2/mix/position/all-position?productType=USDT-FUTURES&marginCoin=USDT`:
   offene Positionen.

Der native Transport behält seine bestehenden TLS-/Hostname-/Größen- und
Timeoutprüfungen. Die Registrierungs- und Lesepfade teilen denselben lokalen
UID-Limiter und Mutex. Jeder Cohort ist auf fünf Sekunden begrenzt, prüft den
aktuellen verschlüsselten Datensatz vor und nach jeder Anfrage und wiederholt
keine fehlgeschlagene Anfrage automatisch. Die Quellezeit ist der ältere
Zeitpunkt von Konto- und Positionsantwort. Mehr als 100 Positionen oder
unzulässige Antworten werden verworfen, nicht gekürzt.

Der private Antwortvertrag `investalo-demo-account/1` erlaubt ausschließlich
Mandantschafts-/Plattformkonto-ID, Quellezeit, USDT-Walletwerte und diese
Positionsfelder. Broker-UID, Parent, API-Key, Secret, Passphrase, native
Rohantwort, Provenienz und Ciphertext gelangen nicht in die Anzeige.
Beträge bleiben dezimale Strings; Liquidationspreise ≤0 gelten als unbekannt.

Quellen: [Bitget Demo REST](https://www.bitget.com/docs/classic/demo-trading/rest-api),
[Contract Account](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account),
[Contract Position](https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position).

## Betrieb und Abnahme

Explizites, standardmäßig inaktives Overlay:
`infra/compose.demo-account-sync.yaml`. Es aktiviert ausschließlich
`DEMO_ACCOUNT_SYNC_ENABLED=1` und `COCKPIT_DEMO_ACCOUNT_SYNC=1`.
Die bisherigen Public-/Paper-/Demo-Trading-/Admin-Mail-Overlays bleiben
Bestandteil derselben Compose-Installation. Keine Migration, neue
Abhängigkeit, weitere Portfreigabe oder Keyänderung.

Nach Merge und Freigabe gemäß AGENTS.md die geprüften Cockpit-/Executorimages
in dieser vollständigen Kombination verwenden und nur `cockpit` und
`demo-trading-executor` neu erstellen. API, Postgres, Paperworker und
Identitätsprovider müssen nicht verändert werden. Abschalten durch Entfernen
des Sync-Overlays und Neuerstellen derselben beiden Dienste.

Geprüft am 2026-11-22: 60 gezielte gepinnte Node- und 42 Pythonfälle, echte lokale Node- und
ASGI-mTLS-Verbindungen, reale AEAD-Entschlüsselung synthetischer Keys,
Rechte-/UID-/Session-/Replay-/Revocation- und Projektionstests sowie
Typprüfung und vollständige Compose-Konfiguration. Die bestehende
Demo-Key-Einrichtung bleibt in den Regressionen enthalten.

Der einmalige native Vorabprobeversuch stoppte vor Bitget am abgelaufenen
ursprünglichen Registrierungssitzungskontext. Kein Ersatz-Authzeitpunkt und
keine Ersatzsitzung erzeugt; keine native Kontoantwort oder Brokerabnahme
behauptet. Privater Diagnosebeleg:
`infra/local/demo-account-sync/probe-error`. Der erste tatsächliche Abruf
erfolgt nach Freischaltung und gültiger Cockpit-Anmeldung. Anschließend
Kontowerte, native Latenz und Quota praktisch prüfen.

Dieser Überblick ist keine vollständige Order-/Trigger-/Cash-/Kosten-
Reconciliation und startet keine Orders. Diese Abnahme und der
Demo-Orderdispatcher bleiben separate nächste Aufgaben.
