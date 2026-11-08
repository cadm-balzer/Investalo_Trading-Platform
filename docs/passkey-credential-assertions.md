# Getrennter Passkey-Credential-Assertionvertrag

Der isolierte Vertrag ist inzwischen über008/009 mit einem privaten Executor
verbunden: [Ausführung und Abnahmegrenzen](passkey-credential-execution.md).
IP-041 ergänzt den [privaten Cockpitablauf](passkey-credential-cockpit.md)
mit standardmäßig deaktivierter API-Zweckbrücke und vollständiger Fixtureprüfung.
Die folgende Beschreibung dokumentiert den isolierten IP-038-Vertrag.

Stand 2026-11-08. IP-038 ergänzt einen isolierten TypeScript-Signer und
Python-Verifier für die spätere Credentialintegration. Er bewahrt die
ursprüngliche OIDC-Anmeldezeit und führt die frische Passkeyprüfzeit separat.
Keine Route, Receipt-Ausgabe, Datenbankmigration, Credentialmutation oder
Brokerprobe ist angeschlossen. Bestehender Signer, Verifier und004 bleiben
unverändert; das neue Pythonobjekt wird von `BitgetOnboarding` nicht akzeptiert.
IP-039 ergänzt inzwischen die separate [dauerhafte Zweckgrenze008](passkey-credential-authorizations.md).
Signer/Verifier allein bleiben wiederholbare Primitive ohne eigene DB-Autorität.

## Zweck und Bindungen

Der neue Dienstvertrag hat ausschließlich Audience
`investalo-credentials-passkey` und
`authorization_kind=passkey-credential-authorization/1`.
HS256 mit exakt `{alg:HS256,typ:JWT}` und eine getrennt zu provisionierende
Signaturidentität sind erforderlich. Bisher gibt es nur injizierte Testkeys.
Alter Credentialvertrag und neuer Vertrag weisen einander auch bei identischem
synthetischem Testkey ab.

Der Signer benötigt einen eigenen privaten Zweckreceipt mit `kind` und einer
`authorization_id`, die sich von Proof- und Grant-ID unterscheidet. Weder die
öffentliche007-Antwort `execution_enabled:false` noch der interne007-Grant
hat dieses Schema. Eine abgeschlossene Funktionsprüfung ist keine Zustimmung
zu einer Kontoänderung. Der neue Receipt wird gegen separat vertrauenswürdigen
Actor-/Sitzungskontext geprüft; Tokenclaims selbst liefern diesen Kontext nicht.
Es gibt in diesem Checkpoint noch keinen autoritativen Aussteller für den Receipt.

| Bindung | Prüfvertrag |
|---|---|
| Identität | Tenant, Nutzer, Subject, Epoch, konfigurierter OIDC-Issuer und unveränderte ursprüngliche OIDC-Zeit |
| Sitzung | Eigener Sitzungshash, ursprüngliche Frist, konfigurierter HTTPS-Origin und exakte RP |
| Nachweis | Verschiedene Authorization-/Proof-/Grant-IDs, Faktor-ID und Assertionversion mindestens2 |
| Vorschau | Exaktes eingefrorenes Konto-/Verbindungsziel und beobachtete Revision/Speicherversion |
| Metadaten | `metadata_sha256` als unverändert authentifizierter Digest der künftig autoritativen DB-Vorschau |
| Anfrage | POST, fester Aktionspfad und SHA256 der unveränderten UTF8-Bodybytes |
| Zeit | Schrittbeginn, Passkeyprüfung, ausdrückliche Autorisierung, Receipt-, Session- und Tokenfrist getrennt |

Der alte Vertrag verlangt eine frische IdP-Zeit ab Schrittbeginn;007 erhält
bewusst auch eine ältere ursprüngliche Loginzeit. Die neue Frische folgt
`passkey_checked_at`; die ursprüngliche Zeit muss zum vertrauenswürdigen
Kontext passen und darf höchstens fünf Sekunden in der Zukunft liegen.
Es wird kein `oidc_amr` erfunden. Token gelten höchstens60 Sekunden und nie
länger als Receipt, ursprüngliche Sitzung oder `checked_at+120`.
Passkeyprüfung/Autorisierung dürfen nicht in der Zukunft liegen.
Langsame Signierung und Rücksprung der Uhr werden vor Rückgabe abgewiesen.

Beide Sprachen verlangen exakte Felder, kanonische UUIDs und sichere
JS-Ganzzahlen. CAS-Werte im Body dürfen keine Bool-, Float- oder Exponentform
haben. JSON-Duplikate einschließlich escaped Feldnamen werden abgewiesen.
Bodygröße höchstens4096 Byte; Triplefelder maximal256/1024/256 UTF8-Byte,
ohne Unicode-Steuer-/Format-/Surrogatzeichen. Bytes und Whitespace bleiben
unverändert; keine Normalisierung von Secrets.

Der neue Vertrag beschränkt auch den OIDC-Issuer auf einen kanonischen
HTTPS-DNS-Origin ohne Pfad, Query, Fragment, Nutzerinfo oder redundanten443-Port.
Die bestehenden Konfigurationen erfüllen dies. Der alte Verifier erlaubte
Issuer mit Pfad; dessen Vertrag wird nicht verändert.

## Persistenz und nächste Integrationsgrenze

Signieren und Verifizieren sind wiederholbare vertrauenswürdige Primitive.
Eine neue JTI verhindert nicht die erneute Verwendung desselben Proofs.
Die Assertion beweist weder aktuelle DB-Autorität noch einen tatsächlich
ausgestellten Zweckreceipt. Der Metadatendigest wird hier nicht aus JSON
neu berechnet; seine Ausgabe und der Vergleich mit aktuellen DB-Metadaten
gehören in die spätere additive Integration.

Die additive008 in IP-039 stellt ausdrückliche Zweckfreigaben aus und konsumiert
sie global einmalig mit unveränderlichen Bindungen und Bodyhash.
Die Probe-/Writeintegration folgt noch separat. Eine bloße007-
Funktionsbestätigung darf nicht nachträglich in eine Schreibfreigabe
umgedeutet werden. Aktueller Actor/Epoch/`reauth_after`, ursprüngliche
OIDC-Zeit, Sitzung, Faktorstatus/-version, Zeit, Metadaten und CAS müssen
bei Annahme und endgültigem Write erneut geprüft werden. Consume vor Probe
committen; CAS, Mutation und Abschlussaudit atomar. Unbekannte Commits
abgleichen; kein automatischer Replay.001–007 bleiben immutable.

Physische Geräteprüfung, tatsächliche E-Mail-Attestierung, öffentliche
Aktivierung, geschützte Eingabe, Betriebsschlüssel, Broker-/Egress-/Quota-
Nachweise und Recovery bleiben IP-033/BL-020/021/022/024/025.

## Prüfbelege

333 Cockpittests einschließlich68 neuer Vertragsfälle,77 Offline-Onboardingtests
einschließlich36 neuer Verifierfälle und109 tatsächliche sprachübergreifende
TS/Jose/Python-Prüfpunkte bestanden. Letztere verwenden vom echten TS-Signer
erzeugte Tokens für alle drei Aktionen, UTF8/Whitespace, kurze Frist und
größte sichere Integer sowie wechselseitige Ablehnung des alten Vertrags.
Nur synthetische Receipts und Testschlüssel; keine Datenbank-/Browser-/Broker-
oder E-Mail-Abnahme. Typecheck und gepinnter Cockpitbuild bestanden.
Alle77 Offline-Onboardingtests auch im gepinnten Python3.14.10-Container
bestanden; Composekonfiguration ohne Netzwerk/Secrets/Mounts/Ports/DB-
Abhängigkeiten geprüft. Bestehende sechs öffentliche Dienste unverändert
und gesund, HTTPS200 mit regulärer Zertifikatsprüfung.
Die früheren API-/PG-/Credential- und HTTPS-Belege wurden nicht erneut gezählt.

Prüfanleitung: [Tests](../tests/README.md).
Grundlagen: [RFC8725, getrennte JWT-Prüfregeln](https://www.rfc-editor.org/rfc/rfc8725.html#section-3.12),
[OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html),
[Nachweis007](passkey-action-proofs.md).
