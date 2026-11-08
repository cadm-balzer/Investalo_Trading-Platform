# Privater Entwicklungs-HTTPS-Transport für Credentials

IP-042 ergänzt die injizierte [Cockpit-Orchestrierung](passkey-credential-cockpit.md)
um einen getrennten HTTPS-Übergang zum [privaten Executor](passkey-credential-execution.md).
Der Pythonadapter ist standardmäßig deaktiviert und ausschließlich für lokale
Entwicklungsprüfungen gedacht. Kein Produktionslauncher, Browserformular,
öffentlicher Dienst oder tatsächlicher Brokertransport wird aktiviert.

## Unabhängige Transportidentität

Der Server verlangt ein Clientzertifikat aus einer eigenen vertrauenswürdigen CA
und den fest konfigurierten SHA256-Fingerprint des erlaubten BFF-Zertifikats.
Ein anderes gültiges Zertifikat derselben CA reicht nicht. TLS mindestens1.2,
CA- und Hostnamenprüfung bleiben zwingend. Die synthetische Fixture erzeugt
eine separate kurzlebige CA samt Server-/Clientzertifikaten; öffentliche
Caddy-/API-Zertifikate verleihen keine Credentialrechte.

Nach authentifiziertem TLS übergibt der BFF einen strikten Kontextheader aus der
bereits autorisierten ursprünglichen Sitzung. Er enthält ausschließlich
Tenant, User, Subject, Epoch, OIDC-Zeit, Sitzungsbindung und ursprüngliche
Sitzungsfrist. Der konfigurierte `StoreContext` legt Tenant/User und
`SESSION_USER`-Rolle unabhängig fest. Rollen, DSN, Origin, Issuer, KEKs und
Provider werden niemals aus Requestdaten gewählt.

Der separate Passkey-JWT bleibt undurchsichtig für den TS-Transport.
Seine Claims werden nicht benutzt, um den erwarteten Sitzungskontext zu erzeugen.
Der vorhandene Pythonverifier vergleicht ihn mit diesem unabhängigen Kontext;
008 und009 erzwingen weiter Einmalverbrauch, aktuelle DB-Bindung und atomaren
Abschluss. mTLS ersetzt weder Passkeynachweis noch ausdrückliche Zustimmung.

## Drahtvertrag und Grenzen

Nur `POST /v1/credentials/bitget/register`, `/replace` und `/revoke` sind
zugelassen. `Authorization: Bearer` enthält den bestehenden Passkey-JWT;
`X-Investalo-Credential-Context` trägt kanonisches Base64url-JSON mit exakt
sieben Feldern. Der Rawbody ist das unveränderte UTF8-Credentialobjekt,
höchstens4096 Byte. Keine zusätzliche Umschreibung oder JSON-Normalisierung.

Requestzeile, einzelne und gesamte Header, Body, Zeit und Parallelität sind
begrenzt. Doppelte Steuerheader, Transfer-Encoding, Content-Encoding, Expect,
gefaltete Header und Pfade mit Query werden abgewiesen. Jede Verbindung
verarbeitet einen Request und wird geschlossen; keine Keepalive-/Pipelineausführung.
Ausgaben enthalten statische Fehler oder ausschließlich Connection-ID,
Credentialrevision, Speicherversion und Status. Keine Standardzugriffslogs,
Treiberexceptions, Requestheader, JWTs oder Rohschlüssel in der Ausgabe.

Der TS-Client verwendet einen eigenen HTTPS-Agent ohne Proxy-/Redirect-/
Retryverhalten. Er prüft Antwortgröße, Framing, striktes JSON und erwarteten
CAS-Fortschritt. Eine Gesamtfrist schließt auch langsame Antworten ein.
Ein verlorener oder verspäteter Erfolgsresponse kann nach einem tatsächlichen
Commit auftreten: kein automatischer zweiter Request, kein Erfolgsversprechen
und kein Überschreiben des dauerhaften Abschlussaudits. Zustand zuerst abgleichen.

## Fixture und verbleibende Arbeit

Die opt-in Prüfung `check_passkey_credential_cockpit.py --orchestrate --https`
führt echte TS-/WebAuthn-/API-/PostgreSQL-/Jose-/Python-/AEAD-Schritte über
gegenseitiges TLS aus. Nur der administrative Fixturecontainer hat
Migrationscredentials; er ist kein Modell für einen Runtime-Credentialdienst.
Die TLS-Dateien entstehen ausschließlich in dessen temporärem Containerpfad,
synthetische Clientidentität und Bodies reisen durch private begrenzte Pipes.
Keine Hostports, neuen Abhängigkeiten oder Migrationen.
`investalo` bleibt001–007; die Fixture bleibt001–009.

Die vollständige gepinnte Credentialsuite bestand mit376 Tests und37 Subtests
(19 Client,136 Offline einschließlich20 neuer HTTP-/mTLS-Fälle,221 tatsächliche
PG-Fälle).440 Cockpittests einschließlich55 neuer Transportfälle und Typecheck
bestanden.346 integrierte HTTPS-/mTLS-Prüfpunkte bestanden; die unverändert
verfügbare Pipevariante bestand erneut mit306 Prüfpunkten. Diese beiden Läufe
überlappen und sind keine Summe unabhängiger Fälle. Unabhängiger Review hat
keinen verbleibenden Blocker. Der frühere572-API-/Workerlauf aus IP-041 wurde
hier nicht erneut gezählt; API und Migrationen bleiben unverändert.
Gepinnte Python-/Node-Fixturebuilds und der Cockpitbuild bestanden.
Beide Fixture-APIs sind gestoppt; sechs öffentliche Dienste gesund,
reguläre TLS-Prüfung des Cockpits liefert200. Laufende Vorschaucontainer
wurden nicht ersetzt.

Python dokumentiert ausdrücklich, dass `http.server` nur grundlegende
Sicherheitsprüfungen besitzt und nicht für Produktion empfohlen ist. Der
zusätzlich begrenzte Adapter ist daher ein Entwicklungsprüfstand.
Ein geeigneter Produktionsserver, isolierter Launcher, externe Schlüsselgrenze,
provisionierte Signatur-/Transportidentitäten, Quoten/Egress, Recovery und
physische Browserabnahme bleiben vor echter Keyannahme offen.

Offizielle Grundlagen: [Python HTTP-Server](https://docs.python.org/3.14/library/http.server.html),
[Python TLS](https://docs.python.org/3.14/library/ssl.html) und
[Node HTTPS](https://nodejs.org/api/https.html).
