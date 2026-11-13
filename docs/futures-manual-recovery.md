# Manuelle Wiederbelebung nach Liquidation

Q46/IP-088: Ein liquidiertes Asset bleibt gesperrt, bis der Nutzer es
explizit wieder für neue Baskets freigibt. Der laufende Hebelvergleich
simuliert keine solchen manuellen Eingriffe.

## Implementierter Prüf- und Darstellungskern

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
recreated. Das API-Ziel `/v1/futures-recovery` hat **noch keinen Runtimeadapter**:
Die bestehende Runtime betreibt Spot-Paper; native Futures sind offline.
Ein bloßes Einschalten des UI-Flags aktiviert daher keinen Futureshandel.
Der Bildschirm zeigt bei fehlender Quelle „Status nicht verfügbar“.

## Abnahme und ausstehende Anbindung

Fünf gepinnte Pythonfälle/13 Subtests prüfen reale synthetische Liquidation,
fehlendes volles Neubudget, erhaltene Verluste/IDs, neue Hebelentscheidung,
frischen RSI, Zeitablauf beim Commit sowie fremde/stale/ungeklärte Anfragen.
Fünf Cockpitfälle prüfen den eigenen Statusvertrag, echte HTML-Darstellung
von Startseite/Details/gesperrtem Button und Origin-/CSRF-/Default-off-Routen.
Typecheck und Next.js-Produktionsbuild bestehen. Ein produktiver Browser-/Broker-/Commitnachweis folgt erst
mit der Futures-Runtime und deren dauerhaftem Reconciliationexecutor.

IP-088 bleibt deshalb IN_PROGRESS: aktueller Futuresstatus aus eigener
Persistenz, atomare CAS/Receipt-Writes und Readback nach unbekanntem Commit,
Reconciliation unter Parallelität und tatsächliche UI-Anbindung sind noch offen.
Keine pauschale Live-/Public-/AI-Freigabe aus Q46 ableiten.
