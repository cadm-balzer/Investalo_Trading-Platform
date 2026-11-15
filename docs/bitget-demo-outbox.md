# Dauerhafte Classic-Demo-Outbox

Stand 2026-11-15, IP-016. PR73 (`11af70a`) ist in `maineac822e`
enthalten; GH/Fetch/Ancestry bestätigt.

`futures_demo_outbox.py` ergänzt den separaten
[Demo-Auftragsvertrag](bitget-futures-demo.md) um echte private Dateipersistenz,
exklusiven Writer, Konto-/Commandbindung, Revision-CAS und vollständigen Replay.
Der Kern enthält weiterhin **keinen HTTP-Dispatcher**, keine Credentials und
keine Finanz-/Basketbuchung. Seine Genesis enthält `execution_enabled=false`.
Die lokale Journalabnahme erlaubt keinen Demo- oder Echtgeldversand.

## Bindung und Lebenszyklus

Der Aufrufer gibt das ursprüngliche `DemoBinding`, eine eigene `outbox_id`,
den authentifizierten `OwnerContext` und ein bereits vorhandenes eigenes
absolutes Verzeichnis vor. Das Verzeichnis muss0700, die Dateien0600 und vom
gleichen Filesystemnutzer besessen sein. Descriptorweises Öffnen aller
Pfadkomponenten verweigert Symlinks; Journal-/Lockdatei bleiben an ihren
tatsächlichen Inode gebunden. Hardlinks und unzulässige Rechte werden abgewiesen.

`writer.lock` wird während der gesamten geöffneten Outbox exklusiv gehalten.
Ein zweiter kooperierender Writer derselben Outbox scheitert vor Replay/Append.
Ein lokaler RLock serialisiert Threads; jeder Command benötigt zusätzlich
die aktuelle erwartete Gesamtrevision. Stale-/Fremdscope-Eingaben schreiben nichts.
**Der Lock schützt diese Outbox**, keine beliebigen anderen Pfade oder Keys
derselben Broker-UID. Vor tatsächlicher Ausführung muss die vertrauenswürdige
Kontoregistry genau einen ursprünglichen Outboxpfad pro Brokerkonto/Umgebung
und alle Writer daran binden. Eine zweite Allocation wird nicht automatisch
gefunden oder global verhindert.

`create` erzeugt `commands.jsonl` ausschließlich neu und setzt eine private
Genese mit unveränderlicher Binding/Outbox-ID/Kapazität. Vorhandene oder nach
Fehler teilweise geschriebene Originaldateien werden nicht zurückgesetzt.
`restore` erwartet die ursprüngliche Binding/Outbox-ID; andere UID, Account,
Keyreferenz oder Umgebung werden nicht als automatische Rotation übernommen.

## Commands und durable Versandgrenze

| Operation | Persistierte Bedeutung |
|---|---|
| `prepare` | Ursprünglicher vollständiger Intent/Grid/Digest; gleiche Command-ID und Payload bleiben idempotent, geänderte Payload scheitert |
| `begin_attempt` | Prepared → Submission-unknown, **vor** einem möglichen zukünftigen HTTP-Send |
| `accept_ack` | Validierte eigene Bestätigung/optionale Order-ID, niemals Fill |
| `accept_observation` | Validierte kumulierte Ordermenge/-preis/-status/-fee und tatsächliche Quellen-/Kenntnisuhren |

Der stabile Command muss vom späteren eigenen Signal-/Ausführungsplan stammen.
Ein anderer UUID-Wert ist ein anderer Command: Semantische Signal-/Stage-
Deduplizierung und reservierte Budgets benötigen ihre gesonderte Anbindung.
Auch eine erfolgreich abgeschlossene Journalaktion ist keine Kapitalfreigabe.

Vor Append werden Command und Zustandsübergang rein validiert. Danach:
vollständiger Append, Journal-fsync, bytegenauer Readback, atomarer eigener
Receipt mit File-/Directory-fsync und Readback. Erst danach wird der neue
Receipt an den Aufrufer zurückgegeben. Hashkette und Zustandsdigest binden
Genese, lückenlose Gesamtrevision, Vorgänger und sämtliche eigenen Orderstände.
Keine Providertexte oder rohe HTTPantworten werden gespeichert; nur die zuvor
geprüfte private Projektion. Das Journal ist kein natives HTTP-Beweisarchiv.

Der spätere Dispatcher darf nur nach einem bestätigten `begin_attempt`
einmalig senden. Geht diese Bestätigung verloren, ist der neue Zustand
**unklar**, auch wenn die HTTPanfrage vermutlich noch gar nicht stattfand.
Die Outbox setzt ihn beim Replay nicht wieder auf Prepared. Erst Lookup mit
derselben `clientOid` kann ein tatsächliches Brokerergebnis feststellen;
Not-found erlaubt weiterhin keinen Blind-Resend.

## Fehler und Wiederanlauf

Jeder Fehler nach Beginn der Diskprüfung/Append-/Publikationsfolge vergiftet
den geöffneten Writer: keine weiteren Reads als aktuelle Bestätigung,
Commands oder Wiederholungen. Der Besitzer muss schließen und vollständig
restaurieren. Bekannte reine Validierungs-/CAS-/Kapazitätsfehler verändern
den bereits bestätigten Stand nicht.

`receipt.json` ist ein unabhängig gespeicherter Mindeststand. Optional kann
der Aufrufer zusätzlich einen bereits vertrauenswürdig bestätigten
`minimum_receipt` vorgeben. Beide müssen an einer tatsächlichen Stelle der
vollständig restaurierten Hashkette exakt passen; abgeschnittene, geforkte,
fremde, fehlende oder beschädigte Belege werden nicht repariert.

Ein vollständig validierbarer Suffix nach unbekanntem Append wird erhalten,
erneut gefsynct und als tatsächlicher neuer Mindestreceipt publiziert.
Das kann eine bereits gespeicherte Unknown-/Ack-/Fillaktion bestätigen,
erzeugt aber keinen erneuten Brokerauftrag. Unvollständige letzte Zeilen
bleiben als Fehlerbeleg erhalten; kein automatisches Abschneiden/Neustart
mit alter Prepared-Version.

Der Filesystembesitzer und seine ursprüngliche Kontoregistry sind vertrauens-
würdig. Hashes ersetzen keine externen Signaturen: Ein absichtliches
gemeinsames Zurückrollen von Journal **und** privatem Checkpoint kann nur ein
zusätzlich separat erhaltener Mindestreceipt aufdecken. Keine automatische
Bereinigung, Rotation oder Zusammenführung fremder Kontojournale.

## Abnahme und verbleibende Integration

22 neue echte lokale Filesystemfälle plus48 bestehende Demo-/Readfälle:
**70 grün** auf Host-Python3.14.4. Tatsächlicher Kindprozess endet nach
bestätigtem Attempt via `os._exit(23)`; neuer Writer restauriert Unknown ohne
Resend. Zusätzlich konkurrierende CAS/Writer, fsync-/Readback-/Checkpoint-
Fehler, Teilfill/Storno, Trunkierung, Fork, Rechte, Symlink/Hardlink und
unveränderte ursprüngliche Payload geprüft.

Die Outbox ist begrenzt: standardmäßig1000 Commands, maximal10000,
höchstens16MiB und16KiB pro Record. Vollreplay und komplette Disk-/Digest-
Prüfung pro Commit sind bewusst lokal und benötigen vor dauerhaftem Betrieb
eine Last-/Betriebsabnahme. Keine unbegrenzte Pollingpersistenz oder Retention.

Der folgende [Accountcheck](bitget-demo-account-check.md) ergänzt den
readonly14-Achsen-Snapshotabgleich unter derselben Outboxrevision;
er publiziert weder finanzielle Commands noch eine Versandzulassung.
Als Nächstes native Account-/ältere Normal-/Triggerorder-Abdeckung,
kalibrierte tatsächliche Demo-Kosten/Fundingquelle
und sichere Demo-Key-/UID-/Parent-/IP-/Rechteprovenienz; danach der ausdrücklich
gebundene Transport und eigene native Abnahme. Terminale Order heißt weder
vollständig geschlossener Basket noch freies Budget. Paper-Vollfills,
Kosten-/Gewinnetappen und Liquidations-Recovery werden nicht importiert.

Keine Brokerrequests, echten Schlüssel, laufenden Dienste, Datenbank/Migration,
Dependency, Frontendbuild, Backtest oder Public/Live/AI-Aktivierung.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=integrations/bitget/src \
  python3 -m unittest discover -s tests/bitget -v
```
