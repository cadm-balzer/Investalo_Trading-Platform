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
  gegenüber Cash. Bei spätem fünften Fill kann der Kaufbereich zwischen
  5%-Abstand und −55%-Exit leer sein; dann keine Ausnahme erzwingen.
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
