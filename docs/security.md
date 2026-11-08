# Sicherheitskonzept

Stand 2026-11-08. Verbindliche Leitlinien aus AGENTS.md:
privater Nutzerkreis, Verschlüsselung und minimale Rechte. Q20 konkretisiert
den Zugang als öffentlichen zentralen HTTPS-Einstieg schon im Privatpilot.
Docker Compose und lokales Authelia sind in Q13/Q14 bestätigt;
Administratives E-Mail-Recovery ist in Q24 bestätigt. Q31 beauftragt Umsetzung:
Pins, dienstbezogene lokale Testsecrets, TLS, BFF-Assertions und RLS sind im
Fundament umgesetzt. API-/Workertests prüfen echte PostgreSQL-Mandantentrennung,
geschützte Holdouts, Rollen und abgelaufene Claims. Research besitzt eine eigene
tenantgebundene DB-Identität ohne Broker-/BFF-Secrets. Recovery, Brokercredentials, Step-up und
Pilotbackup bleiben weitere Abnahmen.

Die öffentliche Entwicklungsvorschau wurde separat freigegeben und aktiviert:
zwei gültige Let’s-Encrypt-Zertifikate, ausschließlich zentraler Edge80/443,
Passwort plus TOTP und48 tatsächliche HTTPS-Prüfpunkte. Der synthetische
öffentliche Nutzer ist ausdrücklich im bestehenden Entwicklungstenant;
alte Identitäts-/Credentialbindungen bleiben erhalten.
[Zugang und Betriebsgrenzen](https-entry.md).

Der zusätzliche interne Aktionsnachweis007 speichert zielgebundene Challenges,
einen committed Einmalclaim, CAS/Grant und die Bestätigung der eigenen Vorschau.
Der BFF prüft echte UV/UP-Signaturen; SQL/API vertrauen diesem Dienstverdict und
prüfen Actor, ursprüngliche OIDC-Claims, Ziel, Versionen und Fristen erneut.
IP-037 ergänzt eine ausdrücklich aktivierbare BFF-Browservorschau; Standard-
und öffentliches Composeprofil lassen sie ausgeschaltet. Die HTTP-Grenze
übergibt eine unveränderliche CSRF-autorisierte Sitzung und prüft Bindungen nach
asynchronem Bodylesen, Krypto-/API-Aufrufen und vor Ausgabe erneut.
Nur sichere Projektionen gelangen in lokalen Reactzustand. Der Nachweis liefert
`execution_enabled:false`; Credential-Schreibfreigabe bleibt gesperrt.
[Ablauf und Abnahmegrenzen](passkey-action-proofs.md).
[Browservorschau](passkey-browser-proof.md).
Der isolierte IP-038-Assertionvertrag bindet eine gesonderte zweckgebundene
Freigabe an Actor, ursprüngliche OIDC-Sitzung, frische Passkeyzeit, Ziel/CAS,
unveränderte Bodybytes und eingefrorenen Metadatendigest. Eigene Audience/Kind
trennen ihn vom alten Signer;007-Confirm erteilt diese Freigabe nicht.
Signieren/Prüfen ist wiederholbar und liefert keinen Einmalverbrauch. Ein
künftiger dauerhafter Consumer muss Freigabe/Proof vor der Probe global
konsumieren und aktuelle Autorität bei Beginn und Schreiben erneut prüfen.
[Vertrag und fehlende Ausführung](passkey-credential-assertions.md).

## Bedrohungen und Kontrollen

| Bedrohung | Kontrolle / Abnahme |
|---|---|
| Kontoübernahme | MFA/Passkeys, sichere Recovery, Sessionsperre und Step-up |
| Mandantenübergriff | Autorisierung, DB-RLS, tenantgebundene Relationen, Negativtests |
| Brokerkey-Leak | Geschützte Übertragung/Speicherung, keine Ausgabe, Rotation und Audit |
| Manipulierte oder doppelte Orders | Command-ID, Frist, lokale Journale, idempotente Verarbeitung und Abgleich |
| Veraltete Daten | Frische-/Lückenprüfung, Expositionsstopp und sichtbarer Status |
| News-/AI-Prompt-Injection | Inhalte als Daten behandeln; kein Secret-/Ordertoolzugriff |
| Hostkompromittierung | Getrennte Serviceidentitäten, minimale Rechte, Updates und externe Schlüsselgrenze |
| Supply-chain-Risiko | Exakte Pins/Hashes, Lockdateien, Lizenz-/Sicherheitsprüfung |
| Daten-/Backupransomware | Geschützte externe Backupgenerationen, unabhängige Löschrechte, Verschlüsselung und Restoreübungen |
| Missbrauch/Überlastung | Rate-/Ressourcenlimits und Trennung von Forschung und Livepfad |

Absolute Sicherheit ist nicht zusicherbar. Kontrollen werden nachgewiesen und
Restrisiken dokumentiert, besonders Rootkompromittierung einer Einzel-VM.

## Identity und Tenantkontext

OIDC Authorization Code mit PKCE vorgeschlagen. Issuer, Audience,
Redirectziele, State und Nonce prüfen. Browser verwendet geschützte serverseitige
Sitzung mit `Secure`, `HttpOnly`, geeigneter `SameSite`-Policy und CSRF-Schutz.
Keine Bearertokens im Browser-LocalStorage.

MFA bevorzugt phishingresistent. Credentialänderung, Liveaktivierung und
wesentliche Risikoänderung erfordern Step-up. Mitgliedschaft und Kontorechte
werden serverseitig geprüft; Entzug beendet auch Streams und Jobs, soweit
deren Ausführung entsprechende Rechte voraussetzt.

In Q14 ist lokales Authelia bestätigt, mit stabiler Passwort-plus-
TOTP/WebAuthn-Policy. Benutzerprovisionierung und Recovery erfolgen kontrolliert.
Ein alleiniger Passkey-Login ist dort nicht automatisch ein belegter Zwei-Faktor-
Login. Die Cloudalternative ZITADEL braucht eine Datenverarbeitungsentscheidung
und einen belastbaren Mail-/Recoveryweg auch im Free-Tarif.

Für bereits eingerichtete MFA-Nutzer verlangen reguläre Faktoränderungen zusätzlich
den vorhandenen zweiten Faktor; Mail-only-Elevation ist keine gleichwertige
phishingresistente Prüfung. Q22 bevorzugt E-Mail als ausreichenden
Recoverynachweis; die damit vom Postfach abhängige Sicherheitsgrenze wird
ausdrücklich dokumentiert. Q24 bestätigt gesonderten administrativen
Reset mit Einmalchallenge, Sitzungssperre und anschließender MFA-Neuregistrierung.
Der Ablauf benötigt noch Implementierung und nachgewiesene Laufzeitabnahme.
File-Notifier ist nur für Entwicklung; Q21 bestätigt vorhandenen kostenlosen
SMTP mit TLS, Zustellung noch ungeprüft.
Konkrete Grenzen: [deployment-plan.md](deployment-plan.md).

RLS-/Cache-/Workergrenzen stehen in [architecture.md](architecture.md).
Unauthentifizierte Healthchecks enthalten keine Konten, Schlüssel oder
internen Konfigurationen.

## Brokercredentials

Authelia4.39.28 kann den bisherigen zweiten Faktor beim Passwort-Reauth
erhalten; `auth_time`/`amr=mfa` belegen keinen neu verwendeten Faktor.
Der Nutzer hat deshalb einen zusätzlichen Cockpit-Passkey bestätigt.
Dauerhafte Publickey-Registry, administratives Einmalticket und lokales
Browser-Enrollment sind implementiert. Das 32-Byte-Ticket liegt nur als Hash
in der DB, gilt höchstens600 Sekunden und wird vor der Kryptoprüfung
unwiderruflich beansprucht; Enrollmentversuche gelten höchstens120 Sekunden.
Registrierung verlangt exakten HTTPS-Origin/RP, UV/UP und ES256 mit
`fmt=none`. Sie ersetzt keinen frischen privaten Schlüsselnachweis durch
eine eigene Assertion. Counter-CAS allein verhindert keinen Challenge-Replay;
ein entsprechender HTTP-Endpunkt fehlt bewusst. Kontoänderungen bleiben
gesperrt. Einmalige zielgebundene Assertion-/Granttransaktionen und der
vollständige BFF-Enrollment-/Nachweisablauf sind synthetisch über echtes
HTTPS/API/PG geprüft; physische Geräteabnahme, echte E-Mail-Attestierung,
öffentliche Aktivierung und003/004-Integration fehlen weiterhin.
Enrollment erhält die ursprüngliche Sitzungsfrist und veröffentlicht Erfolg
erst nach autoritativem Faktor-Readback. Administrativer Widerruf erhöht die globale
Nutzer-Epoch und setzt `reauth_after`, sodass alle Tenant-Sitzungen ungültig
werden; terminale Registryeinträge erlauben derzeit keine Wiederherstellung.
[Passkeygates](passkey-step-up.md).

Schlüssel dürfen nach Einrichtung nur maskiert angezeigt werden.
Requestbodies, Authheader, URLs mit Querykeys, Exceptions, Traces und Dumps
müssen redigiert werden. Eine Debugoption darf das nicht umgehen.

Vorschlag: AEAD Envelope Encryption mit Tenant-/Accountbindung, Schlüsselversion
und getrenntem Root-of-Trust. API darf geschützt entgegennehmen; Research,
Marktinformationen und AI dürfen nicht entschlüsseln. Execution erhält nur die
benötigten konto-/zeitgebundenen Rechte.

Bitget: Lese-/Tradingrechte nur nach Bedarf, keine Withdrawal-/Transferrechte.
Feste Egress-IP und IP-Bindung prüfen. Demo-/Livekeys strikt getrennt.
Jeder Nutzer erstellt einen eigenen dedizierten API-Key samt Secret/Passphrase.
Classic mit getrennten Wallets ist für das Nutzerkonto bestätigt; signierte
UID-/Parent-/Rechteprüfung und tenantgebundene Speicherung vor echter Einrichtung.
Schlüsselwechsel muss dieselbe Brokeridentität bestätigen. Der lesende M1-Zugang
weist Write-/Transfer-/Withdrawal-/Manage- und unbekannte Rechte ab.
Einrichtungsablauf und API-Familiengrenzen:
[bitget-connection.md](bitget-connection.md).
MT5: geschützte Geräteidentität, festes Konto, Ablauf-/Replayprüfung und
ausgehendes HTTPS vom separaten Heimnetzserver zum zentralen Einstieg.
Keine eingehenden Heimnetzports. Maschinenidentität und feste Tenant-/Demo-
Kontobindung ersetzen dort den interaktiven Browserlogin; es gibt keinen
unauthentifizierten Bridgepfad. Details: [mt5-bridge.md](mt5-bridge.md).

Im ersten Paperrelease besitzen reale Kontoverbindungen nur Leserechte.
Paper simuliert lokal, Demo verwendet eigene Konten/Keys. Echtgeld-Dispatch
bleibt unabhängig von der Frontendanzeige serverseitig gesperrt.
Tradingrechte werden erst beim separat freigegebenen Liveübergang ergänzt.

Ein auf derselben VM gespeicherter Rootkey bietet keinen ausreichenden Schutz
gegen deren vollständige Kompromittierung. Eine Free-only-Lösung muss diese
Grenze transparent halten; bei unzureichendem Schutz wird Echtgeldbetrieb
zurückgestellt, statt eine falsche Sicherheitsgarantie auszugeben.
Backup und Wiederherstellung schließen die erforderlichen Schlüssel ein,
ohne sie gemeinsam ungeschützt mit Ciphertext abzulegen.

Der isolierte [Credentialkern](../packages/credentials/README.md) verwendet
AES-256-GCM aus der gepinnten Cryptography-Bibliothek: eigener zufälliger DEK
je Payload, versionierter KEK für dessen Schutz und getrennte authentifizierte
Bindungsdaten für Payload und DEK. Ciphertextmanipulation oder falsche
Tenant-/Nutzer-/Konto-/Broker-/Revisionsbindung wird abgewiesen.
Rewrap prüft zuvor beide bestehenden AEAD-Schichten. 20 Offline-Tests bestanden;
kein echter Nutzerkey oder Runtime-Schlüsselprovider eingerichtet.
Der [Credentialstore](../services/credentials/README.md) prüft tatsächliche LOGIN-
Identität und die über `SESSION_USER` gebundene aktive Tenant-/Nutzerzuordnung.
Private Tabellen haben FORCE RLS; API und Research haben weder Tabellenzugriff
noch Ausführungsrechte auf die Credentialfunktionen. Jede Operation prüft
Mitgliedschaft und Kontobindung. Credentialrevision und Speicherversion werden
atomar verglichen; Rewrap erhält den Payload, Widerruf ist terminal und auch bei
pausiertem Konto ohne den alten KEK möglich.

Die zusätzliche private Einrichtung verifiziert eine gesondert signierte,
body-/zielgebundene BFF-Assertion mit frischer Authzeit ab Schrittflowstart.
Migration004 konsumiert deren JTI vor der Probe dauerhaft; Replay kann keine
zweite Probe starten. Identität/Auth-Epoch, Reauth-Grenze, Konto, Ablaufzeit und
Versionen werden vor der Änderung erneut geprüft. Änderung und Abschlussaudit
sind atomar; ein unbekannter Commitausgang verlangt Abgleich statt Wiederholung.
SQL vertraut der Python-Signaturprüfung und beweist keine Browser-MFA.
Bestehende direkte Storefunktionen erzwingen diesen höheren Vertrag nicht.

120 Client-/Onboarding-/PostgreSQL-Tests bestanden mit ausschließlich
synthetischen Daten, davon 60 tatsächliche PG-Fälle. Vier Provisionierungstests
und eine zurückgerollte Rollen-Driftprüfung waren im Storecheckpoint grün. Die
separate Fixture-DB isoliert Testdaten; der administrative Checkcontainer besitzt
die Migrationsidentität und kann damit auch die Entwicklungsdatenbank erreichen.
Es gibt noch keinen Betriebsdienst oder HTTP-Keyeingang. Der explizite
Entwicklungs-Dateiprovider prüft feste Fingerprints, Dateityp, Eigentümer und
Modi; bei Kontrolle über VM-root schützt diese Grenze nicht. Unabhängig
vertrauenswürdige Fingerprintkonfiguration bleibt erforderlich. Betriebsprovider,
physische MFA-Abnahme, Credentialintegration, gemeinsame Nutzungslimits und
externer Restore bleiben Voraussetzungen.
Ein vollständiger Rollback von DB und Ciphertext wird durch die aktuelle
Revisionsprüfung allein nicht erkannt. Widerruf entfernt bereits ausgelieferten
Klartext nicht aus Prozessen; vor künftigem Brokerdispatch erneut autorisieren.

## Befund: bereits versionierte Schlüsseldatei

Bei Projektstart ist `secrets/secrets.keys` bereits Git-getrackt.
Inhalte wurden nicht gelesen. Der Pfad wird ignoriert und aus zukünftigen
Snapshots entfernt, die lokale Datei bleibt erhalten.

Das beseitigt vorhandene Commits nicht. Falls echte Credentials enthalten sind:
betroffene Zugänge identifizieren, widerrufen/rotieren, Berechtigungen und
Zugriffsprotokolle prüfen. Keine Schlüssel in Tickets oder Chats kopieren.
Anschließend Historybereinigung, Remote-/Clonekoordination und gegebenenfalls
Force-Push ausdrücklich abstimmen. Der Nutzer hat Zwischenstand-Pushes inzwischen
beauftragt; die historische Datei lag bereits auf remote main. Neue Snapshots
schließen Secrets aus. Rotation und Historyremediation bleiben IP-005.

## Netz und Dienste

Ein zentraler TLS-Einstieg; private Einladung, keine öffentliche Registrierung.
Q20 plant den HTTPS-Einstieg bereits für diesen Privatpilot öffentlich.
Datenbank, Secrets, Metriken und interne Worker sind nicht öffentlich.
Die Domain `cockpit.investalo.de` ist für die ausdrücklich freigegebene
Entwicklungsvorschau aktiv. Vollständiger Pilot-/Produktionsrollout bleibt
separat; [Zugang und Gates](https-entry.md).
Forwarded-Headers nur vom eigenen Proxy übernehmen; Rate Limits und
unauthentifizierte Login-/Recoverypfade bei der öffentlichen Abnahme prüfen.

Bei der bestätigten Dockerbereitstellung interne Ports nicht öffentlich publishen:
Docker-Portregeln können UFW-/firewalld-Regeln umgehen. Keine Docker-Socket-
Mounts im Cockpit/API; tatsächliche externe Erreichbarkeit prüfen.

Keine Applikation als Root; dedizierte Identitäten, restriktive Dateirechte,
begrenzte Schreibpfade und Ressourcen, passende AppArmor-/Sandboxkontrollen.
Host-/SSH-/Firewalländerungen erst mit dokumentiertem Zugangserhalt und
Wiederherstellungspfad. Der lokale Adminskill beschreibt Ubuntu 24.04;
Kommandos müssen für den tatsächlichen 26.04-Host überprüft werden.

## Datenschutz und Freigabe

Datenminimierung, getrennte Audit-/Fachdatenfristen, Export/Löschung und
Backuplöschung planen. Externe AI erhält keine Schlüssel, Identitäten oder
privaten Kontodaten ohne konkrete Freigabe und geprüfte Verarbeitung.
Offizielle Marktinformationen sind nicht automatisch frei redistributierbar.

Vor Echtgeld/Produktion: Threat Model, Tenant-/RBAC-Negativtests,
Secretrotation, Bridge-Replaytests, unsichere Ordertimeouts, Backuprestore und
Kill-Switch nachweisen. Neue externe Konten, kostenpflichtige Dienste und
CI/CD-Abhängigkeiten erst nach der jeweils erforderlichen Abstimmung.
