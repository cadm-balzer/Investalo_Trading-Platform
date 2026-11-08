# Privater Cockpitablauf für Credentialfreigaben

IP-041 verbindet den privaten Cockpitkern mit der dauerhaften Zweckfreigabe008
und dem [Credentialexecutor](passkey-credential-execution.md). Die neuen
API-Routen sind standardmäßig deaktiviert. Browserformulare und öffentliche
Credentialrouten werden mit diesem Checkpoint noch nicht aktiviert.

## Ablauf und Vertrauensgrenzen

Der aufrufende Server übergibt die vollständige, bereits autorisierte
`ProofSession` mit Handle, CSRF, Origin und ursprünglichen OIDC-Claims.
Der Ablauf prüft diese Bindung nach asynchronen Schritten erneut. User-ID und
aktuelle Faktor-/Accountdaten stammen aus dem authentifizierten API-Kontext.

Die Vorbereitung leitet das Ziel aus aktuellen eigenen Accountmetadaten ab.
Ein injizierter Bodybuilder erzeugt den exakten privaten Request für dieses
Ziel. Der BFF validiert dessen Form und UTF8-Bytes;008 friert ausschließlich
Bodydigest, Metadatendigest, Zweck und Origin zusammen mit007 ein.
Rohschlüssel werden weder in SQL noch in Fortsetzungsobjekten gespeichert.

Die API committed den einmaligen007-Claim vor der realen WebAuthnprüfung im BFF.
Der anschließende Grant reicht allein für eine Credentialänderung nicht aus.
Eine gesonderte Zustimmung zum Credentialzweck bestätigt über008 genau diese
Vorbereitung und diesen Grant. Die bisherige007-Funktionsbestätigung bleibt
ein eigener Ablauf und kann nicht umgewidmet werden.

Vor Signatur und Übergabe werden Receipt, eigener Grant, Faktor, Actor,
Session, Ziel/CAS, Frist und unveränderter privater Body erneut verglichen.
Der Signer erhält eine separat injizierte Identität. Der private Executor
prüft den tatsächlichen TS/Jose-Token, konsumiert008 vor Probe und schreibt
AEAD-Credentials samt009-Abschluss atomar. Kein automatischer Retry.

## Interne API

| Route | Eingabe | Ausgabe |
|---|---|---|
| `POST /v1/passkey-credential-authorizations/prepare` | Strikte007-Vorbereitung plus `body_sha256` | `authorization_id`, `metadata_sha256`, bestehender sicherer `attempt` |
| `POST /v1/passkey-credential-authorizations/authorize` | Authorization-/Grant-ID, Sessionbindung, Bestätigungshash | `status: authorized`, `execution_enabled: false`, exakter23-Feld-Receipt |

`API_PASSKEY_CREDENTIAL_AUTHORIZATIONS=1` aktiviert diese beiden internen
Routen explizit. `API_PASSKEY_ORIGIN` muss ein kanonischer HTTPS-Origin sein
und exakt zu `API_PASSKEY_RP_ID` passen. Authentifizierung, Tenant/Epoch,
ursprüngliche OIDC-Zeit und die Serversignatur bleiben zwingend. Die Routen
nehmen keine API-Schlüssel, privaten Requestbodys oder Credential-JWTs an.
`execution_enabled: false` beschreibt die fehlende Runtimeaktivierung;
der Fixtureexecutor wird ausschließlich über injizierte Testports erreicht.

API/SQL vertrauen der authentifizierten BFF-WebAuthnprüfung; SQL führt keine
Signaturprüfung durch. Direkte003-Primitive bleiben vertrauenswürdige private
Operationen und erhalten keine universelle MFA-Garantie.

## Prüfungen und verbleibende Arbeit

Der vollständige synthetische Ablauf wird in der separaten Fixture-DB mit
realer WebAuthn-/Joseprüfung und dem privaten Pythonexecutor geprüft.
299 integrierte Prüfpunkte bestanden: Register1/1, Replace2/2 und Revoke2/3,
drei echte synthetische P256-Assertions, HTTPS/API/PG-Receipts, originale OIDC-
Zeit, exakte UTF8-/Whitespacebytes, AEAD-Entschlüsselung und atomarer009-Abschluss.
Bodydrift vor Verbrauch und Replay nach Write starten keine zusätzliche Probe.
Der standardmäßig ausgeschaltete API-Pfad liefert404.

385 Cockpittests einschließlich52 neuer Orchestrierungsfälle und Typecheck
bestanden. Die vollständige API-/Workerregression umfasst572 bestandene
Tests einschließlich111 neuer Fälle (87 Unit,24 tatsächliche PG).
Gepinnte API-/API-Check-/Cockpit-/Node-/Python-Fixturebuilds und unabhängige
Reviews bestanden. Die historische356-Credentialsuite aus IP-040 wurde nicht
erneut gezählt; private Python-/SQL-Implementierung bleibt unverändert.
Ein älterer zeitabhängiger Test berechnet relative Zeitwerte
jetzt beim Testaufruf statt beim Einsammeln der Suite. API-Prüfregeln bleiben
unverändert. Der erste Lauf hatte vorübergehende Container-DNS-Ausfälle.
Nach dem vom Nutzer ausgeführten Hostneustart wurde nur die geschützte
synthetische Fixtureablage neu vorbereitet. Finale Regression und Fixturelauf
bestanden. Beide Fixture-APIs sind gestoppt; sechs öffentliche Dienste gesund,
reguläres TLS HTTPS200 bestätigt.

`investalo` bleibt001–007, `investalo_credentials_checks` bleibt001–009;
angewendete Migrationen werden nicht verändert. Die öffentliche Vorschau
erhält keine neuen Flags oder Dienste. Tatsächliche Browser-Keyeingabe,
physische Geräteabnahme, provisionierte Signaturidentität, Credentialdienst,
Brokertransport/Egress und Betrieb/Recovery bleiben IP-033 und eigene Gates.

IP-042 ergänzt darauf aufbauend einen getrennten injizierten
[Entwicklungs-HTTPS-Transport](passkey-credential-https.md) mit gegenseitigem
TLS und unabhängigem ursprünglichem Sitzungskontext. Das ist kein
Produktionslauncher und aktiviert keine Browser-Keyeingabe.

Grundlage: [OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html),
[OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
