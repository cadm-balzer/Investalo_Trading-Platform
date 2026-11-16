# Eigene Demo-Metadaten und Cockpit-Serveradapter

Nachfolgender Stand: [eigener geschützter Demo-Browserablauf](bitget-demo-browser-flow.md)
mit Formular und getrennten Next-Routen ergänzt. Operativer Provider fest aus;
private Identitätsverdrahtung und kombinierte laufende Abnahme bleiben offen.

Stand 2026-11-15, IP-009/IP-015. PR83 (`c8bb4a2`) ist in
`maincad4e2d` enthalten; GitHub/Fetch/Ancestry bestätigt.

Der [private Demo-BFF](bitget-demo-bff-flow.md) erhält einen eigenen tatsächlichen
Metadatenzugriff und einen Serveradapter für aktuelle Sitzung und API-Anfragen.
Der Adapter verbindet vorhandenes `getBoundSession`/`apiRequest` mit den eigenen
Demo-Verträgen. Signingidentität und privater Executor werden weiterhin explizit
vom vertrauenswürdigen Serversetup injiziert. Kein Browser-Keyeingang aktiviert.

## Metadatenzugriff

`API_DEMO_CREDENTIAL_METADATA=1` registriert ausschließlich
`GET /v1/bitget-demo/credential-actions/{account_id}`.
Standardmäßig aus; das vorhandene Proof-/Consentflag aktiviert diesen Zugriff
nicht. Normale Compose-/öffentliche Services behalten ihre bisherigen Flags.

Additive017 stellt `platform.demo_credential_action_context(uuid,bigint,bigint)`
bereit. Eigener Security-Definer mit festem `pg_catalog`-Searchpath, ausschließlich
für den tatsächlichen restriktiven `investalo_runtime`-LOGIN. Bestehendes
`passkey_actor` prüft ursprünglichen OIDC-Actor, aktive Owner-/Tradermitgliedschaft,
aktuelle Auth-Epoch und `reauth_after` unter Sperren. Runtime-GUCs stammen weiterhin
aus der vertrauenswürdigen signierten API-Authentifizierung.

Nur eigenes Bitget-Demo-/USDT-Konto und explizite Verbindungsmetadaten werden
selektiert; Broker-UID, Parent, IP, Provenienz und Envelope werden nicht gelesen.
Die interne User-ID dient ausschließlich dem Eigentumscheck. Ein Tenantpeer
bekommt eine verweigerte Antwort statt einer vermeintlich freien Registrierung.
Pausierte/getrennte Konten und widerrufene Verbindungen bleiben sichtbar.
Der Reader erteilt keine Passkey-/Credential-/Orderfreigabe und erstellt keinen
Purpose, Grant, Consent oder Storeeintrag. Die gemeinsame API-Requestnonce wird
wie bisher transaktional verbraucht.

APIprojektion validiert die exakte eigene015-Metadatenform samt angefragter
Account-ID. Fehlende017 liefert503 ohne privaten Tabellenfallback. Aktuelle
Authentifizierung ist vor und nach dem bestätigten Commit erforderlich.
Fehler bleiben statisch; bestehende No-store-/Nosniff-Header gelten.

## Gebundener Serveradapter

`createDemoPasskeyCredentialServerPorts` verbindet tatsächliche Serversitzung,
APIconfig und requestgebundene BFF-Assertions mit dem eigenen Portadapter.
Ursprüngliche Sitzung und Callbacks werden vor asynchronen Grenzen eingefroren.
Handle/CSRF/Origin/Issuer/Subject/Tenant/Epoch/OIDC-Zeit/Expiry müssen gleich
bleiben. Die ursprüngliche OIDC-Zeit wird durch Reads oder Passkeyprüfung
nicht erneuert.

Metadaten gehen nur an den eigenen GET; Registrykontext bleibt der bestehende
`/v1/passkeys/context`. POSTs erlauben nur die fünf eigenen Demo-Proof-/Consent-
Pfade. Strikte eigene Metadaten-/Factorparser prüfen Readbacks; zusätzliche
private Felder, fremde Konten und Normalmetadaten werden abgewiesen.
Key-/Executoranbindung bleibt eine separate vertrauenswürdige Servergrenze;
keine Umgebungsvariable oder Browserangabe erzeugt diese Identität.
Keybytes werden nach ihrem Read kopiert, Sitzung auch nach privatem Dispatch
erneut geprüft. Kein Retry oder automatische Erfolgsannahme bei unbekanntem
Abschluss. Durable015/016 behalten ihre Autorität.

## Lokale Abnahme und Grenzen

017 wurde nach vollständig zurückgerolltem DDL-/Actor-/ACL-/Owner-/Searchpath-
Preflight ausschließlich in `investalo_credentials_checks` angewendet.
001–016 und das Entwicklungsmigrationsset bleiben unverändert.
`infra/scripts/prepare-demo-metadata-checks.py` prüft dies einschließlich
byteidentischer017 bei weiteren Aufrufen. Keine operative DB-Migration.

19 neue Nodefälle plus186 bestehende Demo-BFF-Fälle:205 gepinnt grün.
18 neue APIverträge und17 tatsächliche restriktive HTTP/API/PG-Fälle plus108
bisherige Demo-API-/Normalmetadatenfälle:143 unterschiedliche gepinnte Fälle
über Ausgangs- und gezielten Abschlusslauf, final36 betroffene Fälle grün.
Insgesamt348 unterschiedliche Fälle,54 neu; Typecheck und gepinnte API-/
Check-/Migration-/Cockpitbuilds grün.

Neue Testfixtures verwenden den eigenen Router für Endpointinspektion, weil
FastAPI inkludierte Router nicht als flache App-Routenliste exponiert.
Ein bisheriger Replaytest erzeugte `checked_at` vor dem späteren Claim; der
simulierte erfolgreiche Verifikationszeitpunkt wird nun nach dessen ACK erfasst.
DB-Uhr-/Claimchecks werden nicht gelockert.

Tatsächliche DB-/HTTPreads und Node-Portadapter sind getrennt geprüft.
Strukturelle synthetische Credentialfixtures beweisen keine AEAD-/native
Demo-Keygültigkeit oder kombinierte HTTPS/BFF/API/PG/Executor-Abnahme.
Als Nächstes geschützter eigener Dashboard-Keyeingang und explizite private
Identitäts-/Executorverdrahtung in isolierter kombinierter lokaler Abnahme,
danach native Demo-Key-/UID-/Parent-/IP-/Rechte-/Readkalibrierung.
Keine neuen Dependencies, normalen Dienste, echten Keys/Brokerrequests,
Orders, Backtests, Public/Live/AI-Aktivierung.
