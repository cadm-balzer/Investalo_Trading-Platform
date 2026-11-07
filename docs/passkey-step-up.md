# Zusätzlicher Cockpit-Passkey

Stand2026-11-07. Der Nutzer hat die zusätzliche kostenlose Passkey-Bestätigung
für Kontoänderungen ausdrücklich bestätigt. Authelia bleibt der Anmeldeprovider.
Registrierung und ein aktiver HTTP-Schrittflow sind noch nicht aktiviert.
Der isolierte Assertion-Verifier ist der erste Implementierungsschritt.

## Warum ein zusätzlicher Nachweis nötig ist

Authelia4.39.28 behält bei `SetOneFactorReauthenticate` den bisherigen zweiten
Faktor. Die OIDC-Anmeldeprüfung und `auth_time` verwenden die spätere Zeit
irgendeines Faktors; `amr=mfa` kann weiterhin den alten MFA-Kontext beschreiben.
`prompt=login` erzwingt damit eine neue Anmeldung, keinen nachweislich neuen
zweiten Faktor. Auch ein vorgeschalteter Browserlogout lässt sich überspringen.
Normale Cockpitanmeldung ist keine Freigabe für Credentialänderungen.

Beginn/Callback/Grant/Bestätigung bleiben serverseitig gesperrt. Die Oberfläche
zeigt Metadaten und deaktivierte Aktionen; gültiger CSRF hebt die Sperre nicht
auf. Eine echte Keyeingabe gibt es weiterhin nicht.

## Verbindliche Integrationsgates

1. Registrierung nur nach administrativ freigegebenem Einmalticket, gebunden
   an vorhandene Identität, Tenant, aktuelle Auth-Epoch, Zweck und kurze Frist.
   Eine alte IdP-Sitzung kann keinen Faktor eigenständig einrichten.
   Normale Faktoränderung benötigt den bestehenden Passkey; administratives
   E-Mail-Recovery bleibt der bestätigte gesonderte Weg mit Sitzungssperre.
2. Dauerhafte Publickeys mit unveränderlicher Nutzerbindung und global
   eindeutiger Credential-ID je RP speichern. Opaquer zufälliger Userhandle.
   Versionierte CAS-Updates, Counter/Backupzustand, Widerruf und Audit müssen
   atomar sein. Der vorhandene Session-TTL-Store ist hierfür ungeeignet.
3. Challenge serverseitig zufällig, einmalig konsumiert, höchstens120 Sekunden;
   an Sitzung/CSRF, Identität/Epoch, Zweck, Konto/Aktion und aktuelle Versionen
   binden. Registrierung und Assertion strikt trennen.
4. Exakter konfigurierter HTTPS-Origin und RP-Hostname ohne Port;
   `userVerification=required` und serverseitig UV sowie UP verlangen.
   Cross-Origin/Top-Origin und nicht zugeordnete Credential-IDs abweisen.
   Keine frei vom Browser gewählten RP-/Key-/Nutzerwerte akzeptieren.
5. OIDC-Code/PKCE/Nonce/Loginzeit weiterhin überprüfen und Originalclaims
   erhalten. Der lokale Passkey liefert einen zusätzlichen serverinternen
   Nachweis; seine Prüfzeit wird nicht als IdP-`auth_time` ausgegeben.
6. Vor Grantpublikation aktuellen Nutzer/Epoch, Passkeystand/Widerruf,
   frozen Kontometadaten/CAS und tatsächliche Uhr nochmals prüfen. Bestätigung
   benötigt den Token genau der angezeigten Vorschau, auch bei mehreren Tabs.
   Crash oder unbekannter Commit darf keinen Replay öffnen.

Synchronisierte Passkeys können Counter0 behalten; `0→0` ist zulässig und
braucht einmalige Challenges. Nichtnull-Counterrückschritt bleibt gesperrt.
Der Verifier verwendet `@simplewebauthn/server@14.1.0` mit npm-Integritätslock
und eigener strenger Eingabegrenze. Tests erzeugen synthetische P256-Schlüssel
und echte WebAuthn-Signaturen; sie ersetzen keinen Browser-/Gerätenachweis.

## Noch offene Betriebsabnahmen

Dauerhafte Faktorverwaltung/Registrierung und Recovery, Challenge-/Grant-
Transaktionen, echte Browser-/Gerätetests und auditierter Schrittflow folgen
IP-033. Pilot-RP ist `cockpit.investalo.de`; lokales
`cockpit.local.test` ist eine andere RP und erfordert eigene Registrierung.
Kein automatischer Domainwechsel und keine öffentliche Passkeyregistrierung.
Rate-/Speicherlimits und externe Sicherung vor Pilotbetrieb nachweisen.

## Offizielle Grundlagen

- [Authelia-Sitzungszeiten](https://github.com/authelia/authelia/blob/v4.39.28/internal/session/user_session.go)
- [Authelia OIDC-Prüfung](https://github.com/authelia/authelia/blob/v4.39.28/internal/handlers/handler_oauth2_authorization_consent_core.go)
- [SimpleWebAuthn-Server](https://simplewebauthn.dev/docs/packages/server)
- [SimpleWebAuthn-Passkeys/UV](https://simplewebauthn.dev/docs/advanced/passkeys)
- [W3C Assertionprüfung](https://www.w3.org/TR/webauthn-3/#sctn-verifying-assertion)
