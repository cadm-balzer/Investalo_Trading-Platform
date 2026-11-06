# Privater Compose- und Identityplan

Stand 2026-11-07. Q13 bestätigt Docker Compose, Q14 lokales Authelia.
Dieser Plan konkretisiert die Auswahl; es gibt noch keine ausführbare
Composekonfiguration oder Installation. Zugang, Mail und Recovery sind in
Q20–Q22 offen. Siehe [architecture.md](architecture.md).

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
öffentlich veröffentlichten Ports. Bei privatem Development ist Loopback plus
Tunnel eine Variante; tatsächliche Erreichbarkeit wird geprüft.
Docker-Portregeln können Hostfirewallregeln umgehen.

Authelia benötigt einen Standarddomainnamen mit Punkt und HTTPS; `localhost`
oder eine reine IP als Sessiondomain reichen nicht.
Vorgeschlagen sind kontrollierte Namen unter `cockpit.investalo.de`,
beispielsweise `auth.cockpit.investalo.de`, ohne DNSänderung in dieser Phase.
Private Auflösung, Zertifikat, Browsername und OIDC-Redirect müssen zusammenpassen.
Eine Domainwahl darf Sessioncookies nicht unnötig an die bestehende Website
weiterreichen.

Bei interner CA müssen Browser und OIDC-/API-beteiligte Container ihr vertrauen.
Keine deaktivierte Zertifikatsprüfung. Für WebAuthn stabile RP-/Hostnamen
festlegen, damit spätere Umbenennungen nicht unbemerkt Neuregistrierung erfordern.
Die konkrete Zugangsvariante folgt Q20; öffentliche Produktion bleibt separat.

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
Daten und dürfen nicht in Git/Logs landen. Echter Privatbetrieb braucht den
in Q21 zu wählenden SMTP-Weg mit TLS und geprüften Absenderrechten.
Noch werden keine externen Nachrichten versendet.

Stabile MFA: Passwort plus TOTP oder WebAuthn. Passkey allein wird nicht als
belegte Zwei-Faktor-Anmeldung behandelt. Für eingerichtete MFA-Nutzer soll
Elevation zusätzlich den vorhandenen zweiten Faktor verlangen;
Authelias Default `require_second_factor: false` ist hierfür nicht ausreichend.
Der erste Faktoraufbau braucht gesondert den vorgesehenen Initialisierungsnachweis.

Q22 entscheidet unabhängigen Ersatz und administrativen Recoveryweg.
Keine unbestätigten „Authelia-Recoverycodes“ zusagen. Bei vollständigem
Faktorverlust: Identität prüfen, konkrete Wiederherstellung freigeben, auditieren
und bestehende IdP-/Anwendungssitzungen behandeln. Kein automatischer Reset
über eine normale Cockpitaktion.

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

## Abnahme vor privatem Nutzerbetrieb

- Frischer Checkout reproduzierbar, Pins/Locks/Digests nachvollziehbar.
- Keine unbeabsichtigt extern erreichbaren Serviceports; TLS in Browser/BFF geprüft.
- MFA am OIDC-Client, Session-/Logout-/Entzugpfade und Recovery nachgewiesen.
- IdP-/Trading-DB-Zugriffe und Tenant-Negativtests getrennt geprüft.
- Mailweg und tatsächlicher Nachrichtenversand konkret autorisiert/geprüft.
- Ressourcenmessung mit Loginlast und einem begrenzten Backtest.
- Backup-/Schema-Restore mit deaktivierter Execution und Brokerabgleich.

Offizielle Quellen stehen in [sources.md](sources.md); Fachabnahme in
[roadmap.md](roadmap.md), ausführbare Aufgaben in [tasks/board.md](tasks/board.md).
