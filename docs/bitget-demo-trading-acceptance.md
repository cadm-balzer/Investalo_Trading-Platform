# Gemeinsame isolierte Abnahme des Demo-Handelskey-Ablaufs

Stand 2026-11-19, IP-009/IP-015, D-135. PR95/978d732 ist als05a7f0a
in main gemerged; GitHub/Fetch/Ancestry geprüft.
Eigener Abnahmepfad verbindet den [Handelskey-Dashboard-/BFF-Ablauf](bitget-demo-trading-dashboard.md)
mit tatsächlicher HTTPS-API, Fixture018/019 und separatem privatem Python-
Executor. Sitzung und Broker-Key-/UID-/Parent-/IP-/Rechteprovenienz synthetisch.

## Nachweis

Der tatsächliche HTTPS-BFF verwendet die vorhandenen eigenen Handels-HTTP-/
Browser-/Private-Identitymodule. Der ursprüngliche Testactor wird unabhängig
vom Credential-JWT durch die echte API gelesen. Tatsächliche P256-Signaturen
durchlaufen WebAuthn-Verifikation und aktuellen Factor-CAS. Challenge,
Original-OIDC-Zeit, Bodyhash, Consent und Claim werden von API/PG019 verwaltet.

Der Node-BFF übergibt die unveränderten Bytes per mTLS an einen separaten
Python-Prozess. Der tatsächliche Handels-Executor bestätigt Consume vor
Provisioning/KEK und verbindet018 AEAD-Schreiben und019 Abschluss atomar.
Der LOGIN `investalo_credentials_tests_a` ist nur an den neuen Testactor
gebunden. Node/API/Audit erhalten dessen Passwort nicht; der Auditprozess
hat ausdrücklich Fixture-Migrationsrechte für Setup und unabhängige Prüfung.
Das ist keine operative Minimalidentität.

Geprüfte Phasen:

- Zwei gleichzeitige Registrierungsdispatches mit genau einem Gewinner;
  erneute Verwendung des alten Handles dispatcht nicht erneut.
- Tatsächlicher Neustart des Executorcontainers mit denselben geschützten
  Originaldateien und unverändertem Verschlüsselungs-/Freigabestand.
- Frische Passkeyprüfung und ausdrücklicher Consent für schlüssellosen
  Widerruf: Revision1, Storage1→2, `revoked`; Ciphertext und genaue native
  Rechte-Liste bleiben unverändert.
- Registrierung auf einem zweiten eigenen Konto mit absichtlich fehlender
  Erfolgsantwort nach tatsächlich bestätigtem Commit. BFF meldet unbestätigt;
  derselbe Handle sendet nicht erneut. Unabhängiges PG-/AEAD-Audit und aktueller
  API-Readback bestätigen trotzdem `active` und `completed`.

Die unabhängige Prüfung bestätigt tatsächliche JTI-/Bodyhash-/Original-
OIDC-Bindung, identische Final-Lock-/Completion-Transaktions-ID, einmalige
Auditzeilen, eigene Handelsprofile/Rechte/UIDs und erfolgreiche Entschlüsselung
der synthetischen Triples. Mit demselben KEK und passenden Accountdaten kann
der alte Demo-Lesepurpose dieses Handels-Ciphertext nicht entschlüsseln.
Read-/Normal-APIpfade bleiben geschlossen; disabled Trading-API liefert404.
Falscher CSRF, fremde Konten, alte Browserpfade und abweichende Triples werden
abgewiesen. Der reine Abnahmelauncher akzeptiert keine echten Brokerkeys.

## Beleg und Ausführung

449 tatsächliche kombinierte Prüfungen bestanden: Node246, Audit71, Host132.
Lauf `eddf1d23-811d-4793-8c47-e16f0f3eb5da`.
Create-only0600/fsync/readback-Beleg:
`infra/local/bitget-demo-trading-local-acceptance/eddf1d23-811d-4793-8c47-e16f0f3eb5da/receipt.json`.
SHA256 `977070ea72698a33cf1b9f261788922cf6a3948b9b25a98727ac9797cab02fa9`.

48 gezielte gepinnte Pythonfälle/57 Unterfälle bestanden, darunter3 eigene
Default-off-/Schema-/Intakeguards. Gepackter Node-Treiber typgeprüft.
Eigene Audit-/Executor-/Nodeimages gebaut. Fixture001–019-Checksums und
tatsächliches Entwicklungsset vor/nach unverändert. Alle selbst gestarteten
Ablaufcontainer beendet; Original-Test-LOGIN-Bindung per CAS wiederhergestellt,
append-only Evidenz und private Testwurzeln bleiben erhalten.

Die eigene Compose-Datei enthält ausschließlich zusätzliche Testservices
ohne Hostports. Tatsächliche Containerkonfigurationen werden auf UID10003,
readonly Rootfs, CapDropALL/no-new-privileges, Limits, Loggingnone, interne
Netzwerke und getrennte Secrets geprüft. Compiler512MiB, Ablauf192MiB.
Vorhandene Pins/Dependencies bleiben unverändert.

```bash
python3 infra/scripts/prepare-demo-local-acceptance.py
python3 infra/scripts/prepare-demo-trading-local-acceptance.py
python3 infra/scripts/prepare-demo-trading-passkey-checks.py
bash infra/scripts/compose.sh --file infra/compose.demo-trading-local-acceptance.yaml --profile demo-trading-local-acceptance build demo-trading-acceptance-audit demo-trading-acceptance-executor demo-trading-acceptance-node
bash infra/scripts/compose.sh --file infra/compose.demo-trading-local-acceptance.yaml --profile demo-trading-local-acceptance run --rm --no-deps -T demo-trading-acceptance-node-checks
python3 tests/infra/check_demo_trading_local_acceptance.py --orchestrate
```

Voraussetzung: Fixture001–019, aktuelle API mit eigenen Tradingrouten und
vorhandene geschützte DB-/TLS-/API-Testsecretdateien. Beide Read-/Trading-
Abnahmeläufe teilen den vorhandenen Fixturelock unter
`/tmp/investalo-demo-local-acceptance`, weil sie denselben Test-LOGIN
temporär binden. Andere Credentials-Fixturetests ebenfalls nicht parallel
starten. Neue eigene Wurzeln liegen unter
`/tmp/investalo-demo-trading-local-acceptance`; Read-Abnahme bleibt unverändert.
Host-RPC mit Testmaterial wird privat über Standardstreams weitergereicht.
Fehlgeschlagene Wurzeln bleiben ohne Erfolgsbeleg erhalten.

## Operative Grenze

Nur das genaue `--synthetic-demo-trading` öffnet diesen Launcher. Eigener
Configtyp, feste Testtriples und zwei deklarierte Testkonten bleiben zwingend.
Altes Read-Opt-in/-Schema wird abgewiesen. Diese Guards dürfen nicht entfernt
werden, um tatsächliche Keys aufzunehmen.
Die HTTPS-Abnahme verwendet den echten BFF-HTTPadapter mit einer synthetischen
ursprünglichen Sitzung; keine physische Browser-/Next-/OIDC- oder native
Bitget-Abnahme wird daraus abgeleitet.

Als Nächstes separaten operativen Tradingruntime mit echten geschützten
Plattform-/Serviceidentitäten und nativem Trading-Provisioner vorbereiten.
Tatsächliche Key-/UID-/Parent-/IP-/Rechteherkunft sowie Account-/Order-/Kosten-/
Latenz-/Quotaabnahme vor Brokerbetrieb prüfen. Öffentlicher Rollout benötigt
seine eigene Freigabe. Keine normalen Dienste, neue Migrationen/Dependencies,
realen Keys, nativen Brokerrequests, Orders, Backtests oder Public-/Live-/AI-
Freischaltungen.
