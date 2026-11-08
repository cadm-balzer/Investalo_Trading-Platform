# Isolierter Credentialdienst für Entwicklungsprüfungen

IP-043 startet den [privaten Credentialexecutor](passkey-credential-execution.md)
in einem eigenen Container. Die administrative Fixture richtet Testdaten ein
und prüft das Ergebnis; ausschließlich der getrennte Dienst konsumiert die
Freigabe und schreibt Credentials. Der vorhandene
[Entwicklungs-HTTPS-Adapter](passkey-credential-https.md) bleibt ein synthetischer
Prüfstand. Reale API-Schlüssel werden vor Verifier, 008-Consume und Probe
abgewiesen. Es gibt keinen tatsächlichen Brokertransport.

## Feste Identität und Startprüfung

Der Launcher verlangt ausdrücklich `--development` und UID 10003. Ohne diese
Option öffnet das Image keinen Listener. Die vertrauenswürdige Konfigurationsdatei
enthält exakt Schema, Tenant/User, synthetische Broker-UID sowie SHA256-Pins
für Signaturschlüssel, KEK und erlaubtes BFF-Clientzertifikat.
Pfad, PostgreSQL-Host, Fixture-Datenbank, LOGIN, Issuer und Origin sind im
Entwicklungslauncher festgelegt; Requestdaten und Umgebungsvariablen wählen
keine Rolle, Verbindung oder Schlüssel. Geerbte `PG*`-Variablen werden abgewiesen.

Vor dem Listener prüft der Dienst die tatsächliche `SESSION_USER`-/`CURRENT_USER`-
Identität, gefährliche Rollenattribute, aktuellen Tenant/User und notwendige
008-/009-Funktionsrechte. Die Rolle hat keinen Zugriff auf das Migrationledger;
dessen unveränderte Prüfsummen prüft die administrative Fixture.
Neue Verbindungen sind ungepoolt, ohne Autocommit oder automatische Wiederholung,
mit CA-/Hostnamenprüfung sowie Verbindungs-, Statement- und Lockfristen.
Die bestehenden Prüfungen im Store bleiben zusätzlich wirksam.

Signaturschlüssel und KEK sind getrennte 32-Byte-Dateien mit festen Fingerprints.
Private Konfiguration und TLS-Dateien sind reguläre, einfach verlinkte Dateien.
Sie gehören UID 10003 und haben Modus 0400. Der vorhandene
`DevelopmentKeyFileProvider` verlangt zusätzlich eine KEK-Ablage mit Modus 0700.
Dateideskriptoren und `NOFOLLOW`
verhindern das Nachladen ersetzter Pfade. Der vorhandene öffentliche PostgreSQL-
CA-Bestand bleibt mit Modus 0444 lesbar. Kein neuer Verschlüsselungs- oder Signaturvertrag.

## Container und vollständiger Ablauf

Das zusätzliche opt-in Profil verwendet ein gepinntes Runtimeimage aus den
bestehenden Credentiallocks, ohne Tests oder administrative Werkzeuge.
Der Dienst hat UID/GID 10003, keine Zusatzgruppen oder Capabilities, ein
schreibgeschütztes Rootfilesystem, `no-new-privileges`, Ressourcenlimits und
keine Logs oder Hostports. Er erreicht ausschließlich die interne Datenbank
und das interne Testnetz.

Mounts umfassen nur sein Credential-LOGIN-Passwort, öffentliche PG-CA,
eigene Konfiguration, Signaturschlüssel, KEK und Server-TLS-/Client-CA-Dateien.
Migrations-, API-/Research-Credentials und der private BFF-Clientschlüssel
werden nicht gemountet. Eine begrenzte Docker-Metadatenprüfung kontrolliert
diese Eigenschaften ohne Environment-, Secret- oder Logausgabe.

Der Hostrelay startet den Dienst erst nach administrativer Einrichtung. Seine
Bereitschaftsprüfung wiederholt ausschließlich lesende TLS-/GET-Anfragen;
Credentialrequests werden nie wiederholt. Der TS-Treiber führt echte
SimpleWebAuthn-/Jose-/API-007-/008-Schritte über mTLS aus: Register, Replace,
Revoke, unveränderter UTF8-Body, fremdes Clientzertifikat, manipulierte Bodybytes
und Replay. Der administrative Checker prüft danach 003-Ciphertext/AAD,
CAS-Fortschritt und 009-Abschluss im selben finalen Transaktionskontext.
Er führt im Dienstmodus keinen Credentialexecutor oder Consume aus.

Das Vorbereitungsscript erzeugt ausschließlich eine markierte synthetische
0700-Ablage unter `/tmp`. Jeder Lauf erzeugt darin neue UUID-Verzeichnisse
und 0400-Dateien einmalig; bestehende Dateien werden nicht überschrieben.
Die Dateien bleiben für die nachvollziehbare lokale Prüfung erhalten und
werden nicht durch automatische destruktive Bereinigung entfernt.
Clientidentität, JWTs und Bodies werden weiterhin nur durch private begrenzte
Prozesspipes übergeben. Nach einem Neustart lässt sich der synthetische Bestand
neu erzeugen. [Konkrete Prüfkommandos](../infra/README.md).

## Abnahme und verbleibender Betrieb

Die Abnahme prüft Startbedingungen, Dateisicherheit, feste Datenbankidentität
und den kompletten synthetischen Ablauf im getrennten Dienst. Angewendete
001–009, bestehende öffentliche Dienste und Flags bleiben unverändert:
`investalo` bleibt bei 001–007, `investalo_credentials_checks` bei 001–009.

401 Tests und 52 Subtests bestanden im gepinnten Credentialcontainer
(19 Client, 161 Offline einschließlich 25 neuer Launcherfälle, 221 tatsächliche
PG-Fälle). Zehn Hosttests prüfen die geschützte Vorbereitung mit tatsächlichen
UIDs. Der getrennte Dienstablauf bestand 440 integrierte Prüfpunkte.
Sein Image beendet sich ohne `--development` mit statischem Fehler vor dem
Netzwerkstart. Runtime-/Python-/Node-Images wurden mit bestehenden Pins gebaut.
Unabhängiger Review hat keinen verbleibenden Blocker.
Der bisherige injizierte HTTPS-Ablauf bestand erneut 387, die Pipevariante 329
Prüfpunkte.
Diese Läufe überlappen und werden nicht als unabhängige Tests addiert.
Die vollständigen Migrationsprüfsummen beider Datenbanken wurden lesend mit
den SQL-Dateien verglichen. Die historischen 440 Cockpit- und 572 API-/Workertests
werden hier nicht erneut gezählt; deren Anwendungscode blieb unverändert.
Eigene Fixturecontainer sind beendet. Sechs öffentliche Dienste laufen
unverändert; beide Domains liefern bei regulärer TLS-Prüfung HTTP 200.

Die Containertrennung beweist die Entwicklungsgrenze; der synthetische
Dateiprovider schützt nicht vor VM-Root oder vollständigem DB-Rollback.
Ein geeigneter Produktions-HTTP-Server, provisionierte Betriebsidentitäten,
extern abgesicherter Schlüsselbetrieb, reale Egress-/Brokerprüfung,
Quoten/Reconciliation/Recovery, Browser-Keyeingabe und physische Geräteabnahme
bleiben vor echter Kontoverbindung offen. Python empfiehlt `http.server`
ausdrücklich nicht für Produktion. Öffentliche Aktivierung, Produktion und
Echtgeld behalten ihre gesonderten Freigaben.

Offizielle Grundlagen:
[Python Servergrenzen](https://docs.python.org/3.14/library/http.server.html),
[PostgreSQL Verbindungsparameter](https://www.postgresql.org/docs/18/libpq-connect.html#LIBPQ-PARAMKEYWORDS),
[Docker Compose Services](https://docs.docker.com/reference/compose-file/services/).
