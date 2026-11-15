# Interne Demo-Passkey-API

Stand 2026-11-15, IP-009/IP-015. PR81 (`9875525`) ist in
`main7b804fd` enthalten; GitHub/Fetch/Ancestry bestätigt.

Die eigene API verbindet den vertrauenswürdigen BFF mit dem vorhandenen
[Demo-Purposeledger015](bitget-demo-passkey-purpose.md). Sie bereitet die
Freigabe vor und stellt nach ausdrücklich bestätigtem Consent eine dauerhafte
Demo-Receipt bereit. Der [private Executor016](bitget-demo-passkey-executor.md)
bleibt für die spätere tatsächliche Speicherung verantwortlich.

## Vertrag

Alle fünf POST-Routen liegen unter `/v1/bitget-demo/passkey-authorizations`:

| Route | Ergebnis |
|---|---|
| `/prepare` | Eigene Authorization-ID, eingefrorener Metadatenhash und Passkey-Challenge |
| `/claim` | Einmaliger Claim; Commit vor WebAuthn-Prüfung durch den BFF |
| `/finish` | Eigener Grant nach vertrauenswürdigem Verifikationsurteil und tatsächlichem Factor-CAS |
| `/grant` | Aktuell geprüfter, noch nicht bestätigter Grant |
| `/authorize` | Eigene dauerhafte Receipt nach ausdrücklichem Consent |

Nur `API_DEMO_PASSKEY_AUTHORIZATIONS=1` registriert diese Routefamilie.
Standardmäßig antwortet sie404 vor Authentifizierung, Parsing und DB-Zugriff;
das bisherige Normalflag aktiviert sie nicht. Origin/RP müssen exakt kanonisch
konfiguriert sein. Die normalen Service-/Composeflags bleiben unverändert.

Jeder Request benötigt die bestehende kurzlebige BFF-Assertion mit exakten
HTTP-Methoden-/Pfad-/Bodyhashbindungen. Die API prüft aktuelle ursprüngliche
OIDC-Sitzung, Tenant/User/Membership/Epoch/Reauth und persistente Requestnonce
im bestehenden eingeschränkten Runtime-LOGIN. SQL015 bindet außerdem aktuelle
Kontometadaten, ursprüngliche Proofsitzung, Factorversion und Ablauf.
Passkeyzeit ersetzt niemals die ursprüngliche OIDC-Zeit.

Demo erlaubt Register und Revoke bei Keyrevision1. Ersatz, fremde Zwecke,
Normalmetadaten und zusätzliche private Felder werden verworfen.
Der eingefrorene Snapshot enthält genau eigene Zweck-/Profil-/Environmentwerte,
Account-ID/Name/Bitget/bitget_demo/USDT/Status und optionale Connection-ID/
Revision/Storage/Status. UID, Parent, IP, Provenienz, Ciphertext und Credentials
werden nicht projiziert. Requestbodies enthalten lediglich Digest-/Proofdaten;
die API nimmt keine Broker-Keytriple an.

`authorize` liest und hält den aktuellen Grant, vergleicht Consentbindung und
ruft ausschließlich die eigene015-Authorizationfunktion in derselben
Transaktion auf. Fehlerhafte Projektion rollt Proof-/Purpose-/Auditänderungen
zurück. Erfolgreiche Ergebnisse werden erst nach bestätigtem Commit und
erneuter Ablaufprüfung veröffentlicht. Ein unbekannter Commitack liefert
statisches503 ohne automatischen Retry; bereits committed Claim/Consent
bleiben einmalig verbraucht. BFF muss vor Fortsetzung den Zustand abgleichen
oder eine neue Challenge/Freigabe verwenden.

Receiptkind ist `passkey-demo-credential-authorization/1`;
`execution_enabled=false` beschreibt diese API. Sie signiert keinen
Credential-Executortoken und führt keinen Storewrite aus.
Die bestehenden Normal-API-/Ledger-/Projektionsdomains bleiben unverändert.
Geteilt werden passive strikte Wire-/Zeit-/Konfigurationshelfer sowie die
bestehende006-Öffentlichschlüsselprojektion, keine Normalfreigaben.

## Abnahme und nächste Arbeit

52 neue gepinnte Prüfungen:27 Projektions-/Vertrags-/Default-off-Fälle und
25 tatsächliche HTTP/TestClient-/Runtime-PostgreSQL-Fälle. Dazu111 bestehende
Normalfreigabeprüfungen grün:163 unterschiedliche Fälle insgesamt.
Final alle52 neuen Fälle erneut geprüft. Python3.14.10, vorhandene
gehashte Dependencies; API-/Checkimages gebaut.

Register-/Revoke-Consent, pausierter keyloser Widerruf, committed Claim vor
Verdikt, Replay, zwei parallele Claims mit genau einem Gewinner, Normal/Demo-
Crossdomain, aktuelle Rollen-/Epoch-/Reauth-/Factor-/Metadatenänderungen und
fehlerhafte öffentliche Projektion mit tatsächlichem Rollback geprüft.
Verlorener Ack nach tatsächlich committed Claim und Consent liefert keinen
Erfolg und keinen erneuten Command. Ein Test musste eine neue Challenge für
die Freigabe nach Kontopause erzeugen; Wiederverwendung wurde korrekt gesperrt.
Fixtures verwenden synthetische Keys, strukturelle Ciphertexts und injizierte
WebAuthn-Urteile; keine physische Browser-/Authenticator-/native Brokerabnahme.

Keine neue Migration;001–016/Entwicklungs-DB unverändert. Testfixtures bleiben
in `investalo_credentials_checks`, normale Dienste nicht neu gestartet.
Als Nächstes eigener BFF-Verifikations-/Consent-/Signingflow und privater
Executortransport, danach geschützte Dashboard-Keyeinrichtung/Serverprovider
und native Demo-Key-/UID-/Parent-/IP-/Rechte-/Readabnahme.
Der [eigene private BFF-/mTLS-Vertrag](bitget-demo-bff-flow.md) ist inzwischen
separat implementiert; operative Adapter/Dashboard-/kombinierte Abnahme folgen.
Keine realen Keys/Brokerrequests, Orders, Backtests oder Public-/Live-/AI-Aktivierung.
