# Zielgebundener Passkey-Aktionsnachweis

Stand 2026-11-08. IP-036 ergänzt die dauerhafte Registry006 um einen
einmaligen, an die konkrete Vorschau gebundenen Nachweis. IP-037 verbindet ihn
mit einer ausdrücklich aktivierbaren BFF-Browservorschau. Standard- und
öffentliches Composeprofil lassen diese ausgeschaltet; echte Brokerkeyeingabe
und die003/004-Credentialausführung bleiben gesperrt.
Die zusätzliche Passkeybestätigung ist vom Nutzer bereits bestätigt;
Authelia bleibt der Anmeldeprovider.

## Ablauf und Grenzen

| Schritt | Gespeicherter Nachweis |
|---|---|
| Prepare | Identität/Tenant/Epoch, ursprüngliche OIDC-Zeit, Sitzung-/CSRF-/Originbindung, konkrete Kontoaktion und vollständige sichere Metadaten, Faktorversion, zufällige Challenge und Hash der eigenen Vorschaukennung |
| Claim | Einmalige, committed Zustandsänderung vor WebAuthn-Prüfung; ein Fehler oder Crash gibt den Versuch nicht frei |
| Finish | Nach UV/UP/Signaturprüfung aktuelle Identität, Konto/CAS, Faktorversion und Uhr erneut prüfen; Counterfortschreibung und kurzlebiger Grant atomar |
| Grant lesen | Aktuellen Actor, Sitzung, Faktor, Ziel und Frist prüfen; keine freie Tenant-/Kontowahl |
| Confirm | Genau Grant-ID plus eigene Vorschaukennung prüfen; Grant einmalig verbrauchen und verifizierten Nachweis ausgeben |

Die interne API verwendet fünf POST-Routen unter
`/v1/passkey-action-proofs/`. Originale signierte OIDC-Claims bleiben bei jedem
Aufruf unverändert. `checked_at` ist eine separate, tatsächliche Passkeyprüfzeit,
kein neuer IdP-`auth_time`. Derselbe Sitzungshash bindet auch den exakten
HTTPS-Origin und die ursprüngliche Sitzungsfrist.

Die Browsergrenze bietet `/security/passkeys/verify` und POST
`/api/passkeys/actions/{start,finish,grant,confirm}` ausschließlich mit
`COCKPIT_PASSKEY_PROOF_PREVIEW=1`. Sie übergibt die unveränderliche
CSRF-autorisierte Sitzung an den Adapter und prüft aktuelle Bindungen nach
Bodylesen, Kryptoprüfung, API-Aufrufen und vor Ausgabe erneut. Der Browser
erhält sichere Projektionen; Versuch, Grant und eigener Bestätigungstoken
bleiben im lokalen Reactzustand. [HTTP-Vertrag und Abnahme](passkey-browser-proof.md).

Der BFF verwendet den vorhandenen SimpleWebAuthn14.1.0-Verifier und vergleicht
zusätzlich den verifizierten Gerätetyp mit der gespeicherten, unveränderlichen
Backup-Eligibility. Registrierungsdaten aus `fmt=none` allein liefern keinen
Besitznachweis. Synchronisierte Counter0→0 bleiben zulässig; verbrauchte und
RP-weit einmalige Challenges verhindern den Replay dieses Nachweises.

Die API akzeptiert ausschließlich einen signierten, bodygebundenen BFF-Aufruf.
Python/SQL vertrauen dessen Kryptoverdict; sie prüfen keine WebAuthn-Signatur.
Der BFF prüft die Signatur vor Finish. Eine kompromittierte vertrauenswürdige
Dienstidentität wird dadurch nicht zu einer untrusted Browseridentität.
Private Credentialtabellen/-funktionen bleiben für API/Research gesperrt.

## Persistenz und Abnahme

Additive007 erweitert001–006; angewendete Migrationsdateien bleiben unverändert.
Beide lokalen Datenbanken `investalo` und `investalo_credentials_checks`
haben001–007 angewendet. Die laufenden öffentlichen Vorschaucontainer wurden
für diesen internen Checkpoint nicht neu erstellt.
FORCE RLS, begrenzte Runtimefunktionen, unveränderliche Bindungen, monotone
Zustandsübergänge und Audit ersetzen einen Session-TTL-Store als Replayquelle.
RP-weite Challenge-Eindeutigkeit bleibt auch nach Abschluss erhalten. Pro
Actor/Tenant/RP sind höchstens acht noch gültige vorbereitete, geclaimte oder
erteilte Nachweise möglich; das ersetzt keine spätere Raten-/Retentionabnahme.
Bei unbekanntem Commit zuerst den gespeicherten Zustand abgleichen; keine
automatische Claim-/Finish-/Confirmwiederholung.

Der Nachweis bestätigt ausschließlich die vorbereitete Aktion und liefert
`execution_enabled: false`. Die Brokercredentialfreigabe004 verwendet noch
ihren bisherigen Frischevertrag; ein neuer Nachweis wird nicht automatisch
dorthin übertragen. Diese Integration benötigt eine eigene geprüfte Änderung.

Der vollständige BFF-Enrollment- und Nachweisablauf ist unter IP-037 mit
synthetischen P256-Daten über echtes isoliertes HTTPS/API/PG geprüft.
IP-033 bleibt für physische Browser-/Gerätenachweise, reale E-Mail-Attestierung,
öffentliche Aktivierung und die Verbindung zur Credentialfreigabe offen.
BL-025 betrifft terminales Recovery, BL-017 Raten-/Speicher-/Retentionbetrieb,
BL-021/022/024 echte Keyannahme, Schlüsselbetrieb und Crashabgleich.

## Prüfbelege

98 API-Vertragsfälle und70 tatsächliche PostgreSQL-Fälle prüfen den vollständigen
internen Ablauf, Claimcommit vor Antwort, originalen OIDC-Zeitwert, alle drei
Aktionen, Replay, parallele Aufrufe, gesperrte Rollen, Faktor-/Kontoänderungen,
Vorschauverwechslung und Fristablauf während einer Locksperre. Ein tatsächlicher
Registrierungsinsert mit derselben Konto-SHARE-Sperre wie003/004 wird bis zum
Registrierungsnachweis-Commit blockiert.

28 neue Cockpitfälle verwenden echte synthetische P256-Registrierungen und
Signaturen durch die BFF-Orchestrierung. Sie prüfen auch unveränderte OIDC-Claims,
Counter0-Replay, falsche Backup-Eligibility, Fehler/Crash nach Claim und
Änderungen während asynchroner Aufrufe. Synthetische Browserdaten und PG-Tests
ersetzen keine vollständige echte Browser-/Geräteabnahme.

Der vollständige IP-036-Regressionslauf umfasst 724 bestandene Tests:
461 API/Worker, 143 Cockpit und 120 Credentialprüfungen.
SQL, API und BFF wurden unabhängig geprüft; keine offenen Reviewblocker.
Typecheck sowie die gepinnten API-/Migrate-/Check-/Cockpitbuilds bestanden.

IP-037: 265 Cockpittests bestanden (143 bisherige, 64 HTTP-, 44 Enrollment-
und 14 Browserprojektionsfälle), Typecheck und gepinnter Cockpitbuild ebenfalls.
90 tatsächliche isolierte HTTPS/BFF/API/PG-Prüfpunkte mit synthetischer
P256-Registrierung/Ticketattestierung, eigenen Testsecrets und Fixture-DB
prüfen den vollständigen BFF-Ablauf. Neun Prüfungen mit ausgeschalteter Vorschau
belegen ausbleibende Faktor-/Nachweismutationen; acht Helper-Sicherheitsfälle
bestanden. Der Enrollmentablauf erhält die ursprüngliche Sitzungsfrist und
veröffentlicht Erfolg erst nach autoritativem Faktor-Readback.
SQL, API, Migrationen und Lockstände wurden nicht verändert. Die 461 API-/
Worker- und 120 Credentialregressionen aus IP-036 wurden nicht erneut ausgeführt.
Laufende öffentliche Vorschaucontainer blieben unverändert. Diese Belege
ersetzen keine physische `navigator.credentials`-/Geräte- oder reale
E-Mail-Abnahme.

Grundlagen:
[OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html),
[SimpleWebAuthn-Server](https://simplewebauthn.dev/docs/packages/server),
[PostgreSQL18 Sperren](https://www.postgresql.org/docs/18/explicit-locking.html).
