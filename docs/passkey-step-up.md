# Zusätzlicher Cockpit-Passkey

Stand 2026-11-07. Der Nutzer hat die zusätzliche kostenlose Passkey-Bestätigung
für Kontoänderungen ausdrücklich bestätigt. Authelia bleibt der Anmeldeprovider.
Dauerhafte Registry und lokales Browser-Enrollment sind implementiert.
Kontoänderungen bleiben bis zur Assertion-/Grantintegration und echten
Browser-/Geräteabnahme gesperrt.

IP-036 ergänzt den internen dauerhaften
[Aktionsnachweis007](passkey-action-proofs.md): zielgebundene Challenge,
committed Einmalclaim vor Kryptoprüfung, atomarer Counter/CAS-Grant und
einmalige Bestätigung der eigenen Vorschau. Originale OIDC-Claims bleiben
erhalten. Der neue BFF-Adapter hat noch keine Browserroute;003/004 werden
dadurch nicht für Kontoänderungen freigegeben.

## Warum ein zusätzlicher Nachweis nötig ist

Authelia4.39.28 behält bei `SetOneFactorReauthenticate` den bisherigen zweiten
Faktor. Die OIDC-Anmeldeprüfung und `auth_time` verwenden die spätere Zeit
irgendeines Faktors; `amr=mfa` kann weiterhin den alten MFA-Kontext beschreiben.
`prompt=login` erzwingt damit eine neue Anmeldung, keinen nachweislich neuen
zweiten Faktor. Auch ein vorgeschalteter Browserlogout lässt sich überspringen.
Normale Cockpitanmeldung ist keine Freigabe für Credentialänderungen.

Beginn/Callback/Grant/Bestätigung von Kontoänderungen bleiben serverseitig
gesperrt. Die Oberfläche zeigt Kontometadaten und deaktivierte Aktionen;
gültiger CSRF und Passkeyregistrierung heben diese Sperre nicht auf.
Eine echte Brokerkeyeingabe gibt es weiterhin nicht.

## Implementierter lokaler Enrollmentablauf

1. Der Migrationsoperator attestiert eine tatsächlich manuell geprüfte
   E-Mail-Bestätigung und protokolliert eine opake Bestätigungs-UUID.
   Er stellt ein an Identität/Tenant/RP/aktuelle Epoch gebundenes Einmalticket
   aus. Sein zufälliges 32-Byte-Token gilt höchstens600 Sekunden; die DB
   speichert nur dessen SHA-256-Hash. Die CLI versendet keine E-Mail.
2. Der angemeldete Nutzer gibt das Ticket unter `/security/passkeys` ein.
   BFF-Start und -Abschluss verlangen aktuelle Sitzung, exakten Origin und
   CSRF. Der Ticketclaim committed in der API vor Browser-/Kryptoprüfung.
   Claim und Challenge gelten höchstens120 Sekunden. Versuche binden
   Sitzung/CSRF, Actor, Tenant, Epoch und RP und werden vor Prüfung einmalig
   konsumiert; Fehler und Crash geben kein verbrauchtes Ticket frei.
3. SimpleWebAuthn14.1.0 prüft ES256/P256, exakten HTTPS-Origin/RP-Hostname,
   Challenge, UV und UP. Registrierung verlangt `fmt=none`, residenten Key,
   opaken 32-Byte-Userhandle und Credential-ID von1 bis1023 Byte.
   Cross-Origin/Top-Origin und frei gewählte Nutzer-/RP-Werte werden abgewiesen.
4. Additive006 speichert Publickeys, Counter, Backupzustand, Version und Audit
   dauerhaft unter FORCE RLS. Ein Faktor je Tenant/Nutzer/RP und RP-weit
   eindeutige Credential-ID bleiben auch nach Widerruf reserviert.
   Runtime erhält nur begrenzte Funktionen, Research keinen Zugriff.
   Der Session-TTL-Store hält nur kurzlebige Enrollmentversuche.

`fmt=none` enthält keine Attestierungssignatur. Die gespeicherte Registrierung
ist daher ein Kandidat: Vor einer sensiblen Aktion ist eine separate frische
Assertion mit privatem Schlüsselnachweis und UV/UP zwingend.

Synchronisierte Passkeys können Counter0 behalten; `0→0` ist zulässig und
braucht einmalige Challenges. Nichtnull-Counterrückschritt bleibt gesperrt.
Die SQL-Counter-/Versions-CAS-Primitive vertraut der Kryptoprüfung ihres
Aufrufers; sie beweist keinen Challenge-Replayschutz. Bewusst kein HTTP-
CAS-Endpunkt, keine aktivierte Actionfreigabe. Der Verifier verwendet den
bestehenden npm-Integritätslock und strenge Eingabegrenzen. Synthetische
P256-Signaturen ersetzen keinen Browser-/Gerätenachweis.

## Widerruf und offene Wiederherstellung

Der Migrationsoperator kann nach manuell bestätigter E-Mail einen Passkey
mit erwarteter Speicherversion widerrufen. In derselben Transaktion werden
Audit und Version fortgeschrieben, die globale Nutzer-`auth_epoch` erhöht
und `reauth_after` gesetzt. Damit werden alle Tenant-Sitzungen dieses Nutzers
ungültig, einschließlich anderer noch laufender Enrollmentversuche.
Der terminale Eintrag bleibt erhalten. Recovery, Ersatzfaktor und erneutes
Enrollment nach Widerruf sind noch nicht implementiert (BL-025).
Unbekannte Commitausgänge administrativ abgleichen, niemals blind wiederholen.
Lokale Bedienung: [Operatoranleitung](../infra/README.md#passkey-enrollment-und-widerruf).

## Verbleibende Integrationsgates

- Die vorbereitete einmalige Assertionchallenge007 an die tatsächlichen
  Browserrouten anschließen; Registrierung strikt trennen und den vollständigen
  BFF-Enrollmentablauf sowie die physische Geräteprüfung abnehmen.
- Die bereits intern geprüften Bindungen auch in der Browserintegration erhalten:
  Vor Grantpublikation aktuellen Nutzer/Epoch, Faktor/Widerruf,
  frozen Kontometadaten/CAS und tatsächliche Uhr nochmals prüfen.
  Verifiziertes `deviceType` gegen die unveränderliche gespeicherte
  Backup-Eligibility prüfen, bevor Counter/CAS fortgeschrieben werden.
  Bestätigung benötigt den Token genau der angezeigten Vorschau, auch bei
  mehreren Tabs. Crash oder unbekannter Commit darf keinen Replay öffnen.
- Normale Faktoränderung verlangt den vorhandenen Passkey; den gesonderten
  E-Mail-bestätigten administrativen Recoveryweg einschließlich Ersatzfaktor
  und Sitzungssperre abnehmen.
- OIDC-Code/PKCE/Nonce/Loginzeit weiterhin überprüfen und Originalclaims
  erhalten. Passkeyprüfzeit niemals als IdP-`auth_time` ausgeben.

## Noch offene Betriebsabnahmen

Zielgebundene Assertion-/Granttransaktionen sind intern unter007 implementiert.
Erfolgreicher vollständiger BFF-Enrollmentablauf, echte Browser-/Gerätetests,
Browseraktivierung und Verbindung zur Credentialfreigabe folgen IP-033;
Recovery bleibt BL-025.
Pilot-RP ist `cockpit.investalo.de`; lokales
`cockpit.local.test` ist eine andere RP und erfordert eigene Registrierung.
Kein automatischer Domainwechsel und keine öffentliche Passkeyregistrierung.
Rate-/Speicherlimits und externe Sicherung vor Pilotbetrieb nachweisen.

## Offizielle Grundlagen

- [Authelia-Sitzungszeiten](https://github.com/authelia/authelia/blob/v4.39.28/internal/session/user_session.go)
- [Authelia OIDC-Prüfung](https://github.com/authelia/authelia/blob/v4.39.28/internal/handlers/handler_oauth2_authorization_consent_core.go)
- [SimpleWebAuthn-Server](https://simplewebauthn.dev/docs/packages/server)
- [SimpleWebAuthn-Passkeys/UV](https://simplewebauthn.dev/docs/advanced/passkeys)
- [W3C Registrierungsprüfung](https://www.w3.org/TR/webauthn-3/#sctn-registering-a-new-credential)
- [W3C Assertionprüfung](https://www.w3.org/TR/webauthn-3/#sctn-verifying-assertion)
