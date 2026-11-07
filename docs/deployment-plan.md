# Compose- und Identityplan für den Privatpilot

Stand 2026-11-07. Q13 bestätigt Docker Compose, Q14 lokales Authelia.
Q31 bestätigt die lokale Implementierung. Eine ausführbare Testkonfiguration
steht unter [infra/README.md](../infra/README.md), Pins unter
[runtime-pins.md](runtime-pins.md). Sie bindet ausschließlich Loopback und
verwendet generierte `.invalid`-Testidentitäten; der folgende Plan beschreibt
weiterhin die vollständige Pilotabnahme. Q20 bestätigt einen öffentlichen
zentralen HTTPS-Einstieg für den privaten Nutzerkreis; Q21 bestehenden
kostenlosen SMTP. Q24 bestätigt administratives E-Mail-Recovery; Q27
Pilotbackupziele. Siehe [architecture.md](architecture.md).

## Services und Berechtigungen

| Service | Zweck | Zulässiger Zugriff |
|---|---|---|
| Zentraler TLS-Proxy | Ein Einstieg, Routing zu Cockpit/IdP | Ein bewusst gebundener Hostport; keine DB-/Workerports |
| Cockpit/BFF | Oberfläche, OIDC-Codeflow und Anwendungssitzung | API und IdP; keine Brokerkeys |
| API | Tenant-/Kontobindung und autorisierte Anwendungsfälle | Eigene eingeschränkte Plattformrolle |
| PostgreSQL | Führende operative Persistenz | Nur interne Netze; getrennte Plattform-/IdP-Datenbanken und Rollen |
| Authelia | Lokale Authentifizierung, MFA und OIDC | Nur eigene IdP-Datenbank, administrierter Nutzerbestand und Notifier |
| Daten-/Signalworker | Marktdaten, Strategie und Risikoprüfung | Nur erforderliche Plattformdaten; kein allgemeiner Secretzugriff |
| Paper/Execution/Reconciliation | Kontrollierte Ausführung und Brokerabgleich | Eigene Rollen; Echtgeld-Dispatch zunächst gesperrt |
| Researchworker | Reproduzierbare Backtests | Eigenes Profil und Ressourcenbudget, kein Brokersecretzugriff |

Die fachlichen Worker können anfangs mit wenigen Prozessen betrieben werden,
ohne Berechtigungsgrenzen zwischen Research und Execution zusammenzulegen.
Keine neuen Redis-/Monitoringvollstacks allein für diesen Start.

Container: explizite Nonroot-Identität, minimale Capabilities, kein
privilegierter Modus und kein Docker-Socket. Schreibpfade und temporäre
Verzeichnisse ausdrücklich begrenzen. Ein Imageentrypoint darf nicht
unbemerkt zunächst als Root laufen, nur weil `PUID/PGID` gesetzt wurden.
Exakte Versionen/Digests und Lockdateien werden vor Bootstrap geprüft.

## Netze und TLS

Nur der Proxy erhält eine explizite Hostbindung. Interne Services haben keine
öffentlich veröffentlichten Ports. Q20 plant bereits für den eingeladenen
Privatpilot einen öffentlichen HTTPS-Einstieg; Entwicklung kann weiterhin über
Loopback/Tunnel erfolgen. Kein öffentlicher Signup oder freier Kontozugriff.
Eingehende Forwarded-Headers entfernen und ausschließlich den Proxy als
vertrauenswürdige Quelle behandeln. Tatsächliche Erreichbarkeit wird geprüft.
Docker-Portregeln können Hostfirewallregeln umgehen.

Authelia benötigt einen Standarddomainnamen mit Punkt und HTTPS; `localhost`
oder eine reine IP als Sessiondomain reichen nicht.
Vorgeschlagen sind kontrollierte Namen unter `cockpit.investalo.de`,
beispielsweise `auth.cockpit.investalo.de`, ohne DNSänderung in dieser Phase.
Auflösung, Zertifikat, Browsername und OIDC-Redirect müssen zusammenpassen.
Eine Domainwahl darf Sessioncookies nicht unnötig an die bestehende Website
weiterreichen.

Bei interner CA müssen Browser und OIDC-/API-beteiligte Container ihr vertrauen.
Keine deaktivierte Zertifikatsprüfung. Für WebAuthn stabile RP-/Hostnamen
festlegen, damit spätere Umbenennungen nicht unbemerkt Neuregistrierung erfordern.
Für öffentliche Zertifikate Challenge festlegen: HTTP-01 benötigt Port 80;
DNS-01 einen TXT-Eintrag. Zusatzports oder DNS-Änderungen nicht ungeprüft
vornehmen. Q20 ist eine Planentscheidung; der tatsächliche öffentliche
Pilot-/Produktionsrollout braucht weiterhin separate Freigabe.

## Authelia, Sessions und Datenbank

Ein Authelia-Prozess mit In-Memory-Sessions ist für diesen kleinen privaten
Start vorgesehen. Redis ist dafür keine Pflicht. IdP-Neustarts verlieren diese
Sessions; bereits ausgegebene Tokens oder BFF-Sessions werden dadurch nicht
automatisch widerrufen. Logout, Entzug und Recovery behandeln alle Schichten.

OIDC: Codeflow, PKCE `S256`, exakte Redirects, minimale Scopes und ausdrücklich
`two_factor` am Client. Eine Reverse-Proxy-2FA-Regel ersetzt diese Clientpolicy
nicht. Tokens verbleiben serverseitig; Browser bekommt eine geschützte Sitzung.
Tenantrechte liegen weiterhin in der Tradingplattform.

Plattform und IdP besitzen getrennte PostgreSQL-Datenbanken/-Rollen.
Standardrechte von `PUBLIC` und `CONNECT` ausdrücklich begrenzen.
Keine Superuser-/`CREATEDB`-/`CREATEROLE`-Rechte für den IdP.

**Begrenzte Fremddienstausnahme:** Authelia migriert sein eigenes Schema beim
Start und benötigt dafür DDL ausschließlich in seiner IdP-Datenbank.
Die Trading-Runtime erhält weiterhin kein DDL. IdP-Upgrades brauchen Backup
und geprüften Schema-Rückfallpfad; ein älteres Image allein ist kein Rollback.

## Mail, MFA und Recovery

Authelia benötigt genau einen Notifier. File-Notifier nur mit
Entwicklungs-Testidentitäten und geschütztem Pfad; Codes und Links sind sensible
Daten und dürfen nicht in Git/Logs landen. Q21 bestätigt vorhandenen kostenlosen
SMTP mit TLS und zu prüfenden Absenderrechten.
Noch werden keine externen Nachrichten versendet.
Ein erfolgreicher SMTP-Startupcheck versendet keine Mail und beweist keine
Zustellung. Empfänger und konkreter Testversand sind vor Pilotbetrieb zu prüfen.

Stabile MFA: Passwort plus TOTP oder WebAuthn. Passkey allein wird nicht als
belegte Zwei-Faktor-Anmeldung behandelt. Für eingerichtete MFA-Nutzer soll
Elevation zusätzlich den vorhandenen zweiten Faktor verlangen;
Authelias Default `require_second_factor: false` ist hierfür nicht ausreichend.
Der erste Faktoraufbau braucht gesondert den vorgesehenen Initialisierungsnachweis.

Q22 verwirft den verpflichtenden unabhängigen Ersatzfaktor und bevorzugt
E-Mail als ausreichenden Identitätsnachweis. Das Sicherheitsniveau hängt dann
auch am Postfach: Seine Übernahme kann einen Faktorreset ermöglichen.
Die normale Policy `require_second_factor: true` soll bestehen bleiben;
damit gibt es bei vollständigem Faktorverlust keinen zugesicherten
Mail-only-Selbstservice in Authelia.

**Bestätigt, Q24 — gesonderter administrativer E-Mail-Recoveryweg:**

1. Kurz gültige Einmalchallenge ausschließlich an die bereits hinterlegte
   Adresse; beispielsweise fünf Minuten. Keine Adressänderung im selben Vorgang.
   Diese Recoverychallenge ist gesondert zu implementieren/prüfen; Authelias
   Elevationcode ist unter der strengen Policy kein fertiger Ersatz.
2. Nutzerbezogene Cockpitsitzungen/sensible Aktionen sperren. Neue Exposition
   durch dessen Aktionen verhindern; Schutz und Reconciliation weiter ausführen.
3. Nach bestätigter Challenge den konkreten Faktorreset administrativ durchführen
   und auditieren. Authelia dokumentiert kontobezogene TOTP- und WebAuthn-
   Löschbefehle; keine allgemeine DB-Löschung und kein öffentliches CLI-Resettool.
4. Cockpit-Authentifizierungsgeneration erhöhen, Streams beenden, betroffene
   Tokens widerrufen und IdP-Sessions behandeln. Ein geplanter Neustart leert
   alle In-Memory-IdP-Sessions, widerruft aber nicht persistierte OAuth-Tokens.
   Authelia unterstützt laut aktueller Tabelle keinen RP-/Front-/Backchannel-
   Logout; jede Schicht gesondert nachweisen. Bis erfolgreicher Prüfung sperren.
5. Erneute Passwortanmeldung und Registrierung eines neuen MFA-Faktors über den
   regulären Bootstrap; erst danach Freigabe. Reset/Neuregistrierung melden,
   tatsächlichen Benachrichtigungsweg testen.

Authelias Elevation ist standardmäßig zehn Minuten gültig, der Mailcode fünf.
Ein Code-Widerruf sperrt den unbenutzten Code, hebt aber keine bereits erteilte
Elevation auf. Keine unbestätigten „Authelia-Recoverycodes“ zusagen.

## Secrets und Ressourcen

Compose-Secrets sind dienstbezogene Dateimounts, kein verschlüsselter Tresor.
Hostdateirechte, Verschlüsselung, unabhängiger Schlüsselzugriff und
Backupgrenzen bleiben erforderlich. Keine Keys als Composewerte, CLI-Argumente
oder Debugausgabe. Schlüsseldateien und administrierter IdP-Nutzerbestand
gehören nicht in Git.

Der Host hat etwa 1,9 GiB RAM. Baseline messen, dann Containerlimits sowie ein
gemeinsames Ressourcenbudget festlegen. Argon2 braucht zusätzlichen Speicher je
parallelem Login. Standardprofile bleiben klein; Research und Builds werden
begrenzt/serialisiert. Ein Containerlimit erzeugt keinen zusätzlichen RAM.
Bei unzureichender Kapazität Umfang reduzieren oder Erweiterung abstimmen.

Q27 bestätigt tägliche verschlüsselte Backups auf ein kostenloses kontrolliertes
Ziel außerhalb der VM, zusätzliche geschützte Offlinekopie und getrennte
Schlüsselaufbewahrung. Pilotziele RPO 24 Stunden/RTO vier Stunden.
Konkretes Ziel und Restoretest müssen vor Pilotfreigabe nachgewiesen werden.
Die Topologie der Heimnetz-Bridge steht in [mt5-bridge.md](mt5-bridge.md).

## Abnahme vor privatem Nutzerbetrieb

- Frischer Checkout reproduzierbar, Pins/Locks/Digests nachvollziehbar.
- Ausschließlich freigegebener zentraler HTTPS-Einstieg extern; TLS in Browser/BFF geprüft.
- MFA am OIDC-Client, Session-/Logout-/Entzugpfade und Recovery nachgewiesen.
- IdP-/Trading-DB-Zugriffe und Tenant-Negativtests getrennt geprüft.
- Mailweg und tatsächlicher Nachrichtenversand konkret autorisiert/geprüft.
- Ressourcenmessung mit Loginlast und einem begrenzten Backtest.
- Backup-/Schema-Restore mit deaktivierter Execution und Brokerabgleich.

Offizielle Quellen stehen in [sources.md](sources.md); Fachabnahme in
[roadmap.md](roadmap.md), ausführbare Aufgaben in [tasks/board.md](tasks/board.md).
