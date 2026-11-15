# Privater Demo-BFF-Ablauf

Stand 2026-11-15, IP-009/IP-015. PR82 (`d4081b7`) ist in
`maind1aeaa8` enthalten; GitHub/Fetch/Ancestry bestätigt.

Eigene TypeScriptverträge verbinden die
[interne Demo-API](bitget-demo-passkey-api.md) mit echter BFF-WebAuthnprüfung,
ausdrücklichem Demo-Consent, eigenem Signer und privatem Executortransport.
Die festen privaten Pythonlistener unterstützen eine eigene, standardmäßig
abgeschaltete `DemoCredentialHTTPApplication`.
Noch kein Dashboard-Keyeingang, operativer Provider oder Dienststart.

## Ablauf und Bindungen

1. Aktuelle ursprüngliche Sitzung, eigener scoped Demo-Metadatenreader und
   bestehende Passkeyregistry müssen dieselben Tenant/User/Epoch/Accountwerte
   liefern. Nur `bitget_demo`/USDT, eigenes Readprofil und Keyrevision1.
2. Unveränderte Bodybytes bleiben beim vertrauenswürdigen Caller. Nur deren
   SHA256, Ziel und neue Challenge/Consentbindung gehen an `/prepare`.
3. Der eigene API-Claim muss bestätigt committen, bevor SimpleWebAuthn die
   tatsächliche P256-Signatur/Challenge/RP/Origin/UV/Counter prüft. Danach
   `/finish` und aktueller Factorreadback mit exakt erwarteter neuer Version.
4. Separater Consent `kind=demo-credential-write, confirmed=true`, unveränderte
   Bodybytes sowie aktueller Grant/Actor/Factor/Metadatenstand sind erforderlich.
   Ausschließlich eigene `/authorize`-Receipt darf signiert werden.
5. Der Signer bindet eigenes Kind/Audience/HTTP-Ziel, Originalsession, Factor,
   Receipt-IDs, Zeit, Metadatenhash und Bodyhash. Kurze JWT-Laufzeit endet
   spätestens mit der eigenen Freigabe/Sitzung; ursprüngliche OIDC-Zeit bleibt.
6. Vor und nach asynchronen Grenzen werden Sitzung und aktuelle Bindungen
   erneut geprüft. Der private Executor bekommt genau die autorisierten Bytes.
   Öffentlicher Erfolg erfordert anschließenden aktuellen Metadatenreadback:
   ursprüngliches Konto/Factor und exakter neuer Connection-CAS-Zustand.

Eigene opaque Prozesshandles korrelieren nur diese konkrete Callerinstanz.
Sie enthalten keine Keytriple oder Signaturen und verleihen keine DB-Autorität.
Nach Claim-/Consent-/Executordispatch kann ein unbekannter Erfolg nicht erneut
über denselben Handle ausgeführt werden. Kein automatischer Transportretry.
Durable015-Consume/016-Abschluss im [Demo-Executor](bitget-demo-passkey-executor.md)
bleiben die serverseitige Autorität über Prozesse/Neustarts hinweg.

`DemoPasskeyCredentialPorts` sind ausschließlich injizierte vertrauenswürdige
Serveradapter. Aktueller eigener Metadatenreader, Sitzung, dedizierter Signingkey
und `.execute`-Anbindung werden nicht aus Browserfeldern oder Tokens gewählt.
Ein operativer eigener Metadaten-/Keyprovider fehlt weiter. Tests injizieren
synthetische APIreceipts, aktuelle Readbacks und Ausführungsantworten; sie
behaupten keinen kombinierten laufenden API/PG/BFF/Executor-End-to-End-Betrieb.

## Private TLS-Verbindung

Der eigene Nodeclient verwendet feste Demo-Register-/Revoke-Pfade, canonical
HTTPS-DNS-Origin, CA/Hostnameprüfung, Clientzertifikat, TLS mindestens1.2 und
eine eigene Agentinstanz ohne Proxy/Redirect/Retry. Unabhängiger ursprünglicher
Kontext kommt aus der vertrauenswürdigen Sitzung, niemals aus JWTclaims.
Zeitbudget umfasst DNS/TLS sowie kontinuierlich tröpfelnde Antworten;
Byte-/Header-/JSON-/Resultbounds und aktueller Sitzungsablauf bleiben verbindlich.

Die bestehenden Python-Stdlib- und gepinnten ASGI-Listener teilen ausschließlich
die Transportmechanik. Exakter serverseitiger Applicationtyp wählt eine feste
Domain; Requests können ihn nicht umschalten. Normalapp akzeptiert nur originale
Normalpfade, Demoapp nur eigene Register/Revoke; fremde Pfade/Replace antworten404.
Eigene Resultate verlangen Revision1. Eigene App und Normalapp verwenden beide
unabhängiges mTLS/Clientleafpinning, fixe DB-Actorbindung und begrenzte Kapazität.
Ein unbekannter Application-Subclass wird bereits bei Konstruktion verworfen.
Der injizierte Demo-Callback muss `DemoPasskeyOnboarding` samt eigener
Verifikation/Consume/Executionlock/Completion verwenden.

Normal-BFF-/Signer-/Metadatenverträge und001–016 bleiben byteidentisch.
Geteilt werden passive Session-/Factor-/Wire-/Zahlhelfer und überprüfte
WebAuthn-/TLSprimitive. Keine Normalfreigabe wird zur Demofreigabe umetikettiert.

## Abnahme und nächste Arbeit

186 neue Nodefälle mit tatsächlichen P256/Jose-Signaturen und injizierten
API-/Readbacks/Transportfehlern plus175 bisherige Normalfälle:361 gepinnt grün.
8 neue tatsächliche lokale mTLS-/Demo-Verifierfälle über beide Listener plus
38 bisherige Transport-/27 tatsächliche Demo-PG-Executorfälle:73 Fälle/
57 Subtests gepinnt grün. Insgesamt434 unterschiedliche Fälle, davon194 neu.
Zusätzlich111 eigene TS/Jose/Python-Interopprüfungen mit fünf Fixtures,
Whitespace/UTF8/kurzer Sitzung/maximaler Storage-CAS und Crossdomain-Rejection.
Gepinnte Node24.22.2/Python3.14.10-Läufe vollständig offline; vorhandene Locks,
Typecheck und gepinnter Cockpit-/Credentialcheckbuild grün.

Keine physische Authenticator-/native Demo-Keyabnahme oder Performancebehauptung.
Keine Migration/Dependency/normalen Dienste/öffentlichen Flags geändert.
Als Nächstes eigener scoped Metadaten-/Provideradapter und geschützter
Dashboard-Keyeingang samt isolierter kombinierter HTTPS/BFF/API/PG/Executor-
Abnahme, danach echte Demo-Key-/UID-/Parent-/IP-/Rechte-/Readabnahme.
Keine echten Keys/Brokerrequests, Orders, Backtests, Live- oder AI-Aktivierung.
