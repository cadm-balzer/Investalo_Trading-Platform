# Dauerhafter Demo-Handelskey-Store

2026-11-18, IP-009/IP-015. PR91 (`e150da2`) ist in main `7ebb733` bestätigt.
Das eigene [Handelskeyprofil](bitget-demo-trading-profile.md) erhält einen
privaten SQL-Store und frischen verschlüsselten Provider.

## Persistenz und Profilgrenzen

Additive018 erweitert die bestehende Demo-Tabelle um unveränderliche
native Rechte. Ein CHECK bindet entweder das ursprüngliche Leseprofil mit
NULL-Rechten oder das Handelsprofil mit kanonischer validierter Rechteliste.
Die bestehenden eindeutigen Broker-UID-/Kontoslots gelten über beide
Demo-Profile, auch nach Widerruf. Kein zweiter Demo-Kontoslot durch Profilwechsel,
keine Konvertierung, Keyersetzung oder Freigabe eines widerrufenen Slots.
Normal-/Demo-Umgebungen und deren Ciphertextdomänen bleiben getrennt.

Eigene Create/Read/Rewrap/Revoke-Definer prüfen tatsächlich gebundenen
SESSION_USER, aktuellen Actor/Membership/Epoch/Reauth/Frist und Konto.
FORCE RLS, fester Searchpath, eingeschränkte EXECUTE-ACL, CAS und vorhandener
atomarer append-only Audit bleiben verbindlich. Rewrap verändert nur
DEK-Wrapdaten; Widerruf benötigt exakte UUID/Revision/Storage, keine Keys und
ist auch bei pausiertem Konto möglich. Unbekannter Commit wird nicht wiederholt.

Ein privater Helper teilt ausschließlich die feste Profil-/Ownershipprüfung.
Die alten Lesefunktionen können Handelsdatensätze nicht lesen, umschlüsseln,
widerrufen oder als leeren/lesenden Passkeyslot darstellen.
Eigene metadata-only Runtime-/interne Passkeyprojektionen zeigen Actor-
gebundene Kontometadaten und tatsächliche Rechte, nie Broker-UID/Parent/IP/
Provenienz/Envelope. Ein widerrufener Slot bleibt sichtbar.
Das ist noch kein eigener Trading-Passkey-Proof-/Consent-/Consume-/Executorpfad.

## Provider und Abnahme

`DemoTradingCredentialStore` teilt nur die bestehenden tatsächlichen
LOGIN-/Kontext-/Ownershipchecks. CRUD/Spec/Snapshot/Provider sind Trading-
spezifisch. Vor/nach Entschlüsselung wird die aktuelle DB erneut gelesen:
Actor-/Epoch-/Readyzustand, vollständiger Spec, Storage und Ciphertext müssen
unverändert sein. Kurze Frist/monotone Uhr/PID werden geprüft. Kein
Plaintextcache; eigene private Lease, keine Umdeutung in DemoReadCredential.

27 neue Fälle (17 tatsächliche PG,10 Provider/AEAD/Fork) und185 betroffene
bestehende Fälle grün:212 verschiedene gepinnte Fälle insgesamt.
Final17 tatsächliche PG-Fälle nach zusätzlicher Widerrufswährend-Keyladung-
und direkter Fremdtenantprüfung erneut bestanden. Tatsächliche TLS/PG/Role/
SQL/AES-GCM/Child-Fork und bisherige42 HTTP/API-Fälle; Keys/Identitäten/
Brokerantworten synthetisch. Keine physische Browser-/native Brokerabnahme.

018 erst vollständig zurückrollend auf DDL/Rechte/Registry/Actor/ACL/
Owner/Searchpath geprüft, danach ONLY `investalo_credentials_checks`
angewendet. SHA256:
`001ea39d3b9aa109c3ee4cb770d503c3371943b638d3cc424e63e0d8fe92e3e7`.
001–017-Checksums und tatsächliches Entwicklungsset unverändert.
Der erste Prüfblock hatte eine PL/pgSQL-Record-/Alias-Kollision; dieser
fehlgeschlagene Durchlauf blieb vollständig zurückgerollt. Diagnosen geben
nur statische SQLSTATEs aus.

Aufruf: `python3 infra/scripts/prepare-demo-trading-store-checks.py`
(Rollback); `--apply-reviewed` erlaubt nur die isolierte Fixture.
Normale Services/öffentlicher Stand, Dependencies und Frontend unverändert.
Keine echten Keys, Brokerrequests, Orders, finanzielle Journals, Backtests,
Live- oder AI-Aktivierung. Als Nächstes eigener dauerhafter Trading-Passkey-
Purpose/Consent/Executor, API/BFF/Browser und operative Einrichtung.
