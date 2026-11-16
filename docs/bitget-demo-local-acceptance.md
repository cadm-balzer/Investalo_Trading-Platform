# Isolierte gemeinsame Demo-Abnahme

IP-009/IP-015, 2026-11-16. Eigener lokaler Abnahmepfad verbindet den
[privaten Dateiprovider](bitget-demo-private-identity.md) und den
[Demo-Browserablauf](bitget-demo-browser-flow.md) mit tatsächlicher HTTPS-API,
PostgreSQL und separat eingeschränktem Python-Executor. Die ursprüngliche
Serversitzung und die Brokerprovenienz sind ausdrücklich synthetisch.

## Ablauf

Der Node-Treiber startet einen tatsächlichen HTTPS-Server mit dem bestehenden
Demo-HTTPadapter und Browserflow. Der private Dateiprovider liest die
geschützten Originaldateien; der aktuelle Benutzer stammt unabhängig aus
dem authentifizierten APIkontext. APIassertions behalten den ursprünglichen
OIDC-Zeitpunkt. Tatsächliche P256-Signaturen durchlaufen die bestehende
WebAuthnprüfung; Challenge, Counter, Grant und Consent werden durch die
echte API und Fixture015 verwaltet.

Der BFF übergibt die unveränderten Requestbytes über mTLS an den separaten
Python-Prozess. Dieser verwendet den tatsächlichen Demo-Executor mit
committed Consume, finalem Transaktionslock, AEAD-/014-Storewrite und
atomarem016-Abschluss. Sein DB-LOGIN ist `investalo_credentials_tests_a`,
fest an den neuen Testactor gebunden; BFF und API erhalten dessen Passwort
nicht. Der Auditprozess benötigt bewusst Fixture-Migrationsrechte zur
Einrichtung und unabhängigen Prüfung, besitzt aber ebenfalls kein
Executor-LOGIN-Passwort. Er ersetzt keine operative Minimalidentität.

Geprüfte Phasen:

- Registrierung mit zwei gleichzeitigen Browser-Dispatches: genau einer
  erfolgreich, einer abgewiesen; danach wird auch der alte Handle abgewiesen.
- Tatsächlicher Executor-Prozessneustart mit denselben geschützten Dateien.
- Widerruf über neue Passkeyprüfung und Consent: Revision1, Storage1→2,
  Status `revoked`, ursprünglicher Ciphertext bleibt unverändert.
- Registrierung auf einem zweiten eigenen Konto mit absichtlich fehlender
  Erfolgsantwort nach dem bestätigten Commit: BFF meldet unbestätigt, der
  alte Handle dispatcht nicht erneut; APImetadaten und unabhängige DBprüfung
  bestätigen trotzdem den aktiven verschlüsselten Datensatz und `completed`.

Die DBprüfung verifiziert tatsächliches JTI, gebundene Body-SHA und originalen
OIDC-Zeitpunkt, identische Transaktions-ID von finalem Lock und Completion,
einmalige Auditzeilen und AEAD-Entschlüsselung der synthetischen Triples.
Normal-Zweckrouten bleiben404. Die separate API ohne Demo-Flags liefert404;
falscher CSRF, Normal-Browserpfad, fremdes Konto und abweichende Testtriples
werden abgewiesen.

## Prüfbeleg

Vollständiger gepinnter Lauf bestanden:438 Prüfungen
(Node241, Audit59, Host138; einschließlich RPC-/Containergrenzen).
Lauf `6a47b6aa-e550-4df2-87c1-6d5f21a98b08`,
lokaler Beleg
`infra/local/bitget-demo-local-acceptance/6a47b6aa-e550-4df2-87c1-6d5f21a98b08/receipt.json`,
SHA256 `ad5582cdc89fe2c96b10df0a4a044fe75473ca3bc2f816910f7b2f7d1297f040`.
Der create-only0600-Beleg wurde fsync/readback geprüft.
54 gezielte gepinnte Python-Fälle mit35 Unterfällen, davon3 neue
Runtime-/Intakeguards, bestanden. Der gepackte Node-Treiber ist typgeprüft.
Fixture001–017-Checksums und Entwicklungs-Migrationssatz vor/nachher
unverändert geprüft. Alle selbst gestarteten Ablaufcontainer beendet.

Fehlgeschlagene private Testwurzeln bleiben ohne Erfolgsbeleg erhalten.
Dabei wurden Testzertifikate für die strengere TLSprüfung ergänzt,
Testkonten ausdrücklich bereit gesetzt, HTTPclient-Bodygrenzen eindeutig
gesetzt und die unabhängigen Entschlüsselungs-/Auditabfragen korrigiert.
Kein fehlgeschlagener Lauf wird als vollständige Abnahme gewertet.

## Ausführung und Grenzen

`infra/compose.demo-local-acceptance.yaml` ergänzt ausschließlich eigene
Testservices ohne Hostports. Tatsächliche Containerkonfigurationen werden
auf UID10003, readonly Rootfs, CapDropALL, no-new-privileges, Limits,
abgeschaltetes Logging, interne Netzwerke und getrennte Secrets geprüft.
Der Compilercontainer benötigt512MiB; die Ablaufcontainer192MiB.
Die gepinnten bestehenden Python-/Node-Abhängigkeiten bleiben unverändert.

```bash
python3 infra/scripts/prepare-demo-local-acceptance.py
python3 infra/scripts/prepare-demo-metadata-checks.py
bash infra/scripts/compose.sh --file infra/compose.demo-local-acceptance.yaml --profile demo-local-acceptance build api demo-acceptance-audit demo-acceptance-executor demo-acceptance-node
bash infra/scripts/compose.sh --file infra/compose.demo-local-acceptance.yaml --profile demo-local-acceptance run --rm --no-deps -T demo-acceptance-node-checks
python3 tests/infra/check_demo_local_acceptance.py --orchestrate
```

Voraussetzung ist die vorhandene isolierte Credentials-Fixture001–017 mit
ihren geschützten DB-/TLS-Dateien und dem APIsecret aus der bestehenden
Passkey-Browserfixture. `prepare-demo-metadata-checks.py` prüft Checksums und
den unveränderten Entwicklungs-Migrationssatz; ohne `--apply-reviewed`
wendet es keine fehlende Migration an. Es initialisiert keinen Testactor.

Der Host startet eindeutige One-off-Container. Die private RPC über deren
Standardstreams enthält Testmaterial und wird nicht ausgegeben oder
protokolliert. Ein exklusiver Fixturelock serialisiert eigene Hostläufe.
Andere Credentials-Fixturetests sind währenddessen ebenfalls nicht parallel
zu starten, da sie dieselbe Test-LOGIN-Bindung verwenden.
Der Auditprozess erstellt pro Lauf eigene UUIDs und private
0700/0400-Dateien mit frischer kurzlebiger CA, Client-/Serverzertifikaten,
Signingschlüssel und KEK. Er stellt die vorherige Test-LOGIN-Bindung per CAS
wieder her; append-only Fixtureevidence und fehlgeschlagene private Wurzeln
bleiben erhalten. Der Host beendet ausschließlich die selbst gestarteten
Container. Bestehende Dienste werden weder ersetzt noch neu gestartet.

Der Launcher `investalo_credential_store.demo_acceptance_runtime` öffnet
ohne exaktes `--synthetic-demo` keine Dateien oder Ports. Auch mit diesem
Argument akzeptiert er ausschließlich die festgelegten Testtriples und
beiden Testkonten. Die UID-/Parent-/IP-/Keyherkunft ist eine deklarierte
synthetische Provisioningantwort, kein nativer Bitget-Nachweis. Der absichtliche
Antwortfehler wird erst nach dem tatsächlichen erfolgreichen Executorabschluss
ausgelöst und schreibt keinen falschen `failed`-Abschluss.

Diese Abnahme benutzt den realen HTTPadapter und BFF-Kern in einem eigenen
HTTPS-Server. Sie behauptet keinen physischen Browser, keinen tatsächlichen
Next-/OIDC-Login und keine installierte operative Serverfactory.
`demoCredentialBrowserRuntimeAvailable()` bleibt fest `false`.
Native Demo-Key-/UID-/Readprovenienz, operative Installation und später der
gebundene Ordertransport bleiben die nächsten Schritte. Kein öffentlicher
Zugang, Livehandel, AI, Brokerrequest oder Backtest wird aktiviert.
