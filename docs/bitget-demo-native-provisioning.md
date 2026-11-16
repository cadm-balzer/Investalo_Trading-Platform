# Demo-Herkunftsfreigabe und native Registrierungsprüfung

IP-009/IP-015, 2026-11-16. PR87 ist als `68038db` in `main` bestätigt.
`demo_native_provisioning.py` ergänzt den konkreten `provision`-Adapter für
`DemoPasskeyOnboarding`: eigene private Herkunftsfreigabe, anschließend genau
ein signierter Classic-Kontoidentitäts-GET mit `paptrading: 1`.
Der Adapter ist noch nicht in einen laufenden Executor installiert.

Die [offizielle Bitget-Dokumentation](https://www.bitget.com/docs/classic/demo-trading/rest-api)
verlangt einen im Demo-Modus erstellten Demo-Key und den zusätzlichen Header
(geprüft 2026-11-16). Der Header und eine passende UID zertifizieren die
Herkunft des Keys nicht. Deshalb bleibt die Herkunft ausdrücklich eine
unabhängige Betreiberbestätigung; `native_demo_creation_verified` bleibt
im internen Digestvertrag `false`. Dieser Schritt behauptet keine native
Brokerabnahme oder automatische Handelsfreigabe.

## Private Freigabe

Vertrauenswürdige Einrichtung erstellt mit `make_demo_origin_record` ein
kanonisches eigenes Herkunftsrecord. Erforderlich sind die bestätigte
Erstellung im Bitget-Demo-Modus, ursprünglicher Tenant/Benutzer/Konto,
Attestations-ID, erwartete UID/Parent/Server-IP, exakt genehmigte bekannte
Leserechte und höchstens 15 Minuten Gültigkeit.

Ein HMAC mit einem separaten zufälligen 32-Byte-Provenienzschlüssel bindet
sämtliche Metadaten und alle drei unveränderten Credentialfelder. Die private
Datei enthält keinen API-Key, kein Secret und keine Passphrase. Kein
öffentlicher ungeschützter Secret-Fingerprint. Der Provenienzschlüssel muss
vor operativer Installation getrennt von KEK und Assertionschlüssel
provisioniert werden; sein Loader bleibt eine vertrauenswürdige Servicegrenze.
Diese Hilfsfunktion ist keine Browserroute und keine selbständige Prüfung
der Betreiberbestätigung.

`PrivateDemoOriginReader` verlangt absolute Originalpfade, eigene UID,
0700-Verzeichnis, 0400-Regularfile, genau einen Hardlink und den separat
erwarteten SHA256. Alle Pfadkomponenten werden ohne Symlink geöffnet;
Datei und Verzeichnis werden über tatsächliche FDs und Originalmetadaten
geprüft. Austausch, Änderung, Löschen, Symlink, FIFO oder nachträgliche
Rechteänderung verweigern weitere Prüfungen. Eine neue Freigabe verlangt
eine ausdrücklich neu eingerichtete Readerinstanz. Keine Dateirotation
oder Übernahme eines beliebigen Browserdokuments.

## Registrierung

Der bestehende Executor verbraucht die Passkeyfreigabe vor dem
Provisioning und schreibt danach weiterhin nur über seinen bisherigen
atomaren 014/015/016-Abschluss. `DemoNativeProvisioner` passt direkt zur
vorhandenen Callbacksignatur:

```python
provision = DemoNativeProvisioner(
    read_approval=private_origin_reader,
    load_provenance_key=trusted_separate_key_loader,
    transport=HTTPSDemoReadTransport(),
)
# Explizit als provision=... an DemoPasskeyOnboarding übergeben.
```

Vor Secretversand müssen ursprünglicher Actor/Konto, vollständiges
Credentialpaket, gültige Freigabe und verbleibende Assertionlaufzeit passen.
Nur `GET https://api.bitget.com/api/v2/spot/account/info`, kein frei
wählbares Ziel, keine Modeänderung, kein Normal-Transport oder Retry.
Der vorhandene HTTPS-Demo-Transport prüft CA/Hostname, verweigert Redirects
und Umgebungsproxies und begrenzt Antwort/Timeout.

Vor und nach dem GET sowie vor Rückgabe werden Freigabe, MAC-Schlüssel,
Originaldatei und Zeit erneut geprüft. Höchstens fünf Sekunden Gesamtdauer;
native Antwortzeit muss auch nach der letzten Prüfung noch frisch sein.
Native UID/Parent müssen exakt passen, die Whitelist enthält genau die
genehmigte IP, die Rechte entsprechen exakt der genehmigten Leserechtemenge
einschließlich `coor`/`cpor`. UTA, Schreibrechte und unbekannte Felder der
bisherigen Classic-Identitätsprüfung werden verweigert.

Eine Instanz verweigert parallele oder geerbte Forkzugriffe und begrenzt
Identitätsabfragen auf eine pro Sekunde; auch ein fehlgeschlagener Versand
belegt dieses Intervall. Eine gemeinsame UID-Quota mehrerer Prozesse ist
weiterhin eine Betriebsanforderung. Ein langsamer GET kann bereits laufen,
wird nach dem Timeout/der Rückkehr aber nie als erfolgreiche Prüfung übernommen.

Nur eine vollständig erfolgreiche Prüfung liefert die eigene `DemoSecretSpec`
mit Revision1, ursprünglicher Connection-ID und einem Digest aus Binding,
Herkunftsrecord-SHA, Antwort-SHA und tatsächlichen Prüfzeiten. Dieser Digest
ist keine persistierte native HTTP-Archivquittung. Die bestehenden
AEAD-Metadaten und die getrennte Demo-Purposebindung bleiben unverändert.

## Abnahme und verbleibende Arbeit

Die neuen Tests verwenden tatsächliche private Dateien und AES-GCM, aber
synthetische Schlüssel und Brokerantworten. Sie prüfen exact signierte
Requestbytes, Konto/IP/Rechte, alle drei Credentialfelder, Fristen,
Dateiaustausch, Änderung während des GETs, Fehlerredaktion und fehlende
Retries. **115 gepinnte Fälle / 84 Unterfälle grün**: neuer Prüfer sowie
bestehende Demo-Secretprovider-, Demo-Readtransport- und synthetische
Runtimeguards. Python3.14.10/cryptography50.0.2/pytest9.2.0 im bisherigen
isolierten Testimage, ohne Netzwerk und ohne Source-Mounts. Im ersten Lauf
war ausschließlich die neue KEK-Testfixture falsch aufgebaut (Dict statt
ursprünglichem Tuplevertrag); korrigierte Fixture und finaler Lauf grün.

Vor realer Verwendung fehlen die sichere operative Einrichtung mit einem
tatsächlich separat erstellten Demo-Key, aktuelle Kontoberechtigungen,
provisionierte MAC-/TLS-/KEK-/Assertionsidentitäten und die native
Endpoint-/Latenz-/Quotaabnahme. Anschließend vollständige Account-/Normal-/
Triggerorder-/Kosten-Reconciliation und gebundener Demo-Ordertransport.
Keine laufenden Dienste, DB/Migrationen, Dependencies, Frontend,
Backtests, Public-, Live- oder AI-Aktivierung in diesem Checkpoint.
