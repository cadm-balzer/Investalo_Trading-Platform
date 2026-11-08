# Dauerhafte zweckgebundene Passkey-Credentialfreigabe

Stand 2026-11-08. IP-039 ergänzt additive008 und einen privaten Pythonclient.
Der Merge von8bb64db in Main13ba2e2 ist verifiziert. Keine HTTProute, öffentliche
Aktivierung, Brokerprobe oder003/004-Credentialmutation ist angeschlossen.
Der vorhandene007-Prüfablauf bleibt `execution_enabled:false`.

## Zweck vor Nachweis, ausdrückliche Zustimmung

`passkey_credential_prepare` bereitet007 und den eigenen Zweckdatensatz atomar
vor. Origin und SHA256 der exakten Anfragebytes stehen bereits vor der
Passkeyprüfung fest. Der Metadatendigest stammt ausschließlich aus PostgreSQL:
SHA256 der UTF8-Bytes von `metadata::text`. Signer/Client tragen ihn unverändert
weiter; sie berechnen ihn nicht aus einer anderen JSON-Darstellung neu.

`passkey_credential_authorize` verlangt den noch nicht bestätigten007-Grant,
die ursprünglichen Actor-/Sitzungs-/OIDC-/Originbindungen und den eigenen
Bestätigungshash. Sie bestätigt007 und erstellt den23-Felder-Zweckreceipt in
derselben Transaktion. IDs müssen verschieden, Zeiten monoton und noch gültig
sein. Eine vorherige007-Funktionsbestätigung ist anschließend ungeeignet;
ein gewöhnlicher007-Nachweis erhält keinen Zweckdatensatz durch Nachrüstung.

| Zustand | Bedeutung |
|---|---|
| `prepared` | Zweck, Bodydigest, Origin und eingefrorene Vorschau stehen vor der Assertion fest |
| `authorized` | Ausdrücklicher Credentialconsent mit aktuellem Passkeynachweis ist bestätigt |
| `consumed` | Authentifizierte konkrete Anfrage ist global einmalig angenommen und committed |
| `locked` | Dieselbe Anfrage besitzt die separate Transaktion für einen späteren finalen Write |

## Verbrauch und erneute Prüfung

`credential_consume_passkey_authorization` akzeptiert ausschließlich den
exakten30-Felder-Vertrag aus dem [IP-038-Verifier](passkey-credential-assertions.md).
Das dedizierte LOGIN ist durch `SESSION_USER` an einen aktiven Tenant/Nutzer
gebunden. Aktueller Actor/Epoch/`reauth_after`, ursprüngliche OIDC-Zeit,
Passkeystatus/-version, sichere Metadaten, Ziel/CAS, Origin/RP, Bodydigest und
Fristen müssen zum gespeicherten Receipt passen. JTI und Freigabe werden dauerhaft
verbraucht; eine neue JTI für denselben Nachweis öffnet keinen weiteren Versuch.

`credential_lock_passkey_authorization` verlangt einen bereits committed
Verbrauch aus einer anderen Transaktion, dasselbe LOGIN und dieselben gesamten
Claims. Sie prüft die aktuellen Bindungen erneut. Locks folgen
Actor → RP-Slot → Konto/Verbindung → Proof → Faktor → Zweckdatensatz;
die Uhr wird auch nach Wartezeiten und Audit erneut geprüft. Registrierung
sperrt das bestehende Konto, weil eine fehlende Verbindungszeile keine
Insert-Lücke schließen kann.

Ein erfolgreicher Lockcommit ist terminal. Innerhalb derselben finalen
Transaktion darf erneut geprüft werden. Rollback der finalen Transaktion
behält den bereits committed Verbrauch; der Client startet keinen automatischen
Wiederholungsversuch. Bei unbekanntem Commit ist ein Abgleich erforderlich.
Ein späterer Writer muss Lock, Credentialmutation und Abschlussaudit in genau
dieser Transaktion verbinden.

## Vertrauensgrenzen

SQL prüft keine JWT-/WebAuthn-Signatur. Der BFF bleibt für die tatsächliche
WebAuthnprüfung verantwortlich, der private Python-Verifier für HS256,
ursprünglichen Sitzungskontext und exakte Anfragebytes. JSONB bewahrt weder
doppelte JWT-Felder noch alle numerischen Wireformen; diese werden vor dem
SQLaufruf abgewiesen. Direkte003/004-Funktionen bleiben vertrauenswürdige
Primitive mit eigenem Vertrag;008 ist kein allgemeiner MFA-Zwang für alle
möglichen Datenbankwriter.

`PasskeyAuthorizationClient.consume` verifiziert vor jedem DB-Zugriff.
Er gibt seinen privaten, clientgebundenen Handle erst nach bestätigtem Commit
zurück. `lock` eröffnet die separate Transaktion. Gespeichert werden Claims,
Hashes und opake IDs; weder JWT noch Klartextbody/Keys liegen im Handle oder
Zweckdatensatz. Statische Fehler und private immutable Objekte verhindern
versehentliche Serialisierung. Der Client ruft keinen Executor oder Broker auf.

Neue Tabellen haben FORCE RLS, private Helper, enge Funktionsgrants und
unveränderliche Bindungen/Audit. Terminale Tombstones bleiben erhalten;
Retention/Quotas folgen BL-017. Bestehende001–007 bleiben unverändert.
Migration008 ist ausschließlich in `investalo_credentials_checks` angewendet;
die laufende Entwicklungsvorschau verwendet weiterhin001–007.

IP-040 verbindet diese private Grenze mit dem003-Writer und atomarem009-Abschluss:
[private Ausführung](passkey-credential-execution.md). Die008-Clientprimitive
selbst bleibt ohne Broker oder Writer.

Physische Geräteabnahme, echte E-Mail-Attestierung, geschützte Keyeingabe,
eigene Betriebsschlüssel, Broker/Egress/Quota, Recovery und endgültige
Browser-/Betriebsintegration bleiben IP-033/BL-020/021/022/024/025.

## Prüfung

271 Credentialtests bestanden:19 Client-,95 Offline-Onboarding- und157 echte
PostgreSQL-Fälle, davon97 neue008-Fälle. Dazu gehören92 Lifecycle-/Scopefälle
und fünf vollständige Receipt→Signatur→Verifier→Clientabläufe mit synthetischen
Schlüsseln. Alle drei Aktionen, konkurrierender Verbrauch, Widerruf, Ablauf
nach Sperrwartezeit und Rollback der finalen Transaktion sind geprüft.

461 API-/Workertests und die gepinnten Migrate-/Credential-/API-Prüfbuilds
bestanden. Die008-DDL und tatsächliche Runtime-Vorbereitung wurden vor Anwendung
in einer vollständig zurückgerollten Fixturetransaktion geprüft. Unabhängiger
Review ohne verbleibenden Blocker. Die008-Prüfsumme ist unveränderlich:
`9328008652ad697a306093301d9488fe3e0b184a3ffd8333f7beda5924712c57`.

Die sechs öffentlichen Dienste laufen unverändert; regulär geprüftes HTTPS
liefert200. Die333 Cockpittests/109 Interopprüfpunkte aus IP-038 wurden hier
nicht wiederholt; der TS-Signer blieb unverändert.

[Tests](../tests/README.md),
[Betrieb/Prüfkommandos](../infra/README.md),
[PostgreSQL18: Sperren](https://www.postgresql.org/docs/18/explicit-locking.html),
[PostgreSQL18: sichere Definerfunktionen](https://www.postgresql.org/docs/18/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).
