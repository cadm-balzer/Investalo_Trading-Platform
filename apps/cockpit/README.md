# Cockpit

Lokales Next.js-Cockpit mit deutscher, responsiver Übersicht, Portfolio,
Tradingjournal, Backtestaufträgen und Sitzungsübersicht. Konten, Positionen,
Journal und Aufträge kommen aus der geschützten API. Fehlende Daten bleiben
leer; fehlende Equity bleibt unbekannt. Keine erfundenen Kurven, Brokerfeeds
oder Leistungsnachweise. Echtgeld bleibt gesperrt.

## Reproduzierbar prüfen

Node 24.22.2 im gepinnten Composeimage; Host-Node 24/26 wird ebenfalls unterstützt.
`npm ci`, `npm run typecheck`, `npm test`, `npm run build`.
Der Build nutzt einen Worker und Webpack; `infra/docker/cockpit.Dockerfile` erwartet den
digestgepinnnten Buildparameter `NODE_IMAGE` aus `infra/images.env`.
Standalone-Runtime: `node server.js`, Port 3000, UID/GID 10002 plus Gruppe 10010.
Builds auf dem 2-GB-Host mit anderen Builds/Research serialisieren.

Exakte direkte Pins und vollständiger npm-Lockstand sind committed:
Next 16.4.5, React/DOM 19.3.1, jose 6.2.15 und TypeScript 5.9.3.
TypeScript 5.9.3 vermeidet vorerst die neue native Compiler-API von TS7.
Keine CI-/Pipelineabhängigkeit eingeführt.

## Anmeldung und API-Vertrauen

Authelia Confidential Client `investalo-cockpit`: Authorization Code,
`require_pkce: true`, S256, `authorization_policy: two_factor`,
`token_endpoint_auth_method: client_secret_basic`. Exakter Callback:
`https://cockpit.local.test:8443/api/auth/callback`.
Scopes: `openid profile email`; kein Offlinezugriff/Refresh.
Der Claimsparameter verlangt `amr` und `auth_time`; Login `prompt=login`.
Die signierte `auth_time` muss mindestens der serverseitig gespeicherten
Startzeit dieses browsergebundenen Loginvorgangs entsprechen. Beide Zeiten
werden in ganzen Sekunden verglichen; frühere Authentifizierungen werden
ohne Toleranz abgewiesen. Die lokale IdP-/BFF-Installation teilt dieselbe
Hostuhr; die vorhandene Toleranz von fünf Sekunden gilt nur für Zukunftszeiten.
Der Vorgang verfällt nach fünf Minuten.
RS256-Signatur, Issuer, Audience/Authorized Party, Nonce, Tokenalter und
RFC8176-MFA-Claim werden geprüft. Unbekannte Identitäten werden durch die API
abgewiesen; keine automatische Nutzer-/Tenantprovisionierung.

Kompatibilität: OIDC Core 3.1.2.1 definiert `prompt=login` als gleichwertig
zu `max_age=0`. Authelia 4.39.28 bewertet `max_age=0` im gespeicherten
Consentformular auch nach der Anmeldung weiterhin als zwingenden Login.
`prompt=login` und die zusätzliche signierte Zeitprüfung erhalten die
frische Anmeldung und vermeiden diese Schleife.
Quellen: [OIDC Core](https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest),
[Authelia 4.39.28 Loginprüfung](https://raw.githubusercontent.com/authelia/authelia/v4.39.28/internal/oidc/util.go).

`.env.example` dokumentiert Konfigurationsnamen, ohne Geheimnisse.
Secrets kommen ausschließlich aus Dateimounts. TLSprüfung bleibt aktiv;
die lokale CA wird über `NODE_EXTRA_CA_CERTS` vertraut.
OIDC-Endpoints müssen unter dem konfigurierten HTTPS-Issuer liegen.

Browser bekommen eine zufällige `__Host-`-Sitzungskennung mit Secure,
HttpOnly und SameSite=Lax. Zustände/Sitzungen liegen AES-256-GCM-verschlüsselt
im exklusiven persistenten `COCKPIT_STATE_DIR`; Loginstate wird atomar und
einmalig verbraucht, signiert und an eine zweite Browserkennung gebunden.
Keine IdP-/Broker-Tokens im Browser oder im Sitzungsstore. Sitzungsdauer
endet spätestens mit dem IDtoken beziehungsweise nach 30 Minuten.
Mutationen brauchen exakten Origin, CSRF und begrenzten Body.

BFF → API verwendet TLS und 30 Sekunden gültige HS256-JWTs:
`iss=investalo-bff`, `aud=investalo-api`, `sub`, `oidc_iss`, `oidc_auth_time`,
`iat`, `exp`, `jti`, `htm`, `htu` inklusive Query sowie `body_sha256`.
`GET /v1/me` löst das Mitgliedschaftsbootstrap; nachfolgende Aufrufe enthalten
autorisierte `tenant_id`/`auth_epoch`. API prüft Mitgliedschaft und Widerruf
erneut; Browserheader/-rollen bestimmen keinen Tenant. Die erste autorisierte
Mitgliedschaft wird verwendet; eine Tenantwechseloberfläche folgt separat.

Private Antworten sind `no-store`. Scripts erhalten eine zufällige CSP-Nonce,
keine externen Fonts/Tracker/Assets. Proxyaccesslogs dürfen Authcallbackquery
mit Code/State nicht speichern. Logout widerruft lokal die Cockpitsitzung;
Authelia unterstützt keinen RP-Logout. Administrative Recovery muss API-
Authentifizierungsgeneration und alte Sessions separat widerrufen.

## Kontometadaten und zusätzlicher Passkey

`/security/credentials` zeigt administrativ zugeordnete Bitget-Lesekonten und
vorgesehene Aktionen. Die Antwort wird gegen Tenant, Account und aktuelle
Auth-Epoch geprüft; fremde Nutzerverbindungen bleiben unsichtbar. Keine
Schlüsseleingabe. Beginn und Bestätigung sind sowohl im Server als auch in der
Oberfläche gesperrt; die beiden POST-Routen liefern auch mit gültiger Sitzung
und CSRF503. Ohne CSRF oder angezeigte Bestätigungskennung erfolgt Ablehnung.

Authelia4.39.28 erhält bei Passwort-Reauth den alten zweiten Faktor.
`auth_time` ist die letzte Zeit irgendeines Faktors; `amr=mfa` beweist deshalb
keine neue Faktorverwendung. Dies ist durch offizielle Quellen und den echten
lokalen HTTPS-Test bestätigt. Der normale Login bleibt zulässig, sensitive
Actionfreigaben dürfen sich nicht allein darauf stützen.

Der Nutzer hat eine zusätzliche Cockpit-Passkey-Bestätigung bestätigt.
Der Verifier nutzt `@simplewebauthn/server==14.1.0` mit UV/UP,
festem RP/HTTPS-Origin, serverseitiger Challenge und gespeichertem Publickey.
Die Assertion-HTTP-Vorschau ist implementiert; echte Browser-/Gerätetests bleiben offen.
`/security/passkeys` bietet lokale Erstregistrierung mit administrativem
Einmalticket. Die beiden BFF-Routen `/api/passkeys/enrollment/start` und
`/api/passkeys/enrollment/finish` verlangen Sitzung/Origin/CSRF, begrenzte
duplicatefreie Bodies und eine einmalig konsumierte gebundene Challenge.
Registrierung prüft ES256/UV/UP mit `fmt=none`; eine frische Assertion bleibt
vor jeder sensitiven Freigabe Pflicht. Publickeys und Counter/CAS/Audit liegen
dauerhaft in PostgreSQL006, nur Enrollmentversuche im Session-TTL-Store.
Der vollständige Enrollmentablauf läuft über getrennte, prüfbare Ports. Er
erhält die ursprüngliche Sitzungsfrist und liest nach dem Schreiben den
autoritativen Faktor erneut, bevor er Erfolg veröffentlicht.
Administrativer Widerruf sperrt den Faktor und alle Nutzer-Tenant-Sitzungen;
Recovery/erneutes Enrollment sind noch nicht verfügbar.
Lokale Passkeyzeiten ersetzen keine IdP-Claims.
Details und Aktivierungsgates: [Passkeys](../../docs/passkey-step-up.md).

Der neue interne Adapter `passkey-action-proof-server.ts` verwendet die
getrennte Orchestrierung `passkey-action-proof.ts`: Prepare, committed Claim
vor echter WebAuthn-Prüfung, Finish mit dauerhaftem CAS/Grant, Lesen und
Vorschau-Bestätigung. Sitzung/CSRF/Origin, Actor/Epoch, sichere Kontometadaten und
Faktorversion werden nach asynchronen Schritten erneut geprüft.
Backup-Eligibility muss zum verifizierten Gerätetyp passen. Alle API-Aufrufe
behalten die ursprünglichen OIDC-Claims; `checked_at` bleibt getrennt.
IP-037 verbindet den Adapter mit `/security/passkeys/verify` und den POST-Routen
`/api/passkeys/actions/{start,finish,grant,confirm}`. Nur
`COCKPIT_PASSKEY_PROOF_PREVIEW=1` schaltet diese Nachweisvorschau frei;
Standard- und öffentliches Composeprofil lassen sie ausgeschaltet. Die
HTTP-Grenze übergibt die unveränderliche CSRF-autorisierte Sitzung an den Adapter
und prüft sie nach Bodylesen, Kryptoprüfung, API-Aufrufen und vor Antwort erneut.
Der Browser erhält nur geprüfte Projektionen; Versuchs-/Grantzustand und
Vorschaukennung bleiben im lokalen Reactzustand.
Bestehende Credentialrouten bleiben503; der Nachweis liefert ausdrücklich
`execution_enabled:false`. Keine Keyeingabe oder003/004-Ausführung.
[Vertrag und Abnahme](../../docs/passkey-action-proofs.md).
[Browservorschau und Prüfbelege](../../docs/passkey-browser-proof.md).

IP-037: 265 Cockpittests bestanden (143 bisherige, 64 HTTP-, 44 Enrollment-
und 14 Browserprojektionsfälle), ebenso Typecheck und gepinnter Cockpitbuild.
90 isolierte tatsächliche HTTPS/BFF/API/PG-Prüfpunkte verwenden synthetische
P256-Daten, Ticketattestierung, eigene Testsecrets und Fixture-DB; neun Prüfungen
mit ausgeschalteter Vorschau belegen ausbleibende Faktor-/Nachweismutationen.
Physische `navigator.credentials`-/Geräteprüfung, echte E-Mail-Attestierung,
öffentliche Aktivierung und Credentialintegration bleiben offen. Laufende
öffentliche Vorschaucontainer wurden nicht verändert.

Vorbereitete Actionzustände frieren Ziel und Versionen serverseitig ein, binden
Handle/CSRF/Issuer/Sub/Tenant/Epoch, prüfen aktuelle Metadaten erneut und
verbrauchen Callback/Grant einmalig. Eine eigene opaque Bestätigungskennung
bindet die Vorschau gegen Tabverwechslungen. Diese Primitive und der getrennte
Credential-Assertion-Signer sind keine aktivierte MFA-/Credentialroute.

IP-038 ergänzt `passkey-credential-token.ts` als isolierten Signaturvertrag mit
Audience `investalo-credentials-passkey` und Kind
`passkey-credential-authorization/1`. Er bindet eine gesonderte zweckgebundene
Freigabe an ursprüngliche OIDC-Sitzung, frische Passkeyzeit, Ziel/CAS, unveränderte
Bodybytes und Metadatendigest. Die bestehende007-Bestätigung kann keinen solchen
Token erzeugen. Dauerhafter Aussteller/Einmalverbrauch und Credentialroute fehlen;
alter Signer und004 bleiben unverändert.
IP-038: 333 Cockpittests bestanden (265 aus IP-037 plus 68 neue), ebenso Typecheck;
109 tatsächliche Offline-Interopprüfungen verbinden TS/Jose mit Python.
Gepinnter Cockpitbuild bestanden. Die 99 isolierten HTTPS-Prüfpunkte aus
IP-037 wurden nicht erneut ausgeführt; öffentliche Vorschau bleibt unverändert
und das Nachweisflag aus.
[Vertrag und Integrationsgates](../../docs/passkey-credential-assertions.md).

## Forschungsaufträge und Ergebnisse

`/backtests` liest ausschließlich authentifizierte Dataset-Metadaten und
übersichtsgebundene Aufträge. Eine ausdrücklich gewählte Dataset-ID wird
mit CSRF und Idempotenzschlüssel über den BFF angefordert; die API friert
Snapshot, Strategie, Konfiguration und Kosten beim Enqueue ein.
Ohne verfügbaren Snapshot entsteht kein scheinbar laufender Auftrag.
Die bekannten API-Statuswerte werden für die Anzeige normalisiert.
Migrierte Altaufträge ohne eingefrorenen Snapshot bleiben als fehlgeschlagen
sichtbar; sie erzeugen weder Ergebnisse noch einen scheinbaren API-Ausfall.
Synthetische Daten benötigen eine zusätzliche bewusste Bestätigung und
bleiben als Funktionstest gekennzeichnet; auch synthetische CSVs sind zulässig.
Echte CSV-/Bitget-Daten dürfen mit Testzweck importiert werden. CSV-Herkunft ist unverifiziert.
Bitgetdaten stammen vom öffentlichen History-Candles-Endpunkt; unvollständige
Zeitabdeckung wird angezeigt.
Ergebnisse zeigen angefordertes und tatsächliches Zeitfenster sowie fehlende
H4-Kerzen am Anfang/Ende. Ohne dokumentiertes angefordertes Fenster bleibt
Vollständigkeit ungeprüft. „Vollständig“ bezieht sich nur auf dieses Fenster;
ein 90-Tage-Probelauf ist kein Drei-Jahres- oder Holdout-Nachweis.

`/backtests/[id]` zeigt den echten Workerstatus und bei bestätigtem Erfolg
Netto-PnL, Drawdown, Profitfaktor, geschlossene Baskets und die tatsächliche
simulierte Equity. Profitfaktor `null` bedeutet „nicht bestimmbar“, niemals
unendliche Profitabilität. Jeder Lauf bleibt ausdrücklich „nicht validiert“:
unabhängiger Holdout, Kostenkalibrierung und Mindeststichprobe stehen aus.
Die manuelle Reserve bleibt Cash; künstliche oder rückwirkend gewählte Fills
werden nicht als automatische Leistung behauptet.

Die Darstellung veröffentlicht nur geprüfte Felder: erwarteter Tenant und
Job-ID, versioniertes Schema, BTC/ETH H4, Decimalstrings mit maximal 64 Zeichen
und endlichen Betragsgrenzen, bekannte Quellen/Kosten sowie geordnete Equity.
API-Antworten werden vor JSON-Parsing auf 2 MiB begrenzt; höchstens 2.000
Kurvenpunkte werden gerendert. Die vollständige Zeitreihe liefert die Kennzahlen;
bei ausgedünnter Anzeige erscheint ein Hinweis. Gleiche Zeitpunkte bleiben
erhalten, weil Candle-Close und nächster Open nacheinander verarbeitet werden.
SVG-Koordinaten werden ausschließlich aus endlichen, begrenzten Zahlen erzeugt.
Snapshot-, Simulationsdaten-, Konfigurations- und Kostendigest plus frozen
Kostenannahmen machen die verwendeten Versionen nachvollziehbar.
Beliebige Ergebnisfehler, private Payloadfelder und Sourcequerys gelangen
nicht zur Oberfläche. Sicherheitstests prüfen Tenant-/ID-Isolation, Zahlen,
Kurvenlimits, Provenienz und Größenbegrenzung.

## Aktuelle Grenze

Ergebnisanzeige benötigt einen durch den Worker erfolgreich verarbeiteten,
eingefrorenen Forschungsdatensatz. Ein Erfolg ist keine Handelsfreigabe.
Der manuelle Reservekauf,
Brokercredentialeinrichtung, AI und Feeds sind hier noch nicht aktiviert.
Paper-/Demo-Ausführung, MFA-Recovery und öffentlicher Pilot brauchen ihre
weiteren Abnahmen; die Oberfläche läuft als ausdrücklich freigegebene
[öffentliche Entwicklungsvorschau](../../docs/https-entry.md).

## Verifizierte Herstellerquellen (2026-11-07)

- [Next Installation und Mindest-Nodeversion](https://nextjs.org/docs/app/getting-started/installation)
- [Next npm-Metadaten](https://registry.npmjs.org/next/16.4.5)
- [Node 24 LTS und Support bis April 2028](https://nodejs.org/en/blog/migrations/v22-to-v24)
- [Authelia Clientpolicy und PKCE](https://www.authelia.com/configuration/identity-providers/openid-connect/clients/)
- [Authelia IDtokenclaims](https://www.authelia.com/integration/openid-connect/openid-connect-1.0-claims/)
- [Authelia MFA-Referenzwerte](https://www.authelia.com/reference/guides/authentication-method-references/)
