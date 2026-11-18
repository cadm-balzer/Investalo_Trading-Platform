# Privater Demo-Key-Prüfaufruf am Serverterminal

Dieser Aufruf bleibt auf reine Leserechte begrenzt. Für den bestätigten
Futures-/Spot-Read-Write-Key ist das
[eigene Handelskeyprofil](bitget-demo-trading-profile.md) vorbereitet;
seine operative Eingabe folgt separat.

IP-009/IP-015, 2026-11-16. PR88 ist als `c9bd492` in `main` bestätigt.
Der separate Operatoraufruf prüft einen im Bitget-Demo-Modus erstellten Key
mit genau einem signierten Identitäts-GET. Kein Plattformkonto wird angelegt,
kein Key registriert, keine Position oder Order verändert.

`demo_private_probe.py` nutzt den
[geprüften Registrierungsadapter](bitget-demo-native-provisioning.md).
Die Herkunft bleibt eine Betreiberbestätigung. Eine erfolgreiche Identität
beweist weder Demo-Keyerstellung noch Kontomodus, Hebel, Orders, Cash, Kosten
oder vollständige Account-Reconciliation.

## Geschützte Vorbereitung

Vor einem echten Aufruf werden erwartete Demo-UID, bekannter Parent
(`"0"` für den bekannten Hauptaccount), kanonische tatsächliche Server-Egress-IP
und die exakt genehmigten bekannten Leserechte in Bitget bestätigt.
Erster Prüfkey ausschließlich lesend, späterer Tradingkey separat.
Keine Schlüssel oder Passphrasen in Chat, Shellargumente, Umgebungsvariablen
oder Konfigurationsdateien kopieren.

Der einmalige separate Compose-Aufruf verwendet ausschließlich
`/tmp/investalo-demo-native-probe` als Hostmount. Vertrauenswürdige Einrichtung
legt diesen Originalordner mit UID/GID10003 und Modus0700 an sowie darin
`setup.json` mit UID/GID10003 und Modus0400. Der Ordner wird nicht automatisch
von Compose angelegt; bestehende fremde Pfade werden nicht übernommen.

```json
{
  "schema": "investalo-demo-private-probe/1",
  "tenant_id": "<kanonische Tenant-UUID>",
  "user_id": "<kanonische Benutzer-UUID>",
  "account_id": "<kanonische Konto-UUID>",
  "connection_id": "<kanonische Verbindungs-UUID>",
  "broker_uid": "<erwartete Demo-UID>",
  "parent_uid": "0",
  "egress_ip": "<bestätigte Server-IP>",
  "authorities": ["coor", "cpor"]
}
```

Die Leserechtemenge im Beispiel muss der tatsächlich genehmigten Menge
entsprechen; Zusatzrechte werden nicht stillschweigend übernommen.
Die Plattform-IDs deklarieren den vorgesehenen Kontext. Dieser eigenständige
Operatorcheck prüft keine DB-/Actor-/Readyberechtigung und seine Quittung
ersetzt niemals die aktuelle Passkey-/API-/DB-Freigabe bei Registrierung.
Doppelte/zusätzliche JSONfelder, Credentials im Setup, abweichende UUIDs,
Schreibrechte, offene IP-Whitelist oder unbekannter Parent werden verweigert.

## Manueller Aufruf

Erst nach abgeschlossener privater Metadateneinrichtung am interaktiven
Serverterminal:

```bash
docker compose --project-name investalo-demo-native-probe \
  --env-file infra/images.env --file infra/compose.demo-native-probe.yaml \
  --profile demo-native-probe build demo-native-probe

docker compose --project-name investalo-demo-native-probe \
  --env-file infra/images.env --file infra/compose.demo-native-probe.yaml \
  --profile demo-native-probe run --rm --no-deps demo-native-probe \
  python -m investalo_credential_store.demo_private_probe --native-demo-probe
```

Der Operator bestätigt verdeckt mit `DEMO` die separate Demo-Keyerstellung,
dann werden API-Key, Secret und Passphrase mit abgeschaltetem Terminalecho
eingelesen. Alle drei Standardstreams müssen echte Terminals sein.
Umleitung, fehlender Opt-in und ein `getpass`-Fallback auf sichtbare Eingabe
stoppen vor Secretversand. Unbekannte Argumente werden nicht im Fehlertext
wiedergegeben. Es gibt keine Keyargumente oder automatischen Wiederholungen.

Eigene UID10003, gepinntes Image, Rootfilesystem readonly, keine Capabilities,
no-new-privileges, begrenzter Speicher/PIDs und Dockerlogging `none`.
Keine Ports, Plattform-/DB-/KEK-/Cookie-/Assertionsmounts oder Dienstneustarts.
Ein eigenes Bridge-Netz ermöglicht den expliziten HTTPS-GET; es ist keine
netzwerkseitige Domain-Allowlist. Der Adapter erlaubt ausschließlich das feste
Bitget-Ziel mit CA-/Hostnameprüfung, ohne Proxies/Redirects.

## Ergebnis und Grenzen

Ein exklusiver Lock auf dem ursprünglichen privaten Ordner verhindert
gleichzeitige Prüfungen desselben Mounts. Die gemeinsame UID-Quota anderer
Prozesse/Dienste bleibt eine eigene Betriebsabnahme; kein Dauerpolling.
Die Originalkonfiguration wird während des GETs und vor/nach Publikation
erneut geprüft. Dateiänderung, falsche UID/Parent/IP/Rechte, Fristablauf oder
unbekannter Transportausgang erzeugen keine erfolgreiche Rückmeldung.

Jeder Versandversuch bekommt einen neuen privaten UUID-Ordner. Nach Erfolg
enthält `receipt.json` (0600) nur eigene Spec-/Konfigurations-/Antwortdigests,
deklarierte Bindung, GET-Zeiten und klare `false`-Flags für zertifizierte
Demo-Herkunft, volle Accountabnahme, Plattformregistrierung und Orders.
Keine Klartextcredentials oder dauerhaft gespeicherten Provenienzkeys.
Der flüchtige MAC-Schlüssel authentifiziert nur diesen Operatorvorgang;
der Beleg ist keine weiterverwendbare Herkunftsfreigabe oder native HTTP-
Archivquittung. Nur ein statischer Status wird am Terminal ausgegeben.

Create-only/fsync/readback; Fehlerverzeichnisse bleiben erhalten. Bei einem
unbekannten Schreibausgang kann eine teilweise oder vollständig geschriebene
Quittung existieren, obwohl der Aufruf scheitert. Sie ist keine automatische
Fortsetzungs- oder Handelsautorität und löst niemals einen erneuten GET aus.

**135 gepinnte Fälle / 84 Unterfälle grün**, davon20 neue Probeprüfungen.
Tatsächlicher Linux-PTY mit frischem Python-Kindprozess prüft Original-
`getpass`, alle drei verdeckten Credentialfelder und private Quittung;
synthetischer Brokertransport. Tatsächliche Datei-/Directorylock-/fsync-
Fehlerfälle sowie bestehende Demo-Provenienz/AEAD/Read/Runtimeguards grün.
Composevertrag validiert. Gepackter Defaultaufruf stoppt ohne Opt-in,
TTY, Keys oder Netzwerk. Keine echte native Bitget-Abnahme behauptet.

Als Nächstes private Metadaten und tatsächlichen Demo-Key gemeinsam
vorbereiten, diesen einmaligen nativen Check durchführen und danach die
vollständige native Account-/Normal-/Triggerorder-/Cash-/Kostenabnahme.
Operative Dashboard-/Executorinstallation und gebundener Ordertransport
bleiben separat; kein Public-/Live-/AI-/Backtest-/DB-/Dependencywechsel.
