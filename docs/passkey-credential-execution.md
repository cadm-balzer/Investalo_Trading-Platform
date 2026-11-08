# Private Passkey-Credentialausführung

Stand 2026-11-08, IP-040. Checkpoint `389082a` ist in Main `be13145`
verifiziert. Der private Pythonexecutor verbindet die dauerhafte Zweckfreigabe
aus008 mit dem bestehenden verschlüsselten Credentialstore. Die Browser- und
öffentliche Aktivierung folgen nach eigener Abnahme.
IP-041 verbindet diesen Executor inzwischen über injizierte Ports mit dem
[privaten Cockpit-Zweckablauf](passkey-credential-cockpit.md), geprüft mit
echtem HTTPS/API/PG und synthetischem WebAuthn-/Broker-/Keymaterial.

## Ablauf

`PasskeyBitgetOnboarding` erhält ausschließlich vertrauenswürdige Serverinputs:
Storecontext, ursprünglichen Sitzungskontext, Passkeyverifier, Keyring,
transaktionale Connectionfactory, expliziten Transport und feste Egress-IP.
Der Executor unterstützt `register`, `replace` und `revoke`.

1. Die Signaturprüfung bindet die exakten Bodybytes, Ziel/CAS, Zweckreceipt,
   ursprüngliche OIDC-Zeit und getrennte frische Passkeyzeiten.
2.008 konsumiert die Freigabe global einmalig. Erst der bestätigte Commit
   erlaubt einen Credentialread oder eine private Probe.
3. Registrierung und Austausch prüfen mit dem bestehenden Classic-V2-Readcore
   die UID/Parentbindung, Leserechte und genau die konfigurierte IP.
   Ein Austausch muss die gespeicherte Brokeridentität erhalten.
4. Eine separate Transaktion prüft unter008-Sperren die aktuelle Identität,
   Epoch/Reauth, Sitzung, Faktor, Kontometadaten/CAS und Frist.
5. Der003-Store verschlüsselt bzw. widerruft die Verbindung.009 prüft anschließend
   den erlaubten neuen Zustand und schreibt das unveränderliche Abschlussaudit.
   Lock, Mutation und Abschluss werden gemeinsam committed.

Widerruf braucht weder Entschlüsselung noch Brokerprobe und bleibt für pausierte
Konten verfügbar. Die öffentliche Ergebnissicht enthält nur Connection-ID,
Credentialrevision, Storageversion und Status.

## Abschluss und Fehler

009 ergänzt eine eigene append-only FORCE-RLS-Abschlusstabelle und die private
Funktion `credential_finish_passkey_authorization(claims, outcome)`.008 und
alle früheren angewendeten Migrationen bleiben unverändert.

`completed` verlangt dieselben authentifizierten Claims und denselben gebundenen
LOGIN, committed Consume in einer anderen Transaktion sowie den008-Lock in
der aktuellen Transaktion. Die gewollte Storeänderung ersetzt die alte
Connectionmetadatenprüfung:

| Aktion | Erlaubter finaler Zustand |
| --- | --- |
| Registrierung | active, Revision1, Storage1 |
| Austausch | active, Revision und Storage jeweils +1 |
| Widerruf | revoked, gleiche Revision, Storage +1 |

Actor/Epoch/Reauth, ursprüngliche OIDC-Zeit, Faktor und unveränderte
Kontometadaten werden erneut geprüft. Die Fristprüfung nach dem Abschlussinsert
deckt dessen mögliche Sperrwartezeit ab. Ein fehlender oder falscher Write,
Auditfehler oder Ablauf rollt die gesamte finale Transaktion zurück;
der vorher bestätigte Consume bleibt erhalten.

`failed` protokolliert nach Rollback best effort den gebundenen Verbrauch,
erteilt keine Schreibautorität und benötigt keine noch frische Passkeyzeit.
Das globale Terminalaudit kann nicht ersetzt oder erneut abgeschlossen werden.
Ein Absturz kann daher einen konsumierten Versuch ohne Abschluss hinterlassen.
Ein unbekannter Consumecommit liefert keinen Handle und startet keine Probe.
Ein unbekannter finaler Commit liefert keinen Erfolg und wird nicht automatisch
wiederholt; ein bereits gespeicherter Abschluss wird nicht mit `failed` überschrieben.
Vor einem neuen Versuch ist der autoritative Zustand abzugleichen.

SQL vertraut dem privaten JWT-Verifier und BFF-WebAuthnverdict. Die direkten
003-Storefunktionen bleiben vertrauenswürdige Primitive; dieser Executor
begründet keinen universellen MFA-Zwang für beliebige direkte SQL-Aufrufe.
Der administrative Prüfcontainer besitzt Fixture-/Migrationscredentials,
die einem späteren Betriebsdienst nicht gegeben werden dürfen.

## Abnahmegrenzen

Nur synthetische Schlüssel, administrative Testfreigaben und injizierte
Brokerantworten werden geprüft. Es gibt keine neuen HTTP-Routen, impliziten
Netzwerktransport, tatsächliche Schlüsselannahme oder öffentliche Aktivierung.
Die laufende Vorschau bleibt auf001–007; neue Migrationen werden ausschließlich
in `investalo_credentials_checks` angewendet.

Physische Geräteabnahme, tatsächliche E-Mail-Attestierung, geschützte
Browser-Keyeingabe, eigene Signatur-/Betriebsidentität, Broker-Egress/Quota,
Recovery und Pilotbetrieb bleiben IP-033/BL-017/020/021/022/024/025.

356 Credentialtests im gepinnten Container bestanden:19 Client,116 Offline,
221 tatsächliche PostgreSQL-Fälle.64 neue PG-Fälle umfassen48 Abschlussfälle
und16 signierte private Executorflows mit AEAD-Mutation, allen drei Aktionen,
Concurrent-Replay, Authorityänderungen, verlorenen Commitantworten und Rollback.
21 neue Offlinefälle prüfen den Executorvertrag. Gepinnte Migrate-/Storage-/
API-Prüfbuilds und unabhängiger Review bestanden.
461 API-/Workertests gegen Fixture009 erneut ausgeführt und bestanden.
Insgesamt817 Tests in diesen beiden Suiten.

009 nach vollständig zurückgerollter DDL-/echter Failure-Abschlussvorprüfung
ausschließlich in der Fixture-DB angewendet. Unveränderliche Prüfsumme:
`435d658458c6be7359ab19ad575421fb843c8756975710cc651eff41c4d62b75`.
001–008 unverändert. Sechs öffentliche Dienste unverändert/gesund, reguläres
TLS HTTPS200. Die333 Cockpit-/109 Interopprüfpunkte aus IP-038 wurden hier
nicht wiederholt; TS/Cockpitcode blieb unverändert.

[Dauerhafte Freigabe](passkey-credential-authorizations.md),
[Prüfkommandos](../infra/README.md),
[Credentialservice](../services/credentials/README.md).

Nachfolgend verbindet IP-042 diesen Executor über einen injizierten
[Entwicklungs-HTTPS-Transport](passkey-credential-https.md) mit dem TS-BFF.
Eigene TLS-CA/Clientpin und unabhängiger Sitzungskontext sind getrennte
Transportgrenzen; ursprüngliche Verifier-/008-/009-Prüfungen bleiben erhalten.
Keine Produktivprovisionierung oder tatsächliche Keyannahme.
