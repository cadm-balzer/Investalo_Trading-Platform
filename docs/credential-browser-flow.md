# Isolierter Browserablauf für Credentialänderungen

IP-045 verbindet die Eingabekomponente mit der vorhandenen privaten
[Credential-Orchestrierung](passkey-credential-cockpit.md) und dem
[ASGI-Dienst](credential-asgi-transport.md). Der Ablauf wird ausschließlich mit
synthetischen Schlüsseln und Brokerantworten geprüft. Die drei Next-Routen und
`/security/credentials/connect` bleiben wegen des noch nicht provisionierten
BFF-Schlüssel-/mTLS-Providers gesperrt. Ein Umgebungsflag allein kann sie nicht
aktivieren; öffentliche Dienste werden nicht neu erstellt.

## Drei getrennte Schritte

| POST `/api/credentials/passkey/…` | Eingabe | Sichere Antwort |
|---|---|---|
| `start` | Konto, Aktion; Triple nur für Register/Austausch | Opaquer Flowtoken, WebAuthn-Optionen und Konto-/Zielvorschau |
| `finish` | Flowtoken und Assertion | Neuer Flowtoken und geprüfte Konto-/Zielvorschau mit Frist |
| `execute` | Neuer Flowtoken, exakter Body und ausdrücklicher `credential-write`-Consent | Connection-ID, Revision, Speicherstand und Status |

Der BFF leitet Connection-ID und erwartete Revisionen aus aktuellen Metadaten
ab. Er erzeugt den privaten Body beim Start mit einem gemeinsamen
browserfähigen Serializer; nur sein SHA256-Digest geht an008. Die Antwort
enthält weder Triple noch Body. Die Seite erzeugt aus ihren eigenen Eingaben
und dem zurückgegebenen Ziel dieselben Bytes und hält sie ausschließlich im
privaten Controllerfeld bis zur ausdrücklichen Ausführung.

Revoke nimmt kein Triple an. Kontoänderung und Passkeyprüfung haben getrennte
Schaltflächen; die Zustimmung ist zunächst nicht ausgewählt.007-Proofconfirm
wird nicht als Credentialzustimmung verwendet. Der bestehende008-/003-/009-
Executor bleibt für Freigabeverbrauch, Probe, AEAD-Mutation und Audit zuständig.
Ursprüngliche OIDC-Zeit und Claims bleiben unverändert.

## Fortsetzungen und HTTP-Grenze

Die bestehenden WeakMaps benötigen die ursprünglichen Coreobjekte und
denselben Ports-Objektbezug. Ein eigener begrenzter Prozessspeicher hält diese
Referenzen und die sichere Sitzungskorrelation; er serialisiert sie nicht in
den Enrollment-/Sessionstore. Keine Bodybytes, Triples, Signaturschlüssel oder
JWTs gehören in die Fortsetzungsdatensätze. Vertrauenswürdige Providercallbacks
dürfen keine Requestcredentials einschließen.

Kapazität wird vor dem ersten Prepare-Await reserviert. Die lokalen Prüfvorgaben
sind32 globale und zwei gleichzeitig belegte Slots pro Sitzungsbindung;
das sind keine abgenommenen Betriebsquoten. Laufende Prepare-/Finish-/Execute-
Promises halten ihren Slot auch nach Fristablauf. Matching-Owner-Handles
werden vor dem ersten weiteren Await synchron konsumiert, fremde Sitzungen
können sie nicht verbrennen. Finish rotiert den Token und verlängert die
ursprüngliche maximal120-Sekunden-Frist nicht. Neustart verliert lokale
Fortsetzungen und lehnt sie ab; dauerhafter007/008-Verbrauch bleibt erhalten.

Jede Phase prüft POST, HTTPS-Origin, Fetch Metadata, CSRF und die ursprüngliche
Sitzung einschließlich Handle/Issuer/Subject/Tenant/Epoch/OIDC-Zeit/Frist.
Origin wird vor der abschließenden Sitzungsabfrage gelesen; ein langsames
Config-Await darf keine inzwischen rotierte Identität weiterreichen.
Die letzte Assertion liegt synchron im aufrufenden Handler unmittelbar vor
Dispatch beziehungsweise Antwort; ein asynchroner Asserthelper würde eine
zusätzliche Microtaskgrenze mit veraltetem Snapshot einführen.
Requests sind auf16KiB und zehn Sekunden beim Bodylesen begrenzt. UTF8 wird
mit `fatal:true` gelesen; defekte Bytes werden nicht stillschweigend ersetzt.
Geschlossene Schemas, doppelte JSON-Felder und nicht erwartete Ergebnisfelder
werden abgewiesen. Antworten verwenden `no-store` und statische Fehler.

## Speicher und unbekannte Ergebnisse

Das Clientformular besitzt keinen nativen Submitweg, der vor der Hydration
Eingaben als GET-Query verschicken könnte. Passwortfelder sind unkontrollierte
DOM-Felder mit ausgeschaltetem Autocomplete; Rohdaten erscheinen nicht in
React-Präsentationszustand, Props, URL, Storage oder Logs.
Nach Prepare werden die DOM-Werte gelöscht. Abbruch, Ablauf, Propswechsel,
Unmount und Pagehide verwerfen Controllerreferenzen; ein Generationzähler
verhindert die Wiederbelebung durch verspätete Antworten. BFCache-Rückkehr
lädt den aktuellen Status neu.

Execute ist ein einmaliger Versuch. Ein abgebrochener Fetch beendet keinen
Datenbankcommit. Fehlende Bestätigung führt deshalb zu „Ergebnis nicht
bestätigt. Lade den Kontostand neu.“ und niemals zu einer automatischen
Wiederholung oder zur Behauptung eines Rollbacks. JS-Strings können nicht
garantiert aus physischem Speicher genullt werden; der Nachweis betrifft
Referenzlebensdauer und fehlende Anwendungspersistenz.

## Prüfstand und offene Abnahmen

Der neue Prüflauf ist
`python3 tests/infra/check_passkey_credential_cockpit.py --orchestrate --service --browser`.
Er ergänzt einen internen Node-HTTPS-Listener mit synthetischem ServerAuth-
Zertifikat. Der tatsächliche Controller sendet POSTs über HTTPS an die
injizierte HTTP-Grenze, anschließend laufen SimpleWebAuthn/Jose, API, PostgreSQL
und der separate mTLS-/AEAD-/009-Dienst. Nur administrative Setup-/Audit-
Container besitzen Migrationscredentials; der Dienst bleibt separat gebunden.
Keine Hostports, neue Abhängigkeiten oder Migrationen.

Die Fixture benutzt einen injizierten Resolver für genau ihren synthetischen
Cookiehandle. Sie beweist weder tatsächliches Next-Routing/Sessionstore noch
Browser-SameSite-Verhalten oder physischen Passkeybesitz. Native Browser-
/Geräteabnahme, provisionierte BFF-/Dienstidentitäten, externer Schlüsselbetrieb,
Quota/Reconciliation/Recovery und echte Broker-/Egressprüfung bleiben offen.
Die Fortsetzungen benötigen einen Prozess oder eine gesondert abgenommene
Workerzuordnung vor Betriebsfreigabe.

## Abnahme dieses Checkpoints

540 Cockpittests bestanden, davon100 neue:19 Fortsetzungs-/echte P256-Fälle,
38 Body-/Controller-/Projektionsfälle und43 HTTP-Fälle. Typecheck sowie
gepinntes Cockpit- und Node-Fixtureimage bestanden. Der neue tatsächliche
Controller-/HTTPS-/Dienstablauf erfüllt481 Prüfpunkte mit synthetischen Keys,
P256-Assertions und Brokerantworten.

`python3 tests/infra/check_credential_browser_disabled.py` erfüllt zusätzlich
sechs tatsächliche Next-Routenprüfungen im gebauten Image: drei POST503 und
drei GET405 ohne Konfiguration, Secrets, Hostmounts, Netzwerk oder Hostports.
Ein Previewflag erschafft keine BFF-Providerautorität. Der Container wird
über seinen einmaligen Namen auch nach unklarer Startbestätigung beendet.
Diese Negativprüfung belegt keine aktivierten Next-Sitzungen.

Die unveränderten Python-/SQL-Kerne wurden nicht erneut als vollständige
419-Credential-/572-API-Suites ausgeführt. Keine Abhängigkeit, Lockdatei oder
Migration geändert; aktuelle Ledgerprüfsummen bestätigen Entwicklung001–007
und Fixture001–009. Unabhängiger Review ohne verbleibenden Blocker.
Der bestehende Dienstablauf wurde mit460 Prüfpunkten erneut bestanden;
überlappende Läufe werden nicht addiert. Alle eigenen Testcontainer beendet.
Die sechs öffentlichen Dienste bleiben unverändert und gesund; Cockpit und
Auth antworten mit regulärer TLS-Prüfung HTTP200.

Offizielle Grundlagen:
[OWASP Transaktionsfreigabe](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html),
[MDN fatal UTF8](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/fatal).
