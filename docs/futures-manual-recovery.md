# Manuelle Wiederbelebung nach Liquidation

Q46/IP-088: Ein liquidiertes Asset bleibt gesperrt, bis der Nutzer es
explizit wieder für neue Baskets freigibt. Der laufende Hebelvergleich
simuliert keine solchen manuellen Eingriffe.

## Eigener dauerhafter Paperadapter (2026-11-15)

`futures_paper_recovery.py` verbindet Q46 mit dem eigenen bestätigten
Futures-Paperjournal. Tatsächlich vollständig gebuchte Modellliquidationen
liefern Zeitpunkt, Zyklus, feste2×, Nettoverlust einschließlich Kosten/Funding
und ursprünglichen Settlementdigest. Die kompakte Historie wird beim vollständigen
Genesisreplay rekonstruiert; bestehende Finanzzustände/Receipts werden nicht verändert.
Unbekannte Appends liefern keine bestätigte neue Historie.

Die manuelle Aktion bindet eigenes Konto, authentifizierten delegierten Actor,
Zyklus, Journalrevision, vollständigen Statedigest, einmalige UUID und echte
boolesche Zustimmung. Vor Commit werden Flatposition, gebuchte Liquidation,
echte Quote-/Markuhren von höchstens30 Sekunden, aktuelle geschlossene H1
und weitere Kontohalts geprüft. Dies ist der eigene vollständige
Paper-Fill-/Journalabgleich, kein realer Bitget-Positions-/Auftragsabgleich.

Das gesamte neueste zukünftige Basketbudget benötigt tatsächliches Cash.
Kandidaten sind keine finanzierten Plätze: Reserviert werden echte finanzierte
Ranges sowie sämtliche übrigen regulären/manuellen/Kosten-/Restorationansprüche
offener und liquidierter Baskets. Aufgeschobene Volumenerhöhungen bleiben
reserviert. Das Zielasset übernimmt die neueste Budgetepoche; dessen
verbrauchtes Kostenbudget beginnt für den nächsten Basket bei null.
Alte Gebühren/Verluste bleiben im Ledgernetto und Originaljournal.
Cash, Tages-/Startbasen, alte Käufe/Hebelentscheidungen und andere Baskets
erhalten keine Gutschrift und werden nicht zurückgesetzt.

Der additive `manual_recovery`-Journalbefehl wird unter CAS und exklusiver
Schreibsperre fsync-bestätigt. Nur der Zielstop wird entfernt; dessen nächster
Zyklus benötigt zwei neue geschlossene RSI-Bestätigungen und bleibt bei2×.
Keine Order wird gesendet. Quote-/Quellenuhr und Archivcursor bleiben erhalten,
nur die äußere Kenntniszeit steigt. Quellenfortsetzung und vollständiger
Restore bleiben möglich. Forschungsjournaldecoder und folgender alter Prüfkern
bleiben unverändert.

## Historischer Forschungs-Prüfkern

`packages/trading/src/investalo_trading/futures_capital_recovery.py`
prüft aktuellen eigenen Tenant/Konto/Zyklus, Revision und vollständigen
Statedigest, einmalige Eventidentität und ausdrückliche manuelle Zustimmung.
Der vertrauenswürdige Serveradapter muss die Nutzerberechtigung prüfen
und Positions-/Auftragsevidenz selbst beschaffen; Browserangaben dürfen
diese Evidenz nicht ersetzen. Die maximal30 Sekunden alte Reconciliation
muss Flatposition, vollständigen Orderabgleich, keine offenen/ungeklärten
Aufträge und abgeschlossene Liquidationsbuchung bestätigen.

Ein neues vollständiges eigenes Basketbudget einschließlich Kostenreserve
muss tatsächlich gedeckt sein. Andere offene, leere eligible und
liquidierte Slots behalten ihre eigenen Kapital-/Kostenansprüche;
Liquidationsverlust und offene Marginrestoration werden nicht ausgeblendet.
Es gibt keinen Recovery-Cashzufluss, keine Budgetverkleinerung und keine
Umwidmung fremder Nachkäufe. Andere Kontohalts/Liquidationspflichten sperren
die Freigabe weiter.

`recover_candidate(..., at=...)` prüft die Bedingungen erneut zum aktuellen
Aktionszeitpunkt. Der neue Zustand entfernt ausschließlich die Sperre des
angegebenen Assets und fügt eine nachvollziehbare manuelle Identität/Auditkette
hinzu. Ledger, realisierte Verluste, alte Käufe und Hebelentscheidungen bleiben
exakt erhalten. `recover_signal_candidate` setzt nur den betroffenen Zyklus
auf den nächsten Basket und löscht alte RSI-Bestätigungszähler sowie alte
Schutz-/Exitautorität. Die Indikatorhistorie und andere Assets bleiben erhalten.
Vor dem nächsten Einstieg sind zwei frisch geschlossene RSI-Bestätigungen und
eine neue ganze Baskethebelentscheidung nötig. Die Freigabe sendet keine Order.

Der Kern liefert bewusst einen **reinen Kandidaten mit Receipt**. Der spätere
Runtimeadapter muss Zustand und Receipt atomar/dauerhaft bestätigen, bevor
er die Freigabe veröffentlicht. Unbekannte Commits dürfen nicht automatisch
wiederholt werden. Die alten Forschungsjournaldecoder bleiben unverändert;
sie sind kein persistenter Recoveryexecutor.

## Cockpit

`FuturesRecoveryPanel` wird auf der Startseite vor den übrigen Panels als
Blockerhinweis und im Portfolio mit einzelnen Assetkarten vorbereitet.
Die Details zeigen Konto, Zyklus, Hebel, Liquidationszeitpunkt, Nettoverlust,
verfügbares/benötigtes Kapital und konkrete verbleibende Sperrgründe.
„Wiederbeleben“ erfordert eine ausdrückliche Checkbox und eine bestätigte
serverseitige Zulassung. Ungeklärte Antworten melden keine erfolgreiche
Freigabe; es gibt keinen automatischen Retry.

Eigener `futures-recovery-status/1`-Vertrag lässt ausschließlich aktuellen
eigenen Paperstatus zu; historische Forschungsergebnisse, fremde Tenants,
Liveantworten und widersprüchliche Zulassungen werden verworfen.
Die BFF-Route prüft Origin, aktuelle Anmeldung, CSRF, begrenzten JSON-Body
und ausschließlich eigene Ziel-/Revision-/Digest-/Consentfelder; keine
Actor- oder Reconciliationbehauptungen vom Browser.

`COCKPIT_FUTURES_RECOVERY_PREVIEW=1` ist ein separates Opt-in.
Default/öffentlicher Compose bleiben aus; keine laufenden Container wurden
recreated. Die vorhandenen Komponenten/BFF lesen jetzt über das normale
authentifizierte `GET /v1/futures-recovery`; `POST` führt ausschließlich
die eigene manuelle Paperaktion aus. Bei fehlender Quelle erscheint weiterhin
„Status nicht verfügbar“.

## Publikation und begrenzter Executor

`FUTURES_PAPER_RECOVERY_ENABLED=1` ergänzt optional die gemeinsame
`isolated-usdt-futures-paper-status/3`-Publikation: Assets, optionale Beratung
und Recovery teilen denselben Journalreceipt. Alte /1-/2-Dateien und Defaults
bleiben lesbar. Republish derselben Revision erneuert keine Frische und
wandelt keine alte Datei um; nach Opt-in ist ein echter neuer Workercommit nötig.

Der gebundene Launcher registriert mit `--recovery-root` einmalig die
ursprüngliche private Allocation/Digest und den eigenen Journalpfad:
0700-Root/create-only0600-Datei, kein Umbiegen alter Einträge.
`API_FUTURES_RECOVERY_PREVIEW=1`, `API_FUTURES_RECOVERY_ROOT` und
`API_FUTURES_PAPER_STATUS_ROOT` verbinden den normalen APIexecutor.
Alle Flags bleiben default-off; keine neuen Abhängigkeiten, Migrationen
oder automatisch gemounteten Verzeichnisse. API und Launcher benötigen
denselben ausdrücklich bereitgestellten Filesystemowner.

Der Server prüft aktuelle eigene Runtime-LOGIN/RLS-Rolle, Auth-Epoche,
ready-Konto und tatsächliche013-Einstellung nochmals vor Append.
Andere delegierte Actors oder noch nicht journalbestätigte Settings
dürfen keine Recovery auslösen. Fehlende Registrierung, abgelaufene Quotes,
Viewer/Paused und ausstehende Settings bleiben sichtbare Blocker.

Der begrenzte Executor stellt das gesamte Journal mit publiziertem
Mindestreceipt wieder her und übernimmt nur einen freien exklusiven Writer.
Ein aktiver Feedlauf wird nicht unterbrochen:503/unbestätigt, kein Retry.
Konkurrierende Klicks bestätigen höchstens eine Freigabe. Unbekannte fsync-/
Statusacknowledgements melden ebenfalls503; erst vollständiger Journalreadback
und Publikationsreparatur durch den eigenen Launcher, niemals blind wiederholen
oder neu allokieren. Die Kapazitätsberatung bleibt nach der manuellen Aktion
bis zum nächsten kalibrierten Feedcommit unbekannt.

## Abnahme und ausstehende Anbindung

Fünf gepinnte Pythonfälle/13 Subtests prüfen reale synthetische Liquidation,
fehlendes volles Neubudget, erhaltene Verluste/IDs, neue Hebelentscheidung,
frischen RSI, Zeitablauf beim Commit sowie fremde/stale/ungeklärte Anfragen.
Fünf Cockpitfälle prüfen den eigenen Statusvertrag, echte HTML-Darstellung
von Startseite/Details/gesperrtem Button und Origin-/CSRF-/Default-off-Routen.
Diese ursprüngliche Kernabnahme ersetzt weder die tatsächliche native
HTTPS/Cockpitabnahme noch den Demo-Positions-/Orderabgleich.

Der eigene Adapter ergänzt synthetische tatsächliche Paperliquidation,
Budgetknappheit/neue größere Budgetepoche, Quellenfortsetzung/Vollrestore,
CAS und unbekannten Commit sowie normale signierte APIabrufe gegen die
vorhandene eingeschränkte PostgreSQL-Fixture. Diese Abläufe sind kein
neuer Backtest oder Performancebeleg.

Sieben neue Domain-/neun tatsächliche PG/API-Fälle:172 gepinnte Regressionen
mit96 Subtests grün, final34 Recovery-/Asset-/Settingsfälle erneut grün.
575 Cockpitfälle einschließlich realer HTML-/BFF-Vertragsprüfung sowie
Typecheck und gepinnte API-/Cockpitbuilds bestanden; die Recoverymodule
laden auch aus dem gebauten normalen APIimage ohne Quellcode-Testmount.

IP-088 bleibt IN_PROGRESS bis zur lokalen nativen HTTPS/Cockpitabnahme und
koordinierten dauerhaften Writerübergabe/Commandqueue. Der eigene Executor
ist dauerhaft, arbeitet jedoch zwischen begrenzten exklusiven Feedläufen.
Echter Bitget-Demo-Positions-/Orderabgleich folgt getrennt.
Keine pauschale Live-/Public-/AI-Freigabe aus Q46 ableiten.
