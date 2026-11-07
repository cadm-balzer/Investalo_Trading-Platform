# Zielgebundener Passkey-Aktionsnachweis

Stand 2026-11-07. IP-036 ergänzt die dauerhafte Registry006 um einen
einmaligen, an die konkrete Vorschau gebundenen Nachweis. Das ist ein
vorbereiteter interner Ablauf: Browserrouten für Kontoänderungen, echte
Brokerkeyeingabe und die003/004-Credentialausführung bleiben gesperrt.
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

IP-033 bleibt für den vollständigen BFF-Enrollmentablauf, echte
Browser-/Gerätenachweise und die konkrete Browseraktivierung offen.
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

Der vollständige Regressionslauf umfasst 724 bestandene Tests:
461 API/Worker, 143 Cockpit und 120 Credentialprüfungen.
SQL, API und BFF wurden unabhängig geprüft; keine offenen Reviewblocker.
Typecheck sowie die gepinnten API-/Migrate-/Check-/Cockpitbuilds bestanden.

Grundlagen:
[OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html),
[SimpleWebAuthn-Server](https://simplewebauthn.dev/docs/packages/server),
[PostgreSQL18 Sperren](https://www.postgresql.org/docs/18/explicit-locking.html).
