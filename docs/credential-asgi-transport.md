# ASGI-Transport für den isolierten Credentialdienst

IP-044 verwendet im [synthetischen Credentialdienst](credential-development-service.md)
den bereits projektweit gepinnten Uvicorn-/h11-Stack statt des bisherigen
stdlib-HTTP-Servers. Der lokale Launcher bleibt ausdrücklich im Entwicklungsmodus
und akzeptiert ausschließlich die vorhandenen synthetischen Keytriples.
Schlüsselprovider, Datenbankidentität und Freigabe-/AEAD-Verträge bleiben erhalten.

## TLS und Ressourcen vor der Requestverarbeitung

Ein kontrollierter Listener nimmt höchstens vier Verbindungen an, einschließlich
laufender TLS-Handshakes. Er übergibt angenommene Sockets über die dokumentierte
`loop.connect_accepted_socket`-Schnittstelle an das gepinnte HTTP-Protokoll.
Die bereits aus geprüften Dateideskriptoren geladene TLS-Konfiguration verlangt
Clientzertifikate, eine eigene CA und mindestens TLS 1.2.
Das Protokoll prüft den tatsächlichen SHA256-Fingerprint des Peerzertifikats
vor jeder HTTP-Verarbeitung. Ein ASGI-HTTPS-Scheme oder Requestheader begründet
diese Transportautorität nicht.

Die absolute Verbindungsfrist beginnt bei Annahme des Sockets und umfasst
Handshake, Header, Body und Antwort; der Launcher setzt 20 Sekunden.
Sie wird nach dem Handshake nicht neu
gestartet. Die Standardfristen des Servers werden nicht stillschweigend
übernommen. Überlast schließt die Verbindung ohne Credentialausführung.

Verbindungen und laufende Executoraufrufe haben getrennte Begrenzungen.
Ein geschlossener Socket beendet keinen bereits laufenden PostgreSQL-Commit.
Ein Arbeitsslot bleibt deshalb bis zum tatsächlichen Ende des Worker-Futures
belegt; ein Threadpool mit unbegrenzter Queue würde hier nicht genügen.
Timeout, Disconnect oder Shutdown lösen keine automatische Wiederholung aus.
Ein unbekannter Commit bleibt anhand des dauerhaften Zustands abzugleichen.

## Strikter Drahtvertrag

Der bestehende [HTTPS-Vertrag](passkey-credential-https.md) bleibt maßgeblich:
drei feste POST-Pfade, separat vom BFF übergebener ursprünglicher Sitzungskontext,
eigener Passkey-JWT und unveränderte UTF8-Bodybytes mit höchstens 4096 Byte.
Nur sichere Ergebnisfelder oder statische Fehler werden zurückgegeben.

Ein begrenzter Rawheader-Guard prüft Requestzeile, CRLF-/ASCII-Grammatik,
Headergrößen und doppelte Steuerheader vor h11. Das ist notwendig, weil h11
gefaltete Header normalisiert und identische Content-Length-Duplikate
zusammenführen kann. Die spätere ASGI-Sicht könnte solche Abweichungen nicht
mehr zuverlässig feststellen. Query, Pfadnormalisierung, Upgrade, Kompression
und uneindeutiges Framing werden nicht als erlaubte Requests behandelt.

Jede authentifizierte Verbindung verarbeitet höchstens einen Request und
antwortet mit `Connection: close`. Proxyheader, WebSockets, Lifespan,
Accesslogs und Exceptionausgaben sind deaktiviert. Der bestehende Executor
prüft unabhängig weiterhin ursprüngliche Sitzung, zweckgebundene Zustimmung,
aktuellen Actor/Faktor und Einmalverbrauch vor Probe und Mutation.
Asyncio-Debug und zusätzliche Uvicorn-Worker werden ausdrücklich ausgeschlossen;
Umgebungsvariablen dürfen keine privaten Callbackargumente protokollieren oder
die feste Kapazität verändern. Die Acceptschleife gibt den Eventloop auch bei
sofort verfügbaren, abzuweisenden Sockets frei, damit Fristen weiter greifen.

## Pins, Prüfung und verbleibende Gates

Der Credentiallock übernimmt die bestehenden API-Pins samt Hashes:
Uvicorn 0.54.0, h11 0.16.0 und click 8.5.1. Es gibt keine neue Paketversion
oder CI-Werkzeugabhängigkeit. Die dokumentierten asyncio-Socket-Schnittstellen
werden verwendet; die Kopplung an Uvicorns `H11Protocol` und `ServerState`
bleibt versionsspezifisch. Upgrades benötigen echte TLS-/Rawframing-/Fristtests
und eine Prüfung der Protokollanbindung.

419 Credentialtests und 52 Subtests bestanden unter gepinntem Python 3.14.10
in 154,35 Sekunden. Darin enthalten sind 18 neue echte TLS-/ASGI-Fälle:
fehlende/falsche/ungebundene Clientzertifikate, Rawframing, exakte Bytes,
Handshakefristen und Slotfreigabe, Disconnect/Timeout während laufender Arbeit,
Shutdown ohne Retry, kopierte Scopes und stille Fehlerausgaben.
Die übrigen Credentialfälle einschließlich 221 tatsächlicher PostgreSQLtests
wurden erneut geprüft.

451 tatsächliche Prüfpunkte im getrennten TS-/WebAuthn-/API-/PostgreSQL-/
Python-/mTLS-Dienstablauf bestanden: Register 1/1, Austausch 2/2,
Widerruf 2/3, AEAD und terminaler Abschlussaudit. Beide Pythonimages wurden mit
Hashlocks gebaut; das Runtimeimage ohne `--development` beendet sich mit
statischem Fehler vor dem Listenerstart. Unabhängiger Review ohne Restblocker.
Historische 440 Cockpit-/572 API-Workertests und die zusätzlichen älteren
HTTPS-/Pipeintegrationen wurden nicht erneut ausgeführt; deren Code blieb
unverändert. Historische Läufe werden nicht zur neuen Abnahme addiert.

Keine neue Migration oder öffentliche Ports/Flags; alle aktuellen
Migrationsprüfsummen stimmen überein: Entwicklung 001–007, Fixture 001–009.
Alle Testcontainer sind beendet. Die sechs öffentlichen Dienste wurden nicht
neu erstellt; Cockpit und Auth liefern mit regulärem TLS HTTP 200.

Dieser Checkpoint ersetzt den HTTP-Unterbau im synthetischen Prüfstand.
Provisionierte Betriebsidentitäten, externer Schlüsselbetrieb, reale
Broker-/Egressprüfung, Quoten/Reconciliation/Recovery sowie Browser-Keyeingabe
und physische Geräteabnahme bleiben vor echter Kontoverbindung offen.
Produktions- und Echtgeldfreigaben folgen weiterhin gesondert.

Offizielle Grundlagen:
[Python asyncio Socketübergabe](https://docs.python.org/3.14/library/asyncio-eventloop.html#asyncio.loop.connect_accepted_socket),
[Uvicorn Serververhalten](https://www.uvicorn.org/server-behavior/),
[ASGI TLS-Erweiterung](https://asgi.readthedocs.io/en/latest/specs/tls.html),
[h11 API](https://h11.readthedocs.io/en/latest/api.html).
