# Eigene Demo-Passkey-Zweckfreigabe

Stand 2026-11-15, IP-009/IP-015. PR79 (`959123b`) ist in `main6410e89`
enthalten; GitHub/Fetch/Ancestry bestätigt.

Additive015 verbindet die bestehende Passkeyregistry mit einem eigenen
dauerhaften Demo-Consent. Die privaten Pythonmodule prüfen signierte Freigaben,
konsumieren sie einmalig und sperren sie in einer separaten Transaktion.
Geschützte Dashboard-Eingabe, Signierprovider und tatsächlicher Demo-Executor
folgen. Alle Keys, Konten und WebAuthn-Verifikationsurteile der Abnahme sind
synthetisch; es gibt keine physische Geräte- oder native Brokerabnahme.

## Zweck, Ziel und aktuelle Berechtigung

Nur eigene Bitget-/USDT-Konten mit Modus `bitget_demo` sind zulässig.
Vorbereitung friert Account-/Verbindungsmetadaten, ursprüngliche OIDC-Identität
und Auth-Zeit, Epoch, Sitzung, Origin/RP, Ziel und SHA256 der exakten Bodybytes ein.
Registrierung verlangt `ready`; keyloser Widerruf eines vorhandenen aktiven
Datensatzes bleibt auch bei pausiertem Konto möglich. Das Ziel umfasst die
eigene Connection-UUID; Widerruf zusätzlich Revision1 und aktuelle Storageversion.
Keyersatz/Rebinding werden nicht angeboten.

Eigene feste Domains:

| Feld | Wert |
|---|---|
| Audience | `investalo-credentials-demo-passkey` |
| Kind | `passkey-demo-credential-authorization/1` |
| Methode | `POST` |
| Ziele | `/v1/credentials/bitget-demo/register`, `/v1/credentials/bitget-demo/revoke` |
| Metadatenpurpose | `demo_read_only` |
| Profil | `bitget-classic-demo-read-secret/1` |

Diese URIs sind Assertionziele, noch keine erreichbaren HTTP-Routen.
Normale008-Freigaben werden nicht umetikettiert. Beide Pythonverifier,
SQL-Consumer und die ursprünglichen007-Proofeingänge weisen das jeweils
andere Profil zurück, auch bei demselben synthetischen Signierschlüssel.
Die Konsum-JTI ist im eigenen Demoledger eindeutig; eine gemeinsame
globale JTI-Registry beider Zweckledger wird nicht behauptet.

015 nutzt Registry/Counter-CAS aus006 und passive Receipt-/Clockprimitive aus
007/008 unverändert. Demo-Vorbereitung/Claim/Finish/Consent verwenden eigene
Eingänge und aktuelle Demo-Metadaten. Gemeinsamer Actor-/RP-Slot und die Grenze
von acht aktiven Proofs bleiben erhalten. Die Verbindungstabelle aus014 wird
dabei nicht verändert.

## Dauerhafter Ablauf

1. Eigene Purpose-Vorbereitung legt den Demoledger und generischen Proof
   atomar an. Der kurzlebige Claim muss separat committen.
2. Ein vertrauenswürdiger Verifier liefert das WebAuthn-Urteil. Finish prüft
   Counter/Version und speichert Grant und Audit atomar. Das ist allein noch
   keine Credentialfreigabe.
3. Ausdrücklicher Consent prüft unveränderte Sitzung, Metadaten, Ziel und
   Confirmationhash und bestätigt den Proof mit eigener Demo-Purposereceipt.
4. `DemoPasskeyRequestVerifier` prüft HS256, strikt begrenzte Claims/JSON,
   feste Domains und genaue Bodybytes vor jedem DB-Zugriff. Die ursprüngliche
   OIDC-Zeit bleibt von der frischen Passkey-Zeit getrennt.
5. Der private `DemoPasskeyAuthorizationClient` verifiziert den tatsächlichen
   gebundenen Credential-LOGIN/Tenant/User und konsumiert die Receipt genau
   einmal. Ein Handle entsteht erst nach bestätigtem Commit. Unbekannter
   Commit liefert keinen Erfolg oder automatischen Retry.
6. Nur derselbe Client akzeptiert sein Handle in einer separaten Transaktion.
   SQL prüft aktuelle Membership, Epoch, Reauth, Factorversion, Metadaten und
   Zeit unter Locks. Nach Rückgabe an den Aufrufer werden diese erneut geprüft.
   Ablauf rollt Lock und Audit zurück; bestätigter Lock ist terminal.

Der aktuelle finale Check verlangt die ursprünglichen unveränderten
Metadaten. Ein künftiger014-Writer benötigt einen eigenen geprüften
Post-Write-/Completionvertrag; er darf nicht einfach zwischen die beiden
Checks eingeschoben werden. Der bisherige009-Normalprofilabschluss wird
nicht verwendet.

FORCE RLS, unveränderliche Übergänge und append-only Audit gelten für beide
neuen Tabellen. Runtime bekommt nur eigene Purpose-/Proofeingänge;
Credentialworker nur Consume/Lock. Direkte Tabellenzugriffe und interne
Helper sind diesen Rollen und Research entzogen. Definerfunktionen haben
festen `search_path=pg_catalog`. Privilegierter DB-Betrieb, originale
Sitzungs-/Signingclaims, Connectionfactory und KEKs bleiben vertrauenswürdig.
SQL verifiziert keine WebAuthn-/JWT-Signatur oder Bitget-Demo-Keyprovenienz.

## Abnahme und nächste Integration

015 wurde nach vollständig zurückgerolltem DDL-/Scope-/Claim-/ACLpreflight
ausschließlich in `investalo_credentials_checks` angewendet. Bereits angewendete
001–014 bleiben byteidentisch; die normale Entwicklungs-DB wurde nicht migriert.
Gepinnte Check-/Migrationimages verwenden die vorhandenen Dependencylocks.
015-Checksum: `044e4be6b7c67c39bd6b9c175e5cc102e51efdd8cee3ef0a64bcf99710271cf8`.

Die PostgreSQL-Abnahme umfasst eigene Ausgabe/Register-/Revokeziele,
Claim-/Consume-Commitgrenzen, exakte Bodybytes, getrennte Domains,
Consentmismatch, konkurrierenden Einmalverbrauch, doppelte Demo-JTI,
aktuelle Konto-/Rollen-/Epoch-/Factoränderungen, Callerrollback,
verlorenen Consume-Ack und Ablauf nach dem Lock.
35 neue Fälle und133 bisherige Passkey-/Assertionfälle sowie31 Demo-Storefälle:
199 unterschiedliche Fälle gepinnt grün
(Python3.14.10/cryptography50.0.2/pytest9.2.0).
Final alle35 eigenen und31 Storefälle erneut grün. Ein bisheriger
Schema-Test wurde von einem breiten Namenspräfix auf die sieben konkreten
014-Storefunktionen begrenzt; neue015-Funktionen werden separat auf Owner,
Searchpath und Definer-/Helpergrenzen geprüft. Kein SQL- oder Storevertrag
wurde für diese Testanpassung verändert.

Als Nächstes eigener Demo-Executor mit finalem Storewrite-/Completionvertrag
und geschützter BFF-/Dashboard-Eingang, anschließend native Demo-Key-/
UID-/Parent-/IP-/Rechteabnahme. Keine echten Keys/Brokerrequests, aktiven
Services, öffentlichen Routen, Orders, Backtest-, Live- oder AI-Änderungen.
