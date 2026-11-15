# Dauerhafte getrennte Demo-Verbindung

Stand 2026-11-15, IP-009/IP-015. PR78 (`054e117`) ist in `maind03a379`
enthalten; GitHub/Fetch/Ancestry bestätigt.

`demo_store.py` verbindet den [eigenen Demo-AEAD-Kern](bitget-demo-secret-provider.md)
mit tatsächlicher PostgreSQL-Berechtigung und dauerhafter Speicherung.
Es sind private Serviceprimitive, kein freigeschalteter Dashboard-Keyeingang.
Nur synthetische Keys und Konten wurden geprüft.

## Konto und Speicher

Additive014 führt `bitget_demo` als eigenen Kontomodus ein, ausschließlich für
Bitget/USDT. Normale `read_only`- und Paperkonten behalten ihre Bedeutung.
Die neue `demo_credential_connections`-Tabelle enthält den vollständigen
ursprünglichen DemoBinding-/Purpose-/Parent-/IP-/Provenienzstand und ausschließlich
den Ciphertextcontainer. Alle Metadaten stammen beim Lesen aus der DB.
Demo-UIDs sind innerhalb dieser eigenen Umgebung global eindeutig;
normale und Demo-UIDs werden nicht als dieselbe Verbindung behandelt.

FORCE RLS und Managementpolicies erlauben keine direkten Tabellenzugriffe für
Runtime-, Research- oder Credential-LOGINs. Nur feste parameterisierte
Definerfunktionen mit `search_path=pg_catalog` werden gezielt dem bestehenden
Credentialworker zugeteilt. Die tatsächliche LOGIN-/Tenant-/Userbindung stammt
aus `credential_context()`/SESSION_USER, nicht aus Request-GUCs.

`DemoStoreAuthority` ist ein vertrauenswürdiger privater Sitzungskontext.
Der Service muss ursprüngliche Auth-Zeit, aktuelle Epoch und kurze Freigabe
unabhängig authentifizieren; SQL verifiziert weder JWT noch Passkeysignaturen.
Jeder Zugriff prüft aktuelle Nutzer-/Membership-/Owner-/Traderberechtigung,
Epoch, `reauth_after`, Auth-Zeit ohne unzulässigen Zukunftssprung und eine
höchstens60 Sekunden verbleibende Freigabe. Reads/Registrierung/Rewrap verlangen
das eigene aktuelle `ready`-Demo-/USDT-Konto. Python prüft zusätzlich exakte
LOGIN-/CURRENT_USER-Identität, Rollenprivilegien und erwarteten Tenant/User.

## Mutationen und aktueller Provider

`register` verschlüsselt nach tatsächlicher DB-Kontextprüfung, prüft die
vollständige zurückgegebene Spec/Storageversion/Ciphertext vor Commit und
beginnt bei Keyrevision1/Storage1. Konto, Keyreferenz, UID und sämtliche
Purposemetadaten bleiben unveränderlich. Ein DB-Eintrag ist kein nativer
Nachweis der Demo-Keyerstellung oder verifizierter Brokerkontofreigabe.

`rewrap` authentifiziert beide bisherigen AEADs und aktualisiert nur den
DEK-Wrap unter atomarem Versions-CAS; Payload und Keyrevision bleiben erhalten.
Keyersatz/Rebinding werden hier nicht angeboten. `revoke` adressiert die
exakte eigene Connection-UUID mit Versions-CAS, benötigt keinen Keyzugriff und
bleibt bei pausiertem Konto möglich. Nutzer-/Epoch-/Zeitberechtigung gilt weiter.
Widerruf ist terminal; keine Löschung, Reaktivierung oder automatische Rotation.

Ein Trigger schreibt Register/Rewrap/Revoke ohne Secrets in ein eigenes
append-only Audit, atomar mit dem Datensatz. Auditfehler rollen die Mutation
zurück. Die finale DB-Kontext-/Zeitprüfung erfolgt vor Transaktionsabschluss.
Ein verlorener Commit-Ack liefert keinen Erfolg und keinen automatischen Retry;
der tatsächliche Datensatz muss mit aktuellem Kontext abgeglichen werden.

Der gebundene `SealedDemoReadProvider` verwendet den tatsächlichen
`read_snapshot`-Adapter vor und nach Decrypt über jeweils frische Transaktionen.
Spec, ursprüngliche Scope, Storageversion und vollständiger Ciphertext müssen
weiter passen. Pause, Widerruf, Nutzer-/Epoch-/Membershipänderung oder
veraltete erwartete Version geben keinen alten Key aus. KEKloader und
transaktionale Connectionfactory bleiben vertrauenswürdige Servicegrenzen.
Revocation kann bereits ausgegebenen Klartext nicht aus dem Speicher löschen;
die bestehenden Readtransportgates und spätere Dispatchprüfung bleiben nötig.

Versions-CAS setzt einen vertrauenswürdigen aktuellen DB-Stand voraus.
Gemeinsames Zurückrollen von DB, Ciphertext und erwarteten Versionen wird
dadurch allein nicht erkannt; Betrieb/Backup/ursprüngliche Registryanchors
bleiben separate Grenzen. Auch privilegierte SQL-Zugänge sind vertrauenswürdig.

## Abnahme und verbleibende Arbeit

014 ist nach vollständig zurückgerolltem DDL-/Read-/Epoch-/Expiry-/Profile-/
Revoke-/Auditpreflight **nur in `investalo_credentials_checks`** angewendet.
Checksum: `4158e3232a104b3f16f61ea83f0fbe387e8bbc12021efd67cb46bb9529f7b586`.
001–013 bleiben byteidentisch, die normale Entwicklungs-DB unverändert.
Gepinnte Credentialcheck-/Migrationimages gebaut.

31 neue Demo-Store-/Authority-/Providerfälle,18 bisherige Store-/PGfälle
und180 bisherige Crypto-/Bitgetfälle:229 Fälle/204 Subtests grün mit
Python3.14.10/cryptography50.0.2/pytest9.2.0. Alle31 eigenen Fälle nach finaler
expliziter UUID-Schnittstelle für den keylosen Widerruf nochmals grün.
Getestet sind echte Neustartverbindungen, zwei konkurrierende CAS-/UID-Writes,
aktuelle Berechtigungsänderung zwischen Reads, terminaler Widerruf,
Auditrollback, Ablauf nach tatsächlichem Write und verlorener Ack nach
tatsächlichem Commit. Alle Broker-/Provenienz-/Sitzungsinputs sind synthetisch.

Die [eigene dauerhafte Demo-Passkey-Zweckfreigabe](bitget-demo-passkey-purpose.md)
ist inzwischen separat vorhanden. Als Nächstes eigener Demo-Executor mit
finalem Completionvertrag und geschützte Dashboard-Eingabe mit getrennten
Demo-/späteren Liveverbindungen. Alte003/008/009-Normalprofilgrants werden
nicht für Demo umetikettiert.
Native Key-/Endpoint-/Quotaabnahme, ältere Orderscope-/Kosten-/Fundingquelle
und operativer KEK-/LOGINbetrieb bleiben erforderlich. Keine echten Keys,
Brokerrequests, API/BFF-Routen, laufenden Dienste, Frontendbuilds, Backtests
oder Public/Live/AI-Aktivierung.
