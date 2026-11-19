# Geschützter Dashboardablauf für Demo-Handelskeys

Stand 2026-11-19, IP-009/IP-015, D-134. PR94/693ac78 ist als f1b376a
in main gemerged; GitHub/Fetch/Ancestry bestätigt. Eigener Dashboard-/BFF-/
privater Transportpfad verbindet den Handelsvertrag018/019 und die
[Handelskey-API](bitget-demo-trading-api.md). Öffentlich weiterhin aus.

## Ablauf und Grenzen

Der Sicherheitsbereich verlinkt einen eigenen Bereich
`/security/credentials/demo-trading`. Die drei festen POST-Routen unter
`/api/credentials/bitget-demo-trading/passkey/{start,finish,execute}` prüfen
Aktivierung, Origin, ursprüngliche Sitzung, CSRF und begrenzte Requestbytes.
Die abgeschaltete Route liefert503 vor Key-/Bodyaufnahme. Die Seite zeigt
statt eines Eingabeformulars den offenen Einrichtungsstand.

Der vorbereitete Ablauf umfasst Kontowahl, Trade-Register oder schlüssellosen
Widerruf, Passkey-Prüfung und getrennte ausdrückliche Bestätigung.
Passkey-P256/UV, ursprüngliche Sitzung und aktuelle API-Faktor-/Metadatenstände
werden vor/nach den relevanten Asynchronaufrufen geprüft. Die eigene
achtfeldrige Metadatenprojektion fordert kanonische Handelsrechte und friert
deren Kopie ein. Read-Metadaten, -Freigaben und -Signingdomains bleiben separat.

Die Browserfortsetzung reserviert Kapazität vor Asynchronaufrufen. Ein
ursprünglich sitzungsgebundener Handle wird einmalig entnommen und nach
erfolgreichem Folgeschritt ersetzt. Er enthält weder Keytriple noch Requestbody,
Signingkey oder JWT. Die private Eingabe bleibt beim begrenzten Aufruf und
im flüchtigen Browsercontroller; kein Local-/Sessionstorage. Ein unbekannter
Antwortausgang führt zu keinem automatischen erneutem Execute.
Die vertrauenswürdige `acceptCredentials`-Policy bleibt ausdrücklich
erforderlich; ein Flag allein erlaubt keine echte Keyaufnahme.

Eigene feste Domains:

| Bindung | Wert |
|---|---|
| Consent | `demo-trading-credential-write` |
| Receiptkind | `passkey-demo-trading-credential-authorization/1` |
| JWT-Audience | `investalo-credentials-demo-trading-passkey` |
| Executorprefix | `/v1/credentials/bitget-demo-trading` |
| Privates Identityschema | `investalo-demo-trading-credential-private-identity/1` |

Die eigene Private-Identityfactory erfordert explizite Originalpfade,
0700/0400/UID/Link-/Inode-/Hashkontinuität, eigene Signingbytes und gültiges
passendes Client-TLS-Material. Die ausgeschlossenen Signingfingerprints müssen
vom vertrauenswürdigen Setup einschließlich Read-/Normal-/API-/Session-/KEK-
Identitäten geliefert werden. Keine Envinstallation, automatische Rotation
oder native Schlüsselherkunft wird dadurch behauptet.
Der aktuelle User kommt unabhängig vom JWT aus dem authentifizierten API-
Kontext, bevor die private Identität an die ursprüngliche Sitzung gebunden wird.

Der BFF signiert die exakt bestätigten Requestbytes. Der Node-mTLS-Client
schickt ausschließlich eigene Register-/Revoke-Pfade mit unabhängigem
ursprünglichem Kontextheader. Beide bestehenden Python-Listener wählen den
Handelspurpose nur anhand des exakten, vertrauenswürdig installierten
`DemoTradingCredentialHTTPApplication`-Typs. Keine Anfrage kann das Profil
umschalten. Der injizierte Callback muss den eigenen Handels-Executor nutzen;
TLS selbst erteilt keine Passkey-/DB-Freigabe.
Normale und Demo-Read-Domains bleiben unverändert.

Nach erfolgreichem Schreiben werden aktueller Actor/Faktor/Konto und der
genaue Connection-Endzustand erneut gelesen. Die neuen Rechte müssen018
entsprechen; beim Widerruf bleibt zusätzlich die ursprüngliche Liste exakt
gleich. Verlorene oder unbestätigte Antworten werden nicht erneut gesendet.

## Abnahme

- 352 neue und914 bestehende Cockpitfälle,1266 insgesamt, im vorhandenen
  gepinnten Node24.22.2-Image bestanden. Tatsächliche P256/Jose-, React-SSR-,
  Request/Response-, Originaldatei- und Loopback-mTLS-Prüfungen; API-/Executor-
  Replies dieser Nodefälle bleiben synthetisch.
- 9 neue/122 verschiedene gepinnte Pythonfälle und79 Unterfälle bestanden:
  beide tatsächlichen mTLS-Listener, Read-/Normal-/Trading-Crossdomain,
  unveränderte Transportregeln sowie67 tatsächliche PostgreSQL-/AES-GCM-
  Handelsfreigabe-/Executorregressionen. Identitäten/Keys/Faktorurteile synthetisch.
- 121 separate Node/Jose→Python-Interopprüfungen über5 synthetische Samples,
  einschließlich exakter Unicode-/Whitespacebytes, kurzfristiger Deadline,
  hoher sicherer Storageversion und Ablehnung beider fremden Signingdomains.
- Typecheck grün; gepinnte Cockpit-/Credentialcheckimages gebaut.
  Next kompiliert die eigene Seite und drei Routen. Fixture001–019 und
  tatsächliches Entwicklungsset unverändert geprüft.

Das sind1388 verschiedene Testfälle plus121 Interopassertions.
Keine physische Browser-/native Bitget-Abnahme und keine gemeinsame laufende
Trading-HTTPS/BFF/API/PG/Python-Abnahme wird daraus abgeleitet. Keine neuen
Dependencies/Migrationen, laufenden normalen Dienste, echten Keys, nativen
Brokerrequests, Orders, Backtests oder Public-/Live-/AI-Freischaltungen.

## Operative Arbeit

Eigene private Trading-Identität, API-/Account-/LOGIN-/KEK-/mTLS-/Signing-
Zuordnung und den nativen Trading-Provisioner samt vertrauenswürdiger
Intakepolicy installieren. Gemeinsame isolierte laufende Tradingabnahme
vor tatsächlichem Rollout durchführen; alten Read-Abnahme-/TTY-Pfad nicht
umkonfigurieren. Native Key-/UID-/Parent-/IP-/Rechte-/Account-/Order-/Kosten-/
Latenz-/Quotaabnahme bleibt erforderlich. Öffentlicher Rollout benötigt
seine eigene Freigabe; Merges aktualisieren die laufenden Dienste nicht.
