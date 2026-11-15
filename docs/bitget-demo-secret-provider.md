# Getrenntes verschlüsseltes Demo-Leseprofil

Stand 2026-11-15, IP-009/IP-015/IP-016. PR77 (`114e888`) ist in
`main92140a2` enthalten; GitHub/Fetch/Ancestry bestätigt.

Demo-Keys werden in Bitget ausdrücklich im Demo-Modus erstellt. Späterer
Livezugang erhält einen separaten Key und eine getrennte Kontoverbindung.
Die geschützte Dashboard-Demo-Eingabe und tatsächliche Brokerabnahme sind
noch nicht freigeschaltet. Für die erste Leseprüfung benötigt das Profil
bekannte Leserechte und genau die konfigurierte Server-IP. Ein späteres
Futures-Tradingkeyprofil wird gesondert geprüft; keine automatische
Handelsfreigabe durch Hinterlegen eines Keys.

`demo_secret_provider.py` schafft den eigenen verschlüsselten Providerkern
für den [gebundenen Demo-Lesezugang](bitget-demo-read-transport.md).
Er implementiert keine Dashboard-Keyeingabe, DB-Persistenz oder neue
Passkey-Autorisierung.

## Eigene Purposebindung

`DemoSecretSpec` enthält ursprüngliche DemoBinding (Owner, Konto, Keyreferenz,
UID/Umgebung/Familie/Profil), bekannten Parent, kanonische Egress-IP,
Provenienzbelegdigest und Keyrevision. Diese erwarteten Daten stammen aus
vertrauenswürdiger Einrichtung, nicht aus dem Ciphertext oder Browser.

Das feste Profil `bitget-classic-demo-read-secret/1`/`demo_read_only` wird
mit sämtlichen Metadaten als AES-GCM-AAD authentifiziert. Eigene Domains
`investalo.demo.credentials.payload` und `investalo.demo.credentials.dek-wrap`
trennen Demo von den bestehenden normalen Lesekonto-Envelopes.
Der bisherige `AADBinding`-Vertrag mit `real_read_only`, seine Bytes und seine
Konstruktorbeschränkungen bleiben unverändert.

`seal_demo_secret` verwendet bestehende gepinnte AES-256-GCM-Abhängigkeiten,
einen eigenen zufälligen DEK, zwei zufällige 96-Bit-Nonces und getrennten
Payload-/KEK-Wrap. Der vorhandene begrenzte Ciphertextcontainer wird wieder-
verwendet; Zweck/Metadaten werden aus der erwarteten Spec authentifiziert.
Native Strings werden durch den bestehenden strikten Credentialcodec erhalten.
Keine geheimen Klartextdateien, automatische Serializer oder Logprojektionen.

`open_demo_secret` verweigert das normale Profil und abweichende Purpose-/
Owner-/Konto-/Key-/UID-/Parent-/IP-/Revision-/Provenienzdaten.
`rewrap_demo_secret` prüft beide bisherigen AEADs, bevor der gleiche DEK
neu gewrappt wird. Payloadnonce/-ciphertext bleiben erhalten. Dies ersetzt
keinen bestätigten neuen Storage-/Keyrevisionsvertrag.

## Gebundener Provider

`DemoSecretSnapshot` repräsentiert einen ausdrücklich eigenen bestätigten
Demo-Eintrag mit Spec, Envelope und positiver Storageversion.
`SealedDemoReadProvider` erwartet separat die ursprüngliche Spec,
exakte Storageversion und festen kurzen Ablaufzeitpunkt (maximal 60 Sekunden
Restlaufzeit).

Vor Secretzugriff werden Originalbinding und Owner geprüft. Der injizierte
Reader muss tatsächliche aktuelle Actor-/Konto-/Epoch-/Ready-/Demo-Purpose-
Berechtigung nachweisen; sein Rückgabewert ist eine trusted Servicegrenze.
Es gibt in diesem Checkpoint keinen neuen DB-Reader, keine RLS-/Rolebeweise
oder browserseitige Grantannahme.

Vor Decrypt wird der aktuelle eigene Snapshot geprüft; anschließend werden
die tatsächlichen KEKs geladen. Nach Decrypt wird die aktuelle Berechtigung/
Spec/Storageversion/der identische vollständige Ciphertext erneut gelesen.
Pause, Widerruf, fehlende Daten, Metadaten-/Versionswechsel oder ein
Ciphertextfork derselben Version liefern keinen Key. Kein Klartextcache oder
Fallback auf zuvor erfolgreiche Reads. Clock/Expiry werden erneut geprüft.

Erst danach entsteht eine `DemoReadCredential` für den eigenen Readclient.
Die Provenienz bleibt ein geschützter erwarteter Einrichtungsbeleg; Kryptografie
beweist nicht allein, dass der Nutzer den Key tatsächlich im Bitget-Demo-Modus
erstellt hat. Native UID/Parent/IP/Rechteprüfungen bleiben erforderlich.

## Prüfung und nächster Schritt

18 neue tatsächliche Crypto-/synthetische Readerfälle plus19 alte Store-
und143 Bitgetfälle: **180 Fälle / 204 Subtests grün** im isolierten gepinnten
Testimage (Python3.14.10, cryptography50.0.2, pytest9.2.0).
Nach finalem Fixture-Importpfad nochmals alle18 neuen Fälle grün.
Keine Host-Crypto-Version als gepinnte Abnahme ausgegeben.

Demo/Normal-Ciphertextaustausch, sämtliche Scope-/Purposemetadaten,
unabhängige AEAD-Schäden, KEK-Rewrap, fehlende/falsche KEKs,
Owner-/Version-/Pause-/Widerrufs-/Clockgates und Fehlerredaktion geprüft.
Ein echter privater registrierter Journalpfad wird mit dem SealedProvider
und15 synthetischen signierten Brokerreads verbunden; Revision0 bleibt erhalten.

Als Nächstes eigenes dauerhaftes Demo-Purpose-/Berechtigungs-/Passkeyprofil,
geschützte Dashboard-Eingabe und native Endpoint-/Keyabnahme. Bestehende
normale DB-Einträge werden nicht umetikettiert. Keine echte Keyaufnahme,
Brokerrequests, DB-Migration, neue Dependencies, laufenden Services,
Frontendbuilds, Backtests oder Public/Live/AI-Aktivierung.
