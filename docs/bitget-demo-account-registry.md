# Ursprüngliche Demo-Konto-/Journalregistry

Stand 2026-11-15, IP-015/IP-016. PR75 (`1825a39`) ist in
`maina897926` enthalten; GitHub/Fetch/Ancestry bestätigt.

`futures_demo_registry.py` verbindet [Demo-Vertrag](bitget-futures-demo.md),
[Outbox](bitget-demo-outbox.md) und [Accountcheck](bitget-demo-account-check.md)
mit einem ursprünglichen privaten Kontopfad. Identitäten bleiben
vertrauenswürdige lokale Deklarationen; **kein nativer Demo-Key-/UID-Nachweis**.

## Genau ein Original

Alle späteren Executor müssen denselben ursprünglichen privaten Registryroot
verwenden. Der Registryschlüssel enthält Bitget, Umgebung, API-Familie und
Broker-UID; Tenant, Nutzer, Plattformkonto und Credentialreferenz gehören
absichtlich nicht zum Schlüssel. Andere Nutzer/Keys können innerhalb dieses
Roots kein zweites Journal für dieselbe UID registrieren.

Der unveränderliche Eintrag enthält vollständige ursprüngliche `DemoBinding`,
Outbox-UUID, absoluten Pfad und tatsächliche Device-/Inodewerte. Plattformkonto,
Outbox-UUID, Pfad und Verzeichnisinode dürfen auch unter anderer UID nicht
wiederverwendet werden. Andere Credentials erzeugen einen Bindingkonflikt:
keine automatische Rotation oder neue leere Orderhistorie.

`RegisteredDemoOutbox.create(registry_root, directory, ...)` erwartet vorhandene
eigene absolute 0700-Verzeichnisse und einen leeren Originaljournalpfad.
Bestehende nackte Outboxen werden nicht stillschweigend adoptiert.
`restore` verlangt bereits registrierte vollständige Originalbindung und
tatsächliche ursprüngliche Journalverzeichnisidentität.

## Persistenz und Writer

Alle Pfadkomponenten werden descriptorweise mit `O_NOFOLLOW` geöffnet.
Dateien müssen eigene reguläre 0600-Dateien mit einem Link sein.
Maximal 256 Konten; kein unbegrenzter Katalog.

Ein kurzer exklusiver `registry.lock` serialisiert Katalogprüfung,
Originalregistrierung und gebundenen Outboxzugriff. Zusätzlich bleibt
`account-<digest>.lock` für die gesamte Sitzung exklusiv; die ursprüngliche
Outbox behält ihren Writer-/Threadlock. Verschiedene Konten können gleichzeitig
geöffnet sein. Busy-Zugriff schreibt nichts; kein implizites Brokerretry.

UID-Lease vor Claimdatei; create-only Claim mit Schema-/Binding-/Inode-/
Inhaltsdigest, vollständigem Write/fsync/Readback **vor** Outboxgenesis.
Schreib-/fsync-/Readbackfehler lassen den bisherigen Beleg liegen.
Eine fehlgeschlagene registrierte Initialisierung wird weder gelöscht noch
auf anderem Pfad neu begonnen. Ein bestätigter Claim ohne restaurierbare
Genesis bleibt administrativ zu klären.

Vor jedem Zugriff werden Originalroot, benannte Locks, vollständiger begrenzter
Katalog, eigener Claim und Journalverzeichnis geprüft. Fehlende/beschädigte/
ausgetauschte Identitäten stoppen die Sitzung dauerhaft bis Close/Vollrestore.
Bestehender Root ohne globale Lockdatei und registrierte Outbox ohne UID-Lock
erhalten keine automatisch neue Lockdatei. Geerbte Sitzung nach `fork` verweigert
Zugriff.

Der Wrapper bietet vorbereitende Journalaktionen, Receipt/Traces und readonly
Accountcheck. Reine Eingabe-/Owner-/CAS-Konflikte verändern keinen bestätigten
Stand. Vorhandener Journaldecoder und Genesis-/Commandidentitäten bleiben
unverändert; optionaler externer Mindestreceipt wird voll geprüft.
Unknown-before-send bleibt unknown, kein Resend.

## Grenzen und nächster Schritt

Direkte `DemoOutbox` bleibt für bestehende Offlineverträge verfügbar, ohne
Brokerautorität. Ein tatsächlicher Executor muss den registrierten Zugang
und den vertrauenswürdig konfigurierten ursprünglichen gemeinsamen Root nutzen.

Zweite Registry, absichtliches Löschen oder gemeinsames Zurückrollen aller
Belege durch den vertrauenswürdigen Filesystembesitzer werden nicht global
erkannt. Digests ersetzen keine Signaturen; Root-/Backup-/Mindeststandverwaltung
benötigt Betriebsabnahme. Keine Plattformkontoeinrichtung, native Parent-/UID-/
IP-/Rechteprüfung oder Credentialfreigabe.

Als Nächstes native Demo-Provenienz und gebundener Readtransport. Ältere native
Normal-/Triggerorderabdeckung und tatsächliche Kosten-/Fundingabnahme bleiben
erforderlich. Accountcheck-Freigaben bleiben false; kein Versand oder
Budget-/Cash-/Basket-/Gewinn-/Recoveryledger.

## Prüfung

29 neue tatsächliche Filesystem-/Prozessfälle plus 92 bestehende:
**121 grün** auf Host-Python 3.14.4. Alternative Nutzer/Keys/Pfade,
Ressourcenbindung, konkurrierende UID-Claims, zwei unterschiedliche Konten,
Busy/Owner/CAS, fehlende/ausgetauschte Locks/Roots/Inodes, Symlink/Hardlink/
Rechte/FIFO, beschädigte Claims, Initialisierungs-/fsyncfehler, fremder Mindestreceipt
und gebundener readonly Accountcheck geprüft.

Echter Kindprozess endet nach dauerhaftem Unknown-Attempt mit Exit23; ein neuer
Writer restauriert Revision2/Unknown ohne Resend. Identitäten und Antworten
sind synthetisch. Keine Brokerrequests/Credentials/Services/DB/Migration/
Dependency/Backtest/Public/Live/AI-Aktivierung.


Der [getrennte Demo-Lesezugang](bitget-demo-read-transport.md) verbindet
inzwischen feste signierte GETs mit registriertem Scope/CAS und laufender
Provider-/Key-/UID-/Parent-/IPprüfung. Geschützter tatsächlicher Provider und
native Endpoint-/Provenienzabnahme bleiben offen; keine Versandfreigabe.
