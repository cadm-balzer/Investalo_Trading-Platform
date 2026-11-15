# Privater Demo-Passkey-Executor

Stand 2026-11-15, IP-009/IP-015. PR80 (`a3dfce7`) ist in `main5b7ce1e`
enthalten; GitHub/Fetch/Ancestry bestätigt.

`DemoPasskeyOnboarding` verbindet die [eigene Zweckfreigabe](bitget-demo-passkey-purpose.md)
mit dem [verschlüsselten Demo-Store](bitget-demo-credential-store.md).
Registrierung und keyloser Widerruf erhalten einen eigenen atomaren Abschluss.
Es gibt noch keinen HTTP-/Dashboard-Keyeingang oder operativen Launcher.
Keys, WebAuthn-Urteile und Provisioningadapter der Abnahme sind synthetisch.

## Reihenfolge und vertrauenswürdiger Adapter

Der private Verifier prüft Signatur, ursprüngliche Sitzung, eigene Demo-Domains
und exakte Bodybytes. Einmaliger015-Consume muss vor Provisioning, KEKzugriff
oder Write committen. Unbekannter Consume-Ack liefert kein Handle und löst
weder Provisioning noch Write aus.

Für Registrierung erhält ein injizierter Serveradapter die geprüfte Triple,
den eigenen Actor/Account/Connection und die kurze signierte Ablaufzeit.
Er muss Demo-Keyherkunft, UID/Parent/IP/Rechte unabhängig prüfen und liefert
eine vollständige ursprüngliche `DemoSecretSpec`. Der Executor prüft exakten
Typ, Actor/Account/Connection, Revision1 und feste kanonische Server-Egress-IP.
UID/Parent/Provenienz stammen ausschließlich aus diesem vertrauenswürdigen
Adapter, nicht aus zusätzlichen Requestfeldern. Dieser Callback ist **kein
hier implementierter nativer Provenienznachweis**. Native Abnahme bleibt offen.

Die kurze014-Storeberechtigung stammt aus ursprünglicher OIDC-Zeit/Epoch und
dem Ablauf der signierten Assertion. Die Passkeyzeit ersetzt keine OIDC-Zeit.
Nur Registrierung lädt den Server-KEKring. Widerruf benötigt weder alte Triple
noch KEK oder Provisioning und bleibt mit frischem Consent bei pausiertem
Konto möglich. Keyrevision1, eigenes Demo-Readprofil und ursprüngliche
Kontobindung bleiben erhalten; kein Keyersatz/Rebinding oder Orderauftrag.

## Atomarer Abschluss

Additive016 ergänzt eine eigene append-only Completiontabelle und feste
Definerfunktionen. Original003/008/009/014/015 bleiben byteidentisch.
FORCE RLS und feste `search_path=pg_catalog` gelten; Runtime/Research und
Credentialworker erhalten keine direkten Tabellen-/Helperzugriffe.
Nur der gebundene Credential-LOGIN bekommt eigenen Executionlock und Finish.

Executionlock prüft aktuelle015-Berechtigung, Sitzung, Factorversion, Metadaten,
CAS und Zeit unter Locks. Ein vorhandener failed-/completed-Abschluss sperrt
diesen Executor. In derselben finalen Transaktion erfolgen:

1. Eigener Executionlock auf der separat konsumierten Receipt.
2. Tatsächlicher014-AEADwrite oder Versions-CAS-Widerruf samt Storeaudit.
3. Eigener016-Post-Write-Abgleich und Completionaudit.

Der Post-Write-Abgleich erlaubt nur die erwartete Änderung der Zielverbindung:
Register Revision1/Storage1/active; Revoke ursprüngliche Revision1,
Storage+1/revoked. Übrige eingefrorene Metadaten sowie aktuelle Actor-/Factor-
und Zeitbindung bleiben exakt. Der Abschluss verlangt dieselbe finale
Transaktions-ID wie der Lock. Ablauf oder Fehler nach Write/Audit rollen
den ganzen Abschluss zurück, während der frühere Consume erhalten bleibt.
Der unveränderte015-Clientlock erwartet alte Metadaten und wird dafür
ausdrücklich nicht als Writerfactory verwendet.

Nach Rollback wird best effort ein `failed`-Fehlerabschluss geschrieben.
Er erteilt keine neue Freigabe; bei entzogener aktueller Rolle kann auch dieses
Audit fehlen. Ein unbekannter finaler Commit liefert keinen Erfolg und keinen
automatischen Commandretry. Ein tatsächlich bestätigter oder unbekannt
erfolgreicher Abschluss wird durch die Fehlerbehandlung nicht überschrieben.
Aktueller Datensatz/Receipt/Abschluss müssen danach abgeglichen werden.

014/015 bleiben vertrauenswürdige private Primitive;016 behauptet keine
universelle MFA-Sperre für sämtliche direkten Credentialworker-Funktionsaufrufe.
Privilegierter DB-Betrieb/Backup, originale Signing-/Sitzungsclaims,
Connectionfactory, KEKs und Provisioningadapter bleiben Servicegrenzen.

## Abnahme und nächste Arbeit

016 nach vollständig zurückgerolltem DDL-/Claims-/ACL-/Owner-/Searchpathpreflight
nur in `investalo_credentials_checks` angewendet.
Checksum: `8ad398d502a6e3aa4960904259370ebbcecfe0677044984e2e9b7c14814b0e21`.
001–015 und normale Entwicklungs-DB unverändert; gepinnte Check-/Migrationimages
ohne neue Dependencies gebaut.

27 neue tatsächliche PostgreSQL-/Crypto-/Executorfälle plus130 bestehende
Demo-Purpose-/Store-/Normal-Executor-/Normal-Completionfälle:157 unterschiedliche
Fälle gepinnt grün (Python3.14.10/cryptography50.0.2/pytest9.2.0).
Final alle27 eigenen und35 Demo-Purposefälle erneut grün.
Abgedeckt sind frische Storeverbindung/Decrypt, atomarer Register-/Revokeabschluss,
Scope-/IPmismatch, aktuelle Berechtigungs-/Metadatenänderungen, KEKausfall,
konkurrierender Consume, tatsächlicher Write mit anschließendem Ablauf/Fehler,
Widerrufsrollback, Failed-Tombstone und verlorener Ack nach echtem Consume-/
Finalcommit. Öffentliche Ergebnisse enthalten nur Connection-ID/Revision/
Storage/Status. Der015-Metadatentest prüft nun konkrete ursprüngliche
Funktionen und bezieht die neue FK-Childtabelle im Truncatenegativcheck ein.

Als Nächstes geschützter eigener BFF-/Dashboard-Eingang und Serverprovider,
dann tatsächliche Demo-Key-/UID-/Parent-/IP-/Rechteabnahme und Readacceptance.
Keine realen Keys/Brokerrequests, normalen Serviceänderungen, Orders, öffentlichen
Routen, Backtest-, Live- oder AI-Aktivierung.
