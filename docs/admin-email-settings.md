# Administration und E-Mail-Bestätigung

Der Nutzer verlangt einen Adminbereich für allgemeine Einstellungen und
reguläre E-Mail-Bestätigung vor seinem ersten Passkey. Die erste Funktion ist
`/admin/settings`: SMTP-Benutzername/Passwort/Absender speichern, einen Code
an die administrativ zugeordnete Adresse senden und diesen im Cockpit prüfen.
Der freigegebene Provider ist `mail.all4everyone.de`, SSL/TLS465; Empfänger
`info@investalo.de`. Andere SMTP-Hosts benötigen eine neue administrative
Freigabe, damit der Bestätigungskanal nicht durch einen beliebigen Server
ersetzt werden kann. Der Benutzer trägt das Passwort selbst im Dashboard ein.

## Zugriff und Speicherung

Ein eigenes privates Manifest weist genau einen Plattformadministrator zu:
ursprünglicher OIDC-Subject/Issuer, Tenant und Benutzer-ID. Die aktuelle
API-Identität/Epoch und aktive Owner-Mitgliedschaft werden erneut gelesen.
Tenant-Owner erhalten dadurch keine allgemeine Plattformadministration.
Änderungen erfordern eine höchstens15 Minuten alte MFA-Anmeldung, aktuellen
Sessionbezug, Same-Origin und CSRF. Der erste SMTP-Zugang benötigt noch keinen
Passkey, weil damit dessen reguläre E-Mail-Voraussetzung eingerichtet wird;
Brokerkeys behalten ihren bestehenden Passkey-Purpose.

Eigener32-Byte-Schlüssel, eigene AES-GCM-Domain/AAD mit Admin-/Tenant-/Issuer-/
Origin-/Empfängerbindung. Settings liegen verschlüsselt im privaten
`cockpit-public-data/admin-mail/settings.enc`, nie in Env/Logs/Git.
Lesesummary enthält kein Passwort; leerer Passwortwert behält das vorhandene.
Revision-CAS, ein prozessweiter Writer, private Dateirechte sowie
rename/fsync/readback verhindern konkurrierendes Überschreiben und
bestätigen die gespeicherte Änderung. Defekte Daten werden nicht als leere
Konfiguration übernommen. Dies ist eine einzelne Cockpitinstanz.

## E-Mail und Passkey

Der SMTP-Client verbindet nur eine zuvor öffentlich aufgelöste IPv4 mit
Zertifikats-/Hostnameprüfung auf465; private/Loopback/Metadata-/Reservednetze
werden abgelehnt. AUTH PLAIN/LOGIN läuft ausschließlich innerhalb von TLS,
ohne Proxy/Fallback/Retry. Begrenzte DNS-/Verbindungs-/Replygrößen und Deadlines.
[Implicit TLS für Submission](https://www.rfc-editor.org/rfc/rfc8314),
[SMTP-Framing](https://www.rfc-editor.org/rfc/rfc5321).

Ein zufälliger achtstelliger Code gilt10 Minuten, höchstens fünf Fehlversuche.
Nur sein zweck-/Empfänger-/Epoch-gebundener HMAC wird verschlüsselt gespeichert.
Mindestens60 Sekunden zwischen Sends. Durable `pending` liegt vor dem ersten
SMTP-Byte. Fehlende Bestätigung löst keine Wiederholung aus; ein tatsächlich
zugestellter Code bleibt prüfbar. Erst der richtige Code erzeugt `verified`.
Ein alter Epoch oder ein verbrauchter Code kann keine Freigabe erzeugen.

Nach erfolgreicher Prüfung verwendet der Operator:

```bash
python3 infra/scripts/issue-verified-passkey.py --issue-and-email
```

**Nur nach ausdrücklicher Freigabe zur tatsächlichen Ticketausstellung.**
Der Helper prüft aktuelle Identität/Epoch/Owner und dass noch kein Passkey
existiert, liest höchstens24 Stunden alte tatsächliche verschlüsselte
E-Mail-Evidenz, übergibt deren UUID an den bestehenden `passkey_admin` und
stellt sein600-Sekunden-Ticket aus. Ticket und Versandzustand werden
create-only privat erhalten und anschließend über denselben freigegebenen
Provider an die bestätigte Adresse übergeben. Kein Token in URL/Args/Env/
stdout/Logs/Git; unbekanntes Issue-/SMTP-Ergebnis nie automatisch wiederholen.
Das Ticket wird im vorhandenen Passkeyformular eingegeben und anschließend
mit tatsächlicher Geräte-PIN/Biometrie registriert.

Ein geplanter tatsächlicher Negativaufruf wurde von der automatischen
Freigabeprüfung abgelehnt, weil bei vorhandener Evidenz echte Tickets/Mails
entstehen könnten. Er wurde nicht ausgeführt. Die drei Issuerprüfungen
verwenden ausschließlich Mock-DB-/Container-/SMTP-Boundaries.

## Vorbereitung und Rollout

Private Adminzuordnung ist bereits create-only vorbereitet; kein SMTP-Passwort
angenommen. `setup-platform-admin.py --recipient … --smtp-host …` erzeugt
private UID10002-Dateien unter dem ignorierten `infra/local/platform-admin`.
Schalter/Overlay sind standardmäßig aus. Nach Merge und Produktionsfreigabe
die bestehende vollständige Preview/Demo-Konfiguration erhalten:

```bash
bash infra/scripts/compose.sh --env-file infra/local/paper_preview.env \
  --file infra/compose.public-preview.yaml --file infra/compose.paper-preview.yaml \
  --file infra/compose.demo-trading-runtime.yaml --file infra/compose.admin-mail.yaml \
  up -d --no-deps cockpit
```

Nur das Cockpit erhält zusätzlich SMTP-Egress. Der eigene SMTP-Schlüssel/
Adminmanifest sind readonly gemountet. Keine neuen Dependencies/Migrationen/
Finanz-/Broker-/Live-/AI-Änderungen. Die alte Authelia-Testadresse/Dateinotifier
werden damit noch nicht geändert; IdP-Wiederherstellung ist eine separate Aufgabe.

## Beleg

25 gepinnte Nodefälle, drei vollständig offline gemockte Issuerfälle grün.
Typecheck und gepinnter Cockpitbuild bestanden. Tatsächliche vorbereitete
Private Identity unter UID10002 geladen. Tatsächlicher Provider465-TLS-
Hostname/Zertifikat und220-Greeting geprüft, ohne Login oder Mail.
SMTP-TLS-AUTH/DATA in Tests mit tatsächlichem TLS und synthetischen Replies.
Keine echte E-Mail/Passkey-Ticketaufnahme oder Benutzer-/Brokerkeyänderung.
Echter SMTP-Login/Versand folgt nach Dashboardeingabe des Passworts.
