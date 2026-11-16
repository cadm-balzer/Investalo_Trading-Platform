# Eigene private Demo-Identität

Stand 2026-11-16, IP-009/IP-015. Der Code von PR85 (`93134bf`) ist vollständig
in `maina1d7175` enthalten, per Fetch/Ancestry und byteidentischem Dateibaum
bestätigt. GitHub meldete den PR trotzdem weiterhin offen/konfliktbehaftet;
kein erneuter Merge wurde ausgeführt.

Der [eigene Demo-Browserablauf](bitget-demo-browser-flow.md) erhält einen
expliziten Linux-Dateiprovider für separaten Signingkey und mTLS-Clientidentität.
`createDemoCredentialPrivateIdentity` erwartet eine vertrauenswürdig übergebene
Spec `investalo-demo-credential-private-identity/1`: Originalverzeichnis, UID,
Tenant/User/Account, Cockpit-/OIDC-/Executororigins und vier SHA256-Fingerprints.
Es liest keine Umgebungsvariablen, provisioniert keine Dateien und installiert
keinen globalen Provider. Operative Browserruntime bleibt fest `false`.

## Originaldateien und TLS

Feste Dateien: `signing-key` (32 binäre Bytes), `executor-ca`,
`client-certificate`, `client-private-key`. Originalverzeichnis0700,
reguläre Dateien0400, erwartete UID und genau ein Hardlink sind erforderlich.
Jede Pfadkomponente wird über gehaltene Linux-FDs und `O_NOFOLLOW` geöffnet;
`/proc/self/fd` dient ausschließlich als feste FD-Ankermechanik.
`O_NONBLOCK`, Größenbounds, ein Overflowbyte, Fstat/Lstat und abschließende
Pfad-/Metadatenchecks verhindern unbeschränkte Reads und Linkadoption.
Inode/Device und Änderungszeiten werden mit BigInt/Nanosekunden verglichen.

Initiale Originalroot-/Dateiinodes bleiben gebunden. Jeder weitere Zugriff
prüft erneut Rechte, UID, Links, Größen, Fingerprints und TLSmaterial.
Auch eine byteidentische Ersatzdatei oder ein Ersatzroot wird abgewiesen;
kein Hotreload, keine automatische Rotation oder Reparatur.
Die Spec und Ausschlussliste werden vor Await kopiert.
Die gelieferten Ausschlussfingerprints dürfen den Demokey nicht enthalten.
Dass diese Liste vollständig die tatsächlichen Normal-/API-/Session-/KEKkeys
abbildet, muss das vertrauenswürdige spätere Provisioning nachweisen.

Eine einzelne selbstsignierte CA und ein dazugehöriges gültiges Clientleaf
mit ClientAuth-EKU sind erforderlich. Signatur, private Keyzugehörigkeit,
CA-/Leafrollen und beide Gültigkeitszeiträume werden tatsächlich geprüft.
Nur unverschlüsseltes PKCS8-PEM aus der geschützten Datei wird akzeptiert.
Der vorhandene eigene Client prüft zusätzlich Server-CA/Hostname und verwendet
die feste konfigurierte DNS-Origin, ohne Redirect/Proxy/Retry.

## Ursprünglicher Kontext und Provider

`forSession` bindet originale Sitzung/Issuer/Origin/Tenant und unabhängig
gelesene aktuelle API-User-ID an die konfigurierte Identität.
Der private HTTP-Kontext stammt aus dieser Sitzung und der Spec; JWTclaims
liefern weder Endpoint noch Actor. Das unveränderte private Body wird gegen
Register/Revoke/Revision1 und das konfigurierte Accountziel geprüft.
Replacement und fremde Accountausführung scheitern vor Netzwerkdispatch.
Signingkey wird als eigene Kopie gelesen; interne Buffer werden nach Gebrauch
freigegeben/überschrieben, ohne garantierte JavaScript-Heapzeroization zu behaupten.

`createDemoCredentialPrivateProvider` liest zuerst über den bestehenden
geschützten Portadapter den aktuellen `/v1/passkeys/context`, prüft dessen
User und bindet erst dann die private Identität. Originalsessionprüfungen
vor/nach APIawaits bleiben erhalten. `createDemoPrivateCredentialServerPorts`
verbindet dies ausdrücklich mit vorhandenem `getBoundSession`/`apiRequest`.
Diese Factory ist aufrufbar, aber nicht im normalen Browserwrapper installiert.
Der Dateiprovider erteilt selbst keine durable Consent-/Store-/Orderfreigabe;
015/016 und der Python-Executor behalten diese Autorität.

## Abnahme und nächster Schritt

33 neue/914 gesamte gepinnte Cockpitfälle grün, Typecheck/Build grün.
Tatsächliche lokale Dateien prüfen Rechte, Symlink/Hardlink/Owner,
Wiederbelegung von Root/Datei, Fingerprints, falschen TLSkey/EKU, Ablauf und
fremde Sitzung. Tatsächliches Loopback-TCP/mTLS prüft feste eigene Pfade,
Originalkontext und unveränderte UTF8-/Whitespacebytes.

Zwei zusätzliche Abläufe verbinden Request/Response, tatsächliche P256-
Passkeyprüfung, Demo-BFF/Consent, private Dateien und tatsächliches mTLS mit
Jose-Signaturprüfung am synthetischen Node-Executor; Replay dispatcht nicht
erneut. DNS wird ausschließlich für `executor.fixture.invalid` auf Loopback
abgebildet. Der gepinnte Container hat kein externes Netzwerk.
Die TLS-Testkeys/CA sind ausdrücklich öffentliche synthetische Canaries
im Testcode und dürfen niemals als operative Identität installiert werden.

API/Metadaten/DB-Receipts und Executor-Abschluss sind in diesen Abläufen
synthetisch. Die kombinierte laufende HTTPS/BFF/API/PostgreSQL/Python-
Executorabnahme folgt separat, danach native Demo-Key-/UID-/Readabnahme.
Keine Migration, Dependencies, normalen Dienste, echte Keys, Brokerrequests,
Orders, Backtests, öffentliche Aktivierung, Livehandel oder KI geändert.
