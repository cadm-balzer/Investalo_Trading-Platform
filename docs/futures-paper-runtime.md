# Eigener Futures-Paperkern: erster IP-090-Schritt

PR57 ist in Main `f8a2217` gemerged; Head `c196093` ist per GH/fetch als
Vorfahr bestätigt. Dieser Schritt implementiert den eigenen Paperablauf
mit eingespeisten Daten. Aktueller Collector und eigene
[Assetanzeige](futures-paper-assets.md) sind inzwischen implementiert.
Der [Funding-only-Journalbefehl](futures-paper-settlement.md) mit injizierter
Settlementbewertung ist implementiert. Tatsächliche Bewertungsquelle,
vollständiger Fundingbetrieb, Launcher, dauerhafte Status-/Settingsanbindung
und manuelle Wiederbelebung bleiben IP-090/IP-088.

## Kandidaten, Budgets und Handel

`CapitalPaperPoolPlan` hat die eigene Policy
`isolated-usdt-capital-paper-pool/1`. Drei bis sieben konfigurierte
Kandidaten warten auf Signale für anfänglich drei bis fünf finanzierte
Plätze. Jeder Kandidat erhält dieselbe Budgetvorlage; erst der tatsächliche
Einstieg beansprucht die vollständige Range. Leere Kandidaten reservieren
kein zusätzliches Kapital.

Bei 10.000 USDT und drei Plätzen bleiben die sechs Eigenkapitalbeträge
293,13365892 / 366,41707366 / 458,02134207 / 572,52667759 /
715,65834699 / 894,57293374 USDT pro Basket. Kostenreserve separat;
die sechste Stufe bleibt ausschließlich manuell reserviert.
Mengen werden am eingefrorenen Raster abgerundet, Preise in Handelsrichtung
gerundet. Die Config bindet eigene Paperanfangsmittel, keine Spotbalance.

Die Obergrenze ist von tatsächlich finanzierten Plätzen getrennt.
Absenken verändert keine offenen Budgets und erzwingt keinen Ausstieg.
Bestehende Nachkäufe gehen neuen Kandidaten vor; die Kapazitätsprüfung
betrifft nur Erstkäufe. Tatsächliche Margin-/Cash-/Kostenprüfungen bleiben.
Eine Erhöhung auf sieben erzeugt noch keine Gewinnfreigabe: der erste
Kern behält die anfängliche Zahl finanzierter Plätze. Q36-Gewinnetappen
und spätere Volumenerhöhungen müssen noch angebunden werden.
Die Kandidatenliste ist keine Freigabe ungeprüfter Instrumente/Feeds.
Die historische Ledgerdiagnose `reserve_shortfall` summiert weiterhin
alle Kandidatenvorlagen. Sie ist für den Pool kein Kapazitätsbeleg;
der Statusadapter muss tatsächliche offene/gestoppte Ranges und eigenes
Cash aus dem Paperzustand berücksichtigen.

Ein einmaliger Warmup mit 16–72 zusammenhängenden geschlossenen nativen
H1-Trade-/Markkerzen bildet RSI14/Wilder und H1-Supertrend, ohne historische
Käufe. Nach `trading_from` benötigt der erste Einstieg zwei geschlossene
RSI-Werte unter30 und friert 2× für den gesamten Basket ein.
Nachkäufe verlangen RSI-Rearm und maximal95 % des letzten tatsächlichen
Kaufpreises. Nach fünf Käufen bleibt die manuelle Mitteilung gespeichert.
H1-Supertrend/Netto-Breakeven/Profitprotektion verwenden den bestehenden
Finanzkern. 6 %/8 % sind Warnungen, −55 % bleibt Notausstieg.

Ein Batch enthält vollständige kanonische Bid-/Ask-/Markquotes, höchstens
30 Sekunden alt. Modellkäufe verwenden den aufgerundeten Ask mit deklarierter
Slippage, Verkäufe den abgerundeten Bid. Funding verlangt native ID/Rate
und exakt passende Settlementzeit/Mark. IDs bleiben unabhängig von
Paket-IDs dauerhaft erhalten; wiederholtes Funding wird abgewiesen.
Erlaubte eigene Kostenrestoration verändert keine regulären Kaufbeträge.

Der [aktuelle Classic-Collector](futures-paper-feed.md) bewahrt native
Quotenzeiten, geschlossene H1-Achsen, Fundinghistorie und Forecast.
Seine Übergabe stoppt offene Positionen vor unbewerteten Fundingterminen;
vollständiger dauerhafter Fundingbetrieb bleibt noch offen. Der Kern fragt
keinen Provider ab und erkennt keine absichtlich ausgelassenen Settlements.
Fehlende letzte H1-Kerzen, offene Mehrstundenlücken oder eine bereits am
früheren Stundenende beobachtete Liquidation verlangen Abgleich vor neueren
Quotes. Ein erholter Quote darf keine Liquidation rechnerisch beseitigen.

Mitternacht bindet aktuelle Marks vor der Tagesbasis. Der Tradequote
verwendet danach dieselbe Bewertung, ohne die Ledgerphasen umzukehren.
Nach einem Ausstieg erfolgt frühestens mit einem weiteren echten Quote
ein Kauf; keine künstlichen +1s/+2s-Beobachtungen. Terminale Liquidationen
buchen den Verlust und sperren das Asset. Wiederbelebung ist noch kein
Journalbefehl. Gebühren, Wartungsmargin, Raster und Slippage sind explizite
Modellannahmen; Liquidationsgebühr und möglicher Insurancecredit ebenso.
Ohne Kreditannahme blockiert ein negativer Liquidationsrest.
Alle Fills sind vollständige Paper-Modellfills, keine Brokerbestätigungen.

## Journal und Worker

`FuturesPaperJournal` hat die eigene Version
`isolated-usdt-futures-paper-journal/1`. Genesis bindet Tenant/Konto,
Budgets, Regeln, Kostenannahmen und Handelsbeginn. Historische
Researchjournals werden nicht konvertiert oder überschrieben; ihr Decoder
akzeptiert die neue Policy nicht. Gemeinsame Reducer registrieren nur
die zusätzliche explizite Plantype und Erstkauf-Kapazitätsprüfung.

Warmup, vollständiger Handelsbatch, Funding-only-Settlement oder Einstellungsrevision werden
jeweils als ein gehashter Befehl berechnet, geschrieben und per fsync
bestätigt, bevor der Zustand veröffentlicht wird. Settingsbefehle haben
eigene fortlaufende Revisionen; Migration013 ist noch nicht angebunden.
Ein Prozesslock schützt konkurrierende Befehle/Readback, ein Dateilock
weitere Writer. Dateien sind owned0600/create-only, ohne Symlinks/Hardlinks.
Grenzen:50.000 Befehle,256 KiB/Zeile,512 MiB/Datei und vollständige begrenzte
Eventidentitäten. Keine Evidenzlöschung; Langzeitarchivierung/Checkpointrotation
ist vor dauerhaftem Launcherbetrieb noch zu ergänzen.

Restore faltet Genesis und sämtliche Befehle, prüft Kontext, Revision,
Finanzzustand und Hashkette. Der Aufrufer bindet den originalen
Genesis-Configdigest, nicht eine neu berechnete Config aus späteren Settings.
Ein separat geschützter letzter Acknowledgementreceipt als Mindestanker
erkennt auch das Abschneiden vollständiger früherer Zeilen.
Verlorene Schreibbestätigung vergiftet die Instanz: schließen, vollständig
zurücklesen und bestätigten Stand abgleichen; kein automatischer Retry.
Rückwärtslaufende Uhr und veraltete Revisionen werden verworfen.

`FuturesPaperWorker` verbindet den synchronen Injected-Feedvertrag mit dem
Journal und meldet Einträge/Abschlüsse/Zustandsdigest nach bestätigtem
Commit. Kein Orderclient, Credentials oder autonomer Launcher.
Spotdienst und öffentliche Opt-ins bleiben unverändert.
`runtime_ready=false`/`recommendation=null` der Planungs-API bleiben korrekt.

## Prüfung und nächste Schritte

139 gezielte gepinnte Kapital-/Signal-/H1-/Journal-/Kapazitätsfälle und
76 Subtests bestanden. Nach den letzten Korrekturen alle20 eigenen
Paperfälle erneut unter Python3.14.10 geprüft: Kandidaten/volle fünf kausale
Käufe/manuelle Reserve, Mitternacht, Funding/Restoration, Liquidationssperre,
Preis-/Zeit-/Lückenfehler, Settings/CAS, konkurrierende Befehle,
kompletter Restore/Weiterlauf, Truncation und verlorener fsync-Ack.
Synthetische Daten und Modellannahmen; keine neue Marktauswertung,
DBmigration, Abhängigkeit oder öffentliche Aktivierung.

Aktuelle Classicquelle und Quellen-/Journalrestore sind im nächsten
lokalen Zwischenstand geprüft; [Quellenbeleg](futures-paper-feed.md).
Weiter: vollständige Settlementbewertung und aktuelle Instrumentkalibrierung,
dauerhafter Feedcursor/lokaler Launcher/Archivierung, Veröffentlichung an den
eigenen Asset-Reader, Settingsadapter, Q36-Gewinnetappen, IP-088-Recovery und
laufende Cockpitabnahme.
Danach Bitget-Demo mit Orderjournal/Reconciliation. Echtgeld und aktive
AI behalten ihre separaten Freigaben.
