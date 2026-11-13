# Futures-Paperplanung und Übergang zum Handel

Q47 priorisiert nach dem Hebelvergleich die Handelsimplementierung und eine
einstellbare Basketanzahl. 2× ist die Basis für den ersten Futures-Paperbetrieb.
Die bisherige gleiche Modellachse liefert damit das beste Nettoergebnis und
weniger Drawdown; eine allgemeine optimale Rendite oder unabhängige Validierung
ist daraus nicht bewiesen. Mehr gleichzeitige Coins teilen dasselbe Kapital
auf kleinere Baskets und können gemeinsam fallen.

## IP-089: gespeicherte Basket-Obergrenze

Die eigene USDT-Paperkontoplanung speichert eine Obergrenze von3–7;
der noch ungespeicherte Vorgabewert ist5. Owner/Trader dürfen ändern,
Viewer/Researcher nur lesen. Eigene API-, BFF- und Portfoliokomponenten
bilden einen vollständigen Speichern-/Neuladenpfad. Diese Einstellung ist
eine Planung für den folgenden Futuresdienst; sie verändert den bestehenden
Spot-Paperdienst weder wirtschaftlich noch operativ.

`API_FUTURES_PAPER_SETTINGS_PREVIEW=1` und
`COCKPIT_FUTURES_PAPER_SETTINGS_PREVIEW=1` sind getrennte Opt-ins.
Default/Public Compose aktiviert beide nicht. GET
`/v1/futures-paper-settings` liefert nur eigene geeignete Konten.
POST `/v1/futures-paper-settings/{account_id}` akzeptiert ausschließlich
`expected_revision` und `basket_limit`; BFF `/api/futures/settings`
prüft Origin/CSRF/Sitzung und bindet den Kontopfad an den exakten Request.
Browserangaben zu Cash, Hebel, Gewinnfreigaben und Liveautorität sind verboten.

Additive013 enthält FORCE-RLS-Kontoeinstellungen und ein gesondertes Audit.
Ein kontobezogener Transaktionslock serialisiert auch das erste Anlegen;
veraltete Revisionen liefern409. Einstellung und Audit committen gemeinsam,
bevor Erfolg veröffentlicht wird. Bei verlorener Antwort keine automatische
Wiederholung: Neuladen zeigt den tatsächlichen Stand. Das Audit ist für
Runtime nur einfügbar; keine Lösch-/Update-/Order-/Workerberechtigung.
SQL vertraut dem bestehenden authentifizierten API-Transaktionskontext;
direkte Runtime-SQL-Schreibrechte sind kein allgemeiner Signaturprüfer.

013 wurde vollständig zurückgerollt vorgeprüft und danach nur in
`investalo_credentials_checks` angewendet. Checksum:
`78f1c339f6ff8b5bf6827d7eae3d987b6ed6a8bd32b69dcfcc45a88a94753645`.
001–012 im Fixture und die Migrationsmenge der Entwicklungsdatenbank bleiben
unverändert. Niemals automatisch den allgemeinen Migrationlauncher ausführen.

## Kapitalempfehlung

`futures_capacity.py` liefert einen reinen technischen Kapazitätsvorschlag:
aktuelles ungebundenes Futures-Cash minus sämtliche verbleibenden regulären
Kaufbeträge, manuelle Reserve und Gebühren-/Restorationdeckung offener Baskets.
Bereits gepostete Margin wird nicht nochmals als verfügbares Cash gerechnet.
Die minimale vollständige neue Range muss der eigene Adapter aus den aktuell
zulässigen Kandidaten, Mengenrastern, Mindestnotional,2× und sämtlichen sechs
Eigenkapitalstufen samt Kosten ableiten. Er darf keine frei erfundene
Kontogrößenschwelle oder fremde/unrealisierte Gewinne einsetzen.

Der Vorschlag begrenzt sich auf die eingestellte Obergrenze, die separat
finanzierte Kapazität und die Anzahl geeigneter verschiedener Assets. Das
vollständige neue Rangebudget stammt ebenfalls aus der bestätigten
Allokations-/Gewinnetappe und bleibt fest: mehr freies Cash erhöht weder
automatisch dessen Volumen noch finanziert es kleinere Teilranges. Cash
älter als30 Sekunden, zukünftige Zeitpunkte, fehlende vollständige Ranges
oder unterdeckte Reserven erlauben keine neue Empfehlung. Bestätigte Rangebudgets
müssen bereits auf Cashpräzision vorliegen; Mindestbeträge werden aufgerundet.
Der Vorschlag verändert keinen bestehenden Basket und genehmigt keine Order;
aktuelle Marktmaxima, Signal-, Preis-, Margin- und Ausführungsregeln müssen
bei jeder tatsächlichen Order weiterhin geprüft werden.

Anfangs bleiben3–5 finanzierte Baskets. Die Obergrenze7 erteilt keine
Gewinnfreigabe: Q36 benötigt drei neue vollständig abgeglichene profitable
Abschlüsse und ein tatsächlich finanziertes vollständiges Budget je Etappe.
Erst zusätzliche Slots bis7, danach größere zukünftige Ranges.
Eine niedrigere Einstellung wartet auf normale Abschlüsse; offene
Budgets, Nachkäufe, Puffer und Verluste bleiben erhalten.

Es gibt noch keinen aktuellen eigenen Futuresruntime-Kontostand und keinen
kalibrierten Minimum-Rangeadapter. Deshalb veröffentlicht die API ausdrücklich
`recommendation=null`, `runtime_ready=false`; die UI erklärt die fehlende
Anbindung. Spot-Papercash oder historische Backtestendstände sind kein Ersatz.
Die Kapitalprüfung ist mit synthetischen eigenen Futureszuständen getestet;
eine tatsächlich kontogestützte Empfehlung bleibt IP-090.

## Nächste konkrete Schritte

1. **IP-090, eigener dauerhafter Futures-Paperbetrieb:** eigenes Kontoprofil
   und eigener Ledger ohne Umdeutung des Spotkontos; anfangs2×, H1-RSI und
   H1-Supertrend, alle fünf regulären Käufe plus manuelle sechste Reserve.
   Kandidaten von Slots trennen, Budget beim ersten Kauf einfrieren,
   Einstellungen nur für neue Baskets übernehmen. Genesis/Warmup, aktuelle
   Trade-/Markpreise und Funding, atomare Journal-/Zustandscommits,
   Restart-/Unknown-Commit-Abgleich und aktuelle Cockpitprojektion verbinden.
   Tatsächliche Coinanzahl und eigene volle Ranges vor Einstiegen prüfen.
   Kapitalempfehlung mit aktuellem Regel-/Kontobeleg veröffentlichen.
2. **IP-088 in diesen Dienst integrieren:** gebuchte Liquidationsverluste,
   sichtbare eigene Assetsperren und manuelle Wiederbelebung nach Flat-/
   Order-/Kapitalabgleich; Kandidat/Receipt gemeinsam dauerhaft speichern.
3. **Bitget-Demo-Ausführung:** Classic-Kosten-/Margin-/Preisregeln vollständig
   kalibrieren, Brokerorderidentitäten, Teilfills, Schutzorders und unklare
   Antworten auf einem eigenen Demo-/Testprofil abgleichen.
4. **Spätere Freigaben:** unabhängige Strategieabnahme, Betriebs-/Recovery-
   Nachweise und explizite Echtgeldfreigabe; kausale AI-Regimeprüfung separat.

Dieser Checkpoint startet keinen neuen historischen Marktjob, setzt keine
Brokerorder und aktiviert keinen laufenden/public Dienst. Weitere Hebeltests
stehen nicht vor der Paperimplementierung.

Abnahme:28 neue gepinnte Pythonfälle (17 Kapital-/Budgetetappenfälle und11
echte API/PostgreSQL-Fälle), zusammen56 gezielte Fälle/18 Subtests mit
bestehendem Paperstatus/Recovery. Neun Cockpitfälle (vier neue), Typecheck
und gepinnter Next.js16.4.5-Build bestehen. Geprüft sind konkurrierende Tabs,
Auditrollback, Antwortverlust nach Commit, Foreign-/Viewer-/Nicht-USDT-
Ablehnung, Origin/CSRF, Default-off, Budgetpräzision und unveränderte
Gewinnetappen. Tatsächliche Browser-/laufende Futuresabnahme folgt mit IP-090.
