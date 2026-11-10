# Technische Fallstricke

Stand 2026-11-08. Befunde sind dokumentiert, nicht automatisch im Altsystem behoben.

- **Authelia/TLS:** Sessiondomain weder localhost noch reine IP.
  Private Domainauflösung, Browserhostname und TLS müssen zusammenpassen;
  interne CA auch in den OIDC-beteiligten Containern vertrauen.
- **Notifier/Recovery:** File-Notifier nur Tests, SMTP mit TLS für echte Nutzer.
  Elevation verlangt zweiten Faktor nicht per Default; ausdrücklich absichern.
- **IdP-Migrationen:** Authelia braucht eigene begrenzte DDL-Rechte für automatische
  Migrationen. Keine Übertragung dieser Ausnahme auf Trading-Runtime.
- **Compose-Secrets:** Dateimounts sind kein verschlüsselter Tresor.
- **IdP-Neustart:** Memorysessions verschwinden, BFF-/Tokens werden dadurch nicht
  automatisch widerrufen.
- **E-Mail-Recovery:** Gewünschte Mail-only-Identitätsprüfung hängt am Schutz
  des Postfachs. Strenge normale Elevation bedeutet keinen fertigen Mail-only-
  Selbstservice; administrativer Reset und anschließende MFA sind gesondert.
- **Authelia-Logout:** RP-/Front-/Backchannel-Logout laut aktueller Tabelle
  nicht unterstützt. BFF-Authentifizierungsgeneration, Streams, Tokenrevocation
  und IdP-Sessions ausdrücklich behandeln; Codewiderruf beendet keine Elevation.
- **SMTP-Startupcheck:** Kein Nachrichtenversand und kein Zustellungsnachweis.
- **Privatpilot:** Privater Nutzerkreis kann einen öffentlichen zentralen
  HTTPS-Einstieg haben. Nicht mit öffentlicher Registrierung gleichsetzen.

- **Identitybedarf:** Ein großer IdP kann allein den 2-GB-Host beanspruchen.
  Auch leichtes Authelia benötigt zusätzliche Argon2-Ressourcen pro Login.
- **Authelia-Passkeys:** Stabile Zwei-Faktor-Policy wählen; experimentelle
  Interpretation von User Verification nicht als belegte MFA voraussetzen.
- **Cloud-Free-Recovery:** ZITADELs eingebauter SMTP ist nur Evaluation.
  Produktiven Mailweg und Datenverarbeitung vor Auswahl klären.
- **Docker/Firewall:** Veröffentlichte Ports können UFW umgehen. Interne Dienste
  nicht öffentlich publishen, externen Zugang nachweisen.

- **Git-ignore wirkt nicht auf getrackte Dateien.** `secrets/secrets.keys` war
  bereits versioniert. Indexentfernung schützt neue Snapshots, keine alten Commits.
  Kein Secret-Diff ausgeben; Rotation und Historybereinigung separat behandeln.
- **Sandbox und Git:** Projektdateien sind schreibbar, `.git` ist geschützt.
  Bei Gitmutation Tooleskalation nutzen; nicht die Berechtigungsgrenze umgehen.
- **Legacy-RiskGuard:** `max(configured_risk, 1.0)` lässt Risiken über kleineren
  konfigurierten Grenzen zu. Kein pauschales Übernehmen; Nachweis im neuen Kern.
- **Backtestkosten:** Nachträglicher Gebührenabzug auf unveränderten Fills ist
  nicht dasselbe wie Ausführung mit Kosten/Margin. Swap/Slippage und Brokerlots
  fehlen in geprüften Referenzteilen.
- **Multi-Timeframe-Kausalität:** Legacy Trend/Pullback verschiebt H1 um −1 Stunde,
  die EA liefert Bar-Startzeiten. Möglicher Look-ahead; mit abgeschnittenen
  Zukunftsbars und expliziter Open-/Close-Timestampsemantik verifizieren.
- **Gold-CBS ist nicht Trend/Pullback.** Bildvarianten sind nicht als CBS-Plugin
  implementiert; im Registrycode ist Gold mit H1/M15 Trend/Pullback freigeschaltet.
- **Kaufstaffel:** Sechs 1,25×-Quote-Budgets bei 5%-Preisabständen verbrauchen das
  Budget schon nach etwa −22,62 %, nicht erst −50 %. Nach Q16 dient dieses
  Beispiel nur als Vergleich; sechste Tranche ist ausschließlich Notfallreserve.
  Stress jeden Füllstand, auch dauerhaft ausbleibendes Rearm.
- **Notfallreserve:** Einsatz senkt Einstand, erhöht aber Verlustexposition
  gegenüber Cash. Q23 macht den Einstieg manuell; der −40%-Automatikvorschlag
  ist verworfen. Bei beibehaltenem 5%-Abstand kann das Kaufpreisfenster
  oberhalb des −55%-Exit leer sein; keine Ausnahme von Risk-/Schutzgates erzwingen.
- **Diskretionärer Backtest:** Keine rückblickend günstigen manuellen Käufe
  erfinden. Fünf automatische Stufen plus Cash sind der Referenzpfad;
  tatsächlich protokollierte manuelle Paperaktionen getrennt auswerten.
- **Hebel:** Nominal, Margin, Basketbudget und Kontoequity nicht verwechseln.
  Vereinfacht reicht 2× bei −50 % gegenüber Einstand mit Maintenance nicht aus.
- **Supertrend:** Ein Stop ab +5 % kann trotzdem unter Nettobreakeven liegen.
  Linie, Kosten, Stopabstände und Gaprisiko prüfen.
- **Orderannahme ist kein Fill.** `OrderSend=true`, HTTP-Erfolg und Ack nicht als
  endgültige Position verbuchen. Timeout kann bereits ausgeführte Order bedeuten.
- **Idempotenzgrenzen:** Bitget `clientOid`, MT5-Magic und lokale Leases liefern
  keine pauschale Exactly-once-Garantie.
- **Restore:** Alte DB plus reale Brokerfills kann Replay erzeugen.
  Execution erst nach vollständigem Abgleich wieder starten.
- **Doppelte Kontoverbindungen:** Kanonische Brokeridentität und gemeinsame
  Marginpools berücksichtigen; sonst können mehrere Writer/Risikobudgets
  denselben realen Bestand unbemerkt überlasten.
- **Backupverschlüsselung verhindert keine Löschung.** Ältere Generationen vor
  Runtime/Backupwriter schützen, unabhängige Löschrechte und Offline-/Immutablekopie.
- **RLS:** Owner/Superuser/`BYPASSRLS` umgehen Schutz. Tenantkontext transaktionslokal;
  ein kompromittiertes Backend ist mit frei setzbarem Kontext nicht voll isoliert.
- **Free-Datenfeeds:** Quoten, Entitlements und Mehrnutzerrechte separat prüfen.
  TradingView Essentials ist kein allgemeiner Datenfeed für automatischen Handel.
- **MT5:** Pythonintegration hängt an einem laufenden Terminal.
  Terminalkonto fest binden, Journale und Geräteauth vorsehen.
- **Heimnetz-Bridge:** Ausgehendes HTTPS braucht keine Routerportweiterleitung.
  Maschinenendpoint benötigt eigene Authentifizierung statt Browser-MFA.
- **MT5 WebRequest:** Synchron, URL-Allowlist nötig, nicht im Strategy Tester.
  Lange Requests blockieren den EA; OnTimer holt Timer nicht unbegrenzt nach.
- **Demoaccount:** Server/Login/Demomodus beim Start und vor Dispatch prüfen;
  kein automatischer Kontowechsel als Fehlerbehebung.
- **FTMO:** Kontotyp/Phase/Vertragsdatum verändern Regeln. Tageswechsel mit
  IANA-Zeitzone; fremde Konten nicht ohne Vertragsprüfung zentral handeln.
- **Bitget Docs:** Alte URLs können auf neue API-Familien umleiten.
  Classic/UTA und aktuelle Endpoint-/Changelogsemantik gezielt prüfen.
- **Builds:** Floating Images und `npm install || true` aus Referenzrepos nicht
  übernehmen. Lockdateien müssen tatsächlich vom Build verwendet werden.
- **Host:** 1,9 GiB RAM ohne Swap; parallele Builds/Research können kritische
  Dienste verdrängen. Ressourcen messen und getrennt begrenzen.
- **Adminskill:** Lokale Anleitung ist für Ubuntu 24.04, Host ist 26.04.
  Keine unverifizierten Kernel-/Paket-/SSHkommandos übertragen.

## Lokales Fundament

- **Docker 29:** Container ausschließlich an internen Netzen veröffentlichen
  hier keinen Hostport. Caddy braucht zusätzlich ein eigenes Bridge-Netz;
  die Anwendungen behalten ausschließlich interne Netze.
- **PostgreSQL 18:** Datenpfad `/var/lib/postgresql/18/docker`; Parent-Bindmount
  passend zur Nonroot-UID anlegen. Alte Major-PGDATA-Pfade nicht übernehmen.
- **Konfigurationsmounts:** Geänderte Caddy-Konfiguration allein löst keinen
  Containerneustart aus; explizit validieren und neu laden/starten.
- **Logdaten:** Caddy-Fehlerlogs können Request-URI inklusive OAuthcode enthalten.
  Ganzes `request`-Feld herausfiltern. PG-Fehlerstatement-/Parameterlogging
  unterbinden; `log_statement=none` allein reicht nicht bei Passwort-DDL.
- **Authelia-Flow:** `max_age=0` erzeugt in 4.39.28 einen Consentloop;
  gleichwertiges `prompt=login` plus signierte Flowstart-Prüfung verwenden.
  HTTP 200 allein bedeutet bei Provider-JSON nicht Erfolg; `status=OK` prüfen.
  Nach Faktorprüfung denselben gespeicherten OAuthflow weiterführen.
- **Testprovisionierung:** CLI-TOTP für `.invalid` ist ein lokaler Testshortcut,
  keine Abnahme normaler Faktorregistrierung oder administrativen Recoverys.
  Exactformat-Guard verhindert versehentliche Anwendung auf reale Nutzer.
- **Argon2/kleiner Host:** Wiederholte Passwort-/Clientprüfungen brauchen
  RAM-Spielraum. Ein IdP-Neustart wurde beobachtet, Ursache nicht nachgewiesen;
  Limit auf 320 MiB erhöht. Keine belastbare Produktionslastabnahme daraus ableiten.
- **Sandboxtests:** Native Testisolation und AnyIO/TestClient können im
  eingeschränkten Runner hängen. Named Node-Tests mit `--test-isolation=none`;
  API-Integration im gepinnten Docker-Checks-Target mit echter DB verifizieren.
- **Frische Simulationstage:** UTC-Mitternachtsbaseline benötigt aktuelle
  Quotes aller gehaltenen Assets; fehlende Baseline sperrt neue Käufe.

## Snapshot- und Researchintegration

- **Bitget-V3-Zeitgrenzen:** `endTime=H4-Grenze−1ms` wird in tatsächlich
  geprüften öffentlichen Antworten abgerundet und überspringt bei Rückwärts-
  pagination eine Kerze. Exakte Intervallgrenzen verwenden; Lückenprüfung nie
  abschalten. 90 Tage pro Request sind kein garantierter Gesamthistorienumfang.
- **Coverage:** Ohne ausdrücklich gewünschtes Fenster ist Vollständigkeit
  unbekannt (`null`), nicht falsch. `true` gilt nur für genau dieses Fenster.
- **Zwei Hashes:** Datenhash lässt Abrufzeit und gewünschtes Fenster aus;
  vollständiger Contenthash bewahrt das Auditobjekt. Derselbe Datenhash mit
  geändertem Auditobjekt darf nicht unbemerkt einen bestehenden Import ersetzen.
- **Statusvertrag:** DB/API liefert `queued/running/succeeded/failed`, Cockpit
  normalisiert ausschließlich bekannte Werte auf sein Großbuchstabenenum.
  Legacyjobs ohne Snapshot müssen weiter als fehlgeschlagen sichtbar sein.
- **Worker-HBA:** Rollenmitgliedschaft allein reicht nicht; die TLS/SCRAM-HBA
  muss die NOLOGIN-Researchgruppe vor dem allgemeinen Reject berücksichtigen.
  Bestehende PG-Konfiguration nach geprüfter Änderung explizit neu laden.
- **Provisionierung:** Rollenflags und fremde Rollenmitgliedschaften vor GRANT
  atomar prüfen. Ablehnung darf keine vorherige Rechtevergabe zurücklassen.

## Bitget-Classic-Kontozugang

- **Classic versus UTA:** V2-Accountinfo liefert `authorities`; UTAs
  `permType/permissions` dürfen nicht als Classicantwort verarbeitet werden.
  Alte `api-doc`-Links können auf UTA umleiten. Detailquellen und Familie
  ausdrücklich prüfen; kein automatischer Kontomoduswechsel.
- **API-Key ist ein Triple:** API-Key, Secret und Passphrase gehören zur
  Verbindung. Der Keyname allein ermöglicht keine signierten privaten Abfragen.
  Providerrechte und feste Endpointallowlist bilden unterschiedliche Grenzen.
- **Wallet-/Equitygrößen:** Finanziertes Futureskapital ist kein Spotbudget.
  Futures-Equity kann unrealisierte PnL bereits enthalten; nicht doppelt addieren.
  Fehlende Werte unbekannt lassen, mögliche negative Futuresgrößen erhalten.
- **Kontoinfo-Quota:** Classic-Accountinfo ist mit 1 Request/s/UID dokumentiert.
  Mehrere Keys derselben UID teilen diese Grenze. Eine lokale Clientpace
  ersetzt keine Schedulerkoordination über mehrere Clients/Worker.
- **Decimalgrenzen:** `abs(Decimal)` kann mit aktueller Contextpräzision runden.
  Validierungsgrenzen mit `copy_abs()` exakt prüfen; Wirezahlen nur ASCII.
- **Coin-Schreibweise:** Providerassetnamen können gemischte Groß-/Kleinschreibung
  tragen. Wirebezeichner erhalten statt durch pauschales Uppercase zu verändern.
- **Headerredaktion:** Ein gewöhnliches Mapping kann Authheader im `repr` ausgeben.
  Credential- und Requestobjekte samt Headermapping redigieren; keine generische
  Serialisierung oder rohe Providerexceptions in Logs übernehmen.

## Credential-Envelopes

- **AEAD ist keine Autorisierung:** Authentifizierte Tenant-/Kontobindung ersetzt
  weder serverseitige Nutzerrechte noch DB-RLS oder eine getrennte Schlüsselidentität.
- **Revision und Restore:** Ein alter Ciphertext bleibt mit seinem alten Kontext
  kryptografisch gültig. Aktuelle erwartete Revision aus autoritativer DB beziehen;
  lokale Wiederherstellung mit Testkeys ist kein externer Backup-/Restorebeleg.
- **KEK-Wechsel:** Vor Rewrap auch den Payloadtag prüfen. KEK-ID darf historisch
  nicht auf anderes Material zeigen; gleiche KEKbytes unter mehreren IDs abweisen.
  Alte Schlüssel erst nach geprüfter Migration und Recoveryretention ausmustern.
- **Nonces und Speicher:** Zufällige 96-Bit-Nonces haben ein Kollisionsrisiko;
  Nutzungslimits/Rotation gemeinsam pro KEK überwachen. Python bietet keine
  garantierte Speicherlöschung; redigierte Objekte verhindern keine Prozessinspektion.
- **Psycopg-Rowfactory:** Der Credentialclient prüft einen festen 13-spaltigen
  Tuplevertrag. `dict_row` ist für administrative Fixtures erlaubt, nicht für
  seine Connectionfactory. Frische Nonautocommit-Verbindungen verwenden.
- **Versionskonflikt:** Credentialrevision ändert sich bei Payloadwechsel,
  Speicherversion zusätzlich bei Rewrap/Widerruf. Beide prüfen; unbekannten
  Commitausgang zunächst abgleichen, keine blinde Wiederholung.
- **Fixture-DB und Adminrechte:** Getrennte Testdatenbank begrenzt Daten,
  nicht die Rechte eines mit Migrationscredentials laufenden Prüfcontainers.
  Credential-Testlogins selbst nur per HBA/CONNECT zur Fixture-DB zulassen.
- **Delegationstest:** Ein 42501 allein beweist keine Rollen-Driftabwehr.
  Zuerst erlaubte aktuelle Nutzerbindung nachweisen, Setupabschluss markieren
  und nach abgebrochener Testtransaktion ursprüngliche Membership prüfen.
- **Widerruf:** Sperrt künftige DB-Abfragen, löscht keinen bereits ausgegebenen
  Klartext. Brokerdispatch braucht erneute Autorisierung. UID bleibt reserviert;
  keine automatische Wiederanbindung oder Benutzerübertragung.
- **Actionassertion:** Normales BFF-Login-JWT genügt nicht. Eigene Signaturidentität,
  Ziel/Bodybindung und frische Authzeit ab gespeichertem Schrittflowstart brauchen
  einen echten Browsernachweis. SQL prüft diese JWT-Signatur nicht.
- **Freigabezeit:** `now()` bleibt innerhalb einer Transaktion konstant.
  `clock_timestamp()` auch nach blockierenden Sperren und vor der finalen
  Rückgabe prüfen. Ein abgelaufenes Token darf keine Speicherung abschließen.
- **Konsumierte JTI:** Vor der Probe separat committen. Fehler/Crash kann einen
  autorisierten, aber unvollständigen Datensatz hinterlassen; dessen JTI bleibt
  konsumiert. Unbekannte Commits abgleichen, keine automatische Wiederholung.
  Retention darf alte Tokens nicht erneut freischalten.
- **Datei-KEK:** Fingerprintkonfiguration muss unabhängig vertrauenswürdig bleiben;
  Modus0700/0400 und NOFOLLOW ersetzen weder externe Schlüsselisolation noch
  Schutz gegen VM-root. Keine Entwicklungsschlüssel für reale Nutzerkeys verwenden.
- **Authelia-Faktorfrische:** Passwort-Reauth erhält den alten zweiten Faktor.
  `auth_time`/`amr=mfa` und `prompt=login` beweisen keine neu verwendete MFA.
  Sensitive Aktionen benötigen zusätzlich die bestätigte Cockpit-Passkeyprüfung.
  Erzwungener Browserlogout ist kein serverseitig belastbarer Nachweis.
  Native `/api/firstfactor` setzt die Sitzung neu auf; zum Nachweis bestehender
  Faktorwiederverwendung den dedizierten `/api/firstfactor/reauthenticate` prüfen.
  Bei sofortigen CLI-Flows kann die Sekundenpräzision der Authzeit vor der
  gebrochenen OIDC-Requestzeit liegen; im Test die Sekundengrenze überqueren.
- **Mehrere Tabs:** Session-CSRF allein bindet eine Bestätigung nicht an die
  angezeigte Aktion. Grant-eigenen Token vor Consume vergleichen; ein alter
  Tab darf den neuen Cookie-Grant nicht bestätigen.
- **Passkeystore:** Session-TTL-/Sweepstore ist nicht für dauerhafte Publickeys
  und Counter geeignet. CAS/Ownerbindung/Widerruf und Audit atomar halten,
  niemals Credential consume→verify→put. Synced-Counter0→0 ist zulässig;
  Replay verhindern einmalige Challenge und persistierte Version.
- **Passkeyclaims:** UV und UP serverseitig erzwingen, Beispiele können UV
  ausschalten. Lokale Passkeyzeit niemals als OIDC-`auth_time` ausgeben.
  RP-Hostname ohne Port, HTTPS-Origin mit Port; andere Domain erfordert Enrollment.
- **Enrollment und Counter:** `fmt=none` enthält keine Signatur; eine gespeicherte
  Registrierung ist kein privater Besitznachweis für sensitive Grants.
  RP-weite Credential-ID maximal1023 Byte, einschließlich terminaler Tombstones.
  SQL-Counter0→0 mit Versions-CAS verhindert keinen erneuten Gebrauch desselben
  Belegs; Challenge vor Kryptoprüfung einmalig konsumieren.
  Beim späteren Assertionflow verifiziertes `deviceType` zusätzlich mit
  gespeicherter Backup-Eligibility vergleichen; das SQL-CAS-Argument enthält
  nur den neuen Backupzustand und beweist diese Übereinstimmung nicht.
- **Laufende Anmeldung:** Auch nach einem API-/Krypto-Await die aktuelle
  Sitzungsfrist und konfigurierten HTTPS-Origin prüfen. Gleicher RP-Hostname
  erlaubt keine Verwendung eines inzwischen veralteten Origins/Ports.
- **FastAPI-Router:** Gepinnte0.162.0 kann `include_router` als
  `_IncludedRouter` ohne `.path` führen. Tests gezielter Routen müssen darauf
  filtern oder tatsächliche ASGI-Requests prüfen.
- **Lokaler TestClient:** Sandbox-Socketgrenzen können AnyIO-TestClient hängen
  lassen. Die identische Prüfung außerhalb der Sandbox bestand; gepinnten
  Compose-Prüfcontainer verwenden, keine Sandboxgrenzen umgehen.
- **Öffentliche TLS-Namen:** Zertifikat allein migriert keine Anwendung.
  OIDC-Issuer/Callback/Cookiedomain, BFF-Origin und Passkey-RP gemeinsam prüfen;
  `(oidc_issuer,oidc_subject)` ist eine persistierte Identitätsbindung.
  Interne BFF-Netze brauchen kontrollierte öffentliche Namensaliasse zum Proxy.
  Gemeldeten Browserzugang gegen DNS und tatsächliche Hostlistener abgleichen.
- **Compose-Overlay:** Ports ohne `!override` können zum bestehenden Satz
  hinzugefügt werden; Volumeersatz erfolgt nach Zielpfad. Zusammengeführtes
  Ergebnis prüfen, keine automatisch erzeugten Secret-/State-Bindverzeichnisse.
- **PEM-Platzhalter:** Beliebiges Mehrzeilenmatching erlaubt zusätzliche YAML-
  Einstellungen im Signaturkey-Platzhalter. Nur exakt eingerückte PEM-Grammatik
  zulassen; Quellkonfiguration vollständig gegen die vertrauenswürdige Vorlage
  prüfen und hinzugefügte Einstellungen nach dem Footer als Regression abweisen.
- **Aktives öffentliches Overlay:** Default-Compose-`up` ersetzt öffentliche
  Ports/Origins durch lokale Werte. Bei laufender Vorschau immer ausdrücklich
  `--file infra/compose.public-preview.yaml` angeben; Operatorprüfcontainer mit
  `--no-deps` starten, um Runtime nicht unbeabsichtigt zu verändern.
- **Issuer und vorhandene Researchdaten:** Provisionierung allein anhand des
  Tenantnamens kann einen neuen Tenant erzeugen. Genau eine bestehende aktive
  synthetische Ownerbindung ermitteln und deren konkrete Tenant-ID übergeben;
  Workerbindung und Credential-/Passkey-Eigentum nicht umschreiben.
- **DNS und ACME:** Während DNS-Verteilung kann die erste Challenge fehlschlagen.
  Caddy wiederholt automatisch; nach gültiger Auflösung war die Ausstellung
  erfolgreich. Keine CA-Prüfung abschalten oder Ausgabedateien löschen.
- **Proxyheader:** Upstream und Edge können gleiche Securityheader mehrfach
  senden, mit unterschiedlichen Referrer-Policies. Der Edge entfernt die drei
  upstreamseitigen Policyheader und liefert je einen geprüften eigenen Wert;
  CSP-/Cacheheader bleiben erhalten.
- **Fehlende Verbindungszeile:** `FOR SHARE` auf Konto und fehlender Verbindung
  verhindert keinen parallelen003-Registrierungsinsert. Der007-Registrierungsnachweis
  nimmt zuerst `FOR UPDATE` auf das bestehende Konto; der alte Writer verlangt
  dessen SHARE-Lock. Für Replace/Revoke bleibt die vorhandene Connection-
  SHARE-Sperre, um keine gegenläufige Reihenfolge zu003 einzuführen.
- **Aktionsnachweis und OIDC-Zeit:** Die ursprüngliche `oidc_auth_time` für den
  gesamten Versuch einfrieren; ein Test-JWT mit je neuer Zeit pro Phase ist
  eine andere Sitzungsbindung. `checked_at` getrennt halten. API-Confirm liefert
  den exakten Wrapper mit `execution_enabled:false`; BFF prüft ihn vor Veröffentlichung.
- **Counter0 und Challenge-ID:** Eine neue Proof-ID darf nicht dieselbe Challenge
  wiederverwenden. RP-weite Challenge-Eindeutigkeit auch für terminale Zeilen
  erhalten; ein unbekannter Commit öffnet keinen automatischen Wiederholungsweg.
- **Zeitabhängige Testparameter:** `time.time()+60` bei pytest-Collection kann
  während einer längeren PG-Suite zu einer gültigen Gegenwartszeit werden.
  Future-Claims erst bei Ausführung erzeugen; die produktive Zukunftsprüfung
  bleibt unverändert. Der erweiterte84s-Lauf hat diese alte Testschwäche sichtbar gemacht.
- **SSH-Agent nach Wiederverbindung:** Git/SSH warteten ohne Ausgabe am
  Agent-Socket; `ConnectTimeout` begrenzt diese Agentabfrage nicht.
  Mit vorhandenem Deploy-Key und `IdentityAgent=none` gelang der Push sofort.
  `IdentitiesOnly`, `BatchMode` und strikte Hostkeyprüfung erhalten; nur die
  eigenen hängenden Verbindungen beenden, keine Schlüssel ausgeben oder ersetzen.
- **HTTP-Sitzung und asynchrone Adapter:** Nach CSRF-Prüfung nicht erneut eine
  beliebige aktuelle Sitzung als Ausgangsautorität erfassen. Den eingefrorenen
  autorisierten Snapshot bis zum Adapter weiterreichen; Bodylesen, API/Krypto
  und Ergebnisveröffentlichung prüfen auch Rotation, Originalfrist und Origin.
  Alte Enrollmentversuche ohne eingefrorene `sessionExpiresAt` nach dem Update
  geschlossen abweisen; sie gelten ohnehin höchstens120 Sekunden.
- **Synthetische BFF-Prüfung:** UID10003 darf den vorhandenen0400-Sitzungskey
  von UID10002 nicht lesen. Keine ACL der Vorschau lockern: drei eigene
  Testsecrets für Sitzung/BFF/OIDC und vollständig getrennten Zustand verwenden.
  Sandbox-Metadaten können durch UID-Remapping65534 zeigen; tatsächlichen Owner
  nur mit freigegebener Host-Metadatenprüfung beurteilen, keinen Key ausgeben.
- **Privilegierte Fixturevorbereitung:** `lstat` plus spätere Pfadoperation
  ist bei ersetzbaren Elternverzeichnissen nicht ausreichend. Deskriptoren
  mit `O_DIRECTORY|O_NOFOLLOW` halten, `dir_fd`/`fstat`/`fchmod`/`fchown`
  verwenden und Besitz erst nach Vorbereitung übergeben. Marker/Keys vor Lesen
  auf reguläre Datei, Owner, Rechte, Größe und Einfachlink prüfen. Ein Regressionstest
  ersetzt den Elternpfad während der Vorbereitung; fremdes Ziel bleibt unverändert.
- **HTTP-Teststatus:** Die neue Proofgrenze liefert bei Origin/CSRF/Fetch-
  Verstoß403, die bestehende Enrollmentgrenze400. Assertions der tatsächlichen
  Verträge verwenden, die Produktionsgrenze nicht an falsche Testerwartungen anpassen.
- **Isoliertes Compose im gemeinsamen Projekt:** Zusätzliche `browser-proof-*`
  Dienste veröffentlichen keine Ports. Nur ihre Namen stoppen, kein `down`.
  Imagebuild ersetzt noch keinen laufenden Container; öffentliche Dienste weiter
  ausschließlich mit ihrem ausdrücklich aktiven Overlay bedienen.
- **Credentialübergabe und ursprüngliche OIDC-Zeit:** Der alte Credentialvertrag
  verlangt eine frische IdP-Zeit;007 bewahrt ursprüngliche Claims. Frische
  Passkeyzeit niemals in `oidc_auth_time` einsetzen oder nicht vorhandenes AMR
  erfinden. Neue Audience/Zweckkind mit unabhängigen vertrauenswürdigen
  Kontexterwartungen verwenden; alte Prüfregeln nicht lockern.
- **Receipt und dauerhafte Autorität:** Strukturelle Receiptprüfung/HS256
  belegen keinen DB-Aussteller und keinen Einmalverbrauch. Neues JWT/JTI kann
  denselben Nachweis erneut signieren.007-Proofbestätigung nicht nachträglich
  als Credentialzustimmung behandeln; eigener Zweck/Consent und globale
  dauerhafte Consumegrenze vor Probe sind weiterhin erforderlich.
- **TS-/Python-Bodygleichheit:** JS parst `1.0`/`1e0` als Ganzzahl, Python als
  Float. CAS verlangt Integer-Wireform und sichere JS-Grenzen. Unveränderte
  UTF8-Bytes einschließlich Whitespace hashen, Größen in Byte messen und
  Secrets nicht Unicode-normalisieren. Metadatendigest gehört zur späteren
  DB-Autorität; nicht sprachabhängig aus JSON neu ableiten.
- **Neue Migration vor Festschreibung:** PL/pgSQL akzeptiert nicht jede
  unparenthesierte CASE-Bedingung in IF.008-Vorprüfung fand dies vor Anwendung;
  Korrektur vollständig zurückgerollt geprüft. DDL und echte Runtimevorbereitung
  vor dem ersten Checksum-Eintrag prüfen, angewendete Migration nie nachträglich
  ändern. Fixture-DB008 bedeutet nicht, dass investalo008 besitzt.
- **Zweckreceipt und007-Zeit:**007 erlaubt bis fünf Sekunden Future-Checkskew,
  IP038 verlangt checked_at<=authorized_at<=now.008 muss vor und nach Bestätigung
  monotone aktuelle Zeiten prüfen und ungültige Ausstellung atomar zurückrollen.
  Authorization-/Proof-/Grant-IDs paarweise verschieden halten.
- **Consume und finaler Lock:** Frisches JWT/JTI erzeugt keine zweite Freigabe.
  Consume muss vor Probe committed sein; finaler Lock darf nicht in derselben
  Transaktion oder mit anderen Claims erfolgen. Terminalen Lockcommit nicht
  wiederverwenden, unbekannten Commit abgleichen. IP-040 verbindet den separaten
  privaten Executor; Write und Audit gehören in dieselbe Locktransaktion.
- **Prüfung nach Credentialmutation:**008 vergleicht die alte eingefrorene
  Connectionmetadata. Nach erfolgreichem003-Write würde ein erneuter008-Lock
  deshalb die beabsichtigte Änderung ablehnen.009 verlangt stattdessen exakt
  den erlaubten neuen CAS-Zustand; Account/Actor/Faktor bleiben unverändert
  gebunden. Ablauf nach dem letzten Audit-/FK-Warten mit `clock_timestamp()`
  prüfen; dies garantiert keine Uhrzeit der späteren WAL-/Commitantwort.
- **Verschachtelte Connectionfactory:** Der bestehende CredentialStore erkennt
  `StoreRejected`; beliebige `OnboardingRejected` aus einer inneren Factory
  würden zu `unavailable`. Der neue Executor überführt statische Fehlercodes
  an dieser Grenze gezielt, ohne Treibertext oder Secretparameter weiterzugeben.
- **Verlorene Commitantwort:** Testfactory erst nach echtem Commit werfen lassen,
  um einen unbekannten Commit von einem Rollback vor Commit zu unterscheiden.
  Unbestätigter Consume startet keine Probe; unbestätigter finaler Commit liefert
  kein Erfolgsresultat und darf nicht mit `failed` überschrieben werden.
- **Zeitparameter bei Testcollection:** `int(time())+10` in Parametern wird
  bereits beim Einsammeln der Suite berechnet. Bei längeren Builds/Läufen ist
  ein vermeintlicher Zukunftszeitpunkt beim Test schon Vergangenheit. Relative
  Parameter beim Testaufruf auswerten und die Uhr der zu prüfenden Projektion
  auf denselben Zeitpunkt fixieren; Frist-/Ablehnungsregeln nicht lockern.
- **008-Zustimmung konsumiert007:** Nach erfolgreichem Authorize ist der
  bisherige Grant bestätigt und `read_grant` lehnt ihn korrekt ab. Der private
  BFF vergleicht danach den gespeicherten unveränderlichen Grant mit aktuellen
  Actor-/Faktor-/Accountdaten sowie dem exakten008-Receipt; keinen neuen Grant
  auslesen und keine007-Prüfbestätigung als Credentialzustimmung umdeuten.
- **Private Bodybytes im BFF:** Zielabhängigen Request einmal erzeugen,
  strikt validieren und exakt als UTF8 hashen. Rohbody nur beim vertrauenswürdigen
  Aufrufer im Speicher halten; Fortsetzungen speichern Hash/Korrelation.
  Das neue Resultat gegen den beabsichtigten CAS-Fortschritt prüfen, da
  Credentialmetadaten nach erfolgreichem Write absichtlich verändert sind.
- **Neustart und Fixtureablage:** `/tmp/investalo-passkey-browser-state` und
  temporäre Prüfprotokolle können beim Hostneustart verschwinden. Geschützte
  Fixtureablage ausschließlich mit `prepare-passkey-browser-checks.py` neu
  erzeugen. Fixture-API-Container mit neuen Secretmounts gezielt neu erstellen;
  öffentliche Dienste behalten ihre persistente Vorschaukonfiguration.
- **HTTP-Pfadnormalisierung:** `BaseHTTPRequestHandler.parse_request` macht
  aus einem Rawtarget mit `//` einen Pfad mit `/`. Den ASCII-Requesttarget
  vor und nach dem Parser vergleichen; sonst gilt eine kanonisch gebundene
  Assertion auch für einen anderen Rawpfad. Headergrammatik separat prüfen,
  da der Standardparser ungültige Zeilen teilweise ignorieren kann.
- **Unabhängiger Credentialkontext:** TLS authentifiziert den BFF, der JWT
  autorisiert die konkrete Aktion. Erwarteten Actor/Sitzungs-/OIDC-Kontext
  separat aus der autorisierten Sitzung beziehen; nicht aus Tokenclaims
  rekonstruieren. Eine gemeinsame CA ohne festen Peerfingerprint könnte
  anderen gültigen Dienstzertifikaten die Transportgrenze öffnen.
- **Statische HTTP-Fehler:** Exceptionattribute sind veränderlich und
  Subklassen können `CODES` überschreiben. Nur die feste Whitelist der
  Basisklasse zulassen; sonst könnte ein Wrapper private Fehlerdetails
  als vermeintlichen Fehlercode veröffentlichen.
- **Strikte synthetische TLS-Zertifikate:** Python3.14 prüft auch AKI/SKI,
  BasicConstraints, KeyUsage und Server-/ClientAuth-EKU. Testzertifikate
  vollständig erzeugen; strikte Zertifikatsprüfung nicht abschalten.
- **Timeout nach Write:** Ein HTTP-Deadline schließt den Socket, beendet aber
  nicht zwingend den laufenden DB-Commit. Fehlende Antwort bleibt unbekannt;
  kein automatischer erneuter Probe-/Writeversuch und kein `failed`-Audit
  über einen bereits bestätigten Abschluss.
- **Libpq-Umgebung im festen Launcher:** `PGOPTIONS`, `PGSERVICE` und weitere
  geerbte Parameter können Verbindung und Sitzung beeinflussen. Der isolierte
  Entwicklungslauncher weist alle `PG*`-Variablen ab und setzt Verbindung/TLS/
  Timeouts ausschließlich fest. Nicht das PG-Environment des administrativen
  Fixturecheckers in die Credentialruntime übernehmen.
- **Rollenprüfung ohne Migrationledger:** Der gebundene Credential-LOGIN darf
  `schema_migrations` nicht lesen. Notwendige008-/009-Funktionen und EXECUTE-
  Rechte über feste `pg_catalog`-Abfragen vor dem Listener prüfen; angewendete
  Migrationen/Prüfsummen bleiben Sache der getrennten Administration.
- **Zusatzgruppen aus Composeanchors:** Gemeinsame Prüfhärtung kann eine
  administrative Lesegroup enthalten. Die Credentialruntime braucht nur ihre
  UID/GID10003; `group_add: []` ausdrücklich setzen und tatsächliche
  `HostConfig.GroupAdd` neben den exakten Mounts prüfen.
- **Synthetic-only Guard:** Reale Keytriples vor Verifier und dauerhaftem
  Consentverbrauch abweisen. Statische synthetische Brokerantworten allein
  würden versehentliche echte Speicherung nicht verhindern.
- **ASGI-Scheme ist keine TLS-Autorität:** Der gepinnte HTTP-Server liefert
  ohne eigene Anbindung keine verifizierte Clientzertifikatsidentität in den
  Scope. Tatsächlichen TLS-Peer vor Parser prüfen und den Scope an genau dieses
  authentifizierte Protokoll binden; Header oder `scheme=https` reichen nicht.
- **h11 normalisiert vor dem ASGI-Scope:** Gefaltete Header und gleiche
  Content-Length-Duplikate können vor der App normalisiert werden. Strikte
  Rawgrammatik und Duplikatprüfung vor dem Parser beibehalten, Bodybytes danach
  unverändert weitergeben.
- **Disconnect beendet keinen Worker:** Threadpools haben eine unbegrenzte
  Submitqueue. Separate Arbeitsslots bis zum tatsächlichen Future-Ende halten,
  auch wenn Socket oder ASGI-Task beendet wurden. Keine Commitwiederholung
  oder neue Failureaussage aus einem Transporttimeout ableiten.
- **Asyncio-Defaults und geerbtes Debugging:** TLS-Standardfristen können
  deutlich länger als der eigene HTTP-Deadline sein. Handshake explizit
  begrenzen und danach nur die verbleibende absolute Frist verwenden.
  Geerbtes `PYTHONASYNCIODEBUG` kann langsame Callbackreprs mit privaten
  Argumenten protokollieren; für den privaten Loop `debug=False` erzwingen.
- **Bereiter Acceptloop:** Bei einer vollen Acceptqueue kann jedes
  `sock_accept` sofort zurückkehren. Pro Iteration ausdrücklich schedulen,
  damit Frist-/Shutdowncallbacks trotz Verbindungsflut ausgeführt werden.
- **WeakMap-Fortsetzungen über HTTP:** Prepared-/Grantobjekte und Ports nicht
  JSON-roundtrippen. Ein eigener begrenzter, sitzungsgebundener Speicher hält
  Originalreferenzen; keine Credentials in den vorhandenen Sessionstore legen.
  Admission bereits vor Prepare-Await reservieren und laufende Arbeit auch
  nach Ablauf nicht aus der Kapazitätszählung entfernen.
- **Letztes Await vor Autorität:** Erst Konfiguration/Origin lesen, danach
  die ursprüngliche Sitzung erneut vergleichen. Ein langsames Origin-Await
  nach dem Sitzungscheck könnte eine inzwischen rotierte Identität erhalten.
  Auch ein asynchroner Asserthelper erzeugt nach seinem letzten Check eine
  weitere Microtaskgrenze. Letzte Assertion synchron im aufrufenden Handler
  unmittelbar vor Dispatch/Antwort ausführen.
- **UTF8-Replacement verändert geheime Eingaben:** `Buffer.toString("utf8")`
  ersetzt defekte Bytes. Für Credential-HTTP fatal dekodieren; private Bodybytes
  und Unicodewerte weder normalisieren noch erneut beliebig serialisieren.
- **Native Formularnavigation vor Hydration:** Ein Formular ohne feste sichere
  Methode kann Eingaben als GET-Query senden. Credentialformular ohne nativen
  Submit bauen; ausschließlich explizite POST-Buttons mit JS verwenden.
- **Abbruch und späte Antworten:** Abort ist kein Datenbankrollback. Nach
  Execute keine Wiederholung; Controllergenerationen verhindern, dass eine
  späte Antwort verworfene Secrets/Handles erneut aktiviert. Pagehide und
  BFCache-Rückkehr benötigen ebenfalls Verwerfen/Statusneuladen.

- **90 Tage pro Anfrage sind keine Gesamthistoriegrenze:** Bitget V3 kann
  mehrere Jahre rückwärts paginieren. Tatsächliche Coverage prüfen; vier
  Jahre H4 haben8.766 Kerzen und passen in10.000, ohne Grenzen aufzuweichen.
- **Schon ausgewertete Daten sind kein unberührter Holdout:** Das alte
  BTC-Demofenster nicht später umetikettieren. IP-046 reserviert einen
  früheren Jahresabschnitt außerhalb des Demos vor den neuen Leistungsläufen;
  vollständige Vierjahresquellen nicht zusätzlich als Research importieren.
- **API-Tests benötigen die Fixture-DB:** Compose `api-checks` zeigt ohne
  Override auf `investalo` mit001–007. Der aktuelle Gesamtsatz braucht
  `-e PGDATABASE=investalo_credentials_checks` mit008/009; Fehlermeldungen
  wegen fehlender Credentialfunktionen sind kein Grund, die normale DB zu
  migrieren. IP-046 hat den anfänglich falsch zugeordneten Lauf korrigiert.
- **SSR-Datasetoptionen haben ein Standardasset:** Das initiale Backtestformular
  rendert BTC. ETH liegt vor Auswahl in Next-Clientprops. Der HTTP-Prüfstand
  dekodiert nur begrenztes `self.__next_f.push`-JSON und prüft Asset/Digest/
  Researchzweck/Herkunft exakt; keine JS-Auswertung und kein behaupteter
  Browser-Hydrationsnachweis.
- **Separate Forschungsaccounts sind kein Portfolio:** Je Asset10.000 USDT
  nicht zu einer gemeinsamen Rendite addieren. Ohne terminales Zwangsflatten
  enthält Netto-PnL offene markierte Bestände; PF/Basketzahl erfassen nur
  abgeschlossene Baskets. Persistierte SQL-Jobstatus sind kleingeschrieben,
  API-Projektionen großgeschrieben; Read-only-Audit nutzt `succeeded`.

- **Paper-Restore ist kein atomarer Writer:** Snapshot plus letzte Receipt
  ermöglicht Wiederherstellung; vollständiges Journal separat append-only
  und mit Zustand/Revision-CAS in einer Transaktion schreiben. Unknowncommit
  durch Readback klären. Quotezeit muss nach Kaufsignal liegen; ein Quote
  des anderen Assets darf keinen Fill am alten Preis auslösen. Missing
  midnight baseline nicht nachträglich aus aktueller Equity erfinden.

- **Commitklassifikation verlangt frische Transaktion:** Eine Factory mit
  Autocommit oder bereits laufender Transaktion kann Writes vor der erwarteten
  Commitgrenze dauerhaft machen. PaperStore prüft `autocommit=False` und
  `TransactionStatus.IDLE` vor SQL. Unknowncommit nie retry; frisches Readback.

- **Psycopg-Verbindungsfehler können Conninfo preisgeben:** Pytesttrace kann
  Passwortvariablen im internen Frame zeigen. Fixturefactory fängt
  Verbindungsfehler sanitisiert und ohne ursprünglichen Trace; `--tb=short`.
  Anfänglich betroffenes synthetisches Paperpasswort rotiert, lokalen Trace
  bereinigt. TLS/SCRAM-HBA für genau Fixture/Papergruppe vor LOGIN-Test prüfen.

- **Paper010 ist ausschließlich Fixturemigration:** Normale DB bleibt007,
  Fixture jetzt010. Read-only-Ledgerchecker muss beide Stände explizit prüfen.
  Keine normale Migration als Reparatur für Fixturetests; angewendete010
  unveränderlich. Journaltests behalten append-only synthetische Historie.

- **Bitget Current-Candles hat andere Startgrenze als History:** Reale
  SPOT-Abfrage ließ startTime-Kerze aus. Ein vorheriges H4-Intervall anfragen,
  auf exakte geschlossene Sollabdeckung normalisieren; fehlende Kerzen nie
  synthetisieren. Tickerzeit erst nach HTTP-Empfang auf Zukunft/Frische prüfen.

- **Paper-REST-Polling liefert keine exakte Mitternachtsbaseline:** Runner
  verlangt identische exakte00:00-Quote-/Verarbeitungszeit. Fünf-Sekunden-Loop
  erfüllt das nicht zuverlässig; neue Käufe bleiben daily_baseline_required.
  Dauerbetrieb bis BL-028 gesperrt. Keine aktuelle Equity als Tagesstart erfinden.

- **Paperchecks teilen einen festen Fixture-LOGIN:** PG-Tests ändern dessen
  Kontobindung. Nach Tests neue Public-Feed-Fixture/Env vorbereiten; ältere
  Env-UUIDs nicht blind nutzen. Keine Normal-/Research-/Runtimebindung ändern.

- **Statusmigration011 ist jetzt unveränderlich, nur Fixture:** normal007/
  Fixture011 explizit prüfen. Read-only-API benötigt original auth_time,
  aktuellen auth_epoch und aktive Mitgliedschaft; Viewer darf eigene
  Paperkonten lesen. Signaturprüfung bleibt in der API, nicht in SQL-GUCs.

- **Zahlenvalidatoren dürfen Nullbeträge nicht als Fehler behandeln:**
  `decimal` liefert eine Zahl, kein Boolean;0 ist gültiges Paper-Cash/Menge.
  Fehler über Exceptions prüfen. Ein gespeicherter Timestamp beweist keinen
  laufenden Worker; fehlende Kurse ergeben keine bewertbare Equity.

- **Q32 ersetzt die Paper-Quote-Mitternachtsbasis:** Seit IP-052 H4-Modellbasis
  vor dem ersten neuen Tagesquote/FILL committen. Nachmitternächtliche
  Inventaränderungen sind ohne früheren Beleg kein zulässiger Tagesstart.
  Neustart nach day-Commit darf nicht neu bewerten;012 vergleicht eingefrorene
  Kerzenfingerprints auch nach einem ersetzenden Quote-Journaleintrag.
  Normal007/Fixture012; angewendete012 immutable.

- **Modellbewertung ist kein RSI-/Quoteinput:** H4-Kerze danach genau einmal
  im üblichen Indikatorfluss verarbeiten. Positive Prüfung: zweites sub30
  erzeugt nur Intent, späterer echter Ask plus Kostenmodell erzeugt Fill.
  Revidierte OHLC-Testdaten brauchen gültige High/Low, bevor Replay testbar ist.

- **Stabile Paperidentität von Test-Rebinding trennen:** investalo_paper_development
  bleibt fix in Fixture012; prepare-paper-storage/feed-checks binden nur
  investalo_paper_tests neu. Manifest prepared IDs vor DB-Commit speichern,
  bound nur verifizieren; fehlende/abweichende Secrets nie still regenerieren.
- **Session-Advisory-Lock benötigt eigene Autocommitverbindung:** keine lange
  Rowlock-TX. Verlust vor jedem Write und Health prüfen; terminal stoppen.
  Advisorylock ist kooperativ, CAS bleibt im Check/Write-Zwischenraum maßgeblich.
  PGPASSWORD/PGOPTIONS/PGSERVICE und andere zusätzliche PG-Variablen ablehnen.
- **Beobachtungsbudget begrenzt Zyklusstarts:**24h ist kein harter Fetch-/Commit-
  Abbruch. restart:no; sichere Wiederaufnahme nach Unknowncommit mit Readback.
  Zwei Quoteinputs/5s ergeben ca34.560 Journalzeilen/Tag. Logsbegrenzung ist keine
  DB-Retention; unveränderliche Journale nicht automatisch entfernen.

- **Normale Entwicklungsdatenbank seit IP-054012:** alte007-Erwartungen sind
  historische Belege. prepare-paper-preview-schema.py prüft beide012-Ledger.
 008/009-Credentialcapabilities existieren, HTTP-/Dienstgates bleiben aus.
- **Anzeige braucht beide expliziten Overlays:** public-preview + paper-preview
  und eigene paper_preview.env für API/Cockpitupdates. Nur Publicoverlay ist
  Anzeige-Rückfall; keine Schema-/Bindungs-/Journalrücksetzung. Fixturekonto
  nicht kopieren; normale eigene Paperidentität und --once separat.
- **Alte OIDC-Zeit nur gegen tatsächlichen Reauthcutoff testen:** neue User
  haben reauth_after1970 als Default; gestern ist dann gültig. Preflight setzt
  synthetischen Cutoff ausdrücklich aktuell. Fehler blieb vollständig rollback.
- **Existing-role Prepared-Recovery ist Verify, kein Repair:** vor GRANTs alle
  bestehenden Rechte/Bindungen prüfen; verlorene Commitantwort erst lesen.
- **Mehr Baskets vergrößern kein gemeinsames Risikobudget:** voll zugeordnetes
  Kaufprincipal mit korrelierter5%-Staffel verliert im −50%-Beispiel nach fünf
  regulären Stufen31,49% des Kontos, vor Kosten.6%/8% bleiben nach Q33 bindend;
  geplante Budgets, reservierte Stufen und tatsächliche Käufe getrennt prüfen.
- **KI-Backtest braucht damaliges Wissen:** datierte News allein entfernen
  keine Zukunftskenntnis heutiger Modelle. Ohne rekonstruierbare damalige
  Wissensgrenze prospektiven Shadow-/Papernachweis verlangen. Alternative.me
  Fear & Greed ist Bitcoinkontext, kein coinspezifischer Altcoinindikator.
- **Peakdrawdown ist keine Startkapitalverlustgrenze:** Benchmark12,1145%
  vom Hoch verletzt nicht automatisch8% vom Start. Tatsächliche Baseline-
  Verluste hier3,4806% initial/3,1921% täglich. Separat ausweisen/prüfen.
- **Gleichzeitige Researchquotes gemeinsam bewerten:** sequential on_quote
  kann bei gegenläufigen Assets ein gemeinsames Limit vorzeitig latchen.
  Komplette atomare Batches nicht mit asynchronen Brokerquotes gleichsetzen.
- **primitive verarbeitet Dictwerte nicht rekursiv:** Replayreport/Policy
  normalisieren jeden Feldwert. Sonst Tuple/List-Drift beim JSON-Roundtrip
  oder nicht serialisierbares Decimal; globale alte Digestfunktion bewahren.
- **50%-Principalstress braucht gebundenen Kaufpreis:** bei weiterem Kauf
  oberhalb des ersten Fills wäre50% Principal kein ausreichender Verlust bis
  zur Stressreferenz. Maximalpreis tatsächlich durchsetzen; ungültige Bindung
  blockiert den Offlinevorschlag.
- **Kostenreserve einmal zählen:** ungenutzte Slotreserve zählt bereits als
  Stress/Cashbindung; Pending-/Kandidatenfee nicht nochmals addieren.
  Bezahlte Fees stecken bereits in Cash/Equity. Zuordnungsrest nicht ausgeben.
- **Lokale Revision ist keine dauerhafte Reservierung:** immutable View+1
  verhindert lokale Stale-Reuse, beweist keine globale Einmaligkeit.
  Budget-/Orderabgleich und persistente CAS vor Ausführung separat implementieren.
- **Simulator verwendet privaten Dispatchcheck:** nur validate_dispatch zu
  überschreiben schützt PaperSimulator._settle nicht. Sein tatsächlich
  aufgerufener _buy_rejection_for_dispatch muss den Allokator erneut prüfen,
  ohne die eigene Order doppelt zu reservieren; Sells ungehindert lassen.
- **Abgeschlossener Basket löscht aktive Ausgaben:** v1 startet BasketState
  nach vollständigem Exit neu. Eigene Research-Lifetime-Ausgaben separat
  erhalten, sonst erscheinen Kosten/Principal fälschlich wieder unverbraucht.
- **Neue Researchversion nicht als v1-Referenz etikettieren:** gemeinsamer
  Portfolioloop hat harte Referenzlabels. Adapterreport explizit versionieren,
  alle Policy-/Plan-/Config-/Kosten-/Datenbezüge erhalten. Runtime-Restore
  darf neue Zustandsfelder nicht still akzeptieren.
- **Exakte synthetische Quote geteilt durch Preis kann aufrunden:** Fillmenge
  auf echte Fixture-Mengenpräzision nach unten runden. Winzige Überfüllung
  löst sonst zu Recht einen Quote-Budget-Riskhalt im vorhandenen Kern aus.
- **Mindestmenge ist nicht Mindestquote:** heutiges ETH-SPOT hat0,0005
  Mindestmenge neben1USDT Mindestquote. V1-InstrumentRules bildet erstere
  nicht ab. Separaten Researchvertrag verwenden; keine neuen Defaultfelder
  in alte frozen Digests. Aktuelle Metadaten sind keine historischen Regeln.
