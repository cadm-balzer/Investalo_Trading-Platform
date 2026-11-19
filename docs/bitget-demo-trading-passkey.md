# Demo-Handelskey: Passkey und atomare Speicherung

Stand 2026-11-19, IP-009/IP-015, D-132. PR92 ist als f8cd152 in main
gemerged. Dieser Checkpoint verbindet den eigenen Handelsstore mit einer
dauerhaften einmaligen Passkey-Freigabe und einem privaten Executor.
Die öffentliche Keyeingabe bleibt bis zur operativen Dashboardanbindung aus.

## Vertrag

Migration019 ergänzt eigene Freigabe-, Audit- und Abschlusstabellen mit
FORCE RLS und eng begrenzten Definerfunktionen.001–018 bleiben unverändert.
Der bestehende Faktor-/Counter-/Sessionkern wird weiterverwendet; alte
Normal- und Demo-Lesefreigaben werden nicht in Handelsfreigaben umgewandelt.
Die festen Domains sind:

| Bindung | Wert |
|---|---|
| Metadatenpurpose | `demo_futures_spot_trading` |
| Profil | `bitget-classic-demo-trading-secret/1` |
| Freigabeart | `passkey-demo-trading-credential-authorization/1` |
| JWT-Audience | `investalo-credentials-demo-trading-passkey` |
| Requestpfade | `/v1/credentials/bitget-demo-trading/{register,revoke}` |

Diese Pfade sind signierte Requestbindungen für den privaten Executor;
dieser Checkpoint installiert noch keine HTTP-Routen. Die Assertion bindet
die ursprüngliche Sitzung, den aktuellen Faktor, Konto, Aktion, Metadatenhash
und exakte Requestbytes. Consent wird zusammen mit der eigenen Freigabe
gespeichert. Ein erfolgreicher Faktorclaim muss vor dem Verifikationsabschluss
in einer anderen Transaktion bestätigt worden sein.

Der Executor prüft den eigenen Verifiertyp und bestätigt den einmaligen
Consume-Commit vor Provisioning oder KEK-Zugriff. Nur ein tatsächlich
eingespeister vertrauenswürdiger Provisioner darf die genaue Demo-Triple
prüfen und einen eigenen `DemoTradingSecretSpec` zurückgeben. Eigentümer,
Konto, Connection, Revision und Egress-IP müssen zum ursprünglichen Auftrag
passen. Dieses Interface allein beweist keine native Schlüsselherkunft.

In einer zweiten Transaktion werden aktueller Actor, Epoch, Reauth,
Faktorversion, Konto und unveränderte Metadaten unter Locks erneut geprüft.
018 speichert das eigene AEAD-Ciphertext;019 prüft danach den erlaubten
Metadatenwechsel und schreibt den Abschlussnachweis in derselben Transaktion.
Bei Registrierung werden nur die von018 erlaubten nativen Rechte ergänzt:
coow/cpow/stow, optional bekannte Leserechte. Ein Widerruf erhält diese
Rechte und das Ciphertext und erhöht nur Storageversion/Status; er funktioniert
auch beim pausierten Konto ohne Provisioner oder KEK.

Fehler vor dem bestätigten Consume liefern keinen Handle. Ein unbekannter
Consume- oder Final-Commit führt zu keinem automatischen Wiederholungsversuch.
Bereits abgeschlossene Speicherung bleibt bei fehlender Bestätigung
abgeschlossen und darf nicht nachträglich als fehlgeschlagen markiert werden.
Ein fehlgeschlagener Versuch erhält, soweit der aktuelle Actor das erlaubt,
einen terminalen Fehlernachweis; der Executor kann ihn nicht wiederbeleben.
JTI-Eindeutigkeit gilt im eigenen Handelsledger, nicht global über alle Ledger.

Die SQL-Funktionen und injizierten Provisioning-/KEK-/Connectionfactorys sind
vertrauenswürdige Servicegrenzen. Die Storeprimitive allein ist weiterhin
keine universelle MFA-Grenze. Der eigene Python-Authorizationclient teilt nur
die unveränderten Restricted-LOGIN-/Current-Actor-Sessionchecks; Assertions,
Handles, Consume/Lock und Executor bleiben eigene Typen und Domains.

## Abnahme

Vollständig zurückgerollte019-Vorprüfung vor Anwendung ausschließlich auf
`investalo_credentials_checks`: DDL, Actor, ACL, FORCE RLS, Owner und
`search_path=pg_catalog`. Unveränderte Checksummen001–018 und tatsächliches
Entwicklungsset werden vor/nach geprüft. Der neue Operatoraufruf ist:

```sh
python3 infra/scripts/prepare-demo-trading-passkey-checks.py
python3 infra/scripts/prepare-demo-trading-passkey-checks.py --apply-reviewed
```

Die eigenen Tests benutzen echte PostgreSQL-Transaktionen und AES-GCM mit
synthetischen Schlüsseln, Identitäten und WebAuthn-Verifikationsurteilen.
67 neue und139 bestehende gezielte Fälle, insgesamt206 verschiedene Fälle,
bestanden im gepinnten Image (Python3.14.10/cryptography50.0.2/pytest9.2.0).
Sie prüfen Consent/Consume/Lock, Trennung von Normal-/Lesefreigaben,
parallele Gewinner, Session-/Faktor-/Metadatendrift, Post-Write-Rollback,
frische Speicherung/Readback, pausierten schlüssellosen Widerruf und
tatsächlich erfolgte Commits mit fehlender Bestätigung. Keine physische
Browser- oder native Bitget-Abnahme wird daraus abgeleitet.

019-Checksumme:
`d4135bd4ece2198f478402f286459403d62c2dd3056f448c8dc05313ffc410d6`.
Abschließende Prüfung bestätigte Fixture001–019 und unverändertes
tatsächliches Entwicklungsset.

## Nächster Schritt

Eigene Trading-Proof-/Consent-API, BFF-Signing und Browseranbindung bis zum
privaten Executor zusammenführen. Anschließend vertrauenswürdige operative
Identitäten, Schlüsselherkunft, UID/Parent/IP/Rechte und native Account-/
Order-/Kosten-/Latenz-/Quotaabnahme vorbereiten. Erst dann öffentlicher Rollout
mit eigener Freigabe. Keine normalen Dienste, echten Keys, Brokerrequests,
Orders, Backtests, Dependencies oder Live-/AI-Freischaltungen verändert.
