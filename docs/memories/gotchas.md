# Technische Fallstricke

Stand 2026-11-07. Befunde sind dokumentiert, nicht automatisch im Altsystem behoben.

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
