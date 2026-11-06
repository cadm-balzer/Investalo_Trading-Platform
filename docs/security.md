# Sicherheitskonzept

Stand 2026-11-07. Verbindliche Leitlinien aus AGENTS.md:
private Bereitstellung, Verschlüsselung und minimale Rechte.
Docker Compose und lokales Authelia sind in Q13/Q14 bestätigt;
konkrete Pins, Schlüsselbereitstellung und Recoveryabläufe bleiben offen.

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

Für bereits eingerichtete MFA-Nutzer verlangen Faktoränderungen zusätzlich
den vorhandenen zweiten Faktor; Mail-only-Elevation ist keine gleichwertige
phishingresistente Prüfung. Unabhängiger Ersatz und Recoveryweg folgen Q22.
File-Notifier ist nur für Entwicklung, produktiver SMTP-Weg folgt Q21.
Konkrete Grenzen: [deployment-plan.md](deployment-plan.md).

RLS-/Cache-/Workergrenzen stehen in [architecture.md](architecture.md).
Unauthentifizierte Healthchecks enthalten keine Konten, Schlüssel oder
internen Konfigurationen.

## Brokercredentials

Schlüssel dürfen nach Einrichtung nur maskiert angezeigt werden.
Requestbodies, Authheader, URLs mit Querykeys, Exceptions, Traces und Dumps
müssen redigiert werden. Eine Debugoption darf das nicht umgehen.

Vorschlag: AEAD Envelope Encryption mit Tenant-/Accountbindung, Schlüsselversion
und getrenntem Root-of-Trust. API darf geschützt entgegennehmen; Research,
Marktinformationen und AI dürfen nicht entschlüsseln. Execution erhält nur die
benötigten konto-/zeitgebundenen Rechte.

Bitget: Lese-/Tradingrechte nur nach Bedarf, keine Withdrawal-/Transferrechte.
Feste Egress-IP und IP-Bindung prüfen. Demo-/Livekeys strikt getrennt.
MT5: geschützte Geräteidentität, festes Konto, Ablauf-/Replayprüfung und
privater ausgehender Kanal.

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

## Befund: bereits versionierte Schlüsseldatei

Bei Projektstart ist `secrets/secrets.keys` bereits Git-getrackt.
Inhalte wurden nicht gelesen. Der Pfad wird ignoriert und aus zukünftigen
Snapshots entfernt, die lokale Datei bleibt erhalten.

Das beseitigt vorhandene Commits nicht. Falls echte Credentials enthalten sind:
betroffene Zugänge identifizieren, widerrufen/rotieren, Berechtigungen und
Zugriffsprotokolle prüfen. Keine Schlüssel in Tickets oder Chats kopieren.
Anschließend Historybereinigung, Remote-/Clonekoordination und gegebenenfalls
Force-Push ausdrücklich abstimmen. Die Planung wird deshalb zunächst nur
lokal committed und nicht ungeprüft gepusht.

## Netz und Dienste

Ein zentraler TLS-Einstieg; private Einladung und zunächst privater Zugang.
Datenbank, Secrets, Metriken und interne Worker sind nicht öffentlich.
Der spätere Domainzugang `cockpit.investalo.de` braucht eigene
Produktionsfreigabe und bewusste Zugangsentscheidung.

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
