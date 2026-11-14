# Handelsassets, RSI und nächste Kaufgrenze

Q48/IP-090, lokaler Zwischenstand2026-11-14. PR59 (`b6890eb`) ist in
Main `29f6661` gemerged; GH und Git-Ancestry geprüft.
Die eigene Assetprojektion, authentifizierte Lese-API und Dashboardansicht
sind implementiert. Dauerhafte Workerpublikation und öffentliche Aktivierung
bleiben vom vollständigen Futures-Paperbetrieb abhängig.

## Anzeigevertrag

`futures_paper_view.asset_snapshot` liest ausschließlich einen eigenen
`FuturesPaperState` für den exakt erwarteten Mandanten und Account.
Der vertrauenswürdige Reader muss den letzten bestätigten Journalzustand
liefern. Der Leseweg verändert keine Position, Staffel, Signale oder Orders.
Ein fremder/futurischer Zustand wird abgewiesen; ein nicht angeschlossener
Reader liefert einen fehlenden Snapshot statt behaupteter leerer Positionen.

Alle tatsächlich im Paperplan gewählten Kandidaten erscheinen, auch ohne
offenen Basket. Der erste Quellenkorb bleibt BNB/BTC/ETH/SOL/XRP.
Angezeigt werden:

- RSI14/Wilder auf H1, Zeitpunkt des letzten geschlossenen H1-Signals,
  maximal zwei Bestätigungen unter30 und RSI-Rearm.
- Letzter Bid und dessen Beobachtungszeit; offene Menge, Durchschnittseinstieg,
  eigener eingefrorener2×-Hebel, Zahl regulärer Käufe und letzter tatsächlicher
  Ausführungspreis.
- Nächste Kaufstufe und maximale Ausführungspreisgrenze:
  `floor_tick(letzter tatsächlicher Kauf × 0,95)`.
  Die Grenze stammt weder aus dem Durchschnittseinstieg noch aus einem
  geplanten/hypothetischen Kauf. Für Erstkäufe gibt es keine feste Kursgrenze.
- Nächster H1-Signalcheck mit Europe/Berlin-Anzeige. Dies ist ein geplanter
  Auswertungszeitpunkt, keine Kaufzeit- oder Kursprognose.

Beispiel aus der synthetischen Prüfung: letzter Kauf100,01 mit Tick0,01
ergibt95,00 USDT als Grenze. Nach einem tatsächlichen zweiten Kauf bei64
wird60,80 USDT angezeigt, obwohl der Durchschnittseinstieg höher liegt.
Die Ausführung muss Ask, Slippage und die Rundung in Handelsrichtung einhalten.

Die Warteanzeige unterscheidet RSI-Rearm, RSI unter30, zweite Erstkaufbestätigung,
weiteren Preisrückgang und das nächste H1-Einstiegsfenster.
Das bestehende30-Sekunden-Fenster nach geschlossenem Einstiegssignal bleibt
verbindlich: ein neuer frischer Quote verlängert es nicht.
„RSI-Bedingung erfüllt“ ersetzt keine Prüfung von Funding, Margin,
Eigenkapital, Kostenreserve, Ask oder Orderintegrität.

Nach fünf regulären Käufen erscheint die manuelle sechste Stufe ohne
automatische Kaufautorität. Pausierte Konten, aktive Ausstiegsprotektion,
Kontohaltes/Liquidationsabgleich, liquidierte Assets und belegte finanzierte
Erstkaufplätze werden ausgewiesen. Kapazitätsbelegung blockiert keine
bestehende Staffel. Fehlende aktuelle Quotes/geschlossene Stunden markieren
gespeicherte Werte als veraltet; offene Mengen bleiben sichtbar.

## API und Cockpit

GET `/v1/futures-paper-assets` verlangt die bestehende requestgebundene
BFF-Authentifizierung und aktuelle Mitgliedschaft. Die restricted-LOGIN-
Transaktion liest nur eigene Bitget-Paper-USDT-Konten, explizit tenantgebunden.
Der serverseitig injizierte Reader erhält ausschließlich diese festen IDs;
kein Browserzustand, Dateipfad, Snapshot oder Profil wird angenommen.
Exceptions/fremde Zustände ergeben eine generische503 ohne Rohdaten.
Alle Antworten sind `no-store`; keine Schreibroute.

Die TS-Grenze prüft Schema/Mandant/Papermodus, IDs, Zahlen, RSI0–100,
Zeitachsen, Duplikate, Stufen/Positionen und bekannte Status-/Sperrcodes.
Sie entfernt unbekannte Felder. Historische Forschungs- und Liveantworten
werden abgewiesen.

`FuturesAssetsPanel` steht auf Startseite und Portfolio. Eigene Futuresbaskets
bleiben von der bisherigen Positionsliste getrennt. RSI ist auf zwei Stellen
gerundet; der ungerundete Wert steht im Tooltip. Kursgrenzen werden exakt
ausgegeben. Die Ansicht aktualisiert den Serverstand alle15 Sekunden, pausiert
im versteckten Tab und aktualisiert beim Zurückkehren.

API-Opt-in `API_FUTURES_PAPER_ASSETS_PREVIEW=1`,
Cockpit-Opt-in `COCKPIT_FUTURES_PAPER_ASSETS_PREVIEW=1`.
Beide bleiben standardmäßig aus; Compose/Public wurde nicht geändert.
`create_app(..., futures_paper_state_reader=...)` ist der private Anbindungspunkt.
Der normale Launcher stellt derzeit noch keinen solchen Reader bereit.
`runtime_ready=false`/`recommendation=null` bleiben unverändert.

## Prüfung und nächster Anschluss

Neun neue Domainfälle, vier neue tatsächliche restricted-LOGIN/HTTP/
PostgreSQL-Fälle und sechs neue Cockpitfälle. Die erste gezielte Regression
umfasst74 Fälle; zwei zusätzliche Zeitfenster-/Nachkauffälle ergeben insgesamt
76 verschiedene gepinnte Paper/API-Prüfungen mit34 Subtests;
nach letzten Ergänzungen alle13 neuen Domain/API-Fälle erneut gepinnt.
32 gezielte Cockpitfälle plus abschließende sechs Assetfälle und Typecheck grün.
Gepinnter Next.js16.4.5-Cockpit-Build erfolgreich; laufende Dienste unverändert.
Keine neuen Performancejobs, Migrationen, Abhängigkeiten oder öffentliche/
Live-/AI-Aktivierung. Die bestehenden Daten-/Strategie-/Risikoprofile bleiben.

Weiter: native Funding-Settlementbewertung, dauerhafter Quellen-/Journalcursor,
Launcher/Archivierung und Veröffentlichung des bestätigten Zustands an den
Reader; danach Anzeigeabnahme im laufenden Entwicklungscockpit.
013-Einstellungsübernahme, Q36-Gewinnetappen und IP-088-Recovery bleiben IP-090.
