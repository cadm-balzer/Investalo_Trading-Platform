# Dauerhaftes H1-Basketjournal

Weiterführung nach PR124: [gemeinsamer Order-/Fundingabschluss](bitget-demo-order-funding-settlement.md)
ergänzt `settle_order_funding` im neuen Format `/6`.

Weiterführung nach PR123: [native Fundingbuchungen](bitget-demo-basket-funding.md)
ergänzen den vollständigen Fundingprüfzeitraum und gehashte Bill-Identitäten
im neuen Format `/5`.

Weiterführung nach PR122: [native Strategieausstiege](bitget-demo-basket-exits.md)
ergänzen `prepare_exit`/`observe_exit` und den gemeinsamen originalen
Versandversuch im neuen Format `/4`. Ältere Journale werden nicht automatisch
übernommen; das ursprüngliche technische BTC-Journal bleibt getrennt.

Stand2026-11-24. PR118/main`fa7f922` verifiziert.
Die [H1-Kaufanbindung](bitget-demo-h1-basket-entries.md) erhält ein eigenes
`BrokerEntryJournal`. H1-Kerzen, vollständige Bewertungen, Kaufvorbereitung,
Versandmarke und kumulative Brokerbeobachtungen werden aus einem flachen
Genesis vollständig und deterministisch wiederhergestellt.

## Neustart und einmaliger Versand

Vor einem injizierten Versandaufruf schreibt und synchronisiert `invoke_once`
die Orderidentität, den Digest der externen Freigabe und den Requestdigest.
Der Zustand ist damit bereits `get_only`, bevor der Sender aufgerufen wird.
Eine ACK-Antwort bucht keinen Kauf. Brokerfülle bleiben an den ursprünglichen
Order-/Positions-/Gebühren-/Margindebit-Abgleich gebunden.

| Zustand beim Neustart | Fortsetzung |
| --- | --- |
| Kein ausstehender Auftrag | Nächste reguläre H1-Entscheidung |
| Vorbereitung ohne Versandmarke | Originalvorbereitung innerhalb des ursprünglichen Zeitfensters einmal versuchen oder verwerfen |
| Versandmarke vorhanden, ACK fehlt | Ausschließlich ursprünglichen Auftrag abfragen; kein zweiter Versand |
| Teilfill oder unbestätigter terminaler Beleg | Ursprünglichen Auftrag weiter abgleichen; keine weitere Kaufplanung |
| Bestätigter terminaler Fill | Tatsächlicher Kaufstand bleibt erhalten; nächste Stufe nach RSI-/Preisregel |

Eine lokal verworfene, nachweislich unversandte Vorbereitung verbraucht keine
Kaufstufe. Ihre Command-ID bleibt jedoch belegt. Ein bereits versuchter Auftrag
kann nicht lokal verworfen oder wieder zum Versand freigegeben werden.
Vorbereitung, aktuelle Marken und Restore verlängern nicht das ursprüngliche
30s-H1-Signalfenster. Vor der Versandmarke wird die aktuelle Kapital-/Signal-
zulassung nochmals geprüft.

## Persistenz

Das eigene Journal bindet Demo-Umgebung, konkrete Profilidentität, Journal-UUID,
Genesis, jede Sequenz, vorherigen Zustand und Hashkopf. Es übernimmt die
vorhandene private Datei-IO, führt aber eigene Header, Commands und Replayregeln.
Es gibt keine Übernahme des technischen BTC-Outboxjournals, keine Paper-Fill-
Commands und keine Adoption bereits gewachsener Paper-Gewinnetappen.

Ein externer Minimumreceipt schützt den bereits bestätigten Präfix vor Verlust
oder Austausch. Restore verlangt den Parameter ausdrücklich: `None` bedeutet,
dass bislang kein Präfix bestätigt wurde. Ein vollständiger unbekannter neuer
Schreibpräfix wird gefaltet; unvollständige oder widersprüchliche Zeilen werden
abgewiesen und niemals automatisch abgeschnitten.

Private600-Datei, Eigentümer, Einzelverlinkung, exklusive Dateisperre,
Thread-Sperre, Prozess-ID, Inode und Dateigeneration werden geprüft.
Ein geerbter Writer nach `fork` kann nicht weiterarbeiten. Austausch, Änderung,
Trunkierung oder Rechteänderung am offenen Journal stoppen den Writer.
Unbestätigte Schreib-/fsync-Ergebnisse sperren auch Status-/Receiptzugriffe,
bis die Datei geschlossen und vollständig mit dem letzten bestätigten
Minimumreceipt wiederhergestellt wurde. Begrenzungen für Datei, Zeile und
Commands löschen keine alten Belege.

## Prüfung und operative Anbindung

Die neuen Fälle verwenden echte Dateien, fsync, parallele Threads und echte
Kindprozessabbrüche. Sender, Freigabedigests und Brokerbelege sind synthetisch.
Geprüft werden Restart vor/nach Versand, verlorenes ACK, Teilfill/fehlende
Gebühr, einmalige Buchung, zwei parallele Versandversuche, abgelaufene
Vorbereitung, eigener/ungeerbter Writer, beschädigter Präfix, lost ACK/kurzer
Schreibvorgang, Profil-/UUIDbindung, Kandidatenpool und ursprüngliche
Gewinnallokation.
22 neue gepinnte Pythonfälle grün. Der gemeinsame Lauf mit H1-/Kapital-/
Journal-/Paper-/Recoveryregression umfasst177 verschiedene Fälle und82
Subtests, vollständig grün in117,84s.

Das Journal stellt keine Freigabe aus und prüft keine Passkey-, OIDC- oder
Brokerzugangsdaten. Der gespeicherte Freigabedigest ist lediglich die Bindung
an einen separat verifizierten externen Vorgang. Der operative Sender muss
die originale Strategie-Zustimmung, aktuelle Konto-/Actor-/Credentialquelle,
native Identität/Profil/Kosten und den exakten Request nochmals prüfen.
Diese Ports und der operative Worker sind noch nicht installiert;
`execution_enabled=False`. Keine zusätzlichen Brokeraufrufe, kein Deployment.
Der tatsächliche technische BTC-Roundtrip bleibt bei seinem separaten
Revision8-Journal. Alle sechs bestehenden Rolloutoverlays bleiben erforderlich.

Als Nächstes folgen der native Quellen-/Orderadapter und der Strategie-Start
aus der originalen Dashboard-Sitzung, einschließlich der tatsächlichen
Margindebit-Abstimmung. Die technische20USDT-Testfreigabe wird nicht erweitert.
